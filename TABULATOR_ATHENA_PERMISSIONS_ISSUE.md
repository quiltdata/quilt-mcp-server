# Tabulator/Athena Permissions Issue

## Problem Summary

**User `simon@quiltdata.io` cannot query Tabulator tables via Quilt MCP** due to missing Glue/Athena permissions on the JWT-derived IAM role.

## Current Situation

### ✅ What Works:
1. **Authentication**: JWT token works, user is logged in to `demo.quiltdata.com`
2. **AWS Credentials**: STS temporary credentials are generated (`ASIA...` access key)
3. **IAM Role**: `arn:aws:sts::850787717197:assumed-role/ReadWriteQuiltV2-sales-prod/simon@quiltdata.io`
4. **Tabulator Discovery**: Can list tabulator tables via Quilt API
   - `TabulatorTablesResource().list_items(bucket_name="nextflowtower")` ✅ Returns `sail` table
5. **Quilt UI**: Can query Tabulator tables through the UI (server-side has permissions)

### ❌ What Doesn't Work:
1. **Direct Athena Queries**: `athena:StartQueryExecution` - Access Denied
2. **Glue Metadata Access**: `glue:GetDatabase`, `glue:GetDatabases` - Access Denied
3. **Athena Workgroup Access**: `athena:GetWorkGroup` - Access Denied

## Error Messages

```
AccessDeniedException: User: arn:aws:sts::850787717197:assumed-role/ReadWriteQuiltV2-sales-prod/simon@quiltdata.io 
is not authorized to perform: glue:GetDatabases on resource: arn:aws:glue:us-east-1:850787717197:catalog
```

```
AccessDeniedException: You are not authorized to perform: athena:StartQueryExecution on the resource
```

## Root Cause

The `ReadWriteQuiltV2-sales-prod` IAM role has:
- ✅ S3 read/write permissions
- ✅ STS assume role permissions
- ❌ **Missing Athena permissions**
- ❌ **Missing Glue permissions**

## Architecture Issue

```
┌─────────────────────────────────────────────────────────────┐
│                     Quilt Catalog UI                         │
│  (Server-side, has full Athena/Glue permissions)            │
│         Can query Tabulator tables ✅                        │
└─────────────────────────────────────────────────────────────┘
                         ▲
                         │ HTTPS API
                         │
┌─────────────────────────────────────────────────────────────┐
│                    User's JWT Token                          │
│         (simon@quiltdata.io)                                 │
└─────────────────────────────────────────────────────────────┘
                         │
                         │ Exchanged for STS credentials
                         ▼
┌─────────────────────────────────────────────────────────────┐
│          ReadWriteQuiltV2-sales-prod IAM Role                │
│  - S3 permissions ✅                                         │
│  - Athena permissions ❌                                     │
│  - Glue permissions ❌                                       │
└─────────────────────────────────────────────────────────────┘
                         │
                         │ Direct AWS API calls
                         ▼
┌─────────────────────────────────────────────────────────────┐
│            Quilt MCP Server (Local/ECS)                      │
│     Tries to query Athena directly ❌                        │
│     Access Denied                                            │
└─────────────────────────────────────────────────────────────┘
```

## Solutions

### Option 1: Add Permissions to IAM Role (Recommended)

**Add to `ReadWriteQuiltV2-sales-prod` role**:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "athena:StartQueryExecution",
        "athena:GetQueryExecution",
        "athena:GetQueryResults",
        "athena:StopQueryExecution",
        "athena:GetWorkGroup",
        "athena:ListWorkGroups"
      ],
      "Resource": [
        "arn:aws:athena:us-east-1:850787717197:workgroup/QuiltTabulatorOpenQuery-sales-prod",
        "arn:aws:athena:us-east-1:850787717197:workgroup/QuiltUserAthena-*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "glue:GetDatabase",
        "glue:GetDatabases",
        "glue:GetTable",
        "glue:GetTables",
        "glue:GetPartitions"
      ],
      "Resource": [
        "arn:aws:glue:us-east-1:850787717197:catalog",
        "arn:aws:glue:us-east-1:850787717197:database/*",
        "arn:aws:glue:us-east-1:850787717197:table/*/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket",
        "s3:PutObject"
      ],
      "Resource": [
        "arn:aws:s3:::sales-prod-userathenaresultsbucket-*/*",
        "arn:aws:s3:::sales-prod-userathenaresultsbucket-*"
      ]
    }
  ]
}
```

### Option 2: Use Quilt Catalog API Proxy (Alternative)

Create a new Tabulator query endpoint in the MCP that:
1. Uses GraphQL or REST API to query through Quilt catalog
2. Catalog server has permissions to query Athena
3. Returns results to MCP client

**Implementation**:
```python
# In tools/tabulator.py
def tabulator_query(
    bucket_name: str,
    table_name: str,
    query: str,
    max_results: int = 100
) -> Dict[str, Any]:
    """Query a tabulator table via Quilt Catalog API."""
    # Use Quilt's /api/tabulator/query endpoint
    session = quilt_service.get_session()
    registry_url = quilt_service.get_registry_url()
    
    response = session.post(
        f"{registry_url}/api/tabulator/query",
        json={
            "bucket": bucket_name,
            "table": table_name,
            "query": query,
            "limit": max_results
        }
    )
    return response.json()
```

### Option 3: Different Authentication Method

Use a different authentication method that provides full Athena/Glue permissions:
- Service account with Athena permissions
- IAM role with broader permissions
- API key with elevated privileges

## Recommended Action

**Immediate**: Add Athena/Glue permissions to `ReadWriteQuiltV2-sales-prod` role
**Long-term**: Consider adding `/api/tabulator/query` endpoint to Quilt Catalog API

## Testing After Fix

Once permissions are added, test with:

```python
from quilt_mcp.services.athena_service import AthenaQueryService

athena_service = AthenaQueryService()
result = athena_service.execute_query(
    query="SELECT * FROM sail LIMIT 5",
    database_name="nextflowtower",  # or the actual Glue database name
    max_results=5
)
```

## Related Issues

- The hyphenated database name fix we implemented is still valid
- This is a separate permissions issue
- Both need to be resolved for Tabulator queries to work

---

**Date**: 2025-10-09  
**User**: simon@quiltdata.io  
**Stack**: sales-prod  
**Status**: Blocked on IAM permissions


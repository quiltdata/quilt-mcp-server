# Athena/Tabulator Query History Analysis

## Question: Did Athena queries through Quilt ever work without direct AWS permissions?

**Answer: NO** - Athena queries have **always required direct AWS permissions** in the quilt-mcp-server.

## Git History Analysis

### What We Found:

1. **Initial Athena Implementation** (August 2025)
   - Commit `565333c` - "initial athena tool spec"
   - Always used direct AWS API calls via boto3
   - Required `athena:*` and `glue:*` permissions from day one

2. **Feature Branch: `feature/athena-tabulator-queries`**
   - Commit `03a8945` - "Add Athena and Glue integration tools to MCP server"
   - Also used direct AWS API calls
   - No proxy/catalog API implementation

3. **Deleted AWS Policy Files**
   - `configs/aws/athena-glue-partitions-policy.json` (deleted)
   - `configs/aws/athena-glue-policy.json` (deleted)
   - These policies defined required permissions for direct AWS access
   - Were never about avoiding permissions - they documented what was needed

4. **Stateless Refactoring** (September 2025)
   - Removed quilt3 dependency
   - Moved to JWT-based authentication
   - **Still uses direct AWS API calls**
   - Didn't change permission requirements

## Catalog API Endpoint Analysis

### `/api/tabulator/query` Endpoint

**Status**: **Does NOT exist**

#### Test Results:
```
Registry URL: https://demo-registry.quiltdata.com
Endpoint: /api/tabulator/query
Result: 404 Not Found
```

#### Alternative Endpoints Tested:
- `/api/tabulator/execute` - ❌ 404
- `/api/athena/query` - ❌ 404
- `/api/query` - ❌ 404

### Previous Testing (v0.6.74)

From `QURATOR_COMPREHENSIVE_TESTING_v0.6.74.md`:
```
Response: 405 Client Error: Not Allowed
URL: https://demo.quiltdata.com/api/tabulator/query
```

**Note**: This was on `demo.quiltdata.com` (Navigator), not the registry. The registry doesn't have this endpoint at all (404).

## Why The Quilt UI Works

The Quilt UI can query Tabulator tables because:

```
┌─────────────────────────────────────────────┐
│         Quilt Catalog UI (Browser)          │
│  User clicks "Run Query"                    │
└─────────────────────────────────────────────┘
                    │
                    │ HTTPS Request
                    ▼
┌─────────────────────────────────────────────┐
│      Quilt Catalog Backend (Server)         │
│  - Receives query from UI                   │
│  - Uses SERVER'S IAM role (full permissions)│
│  - Calls AWS Athena API directly            │
│  - Returns results to UI                    │
└─────────────────────────────────────────────┘
                    │
                    │ AWS API (boto3)
                    ▼
┌─────────────────────────────────────────────┐
│            AWS Athena Service               │
│  - Executes query                           │
│  - Uses Glue metadata                       │
│  - Returns results                          │
└─────────────────────────────────────────────┘
```

**Key Point**: The UI works because the **backend server** has full Athena/Glue permissions. Users don't need their own AWS credentials to use the UI.

## Why The MCP Doesn't Work

```
┌─────────────────────────────────────────────┐
│      Quilt MCP Server (Local/ECS)           │
│  - Receives query request                   │
│  - Uses USER'S JWT-derived IAM role         │
│  - Tries to call AWS Athena API             │
│  - ❌ Access Denied (missing permissions)   │
└─────────────────────────────────────────────┘
                    │
                    │ AWS API (boto3)
                    │ with user's credentials
                    ▼
┌─────────────────────────────────────────────┐
│            AWS Athena Service               │
│  - Checks caller's permissions              │
│  - ❌ Rejects (no glue:GetPartitions)       │
└─────────────────────────────────────────────┘
```

**Key Point**: The MCP uses the **user's credentials**, which don't have Athena/Glue permissions.

## quilt3 SDK Analysis

**Does quilt3 have query methods?**

Checked `quilt3` module - **NO** built-in query/tabulator methods found.

### What quilt3 Provides:
- ✅ Package operations (`browse`, `push`, `fetch`, `install`)
- ✅ AWS credential management (`create_botocore_session`)
- ✅ S3 operations (via boto3 sessions)
- ❌ **No Athena query methods**
- ❌ **No Tabulator query methods**
- ❌ **No catalog API proxy methods**

## Architecture Comparison

### What Exists (Direct AWS):
```python
# Current MCP implementation
athena_service = AthenaQueryService()
result = athena_service.execute_query(
    query="SELECT * FROM table",
    database_name="db"
)
# ↓ Direct AWS API call
# boto3.client('athena').start_query_execution(...)
# ❌ Requires user to have athena:* and glue:* permissions
```

### What Doesn't Exist (Catalog API Proxy):
```python
# Hypothetical catalog API proxy (DOESN'T EXIST)
catalog_service = QuiltCatalogAPI()
result = catalog_service.query_tabulator(
    bucket="nextflowtower",
    table="sail",
    query="SELECT * FROM sail"
)
# ↓ Would call catalog API
# POST https://registry.com/api/tabulator/query
# ✅ Would use server-side permissions
# ❌ This endpoint doesn't exist
```

## Solutions

### Option 1: Add Permissions (Current Approach)

Add Athena/Glue permissions to `ReadWriteQuiltV2-sales-prod` role.

**Pros**:
- Works with existing code
- No backend changes needed
- Full Athena functionality

**Cons**:
- Requires AWS admin action
- Every user needs these permissions

### Option 2: Create Catalog API Proxy (Future Enhancement)

Add `/api/tabulator/query` endpoint to Quilt catalog backend.

**Pros**:
- Users don't need AWS permissions
- Server-side query execution
- Consistent with UI behavior

**Cons**:
- Requires backend development
- Need to implement query validation
- Security considerations (SQL injection, resource limits)

### Option 3: Hybrid Approach

- Add catalog API for common queries (read-only)
- Require direct permissions for advanced use cases

## Conclusion

**Historical Answer**: 
- ❌ Athena queries through Quilt **never worked** without direct AWS permissions
- ❌ No catalog API proxy has ever existed
- ❌ quilt3 SDK has no built-in query methods

**Current Status**:
- Quilt UI works (server-side permissions)
- MCP requires user permissions (direct AWS calls)
- No alternative implementation exists in git history

**Recommendation**:
1. **Short-term**: Add Athena/Glue permissions to user's IAM role
2. **Long-term**: Consider adding `/api/tabulator/query` endpoint to catalog backend

---

**Date**: 2025-10-09  
**Analysis By**: Claude/Simon  
**Branches Checked**: All (including feature/athena-tabulator-queries)  
**Conclusion**: Direct AWS permissions have always been required


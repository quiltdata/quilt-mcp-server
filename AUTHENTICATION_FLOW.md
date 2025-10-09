# Quilt MCP Server Authentication Flow

## Overview

The Quilt MCP server **DOES use JWT tokens** to authenticate to AWS services. Here's how it works:

## Authentication Chain

### 1. **User Configuration** (Environment Variables)
```bash
QUILT_API_TOKEN="eyJpZCI6ICI4Nzk1ZjBjYy04ZGViLTQwZGQtOTEzMi0xMzM1N2M5ODM5ODQiLCAiY29kZSI6ICJmOTU3MzM1ZC0yOWM4LTQyMGEtOWVjYi1lNzdmZjBiNmUyYmQifQ=="
QUILT_CATALOG_DOMAIN="demo.quiltdata.com"
```

### 2. **quilt3 Authentication**
When `quilt3` is configured with a catalog:
- The JWT token is stored in `~/.config/quilt/config.yml`
- quilt3 validates the token with the catalog
- The catalog returns AWS STS temporary credentials

### 3. **Botocore Session Creation**
```python
# In AthenaQueryService.__init__
quilt_service = QuiltService()
botocore_session = quilt_service.create_botocore_session()
```

This calls `quilt3.session.create_botocore_session()` which:
1. **Fetches temporary AWS credentials** from the Quilt catalog
2. Returns a botocore session with **RefreshableCredentials**
3. Credentials are **automatically refreshed** when they expire

### 4. **Credential Types**

**JWT-derived credentials (✅ Currently used)**:
- Access Key: `ASIA...` (temporary)
- Secret Key: (temporary)
- Session Token: `FwoGZXIvYXdzEFUa...` (STS token)
- **Auto-refreshed** by quilt3

**Ambient credentials (❌ Fallback)**:
- Access Key: `AKIA...` (long-term)
- No session token
- From `~/.aws/credentials` or IAM role

## Current Implementation

### AthenaQueryService
```python
class AthenaQueryService:
    def __init__(self, use_quilt_auth: bool = True, quilt_service: Optional[QuiltService] = None):
        self.use_quilt_auth = use_quilt_auth  # Default: True
        
    def _create_sqlalchemy_engine(self) -> Engine:
        if self.use_quilt_auth:
            # ✅ Path 1: Use JWT-derived credentials
            quilt_service = self.quilt_service or QuiltService()
            botocore_session = quilt_service.create_botocore_session()
            credentials = botocore_session.get_credentials()
            
            # Creates Athena connection with temporary credentials
            connection_string = (
                f"awsathena+rest://{access_key}:{secret_key}@athena.{region}.amazonaws.com:443/"
                f"?work_group={workgroup}&aws_session_token={token}"
            )
        else:
            # ❌ Path 2: Use ambient AWS credentials (fallback)
            connection_string = f"awsathena+rest://@athena.{region}.amazonaws.com:443/?work_group={workgroup}"
```

## Verification

Running the authentication test shows:
```python
=== Creating botocore session ===
Session type: <class 'botocore.session.Session'>
Credentials type: <class 'botocore.credentials.RefreshableCredentials'>
Access key (first 10 chars): ASIA4MFXGK...  # ← Temporary (starts with ASIA)
Has session token: True                      # ← STS token present

✅ Using TEMPORARY credentials (from JWT/STS)
✅ DIFFERENT credentials - Quilt is using JWT-derived credentials!
```

## Why You See Different AWS Accounts

The confusion earlier was because:

1. **JWT token** → Authenticates to `demo.quiltdata.com` Quilt catalog
2. **STS credentials** → Point to the AWS account behind `demo.quiltdata.com`
3. **Ambient credentials** → Point to your local `sales-prod` AWS account

When we tested locally, the code was **correctly using JWT credentials**, but:
- The JWT gives access to `demo.quiltdata.com`'s AWS account
- Athena databases exist in that AWS account
- The `sail` tabulator table exists in that AWS account's Glue catalog

## AWS Account Mapping

| Quilt Catalog | AWS Account | Athena Database | Tabulator Table |
|---------------|-------------|-----------------|-----------------|
| `demo.quiltdata.com` | AWS Account A | `nextflowtower` (virtual) | `sail` |
| `sales-prod.quiltdata.com` | AWS Account B (850787717197) | `userathenadatabase-*` | Various |

## Key Insights

1. **JWT tokens ARE used** ✅
   - The `QUILT_API_TOKEN` environment variable is read by quilt3
   - quilt3 exchanges it for temporary AWS credentials
   - These credentials are auto-refreshed

2. **Credentials are isolated per catalog** ✅
   - Each Quilt catalog URL maps to a specific AWS account
   - The JWT token determines which catalog (and thus AWS account) you access

3. **No manual AWS credential management needed** ✅
   - Users only provide `QUILT_API_TOKEN`
   - quilt3 handles the AWS credential lifecycle

4. **Tabulator databases are virtual** ⚠️
   - The Quilt UI shows "databases" like `nextflowtower`
   - These are virtual namespaces, not real Glue databases
   - The actual Glue database has a different name (e.g., `userathenadatabase-k60cyxsioyx2`)

## Testing Limitations

When testing locally:
- Local JWT token → AWS Account A
- Local ambient credentials → AWS Account B
- Tabulator tables only exist in AWS Account A
- Cannot test with AWS Account B credentials

## Recommendations

1. **Always use JWT authentication** (`use_quilt_auth=True`) for production
2. **Test with matching catalog/AWS account** to avoid confusion
3. **Document which AWS account each catalog uses** for troubleshooting
4. **Check credential type during debugging**:
   ```python
   credentials = botocore_session.get_credentials()
   if credentials.token:
       print("Using JWT-derived temporary credentials ✅")
   else:
       print("Using ambient long-term credentials ⚠️")
   ```

## Related Code

- `src/quilt_mcp/services/quilt_service.py` - `create_botocore_session()`
- `src/quilt_mcp/services/athena_service.py` - `_create_sqlalchemy_engine()`
- `src/quilt_mcp/tools/buckets.py` - `_build_s3_client_for_upload()` (fixed in v0.6.75)

---

**Date**: 2025-10-09  
**Author**: Claude/Simon  
**Status**: Current implementation verified


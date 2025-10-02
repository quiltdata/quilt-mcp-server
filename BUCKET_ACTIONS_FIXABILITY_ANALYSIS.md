# Bucket Actions Fixability Analysis

## Executive Summary

Out of **9 bucket actions**, we can potentially fix **1-2 actions** using GraphQL alternatives. The remaining **5-7 actions** are fundamentally blocked by the JWT architecture (authentication-only JWTs without AWS credentials).

---

## Current Status of 9 Bucket Actions

### ✅ Already Working (1 action)

#### 1. `buckets.discover` ✅
**Status**: Fully working  
**Method**: GraphQL `bucketConfigs` query  
**Test**: Returns 32 buckets successfully  
**No fix needed**: Already uses correct GraphQL query

---

### ❌ Deprecated (3 actions)

#### 2. `buckets.objects_list` ❌
**Status**: Deprecated  
**Alternative**: Use `search.unified_search(scope="bucket", target="bucket-name")`  
**Reason**: Replaced by unified search (GraphQL-based)  
**No fix possible**: Intentionally deprecated

#### 3. `buckets.objects_search` ❌
**Status**: Deprecated  
**Alternative**: Use `search.unified_search`  
**Reason**: Replaced by unified search  
**No fix possible**: Intentionally deprecated

#### 4. `buckets.objects_search_graphql` ❌
**Status**: Deprecated / Not working  
**Issue**: GraphQL schema doesn't have top-level `objects()` query  
**Alternative**: Use `search.unified_search` or `packages(bucket:...)` query  
**No fix possible**: Schema limitation

---

### 🔧 Potentially Fixable with GraphQL (1 action)

#### 5. `buckets.object_link` 🔧
**Status**: Currently requires AWS credentials  
**Current Method**: Uses `boto3` to generate presigned URLs  
**Potential Fix**: Use GraphQL `browsingSessionCreate` mutation

**GraphQL Alternative Discovered**:
```graphql
mutation {
  browsingSessionCreate(
    scope: "quilt+s3://bucket#package=name&hash=..."
    ttl: 180
  ) {
    ... on BrowsingSession {
      id
      expires
    }
  }
}
```

**Status**: ⚠️ **Partially Blocked**
- Browsing sessions require **package context** (not just raw S3 URIs)
- Format: `quilt+s3://bucket#package=name&hash=...`
- Cannot generate presigned URLs for arbitrary S3 objects
- Only works for objects within Quilt packages

**Verdict**: **Cannot fully replace** `object_link` for arbitrary S3 objects

---

### ⛔ Fundamentally Blocked by JWT Architecture (4 actions)

These actions **CANNOT be fixed** without one of the following:
1. Backend assumes IAM role and proxies operations
2. JWT includes AWS credentials (requires frontend changes)
3. Alternative GraphQL endpoints are created (requires backend changes)

#### 6. `buckets.object_fetch` ⛔
**Status**: Blocked  
**Current Method**: `boto3` S3 GetObject  
**Requires**: AWS credentials to read object bytes  
**Why it can't be fixed**:
- GraphQL doesn't provide object content download
- Browsing sessions only work for package-scoped access
- Would need backend proxy to assume role and fetch object

**Possible Solution**: Backend proxy endpoint that assumes role

#### 7. `buckets.object_info` ⛔
**Status**: Blocked  
**Current Method**: `boto3` S3 HeadObject  
**Requires**: AWS credentials to get object metadata  
**Why it can't be fixed**:
- GraphQL doesn't provide object metadata queries
- Package queries only return logical keys, not S3 metadata
- Would need direct S3 access or backend proxy

**Possible Solution**: Backend proxy endpoint

#### 8. `buckets.object_text` ⛔
**Status**: Blocked  
**Current Method**: `boto3` S3 GetObject with text decoding  
**Requires**: AWS credentials to read and decode object  
**Why it can't be fixed**:
- Same as `object_fetch` - needs direct S3 access
- Would need backend proxy

**Possible Solution**: Backend proxy endpoint

#### 9. `buckets.objects_put` ⛔
**Status**: Blocked  
**Current Method**: `boto3` S3 PutObject  
**Requires**: AWS credentials to write objects  
**Why it can't be fixed**:
- GraphQL `packageConstruct` requires files to already exist in S3
- No GraphQL mutation for uploading raw S3 objects
- Frontend JWT has no AWS write permissions

**Possible Solutions**:
1. Backend proxy upload endpoint
2. Use Quilt web UI upload (then reference files)
3. Users upload via AWS CLI, then create packages

---

## Summary by Fixability

| Status | Count | Actions |
|--------|-------|---------|
| ✅ **Already Working** | 1 | `discover` |
| ❌ **Deprecated** | 3 | `objects_list`, `objects_search`, `objects_search_graphql` |
| 🔧 **Potentially Fixable** | 0 | *(browsing sessions don't solve the problem)* |
| ⛔ **Blocked by Architecture** | 5 | `object_fetch`, `object_info`, `object_text`, `object_link`, `objects_put` |

---

## Root Causes Analysis

### Why Most Actions Can't Be Fixed

**1. JWT Architecture**
- Frontend JWT is authentication-only
- Does NOT include AWS credentials
- Backend must assume IAM roles for AWS access

**2. GraphQL Limitations**
- No raw S3 object operations in GraphQL schema
- `browsingSessionCreate` only works for **package-scoped** access
- No presigned URL generation for arbitrary objects

**3. Security Design**
- By design, clients shouldn't have direct S3 access
- Backend controls AWS credentials via IAM role assumption
- This is the **correct security model**

---

## Recommendations

### Option 1: Accept Limitations ✅ (Recommended)
**Accept that 5 actions require AWS credentials**

**Document clearly**:
```
⚠️ These actions require AWS credentials in JWT:
- object_fetch, object_info, object_text, object_link, objects_put

Current frontend JWTs are authentication-only and don't include
AWS credentials. The backend controls AWS access via IAM roles.

Use alternatives:
- Search for packages: search.unified_search
- View package files: packaging.browse
- Upload files: Quilt web UI, then packaging.create
```

**Pros**:
- No code changes needed
- Correct security model
- Clear documentation

**Cons**:
- 5 actions remain unavailable
- Users can't fetch/upload via MCP

### Option 2: Backend Proxy Endpoints 🔧
**Create REST endpoints in backend that proxy S3 operations**

**Implementation**:
```python
# Backend endpoint
@app.post("/api/v1/objects/fetch")
async def fetch_object(bucket: str, key: str, auth: str = Header(...)):
    # Verify JWT
    # Assume IAM role
    # Fetch from S3
    # Return bytes
```

**Pros**:
- Enables all 5 blocked actions
- Maintains security (backend controls access)
- Works with authentication-only JWTs

**Cons**:
- Requires backend implementation
- Additional API endpoints to maintain
- Proxy overhead for large files

### Option 3: GraphQL Extensions 🔧
**Ask backend team to add S3 operation mutations/queries**

**Example**:
```graphql
query {
  objectInfo(bucket: String!, key: String!) {
    size
    contentType
    lastModified
  }
}

mutation {
  objectPresignedUrl(bucket: String!, key: String!, expiresIn: Int!) {
    url
    expires
  }
}
```

**Pros**:
- GraphQL-native solution
- Consistent with existing architecture
- Backend controls access

**Cons**:
- Requires backend team implementation
- Schema changes needed
- May not align with backend priorities

---

## Verdict

### Actions We CAN Fix: **0** 🚫

**Reason**: All unfixed actions require AWS credentials or backend changes

### Actions That Work: **1** ✅

- `buckets.discover` (GraphQL)

### Actions We Should Keep Deprecated: **3** ❌

- Use `search.unified_search` instead

### Actions Requiring Backend Support: **5** ⛔

- `object_fetch`, `object_info`, `object_text`, `object_link`, `objects_put`

---

## Recommendation

**✅ Accept Current Limitations & Document Clearly**

The MCP server is working as designed:
- Authentication is handled via JWT
- AWS operations are controlled by backend IAM roles
- Clients use GraphQL for catalog operations
- Direct S3 access is intentionally restricted

**If direct S3 access is needed**, request backend team to implement:
1. Proxy REST endpoints for S3 operations, OR
2. GraphQL mutations/queries for S3 operations

**For now**: Document that these 5 actions require AWS-enabled JWTs or backend proxy support.

---

## Files to Update

1. **COMPREHENSIVE_ACTION_TESTING.md**: Mark 5 actions as "requires backend proxy"
2. **src/quilt_mcp/tools/buckets.py**: Add deprecation notices with alternatives
3. **README.md**: Document JWT limitations
4. **API docs**: List which actions work vs require backend support


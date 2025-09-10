<!-- markdownlint-disable MD013 -->
# Analysis Document: bucket_object_text with versionId Support

**Issue**: #137 - Add versionId support to bucket_object_text function

## Requirements Reference

Based on `01-requirements.md`, this analysis addresses:

### User Stories

1. **Automatic Version Recognition**: bucket_object_* reader functions should automatically recognize and use versionId query parameters from S3 URIs

### Acceptance Criteria

1. Parse S3 URIs and extract `versionId` from query parameters (e.g., `s3://bucket/key?versionId=abc123`)
2. Automatically fetch specific version when versionId is present in the URI
3. Maintain backward compatibility for URIs without versionId
4. Provide appropriate error handling for invalid versions or access denied scenarios

## Current Codebase Architecture Analysis

### 1. Existing bucket_object_* Functions

The system currently provides four bucket object reader functions in `/Users/ernest/GitHub/quilt-mcp-server/src/quilt_mcp/tools/buckets.py`:

1. **`bucket_object_info(s3_uri: str)`** (lines 78-108)
   - Uses `client.head_object(Bucket=bucket, Key=key)`
   - Returns metadata including size, content type, etag, last modified

2. **`bucket_object_text(s3_uri: str, max_bytes: int, encoding: str)`** (lines 111-148)
   - Uses `client.get_object(Bucket=bucket, Key=key)`
   - Reads and decodes text content with specified encoding
   - **PRIMARY TARGET FUNCTION**

3. **`bucket_object_fetch(s3_uri: str, max_bytes: int, base64_encode: bool)`** (lines 218-283)
   - Uses `client.get_object(Bucket=bucket, Key=key)`
   - Returns binary data as base64 or attempts text decoding
   - **CONSISTENCY CANDIDATE** per requirements open question

4. **`bucket_object_link(s3_uri: str, expiration: int)`** (lines 286-317)
   - Uses `client.generate_presigned_url("get_object", Params={"Bucket": bucket, "Key": key})`
   - Generates presigned URLs for download access

### 2. Current URI Parsing Pattern

**Consistent Pattern Across All Functions:**

```python
# Lines 89-92, 124-127, 233-236, 298-301
without = s3_uri[5:]  # Remove s3:// prefix
bucket, key = without.split("/", 1)  # Split on first slash
```

**Critical Gap**: No query parameter parsing exists anywhere in the codebase.

### 3. S3 Client Usage Patterns

**Current boto3 calls:**

- `client.head_object(Bucket=bucket, Key=key)` - bucket_object_info
- `client.get_object(Bucket=bucket, Key=key)` - bucket_object_text, bucket_object_fetch
- `client.generate_presigned_url("get_object", Params={"Bucket": bucket, "Key": key})` - bucket_object_link

**Version Support Available**: All boto3 methods support optional `VersionId` parameter:

- `head_object(Bucket=bucket, Key=key, VersionId=version_id)`
- `get_object(Bucket=bucket, Key=key, VersionId=version_id)`
- `generate_presigned_url("get_object", Params={"Bucket": bucket, "Key": key, "VersionId": version_id})`

### 4. Error Handling Patterns

**Consistent Error Response Structure:**

```python
return {"error": f"Failed to get object: {e}", "bucket": bucket, "key": key}
```

All functions use try/catch with similar error response formats including context (bucket, key).

### 5. Existing URI Parsing Utilities

**Search Results Analysis:**

- No existing `urlparse` or `parse_qs` usage found in the codebase
- No existing query parameter parsing utilities
- Current URI parsing is manual string manipulation only
- `/Users/ernest/GitHub/quilt-mcp-server/src/quilt_mcp/utils.py` contains `generate_signed_url()` with similar manual parsing pattern

### 6. Quilt3 Library Reference Implementation

**Research from Main Quilt Python Library** ([quilt3/util.py](https://github.com/quiltdata/quilt/blob/0f9e2f7bb2b94f58dd6dff4af8703b58492fb304/api/python/quilt3/util.py#L160)):

**Established Pattern for S3 URI Parsing:**

```python
from urllib.parse import urlparse, parse_qs, unquote

parsed = urlparse(s3_uri)
if parsed.scheme == 's3':
    bucket = parsed.netloc  
    path = unquote(parsed.path)[1:]  # Remove leading /
    query = parse_qs(parsed.query)
    version_id = query.pop('versionId', [None])[0]
    if query:  # Error if other query params exist
        raise URLParseError(f"Unexpected S3 query string: {parsed.query!r}")
```

**Key Implementation Details:**

- Uses Python's standard `urllib.parse` library (no external dependencies)
- Extracts `versionId` specifically from query parameters using `parse_qs()`
- Rejects URIs with unexpected query parameters (strict validation)
- Uses `unquote()` for proper URL decoding
- Returns `None` for version_id when not present

**PhysicalKey Structure Pattern:**

```python
class PhysicalKey:
    def __init__(self, bucket, path, version_id):
        self.bucket = bucket      # str | None (None for local files)
        self.path = path          # str (required)
        self.version_id = version_id  # str | None (optional for S3)
```

**Error Handling Approach:**

- Custom `URLParseError` exception for malformed URIs
- Validates bucket is non-empty (`netloc` must exist)
- Strict query parameter validation (only `versionId` allowed)
- Type assertions for all parameters

## Current System Constraints and Limitations

### 1. URI Parsing Limitations

1. **No Query Parameter Support**: Current parsing logic cannot handle URIs with query parameters
2. **Manual String Manipulation**: Uses basic string operations instead of robust URL parsing
3. **Single Split Logic**: `without.split("/", 1)` assumes no query parameters exist

### 2. Versioned Object Access Constraints

1. **No Version Parameter Support**: S3 client calls lack VersionId parameter support
2. **Missing Version Error Handling**: No specific error handling for version-related failures
3. **No Version Metadata**: Functions don't return version information even when available

### 3. Testing Limitations

**Current Test Patterns** (from `/Users/ernest/GitHub/quilt-mcp-server/tests/test_bucket_tools.py`):

- Integration tests use real AWS objects from `DEFAULT_BUCKET`
- Test URIs constructed as `f"{DEFAULT_BUCKET}/{test_object['key']}"` (lines 53, 111, 134)
- No existing tests for URI query parameters or versioned objects
- Mock tests use basic error simulation but no version-specific scenarios

## Architectural Challenges and Design Considerations

### 1. URI Parsing Architecture

**Challenge**: Current manual parsing approach cannot handle query parameters
**Considerations**:

- Need robust URL parsing to extract base URI and query parameters
- Must preserve backward compatibility with existing URI formats
- Should handle malformed query parameters gracefully
- **Reference Implementation Available**: Quilt3 library provides proven `urllib.parse` pattern for S3 URI parsing with versionId support

### 2. Function Consistency Challenge

**Challenge**: Four functions have identical URI parsing logic that needs updating
**Considerations**:

- `bucket_object_fetch` was identified in requirements as consistency candidate
- `bucket_object_info` and `bucket_object_link` could benefit from version support
- Risk of inconsistent behavior if only some functions support versionId

### 3. Error Handling Architecture

**Challenge**: New version-specific error scenarios need handling
**Considerations**:

- Invalid version IDs (non-existent versions)
- Access denied for specific versions
- Bucket versioning not enabled scenarios
- Distinguish version errors from general S3 errors

### 4. Testing Architecture Challenges

**Challenge**: Need comprehensive test coverage for version scenarios
**Considerations**:

- Real AWS testing requires versioned objects in test bucket  
- Mock testing needs realistic S3 version error responses
- Integration with existing test patterns and fixtures
- Cross-platform testing considerations

## Technical Debt and Refactoring Opportunities

### 1. URI Parsing Duplication

**Current State**: Identical parsing logic in 4 functions (lines 89-92, 124-127, 233-236, 298-301)
**Opportunity**: Extract common URI parsing utility function
**Risk**: Breaking changes if refactoring introduces subtle behavioral differences

### 2. Error Response Inconsistency

**Current State**: Similar but slightly different error response structures
**Opportunity**: Standardize error response format and include version context
**Risk**: Breaking changes for existing consumers

### 3. Missing Utility Functions

**Current State**: No reusable S3 URI utilities despite multiple use cases
**Opportunity**: Create comprehensive S3 URI parsing and manipulation utilities
**Risk**: Over-engineering if utilities become too complex

## Gaps Between Current State and Requirements

### 1. Functional Gaps

1. **No Query Parameter Parsing**: Cannot extract versionId from URIs like `s3://bucket/key?versionId=abc123`
   - **Solution Path**: Quilt3 library provides exact pattern using `urllib.parse.urlparse()` and `parse_qs()`
2. **No Version Parameter Support**: S3 calls don't include VersionId parameter
   - **AWS Support Available**: All current boto3 calls already support optional `VersionId` parameter
3. **No Version Error Handling**: Missing specific handling for version-related errors
   - **Reference Pattern**: Quilt3 uses custom `URLParseError` with strict validation approach
4. **Limited Function Coverage**: Only `bucket_object_text` targeted, but `bucket_object_fetch` consistency question unresolved

### 2. Testing Gaps

1. **No Version Test Coverage**: No existing tests for versioned object scenarios
2. **No Query Parameter Tests**: No tests for URI parsing with query parameters  
3. **No Error Scenario Tests**: Missing tests for version-specific error conditions
4. **No Cross-Function Consistency Tests**: If multiple functions support versionId, need consistency validation

### 3. Documentation Gaps

1. **No Version Usage Examples**: Documentation doesn't describe version parameter usage
2. **No Error Reference**: Missing documentation for version-related error responses
3. **No Migration Guide**: If breaking changes occur, need migration documentation

## Summary of Current State Challenges

**Primary Implementation Challenges:**

1. **URI Parsing Transformation**: Need to replace manual string parsing with robust URL parsing that handles query parameters
2. **S3 Client Parameter Addition**: Add conditional VersionId parameter to boto3 calls
3. **Error Handling Enhancement**: Implement version-specific error detection and response formatting
4. **Function Scope Decision**: Determine which functions should support versionId for consistency
5. **Test Infrastructure**: Establish comprehensive test coverage for version scenarios without breaking existing patterns

**Architecture Decision Points:**

1. Should URI parsing be extracted to a shared utility function?
2. Should all bucket_object_* functions support versionId for consistency?
3. How should version-specific errors be distinguished and reported?
4. Should the response format be enhanced to include version metadata?
5. How should malformed versionId query parameters be handled (reject vs. ignore)?

**Risk Factors:**

1. **Backward Compatibility**: Changes to URI parsing could affect existing consumers
2. **Performance Impact**: URL parsing overhead for all URI processing
3. **Error Response Changes**: Modified error formats might break downstream consumers
4. **Testing Complexity**: Version testing requires more sophisticated test fixtures and AWS setup

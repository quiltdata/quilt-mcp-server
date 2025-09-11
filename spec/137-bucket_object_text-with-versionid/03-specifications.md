# Specifications Document: bucket_object_text with versionId Support

**Issue**: #137 - Add versionId support to bucket_object_text function

## Desired End State

### 1. Standard S3 URI Parsing with versionId Support

Create a shared utility function in `/src/quilt_mcp/utils.py` that parses S3 URIs and extracts versionId from query parameters:

```python
def parse_s3_uri(s3_uri: str) -> tuple[str, str, str | None]:
    """Parse S3 URI into bucket, key, and optional version_id"""
    # s3://bucket/key?versionId=abc123 -> ("bucket", "key", "abc123") 
    # s3://bucket/key -> ("bucket", "key", None)
```

**Implementation Requirements:**

- Use `urllib.parse.urlparse()` and `parse_qs()` for standards compliance
- Reject URIs with unexpected query parameters (strict validation)
- Handle URL-encoded characters with `unquote()`

### 2. All Four Reader Functions Support versionId

Update all bucket object reader functions to use the shared URI parser and pass versionId to S3 API calls:

- `bucket_object_info()` - Uses `head_object(VersionId=version_id)`
- `bucket_object_text()` - Uses `get_object(VersionId=version_id)`
- `bucket_object_fetch()` - Uses `get_object(VersionId=version_id)`
- `bucket_object_link()` - Uses `generate_presigned_url(Params={"VersionId": version_id})`

### 3. Enhanced Test Coverage

**Extend Existing Tests**: Modify existing test functions to include versionId scenarios:

- `test_bucket_object_info_success()` - Add versionId URI test case
- `test_bucket_object_fetch_base64()` - Add versionId mock test case  
- `test_bucket_object_link_success()` - Add versionId URI test case
- `test_bucket_object_text_csv_file()` - Add versionId integration test case

**New Test Functions**: Create dedicated version-specific tests:

- URI parsing with versionId query parameters
- Version-specific error scenarios:
  - `NoSuchVersion` - version ID does not exist
  - `AccessDenied` - insufficient permissions for specific version
  - Invalid versionId format in query parameter
- Backward compatibility validation for existing URIs

## Success Criteria

1. All four functions parse versionId from S3 URIs consistently
2. Version parameter is conditionally passed to S3 API calls
3. Backward compatibility maintained for existing URI formats
4. Comprehensive test coverage for version scenarios
5. Error handling distinguishes version-specific failures (`NoSuchVersion`, `AccessDenied`)

## Quality Gates

- All existing tests continue to pass (fix current test failures first)
- New version functionality tested with real and mocked scenarios  
- Achieve 100% test coverage for bucket_object_* functions
- No breaking changes to function signatures

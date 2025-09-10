# Specifications Document: bucket_object_text with versionId Support

**Issue**: #137 - Add versionId support to bucket_object_text function

## Desired End State

### 1. Standard S3 URI Parsing with versionId Support

Create a shared utility function that parses S3 URIs and extracts versionId from query parameters:

```python
def parse_s3_uri(s3_uri: str) -> tuple[str, str, str | None]:
    """Parse S3 URI into bucket, key, and optional version_id"""
    # s3://bucket/key?versionId=abc123 -> ("bucket", "key", "abc123")
    # s3://bucket/key -> ("bucket", "key", None)
```

### 2. All Four Reader Functions Support versionId

Update all bucket object reader functions to use the shared URI parser and pass versionId to S3 API calls:

- `bucket_object_info()` - Uses `head_object(VersionId=version_id)` 
- `bucket_object_text()` - Uses `get_object(VersionId=version_id)`
- `bucket_object_fetch()` - Uses `get_object(VersionId=version_id)`  
- `bucket_object_link()` - Uses `generate_presigned_url(Params={"VersionId": version_id})`

### 3. Enhanced Test Coverage

Add test cases for:
- URIs with versionId query parameters
- Version-specific error scenarios (invalid version, access denied)
- Backward compatibility with existing URIs

## Success Criteria

1. All four functions parse versionId from S3 URIs consistently
2. Version parameter is conditionally passed to S3 API calls
3. Backward compatibility maintained for existing URI formats
4. Comprehensive test coverage for version scenarios
5. Error handling distinguishes version-specific failures

## Quality Gates

- All existing tests continue to pass
- New version functionality tested with real and mocked scenarios
- 100% test coverage maintained
- No breaking changes to function signatures
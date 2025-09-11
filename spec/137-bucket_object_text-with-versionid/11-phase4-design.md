<!-- markdownlint-disable MD013 -->
# Phase 4 Design: Enhanced S3 API Integration

## Objective

Pass extracted versionId to S3 API calls in all four reader functions when present in the URI.

## Current State

- Phase 3 completed: URI parser extracts `version_id` field
- All four functions receive parsed `version_id` parameter
- S3 API calls use standard parameters without version information

## Target State

- S3 API calls conditionally include `VersionId` parameter when `version_id` is present
- Version-specific errors are properly handled and reported
- Backward compatibility maintained for URIs without version information

## Design Approach

### 1. Conditional S3 API Parameter Addition

For each function, modify the boto3 S3 call to conditionally include `VersionId`:

**Pattern:**

```python
# Before
response = s3_client.operation(Bucket=bucket, Key=key)

# After  
params = {"Bucket": bucket, "Key": key}
if version_id:
    params["VersionId"] = version_id
response = s3_client.operation(**params)
```

### 2. Function-Specific Changes

**bucket_object_info():**

- Modify `head_object()` call to include `VersionId` when present
- Return version information in metadata response

**bucket_object_text():**

- Modify `get_object()` call to include `VersionId` when present
- Version ID affects which object version is retrieved and decoded

**bucket_object_fetch():**

- Modify `get_object()` call to include `VersionId` when present
- Binary data retrieval from specific object version

**bucket_object_link():**

- Modify `generate_presigned_url()` params to include `VersionId` when present
- Presigned URL targets specific object version

### 3. Enhanced Error Handling

Add version-specific error handling:

```python
try:
    # S3 API call with conditional VersionId
except ClientError as e:
    error_code = e.response['Error']['Code']
    if error_code == 'NoSuchVersion':
        return {"success": False, "error": f"Version {version_id} not found for {s3_uri}"}
    elif error_code == 'AccessDenied' and version_id:
        return {"success": False, "error": f"Access denied for version {version_id} of {s3_uri}"}
    # ... existing error handling
```

### 4. Comprehensive Test Coverage

**Extend Existing Test Functions:**

- `test_bucket_object_info_success()` - Add versionId scenarios
- `test_bucket_object_fetch_base64()` - Add versionId scenarios  
- `test_bucket_object_link_success()` - Add versionId scenarios
- `test_bucket_object_text_csv_file()` - Add versionId scenarios

**Test Scenarios for Each Function:**

- Valid versionId with existing object
- Invalid versionId format
- Valid versionId for non-existent object
- versionId with delete marker
- Empty/null versionId handling

### 5. Integration Testing Strategy

Test with real versioned objects:

- Use Quilt Test Resources (.env) to get a versionedObject for testing
  - QUILT_TEST_ENTRY from QUILT_TEST_PACKAGE in QUILT_DEFAULT_BUCKET
- Test each function with valid version IDs
- Test error cases (invalid version IDs, access denied)
- Verify backward compatibility with non-versioned URIs

## Implementation Notes

- No changes to function signatures (version_id already extracted in Phase 3)
- Minimal code changes - only S3 API parameter construction
- Error messages should include version context for clarity
- All existing functionality preserved for URIs without version information

## Success Validation

- All four functions can retrieve specific object versions
- Version-specific error handling works correctly
- Backward compatibility maintained
- Integration tests pass with real AWS S3 versioned objects

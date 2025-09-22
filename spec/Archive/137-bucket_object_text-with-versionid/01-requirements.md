<!-- markdownlint-disable MD013 -->
# Requirements Document: bucket_object_text with versionId Support

**Issue**: #137 - Add versionId support to bucket_object_text function

**Problem Statement**: When Quilt packages store S3 URIs with version IDs (e.g., `s3://bucket/key?versionId=abc123`), the `bucket_object_text` function ignores the version parameter and fetches the current version instead of the specific version that was in the package.

## User Stories

### Story 1: Automatic Version Recognition

**As a** Quilt package user  
**I want** the bucket_object_* reader functions to automatically recognize and use versionId query parameters from S3 URIs  
**So that** I can access the exact object version that was present in the package without additional parameters.

## Acceptance Criteria

1. **URI Parsing**: The function must parse S3 URIs and extract `versionId` from query parameters (e.g., `s3://bucket/key?versionId=abc123`).

2. **Automatic Version Retrieval**: When a versionId is present in the URI, automatically fetch that specific version.

3. **Backward Compatibility**: URIs without versionId continue to work unchanged (fetch current version).

4. **Error Handling**: Appropriate errors when parsed version doesn't exist or access is denied.

## Implementation Approach

Parse the `s3_uri` parameter to extract versionId from query string and pass it to the S3 GetObject call.

## Success Criteria

1. **Functional**: Can read versioned objects using URIs like `s3://bucket/path/file.txt?versionId=xyz`
2. **Compatible**: No breaking changes to existing URI formats

## Open Questions

1. **Other Functions**: Should `bucket_object_fetch` also support versionId parsing for consistency?
2. **URI Validation**: Should malformed versionId query parameters be rejected or ignored?

<!-- markdownlint-disable MD013 -->
# Phase 3 Design: versionId Query Parameter Support

## Objective

Enhance the URI parser to extract versionId from query parameters using `urllib.parse`, with strict validation that only allows the `versionId` query parameter.

## Implementation Plan

### 1. Enhanced URI Parser Function

Modify `parse_s3_uri()` to:

- Use `urllib.parse.urlparse()` to parse the full URI
- Extract query parameters with `parse_qs()`
- Extract `versionId` parameter if present
- Validate that no other query parameters exist
- Return `ParsedS3Uri` with `version_id` field populated

### 2. Strict Query Parameter Validation

Following Quilt3 pattern:

- Only `versionId` query parameter is allowed
- Reject URIs with any other query parameters
- Proper URL decoding with `unquote()`
- Clear error messages for invalid query strings

### 3. Updated Return Type

`ParsedS3Uri` already includes `version_id: Optional[str]` field from Phase 2.

## Implementation Details

### Core Logic (based on Quilt3 reference)

```python
from urllib.parse import urlparse, parse_qs, unquote

def parse_s3_uri(s3_uri: str) -> ParsedS3Uri:
    parsed = urlparse(s3_uri)
    if parsed.scheme != 's3':
        raise ValueError(f"Invalid S3 URI scheme: {parsed.scheme}")
    
    bucket = parsed.netloc
    path = unquote(parsed.path)[1:]  # Remove leading /
    
    # Extract and validate query parameters
    query = parse_qs(parsed.query)
    version_id = query.pop('versionId', [None])[0]
    
    # Strict validation - no other query parameters allowed
    if query:
        raise ValueError(f"Unexpected S3 query string: {parsed.query!r}")
    
    return ParsedS3Uri(
        bucket=bucket,
        key=path,
        version_id=version_id
    )
```

### Error Handling

- Invalid scheme: "Invalid S3 URI scheme: {scheme}"
- Unexpected query parameters: "Unexpected S3 query string: {query!r}"
- Empty bucket/key validation (existing)

## Test Scenarios

### Valid versionId URIs

- `s3://bucket/key?versionId=abc123`
- `s3://bucket/path/to/file.txt?versionId=def456`
- `s3://bucket/key` (no query parameters)

### Invalid Query Parameters

- `s3://bucket/key?other=value` → Error
- `s3://bucket/key?versionId=abc&other=value` → Error
- `s3://bucket/key?prefix=test` → Error

### URL Encoding

- `s3://bucket/key%20with%20spaces?versionId=abc123`
- `s3://bucket/path%2Fto%2Ffile?versionId=def456`

## Success Criteria

- URI parser extracts versionId from query parameters
- Strict validation rejects unexpected query parameters  
- All existing functionality preserved
- 100% test coverage for versionId scenarios
- No impact on bucket_object_text/bucket_object_fetch functions (version_id unused yet)

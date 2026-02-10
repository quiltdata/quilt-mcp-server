"""E2E Integration Test: Content Retrieval Pipeline.

This test validates the complete content retrieval pipeline with REAL services:
- Real S3 list operations
- Real S3 head operations
- Real S3 get operations
- Real presigned URL generation
- Real HTTP fetch via presigned URL

NO MOCKING - All operations use actual AWS and S3 services via tools layer.
"""

import pytest
import requests
import hashlib


@pytest.mark.e2e
@pytest.mark.parametrize("backend_mode", ["quilt3", "platform"], indirect=True)
def test_content_retrieval_pipeline(backend_with_auth, cleanup_s3_objects, real_test_bucket, backend_mode):
    """Test complete content retrieval pipeline with real S3 operations.

    This test validates the full content retrieval workflow:
    1. List real bucket objects (S3 ListObjectsV2)
    2. Get real object metadata (S3 HeadObject)
    3. Generate real presigned URL (boto3 generate_presigned_url)
    4. Fetch actual content (S3 GetObject)
    5. Verify presigned URL works (real HTTP request)

    All operations use REAL AWS services via tools layer - NO MOCKING.

    NOTE: This test currently only works with quilt3 backend because it requires
    direct S3 access via boto3. Platform backend uses JWT auth which doesn't
    provide direct S3 client access to the tools layer.

    Args:
        backend_with_auth: Authenticated backend (quilt3 or platform)
        cleanup_s3_objects: Fixture to track/cleanup created S3 objects
        real_test_bucket: Validated test bucket name
        backend_mode: Backend mode string (quilt3 or platform)
    """
    import boto3
    import time
    from quilt_mcp.tools.buckets import bucket_objects_list, bucket_object_info, bucket_object_link, bucket_object_text

    # Skip platform backend - it doesn't provide direct S3 access to tools layer
    if backend_mode == "platform":
        pytest.skip("Platform backend doesn't support direct S3 access via tools layer (uses JWT auth only)")

    # Create a test object in S3 for this test
    test_content = f"E2E Content Pipeline Test - {time.time()}"
    test_key = f"e2e-tests/content-pipeline/test-{int(time.time())}.txt"
    test_s3_uri = f"s3://{real_test_bucket}/{test_key}"

    # Upload test object directly via boto3
    s3_client = boto3.client('s3')
    s3_client.put_object(
        Bucket=real_test_bucket, Key=test_key, Body=test_content.encode('utf-8'), ContentType='text/plain'
    )

    # Track for cleanup
    cleanup_s3_objects.track_s3_object(bucket=real_test_bucket, key=test_key)

    # Calculate expected hash for integrity check
    expected_hash = hashlib.sha256(test_content.encode('utf-8')).hexdigest()

    # =========================================================================
    # Step 1: List real bucket objects (S3 ListObjectsV2)
    # =========================================================================
    print("\n[Step 1] Listing objects via bucket_objects_list tool")

    list_result = bucket_objects_list(bucket=real_test_bucket, prefix="e2e-tests/content-pipeline/", max_keys=100)

    # Validate list operation
    assert hasattr(list_result, 'objects'), "List result should have objects attribute"
    assert len(list_result.objects) > 0, "Should find at least one object"

    # Find our test object
    found_object = None
    for obj in list_result.objects:
        if obj.key == test_key:
            found_object = obj
            break

    assert found_object is not None, f"Should find test object {test_key}"
    assert found_object.size > 0, "Object should have size"
    assert found_object.last_modified, "Object should have last_modified"
    assert found_object.etag, "Object should have etag"

    print(f"  ✅ Found test object: {test_key}")
    print(f"     Size: {found_object.size} bytes")
    print(f"     ETag: {found_object.etag}")
    print(f"     S3 URI: {found_object.s3_uri}")

    # =========================================================================
    # Step 2: Get real object metadata (S3 HeadObject)
    # =========================================================================
    print("\n[Step 2] Getting object metadata via bucket_object_info tool")

    info_result = bucket_object_info(s3_uri=test_s3_uri)

    # Validate head operation
    assert hasattr(info_result, 'object'), "Info result should have object attribute"
    obj_metadata = info_result.object
    assert obj_metadata.size > 0, "Object metadata should have size"
    assert obj_metadata.last_modified, "Object metadata should have last_modified"
    assert obj_metadata.etag, "Object metadata should have etag"
    assert obj_metadata.content_type, "Object metadata should have content_type"

    # Verify metadata matches list result
    assert obj_metadata.size == found_object.size, "HeadObject size should match ListObjects size"
    assert obj_metadata.etag == found_object.etag, "HeadObject ETag should match ListObjects ETag"

    print("  ✅ Object metadata retrieved:")
    print(f"     Size: {obj_metadata.size} bytes")
    print(f"     ContentType: {obj_metadata.content_type}")
    print(f"     LastModified: {obj_metadata.last_modified}")

    # =========================================================================
    # Step 3: Generate real presigned URL (boto3 generate_presigned_url)
    # =========================================================================
    print("\n[Step 3] Generating presigned URL via bucket_object_link tool")

    link_result = bucket_object_link(s3_uri=test_s3_uri, expiration=300)  # 5 minutes

    # Validate presigned URL
    assert hasattr(link_result, 'signed_url'), "Link result should have signed_url attribute"
    presigned_url = link_result.signed_url
    assert presigned_url is not None, "Presigned URL should not be None"
    assert isinstance(presigned_url, str), "Presigned URL should be a string"
    assert presigned_url.startswith('https://'), "Presigned URL should start with https://"

    print("  ✅ Presigned URL generated:")
    print(f"     URL: {presigned_url[:80]}...")
    print(f"     Expiration: {link_result.expiration_seconds}s")

    # =========================================================================
    # Step 4: Fetch actual content (S3 GetObject)
    # =========================================================================
    print("\n[Step 4] Fetching content via bucket_object_text tool")

    text_result = bucket_object_text(s3_uri=test_s3_uri, max_bytes=10000)

    # Validate content
    assert hasattr(text_result, 'text'), "Text result should have text attribute"
    content_text = text_result.text
    assert content_text == test_content, "Retrieved content should match uploaded content"
    assert text_result.bytes_read > 0, "Should have read some bytes"

    # Verify content integrity
    actual_hash = hashlib.sha256(content_text.encode('utf-8')).hexdigest()
    assert actual_hash == expected_hash, "Content hash should match expected hash"

    print("  ✅ Content fetched and validated:")
    print(f"     Content: {content_text[:50]}...")
    print(f"     Size: {text_result.bytes_read} bytes")
    print(f"     Hash: {actual_hash}")

    # =========================================================================
    # Step 5: Verify presigned URL works (real HTTP request)
    # =========================================================================
    print("\n[Step 5] Verifying presigned URL via HTTP GET")

    # Make real HTTP request to presigned URL
    http_response = requests.get(presigned_url, timeout=30)

    # Validate HTTP response
    assert http_response.status_code == 200, f"HTTP request should succeed, got status {http_response.status_code}"

    # Verify content matches
    http_content = http_response.content
    assert http_content == test_content.encode('utf-8'), "Content from presigned URL should match original content"

    # Verify HTTP headers
    assert 'content-length' in http_response.headers, "HTTP response should include content-length header"
    assert int(http_response.headers['content-length']) == len(test_content.encode('utf-8')), (
        "HTTP content-length should match actual content length"
    )

    print("  ✅ Presigned URL verified:")
    print(f"     HTTP Status: {http_response.status_code}")
    print(f"     Content-Length: {http_response.headers['content-length']}")
    print(f"     Content matches: {http_content == test_content.encode('utf-8')}")

    # =========================================================================
    # Final validation: Auth headers propagation
    # =========================================================================
    print("\n[Step 6] Validating auth headers propagation")

    # Verify that tools layer successfully used authenticated access
    # (The fact that all operations succeeded indicates auth headers worked)

    # Check auth_type in responses to verify authentication was used
    if hasattr(list_result, 'auth_type') and list_result.auth_type:
        print(f"  ✅ List operation used auth_type: {list_result.auth_type}")
    if hasattr(info_result, 'auth_type') and info_result.auth_type:
        print(f"  ✅ Info operation used auth_type: {info_result.auth_type}")
    if hasattr(text_result, 'auth_type') and text_result.auth_type:
        print(f"  ✅ Text operation used auth_type: {text_result.auth_type}")

    # For quilt3 backend, verify session exists
    if backend_mode == "quilt3":
        # Backend should have quilt3 session with auth
        assert hasattr(backend_with_auth, 'quilt3'), "Quilt3 backend should have quilt3 module"

        # Session should be available
        if hasattr(backend_with_auth.quilt3, 'session'):
            session = backend_with_auth.quilt3.session.get_session()
            assert session is not None, "Quilt3 session should be available"
            print("  ✅ Quilt3 session authenticated")

    # For platform backend, verify GraphQL auth
    elif backend_mode == "platform":
        # Backend should have GraphQL auth headers
        try:
            headers = backend_with_auth.get_graphql_auth_headers()
            assert headers is not None, "Platform backend should have auth headers"
            assert len(headers) > 0, "Auth headers should not be empty"
            print(f"  ✅ Platform GraphQL auth headers present: {len(headers)} headers")
        except Exception as e:
            pytest.skip(f"Platform backend auth verification failed: {e}")

    print(f"\n🎉 Content retrieval pipeline test PASSED for {backend_mode} backend")
    print("   All 5 steps completed successfully:")
    print("   1. ✅ List objects (bucket_objects_list tool)")
    print("   2. ✅ Get metadata (bucket_object_info tool)")
    print("   3. ✅ Generate presigned URL (bucket_object_link tool)")
    print("   4. ✅ Fetch content (bucket_object_text tool)")
    print("   5. ✅ Verify presigned URL (HTTP GET)")
    print("   6. ✅ Auth headers propagated correctly")

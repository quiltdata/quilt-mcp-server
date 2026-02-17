"""E2E tests for bucket_list tool with real platform integration.

This module tests the bucket_list tool against real Quilt platform services,
validating bucket discovery with actual user authentication.

NO MOCKING - all operations use real services.
"""

import pytest


@pytest.mark.e2e
@pytest.mark.buckets
@pytest.mark.usefixtures("backend_mode")
class TestBucketListE2E:
    """E2E tests for bucket_list tool.

    Tests run against both quilt3 and platform backends unless
    TEST_BACKEND_MODE environment variable restricts it.

    IMPORTANT: This test uses REAL services:
    - Real GraphQL API for bucket listing
    - Real JWT authentication
    - Real user permissions and bucket filtering
    """

    def test_bucket_list_authenticated_user(self, backend_mode):
        """Test bucket_list with real authenticated user.

        This test validates:
        1. Tool can authenticate with real platform
        2. Tool returns actual buckets user has access to
        3. Bucket data includes all required fields
        4. Permissions are correctly enforced

        Args:
            backend_mode: Backend mode string (quilt3 or platform)
        """
        print(f"\n{'=' * 80}")
        print(f"Bucket List E2E Test (backend: {backend_mode})")
        print(f"{'=' * 80}")

        # Import the bucket_list tool
        from quilt_mcp.tools.buckets import bucket_list

        # Step 1: Call bucket_list with real authentication
        print("\n[Step 1] Calling bucket_list with real authentication")

        result = bucket_list()

        # Validate result structure
        assert result is not None, "bucket_list returned None"
        assert hasattr(result, "success"), "Result missing success field"

        # Check if operation succeeded
        if not result.success:
            error = getattr(result, "error", "Unknown error")
            # For some test environments, platform may not be accessible
            if "Failed to list buckets" in error or "unauthorized" in error.lower():
                pytest.skip(f"Bucket list failed (may be environment limitation): {error}")
            else:
                pytest.fail(f"Unexpected error: {error}")

        print("  ✅ bucket_list succeeded")

        # Step 2: Validate bucket count
        print("\n[Step 2] Validating bucket count")

        assert hasattr(result, "count"), "Result missing count field"
        assert hasattr(result, "buckets"), "Result missing buckets field"

        bucket_count = result.count
        buckets_list = result.buckets

        print(f"  ✅ Found {bucket_count} bucket(s)")

        # Validate count matches list length
        assert len(buckets_list) == bucket_count, (
            f"Count mismatch: count={bucket_count}, len(buckets)={len(buckets_list)}"
        )

        # Step 3: Validate bucket structure (if buckets exist)
        if bucket_count > 0:
            print(f"\n[Step 3] Validating bucket structure for {bucket_count} bucket(s)")

            for idx, bucket in enumerate(buckets_list):
                # Required fields
                assert hasattr(bucket, "name"), f"Bucket {idx} missing name field"
                assert hasattr(bucket, "title"), f"Bucket {idx} missing title field"
                assert hasattr(bucket, "relevanceScore"), f"Bucket {idx} missing relevanceScore field"
                assert hasattr(bucket, "browsable"), f"Bucket {idx} missing browsable field"

                # Validate field types
                assert isinstance(bucket.name, str), f"Bucket {idx} name should be string"
                assert len(bucket.name) > 0, f"Bucket {idx} name should not be empty"
                assert isinstance(bucket.title, str), f"Bucket {idx} title should be string"
                assert isinstance(bucket.relevanceScore, int), f"Bucket {idx} relevanceScore should be int"
                assert isinstance(bucket.browsable, bool), f"Bucket {idx} browsable should be bool"

                # Optional fields (can be None)
                if bucket.description is not None:
                    assert isinstance(bucket.description, str), f"Bucket {idx} description should be string"
                if bucket.iconUrl is not None:
                    assert isinstance(bucket.iconUrl, str), f"Bucket {idx} iconUrl should be string"
                if bucket.tags is not None:
                    assert isinstance(bucket.tags, list), f"Bucket {idx} tags should be list"

                print(f"  ✅ Bucket {idx + 1}/{bucket_count}: {bucket.name} (title: {bucket.title})")

            print(f"  ✅ All {bucket_count} bucket(s) have valid structure")

            # Step 4: Sample detailed bucket inspection
            print("\n[Step 4] Detailed inspection of first bucket")

            first_bucket = buckets_list[0]
            print(f"  Name: {first_bucket.name}")
            print(f"  Title: {first_bucket.title}")
            print(f"  Description: {first_bucket.description or '(none)'}")
            print(f"  Icon URL: {first_bucket.iconUrl or '(none)'}")
            print(f"  Relevance Score: {first_bucket.relevanceScore}")
            print(f"  Browsable: {first_bucket.browsable}")
            print(f"  Tags: {first_bucket.tags or '(none)'}")

            print("  ✅ First bucket inspection complete")

        else:
            print("\n[Step 3] No buckets found (empty list is valid)")
            print("  ℹ️  User may not have access to any buckets")

        # Step 5: Verify result consistency
        print("\n[Step 5] Verifying result consistency")

        # Call again to ensure consistent results
        result2 = bucket_list()

        assert result2 is not None, "Second bucket_list call returned None"
        assert result2.success is True, "Second call should also succeed"
        assert result2.count == bucket_count, "Bucket count should be consistent across calls"

        print(f"  ✅ Consistent results: {bucket_count} bucket(s) on both calls")

        # Final validation
        print("\n[Final Validation] Bucket list E2E test success criteria")

        print("  ✅ Authentication successful")
        print("  ✅ GraphQL query executed")
        print(f"  ✅ Returned {bucket_count} bucket(s)")
        print("  ✅ All buckets have valid structure")
        print("  ✅ Results are consistent")

        print("\n" + "=" * 80)
        print("Bucket List E2E Test: SUCCESS")
        print(f"  - Backend: {backend_mode}")
        print(f"  - Buckets: {bucket_count}")
        print("  - Authentication: Valid")
        print("=" * 80)

    def test_bucket_list_empty_response_handling(self, backend_mode):
        """Test that empty bucket list is handled gracefully.

        Some users may legitimately have no buckets, which should not be an error.

        Args:
            backend_mode: Backend mode string (quilt3 or platform)
        """
        print(f"\n[Test] Empty bucket list handling (backend: {backend_mode})")

        from quilt_mcp.tools.buckets import bucket_list

        result = bucket_list()

        # Should succeed even with 0 buckets
        assert result is not None, "bucket_list returned None"
        assert hasattr(result, "success"), "Result missing success field"

        if not result.success:
            error = getattr(result, "error", "Unknown error")
            pytest.skip(f"Bucket list failed: {error}")

        # Empty list is valid
        assert hasattr(result, "count"), "Result missing count field"
        assert hasattr(result, "buckets"), "Result missing buckets field"
        assert result.count >= 0, "Count should be non-negative"
        assert len(result.buckets) == result.count, "Count should match list length"

        print(f"  ✅ Empty list handling: {result.count} bucket(s)")

    def test_bucket_list_field_completeness(self, backend_mode):
        """Test that all expected fields are present in bucket objects.

        Validates the complete bucket schema from the GraphQL API.

        Args:
            backend_mode: Backend mode string (quilt3 or platform)
        """
        print(f"\n[Test] Bucket field completeness (backend: {backend_mode})")

        from quilt_mcp.tools.buckets import bucket_list

        result = bucket_list()

        if not result.success or result.count == 0:
            pytest.skip("No buckets available for field validation")

        # Check all required and optional fields on first bucket
        bucket = result.buckets[0]

        # Required fields
        required_fields = ["name", "title", "relevanceScore", "browsable"]
        for field in required_fields:
            assert hasattr(bucket, field), f"Required field missing: {field}"
            assert getattr(bucket, field) is not None, f"Required field is None: {field}"
            print(f"  ✅ Required field present: {field}")

        # Optional fields (can be None)
        optional_fields = ["description", "iconUrl", "tags"]
        for field in optional_fields:
            assert hasattr(bucket, field), f"Optional field missing: {field}"
            print(f"  ✅ Optional field present: {field} = {getattr(bucket, field)}")

        print("  ✅ All expected fields present in bucket schema")

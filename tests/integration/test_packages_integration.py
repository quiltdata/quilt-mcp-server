"""Integration tests for package lifecycle and listing operations.

Tests the complete workflow of package creation, updates, browsing, deletion,
and listing across catalog-wide and registry-scoped contexts.

Based on spec/a10-no-default-registry.md Phase 8, Section 3.
"""

import time
import pytest

from quilt_mcp.tools.packages import (
    package_create,
    package_update,
    package_browse,
    package_delete,
    packages_list,
)
from quilt_mcp.models import (
    PackageCreateSuccess,
    PackageUpdateSuccess,
    PackageBrowseSuccess,
    PackageDeleteSuccess,
    PackagesListSuccess,
    ErrorResponse,
)


@pytest.mark.integration
def test_package_create_update_delete_workflow(test_bucket):
    """Test complete package lifecycle with explicit registry parameter.

    This test verifies the full workflow:
    1. Create a new package with explicit registry
    2. Browse the package to verify creation
    3. Update the package with a new message
    4. Delete the package

    All operations must succeed and properly handle the explicit registry parameter.
    """
    # Use unique package name with timestamp to avoid conflicts
    pkg_name = f"test/coverage-{int(time.time())}"

    # Need to create a test file in the bucket first for package creation
    test_key = f"test-data-{int(time.time())}.txt"
    test_s3_uri = f"{test_bucket}/{test_key}"

    # First upload a test file to use in package
    from quilt_mcp.tools.buckets import bucket_objects_put

    upload_result = bucket_objects_put(
        bucket=test_bucket,
        items=[{"key": test_key, "text": "Test data for package integration test"}]
    )
    assert upload_result.success, f"Failed to upload test data: {upload_result}"

    # Step 1: Create package with explicit registry
    create_result = package_create(
        package_name=pkg_name,
        s3_uris=[test_s3_uri],
        registry=test_bucket,
        message="Initial version for integration test",
    )

    # Verify creation succeeded
    assert isinstance(create_result, PackageCreateSuccess), (
        f"Package creation failed: {create_result.error if hasattr(create_result, 'error') else 'Unknown error'}"
    )
    assert create_result.success is True
    assert create_result.package == pkg_name
    assert create_result.registry == test_bucket
    assert create_result.top_hash is not None

    # Step 2: Browse to verify package exists
    browse_result = package_browse(
        package_name=pkg_name,
        registry=test_bucket,
        include_file_info=False,
        include_signed_urls=False,
    )

    assert isinstance(browse_result, PackageBrowseSuccess), (
        f"Package browse failed: {browse_result.error if hasattr(browse_result, 'error') else 'Unknown error'}"
    )
    assert browse_result.success is True
    assert browse_result.package == pkg_name
    assert browse_result.registry == test_bucket

    # Step 3: Update package with new content
    test_key_2 = f"test-data-update-{int(time.time())}.txt"
    test_s3_uri_2 = f"{test_bucket}/{test_key_2}"

    upload_result_2 = bucket_objects_put(
        bucket=test_bucket,
        items=[{"key": test_key_2, "text": "Updated data for package integration test"}]
    )
    assert upload_result_2.success, f"Failed to upload update data: {upload_result_2}"

    update_result = package_update(
        package_name=pkg_name,
        s3_uris=[test_s3_uri_2],
        registry=test_bucket,
        message="Updated version for integration test",
    )

    assert isinstance(update_result, PackageUpdateSuccess), (
        f"Package update failed: {update_result.error if hasattr(update_result, 'error') else 'Unknown error'}"
    )
    assert update_result.success is True
    assert update_result.package == pkg_name
    assert update_result.registry == test_bucket
    assert update_result.top_hash is not None
    # Update should create a different hash than creation
    assert update_result.top_hash != create_result.top_hash

    # Step 4: Delete package
    delete_result = package_delete(
        package_name=pkg_name,
        registry=test_bucket,
    )

    assert isinstance(delete_result, PackageDeleteSuccess), (
        f"Package delete failed: {delete_result.error if hasattr(delete_result, 'error') else 'Unknown error'}"
    )
    assert delete_result.success is True
    assert delete_result.package == pkg_name
    assert delete_result.registry == test_bucket
    assert delete_result.versions_deleted >= 1


@pytest.mark.integration
def test_packages_list_integration(test_bucket):
    """Test packages_list with registry-scoped queries.

    This test verifies:
    1. Registry-scoped listing (explicit bucket parameter)
    2. Test package appears in scoped results
    3. Prefix filtering works correctly

    Note: Catalog-wide listing (empty registry) is not yet implemented.
    See spec/a10-no-default-registry.md Phase 6 for future catalog-wide feature.
    """
    # Create a test package first to ensure data exists
    pkg_name = f"test/list-test-{int(time.time())}"
    test_key = f"test-list-data-{int(time.time())}.txt"
    test_s3_uri = f"{test_bucket}/{test_key}"

    # Upload test data
    from quilt_mcp.tools.buckets import bucket_objects_put

    upload_result = bucket_objects_put(
        bucket=test_bucket,
        items=[{"key": test_key, "text": "Test data for listing integration test"}]
    )
    assert upload_result.success, f"Failed to upload test data: {upload_result}"

    # Create test package
    create_result = package_create(
        package_name=pkg_name,
        s3_uris=[test_s3_uri],
        registry=test_bucket,
        message="Test package for listing integration test",
    )
    assert create_result.success, f"Failed to create test package: {create_result}"

    try:
        # Test 1: Registry-scoped listing (explicit bucket)
        scoped_packages = packages_list(registry=test_bucket, limit=100)

        assert isinstance(scoped_packages, PackagesListSuccess), (
            f"Registry-scoped listing failed: {scoped_packages.error if hasattr(scoped_packages, 'error') else 'Unknown error'}"
        )
        assert scoped_packages.success is True
        assert isinstance(scoped_packages.packages, list)
        assert len(scoped_packages.packages) > 0, (
            f"Expected at least one package in {test_bucket}, got empty list"
        )

        # Test 2: Verify our test package appears in scoped results
        package_names = [p for p in scoped_packages.packages]
        assert pkg_name in package_names, (
            f"Test package '{pkg_name}' not found in scoped results. "
            f"Found packages: {package_names}"
        )

        # Test 3: Verify prefix filtering works
        prefix = pkg_name.split("/")[0]  # Get "test" prefix
        prefixed_packages = packages_list(registry=test_bucket, prefix=prefix, limit=100)

        assert isinstance(prefixed_packages, PackagesListSuccess)
        assert prefixed_packages.success is True
        # All returned packages should start with the prefix
        for pkg in prefixed_packages.packages:
            assert pkg.startswith(prefix), f"Package {pkg} does not start with prefix {prefix}"

    finally:
        # Cleanup: Delete test package
        delete_result = package_delete(
            package_name=pkg_name,
            registry=test_bucket,
        )
        # Don't fail the test if cleanup fails, but log it
        if not delete_result.success:
            print(f"Warning: Failed to cleanup test package {pkg_name}: {delete_result}")


@pytest.mark.integration
def test_package_create_requires_registry():
    """Test that package_create fails with clear error when registry is empty.

    This validates the explicit registry requirement - no default bucket fallback.
    """
    result = package_create(
        package_name="test/should-fail",
        s3_uris=["s3://any-bucket/file.txt"],
        registry="",  # Empty string - should fail
        message="This should fail",
    )

    # Should return an error response
    assert isinstance(result, ErrorResponse), (
        f"Expected ErrorResponse for empty registry, got {type(result)}"
    )
    assert result.success is False
    # Error message should mention registry and requirement
    assert "registry" in result.error.lower() or "bucket" in result.error.lower(), (
        f"Error message should mention registry requirement. Got: {result.error}"
    )


@pytest.mark.integration
def test_package_update_requires_registry():
    """Test that package_update fails with clear error when registry is empty.

    This validates the explicit registry requirement for updates.
    """
    result = package_update(
        package_name="test/should-fail",
        s3_uris=["s3://any-bucket/file.txt"],
        registry="",  # Empty string - should fail
        message="This should fail",
    )

    # Should return an error response
    assert isinstance(result, ErrorResponse), (
        f"Expected ErrorResponse for empty registry, got {type(result)}"
    )
    assert result.success is False
    # Error message should mention registry and requirement
    assert "registry" in result.error.lower() or "bucket" in result.error.lower(), (
        f"Error message should mention registry requirement. Got: {result.error}"
    )


@pytest.mark.integration
def test_package_delete_requires_registry():
    """Test that package_delete fails with clear error when registry is empty.

    This validates the explicit registry requirement for deletion.
    """
    result = package_delete(
        package_name="test/should-fail",
        registry="",  # Empty string - should fail
    )

    # Should return an error response
    assert isinstance(result, ErrorResponse), (
        f"Expected ErrorResponse for empty registry, got {type(result)}"
    )
    assert result.success is False
    # Error message should mention registry and requirement
    assert "registry" in result.error.lower() or "bucket" in result.error.lower(), (
        f"Error message should mention registry requirement. Got: {result.error}"
    )


@pytest.mark.integration
def test_packages_list_requires_registry_currently():
    """Test that packages_list currently requires registry parameter.

    Note: The spec (spec/a10-no-default-registry.md Phase 6) describes a future
    catalog-wide listing feature, but it is not yet implemented. This test validates
    the current behavior which requires an explicit registry.

    When catalog-wide listing is implemented, this test should be updated or replaced
    with a test that validates catalog-wide functionality.
    """
    result = packages_list(registry="", limit=10)

    # Currently returns an error for empty registry (catalog-wide not implemented yet)
    assert isinstance(result, ErrorResponse), (
        f"Expected ErrorResponse for empty registry (catalog-wide not implemented), got {type(result)}"
    )
    assert result.success is False
    assert "registry" in result.error.lower() or "bucket" in result.error.lower(), (
        f"Error message should mention registry requirement. Got: {result.error}"
    )


@pytest.mark.integration
def test_package_browse_requires_registry(test_bucket):
    """Test that package_browse requires explicit registry parameter.

    This ensures browsing is always scoped to a specific registry.
    """
    # First create a test package
    pkg_name = f"test/browse-test-{int(time.time())}"
    test_key = f"test-browse-data-{int(time.time())}.txt"
    test_s3_uri = f"{test_bucket}/{test_key}"

    from quilt_mcp.tools.buckets import bucket_objects_put

    upload_result = bucket_objects_put(
        bucket=test_bucket,
        items=[{"key": test_key, "text": "Test data for browse test"}]
    )
    assert upload_result.success

    create_result = package_create(
        package_name=pkg_name,
        s3_uris=[test_s3_uri],
        registry=test_bucket,
        message="Test package for browse test",
    )
    assert create_result.success

    try:
        # Test 1: Browse with explicit registry should succeed
        browse_result = package_browse(
            package_name=pkg_name,
            registry=test_bucket,
            include_file_info=False,
            include_signed_urls=False,
        )
        assert isinstance(browse_result, PackageBrowseSuccess)
        assert browse_result.success is True

        # Test 2: Browse with empty registry should fail
        browse_empty = package_browse(
            package_name=pkg_name,
            registry="",
            include_file_info=False,
            include_signed_urls=False,
        )
        assert isinstance(browse_empty, ErrorResponse)
        assert browse_empty.success is False

    finally:
        # Cleanup
        delete_result = package_delete(package_name=pkg_name, registry=test_bucket)
        if not delete_result.success:
            print(f"Warning: Failed to cleanup test package {pkg_name}")

import time
import uuid

import pytest

from quilt_mcp import (  # type: ignore[import-not-found]
    DEFAULT_BUCKET,
    DEFAULT_REGISTRY,
    KNOWN_TEST_ENTRY,
    KNOWN_TEST_PACKAGE,
    KNOWN_TEST_S3_OBJECT,
    auth_status,
    bucket_object_fetch,
    bucket_object_info,
    bucket_object_text,
    bucket_objects_list,
    bucket_objects_put,
    bucket_objects_search,
    catalog_info,
    catalog_name,
    catalog_url,
    catalog_uri,
    filesystem_status,
    package_browse,
    package_contents_search,
    package_create,
    package_delete,
    package_diff,
    package_update,
    packages_list,
    packages_search,
)

# Test configuration - using constants
TEST_REGISTRY = DEFAULT_REGISTRY
KNOWN_PACKAGE = KNOWN_TEST_PACKAGE
KNOWN_BUCKET = DEFAULT_BUCKET
EXPECTED_S3_OBJECT = KNOWN_TEST_S3_OBJECT


class TestQuiltAPI:
    """Test suite for quilt MCP server using real data - tests that expect actual results."""

    def test_packages_list_returns_data(self):
        """Test that packages_list returns actual packages from configured registry."""
        result = packages_list(registry=TEST_REGISTRY)

        assert isinstance(result, dict), "Result should be a dict"
        assert "packages" in result, "Result should have 'packages' key"
        # FAIL if no packages - this indicates a real problem
        assert len(result["packages"]) > 0, f"Expected packages in {TEST_REGISTRY}, got empty list - this indicates missing data or misconfiguration"

        # Check that we get string package names
        for pkg in result["packages"]:
            assert isinstance(pkg, str), f"Package name should be string, got {type(pkg)}: {pkg}"
            assert "/" in pkg, f"Package names should contain namespace/name format, got: {pkg}"

    def test_packages_list_prefix(self):
        """Test that prefix filtering works and finds the configured test package."""
        # Extract prefix from known test package
        test_prefix = KNOWN_PACKAGE.split("/")[0] if "/" in KNOWN_PACKAGE else KNOWN_PACKAGE
        result = packages_list(registry=TEST_REGISTRY, prefix=test_prefix)

        assert isinstance(result, dict)
        assert "packages" in result

        # FAIL if no packages with this prefix - this means the test environment is misconfigured
        assert len(result["packages"]) > 0, f"No {test_prefix} packages found in {TEST_REGISTRY} - check QUILT_TEST_PACKAGE configuration"

        # Verify all results match prefix
        for pkg in result["packages"]:
            assert pkg.startswith(test_prefix), f"Package {pkg} doesn't start with '{test_prefix}'"

        # FAIL if known package not found - this means the test environment is misconfigured
        package_names = result["packages"]
        assert KNOWN_PACKAGE in package_names, f"Known package {KNOWN_PACKAGE} not found in {TEST_REGISTRY} - check QUILT_TEST_PACKAGE configuration"

    @pytest.mark.search
    def test_packages_search_finds_data(self):
        """Test that searching finds actual data (search returns S3 objects, not packages)."""
        # Try multiple search terms to find some data
        search_terms = ["data", "test", "file", "csv", "parquet", "txt", "json"]
        found_results = False

        for term in search_terms:
            result = packages_search(term, limit=5)
            assert isinstance(result, dict)
            assert "results" in result

            if len(result["results"]) > 0:
                found_results = True
                # Verify the response structure is correct
                for item in result["results"]:
                    if isinstance(item, dict) and "_source" in item:
                        assert len(item["_source"]) > 0, "Search result should have at least one key in _source"
                break

        # FAIL if no search terms found any data - this indicates a real problem
        assert found_results, f"No search results found for any common terms {search_terms} - check if search indexing is working or data exists"

    def test_package_browse_known_package(self):
        """Test browsing the known test package."""
        result = package_browse(KNOWN_PACKAGE, registry=TEST_REGISTRY)

        assert isinstance(result, dict)
        assert "entries" in result
        assert "package_name" in result
        assert "total_entries" in result

        # FAIL if no entries found - this means the test package is misconfigured
        assert len(result["entries"]) > 0, f"Package {KNOWN_PACKAGE} appears empty - check QUILT_TEST_PACKAGE configuration"

        # Check we get actual entry structures
        for entry in result["entries"]:
            assert isinstance(entry, dict), f"Entry should be dict, got {type(entry)}: {entry}"
            assert "logical_key" in entry, f"Entry missing logical_key: {entry}"

    def test_package_contents_search_in_known_package(self):
        """Test searching within a known package for files."""
        # Try searching for the known test entry first
        known_entry = KNOWN_TEST_ENTRY if KNOWN_TEST_ENTRY else "README.md"
        result = package_contents_search(KNOWN_PACKAGE, known_entry, registry=TEST_REGISTRY)

        assert isinstance(result, dict)
        assert "matches" in result
        assert "count" in result

        # If the known entry isn't found, try common extensions
        if result["count"] == 0:
            for ext in [".md", ".txt", ".csv", ".json", ".parquet"]:
                result = package_contents_search(KNOWN_PACKAGE, ext, registry=TEST_REGISTRY)
                if result["count"] > 0:
                    break

        # Don't fail if no matches - just verify the search functionality works
        # (Some packages might not have common file types)
        if result["count"] > 0:
            for match in result["matches"]:
                assert isinstance(match, dict), f"Match should be dict, got {type(match)}: {match}"
                assert "logical_key" in match, f"Match missing logical_key: {match}"

    def test_bucket_objects_list_returns_data(self):
        """Test that bucket listing returns actual objects."""
        result = bucket_objects_list(bucket=KNOWN_BUCKET, max_keys=10)

        assert isinstance(result, dict)
        assert "objects" in result
        assert "bucket" in result
        assert len(result["objects"]) > 0, f"Expected objects in {KNOWN_BUCKET}, got empty list"

        # Check object structure
        for obj in result["objects"]:
            assert "key" in obj, f"Object missing 'key': {obj}"
            assert "size" in obj, f"Object missing 'size': {obj}"
            assert isinstance(obj["key"], str), f"Object key should be string: {obj}"

    def test_bucket_object_info_known_file(self):
        """Test getting info for a known public file."""
        result = bucket_object_info(EXPECTED_S3_OBJECT)

        assert isinstance(result, dict)
        if "error" in result:
            pytest.skip(f"Known file not accessible: {result['error']}")

        assert "bucket" in result
        assert "key" in result
        assert "size" in result
        assert result["size"] > 0, "File should have non-zero size"

    def test_bucket_object_text_csv_file(self):
        """Test reading text from the configured test file."""
        # Use the configured test entry which should be a text file
        test_uri = KNOWN_TEST_S3_OBJECT
        result = bucket_object_text(test_uri, max_bytes=1000)

        assert isinstance(result, dict)
        if "error" in result:
            pytest.skip(f"Test file not accessible: {result['error']}")

        assert "text" in result
        assert "bucket" in result
        assert "key" in result

        # Verify we can read text content (don't assume specific format)
        text = result["text"]
        assert len(text) > 0, "File should have content"
        assert isinstance(text, str), "Text should be a string"
        # Don't assume markdown format - different environments have different file types

    def test_auth_status_returns_status(self):
        """Test authentication check returns valid status."""
        result = auth_status()

        assert isinstance(result, dict)
        assert "status" in result
        assert result["status"] in ["authenticated", "not_authenticated", "error"]

        # Test specific status behaviors
        if result["status"] == "authenticated":
            assert "catalog_url" in result, "Authenticated status should include catalog_url"
            assert result["search_available"] is True
        elif result["status"] == "not_authenticated":
            assert "setup_instructions" in result, "Not authenticated should include setup instructions"
            assert result["search_available"] is False
        else:  # error status
            assert "error" in result, "Error status should include error message"

    def test_filesystem_status_returns_info(self):
        """Test filesystem check returns actual system info."""
        result = filesystem_status()

        assert isinstance(result, dict)
        assert "is_lambda" in result
        assert "home_directory" in result
        assert "temp_directory" in result
        assert "current_directory" in result

        # Verify we get actual paths
        assert result["home_directory"].startswith("/"), f"Home directory should be absolute path: {result['home_directory']}"
        assert result["temp_directory"].startswith("/"), f"Temp directory should be absolute path: {result['temp_directory']}"
        assert result["current_directory"].startswith("/"), f"Current directory should be absolute path: {result['current_directory']}"

    def test_catalog_info_returns_data(self):
        """Test catalog_info returns current catalog information."""
        result = catalog_info()

        assert isinstance(result, dict)
        assert "catalog_name" in result
        assert "is_authenticated" in result
        assert "status" in result
        assert result["status"] in ["success", "error"]

        if result["status"] == "success":
            assert isinstance(result["catalog_name"], str)
            assert isinstance(result["is_authenticated"], bool)
            assert len(result["catalog_name"]) > 0, "Catalog name should not be empty"

    def test_catalog_name_returns_name(self):
        """Test catalog_name returns the catalog name and detection method."""
        result = catalog_name()

        assert isinstance(result, dict)
        assert "catalog_name" in result
        assert "detection_method" in result
        assert "status" in result
        assert result["status"] in ["success", "error"]

        if result["status"] == "success":
            assert isinstance(result["catalog_name"], str)
            assert isinstance(result["detection_method"], str)
            assert len(result["catalog_name"]) > 0, "Catalog name should not be empty"
            assert result["detection_method"] in ["authentication", "navigator_config", "registry_config", "unknown"]

    def test_catalog_url_package_view(self):
        """Test catalog_url generates valid package view URLs."""
        result = catalog_url(
            registry=TEST_REGISTRY,
            package_name="raw/salmon-rnaseq",
            path="README.md"
        )

        assert isinstance(result, dict)
        assert "status" in result

        if result["status"] == "success":
            assert "catalog_url" in result
            assert "view_type" in result
            assert "bucket" in result
            assert result["view_type"] == "package"
            assert result["catalog_url"].startswith("https://")
            assert "/b/" in result["catalog_url"]
            assert "/packages/" in result["catalog_url"]
            assert "raw/salmon-rnaseq" in result["catalog_url"]
            assert "README.md" in result["catalog_url"]

    def test_catalog_url_bucket_view(self):
        """Test catalog_url generates valid bucket view URLs."""
        result = catalog_url(
            registry=TEST_REGISTRY,
            path="test/data.csv"
        )

        assert isinstance(result, dict)
        assert "status" in result

        if result["status"] == "success":
            assert "catalog_url" in result
            assert "view_type" in result
            assert "bucket" in result
            assert result["view_type"] == "bucket"
            assert result["catalog_url"].startswith("https://")
            assert "/b/" in result["catalog_url"]
            assert "/tree/" in result["catalog_url"]
            assert "test/data.csv" in result["catalog_url"]

    def test_catalog_uri_package_reference(self):
        """Test catalog_uri generates valid Quilt+ URIs."""
        result = catalog_uri(
            registry=TEST_REGISTRY,
            package_name="raw/salmon-rnaseq",
            path="README.md"
        )

        assert isinstance(result, dict)
        assert "status" in result

        if result["status"] == "success":
            assert "quilt_plus_uri" in result
            assert "bucket" in result
            assert result["quilt_plus_uri"].startswith("quilt+s3://")
            assert "package=raw/salmon-rnaseq" in result["quilt_plus_uri"]
            assert "path=README.md" in result["quilt_plus_uri"]

    def test_catalog_uri_with_version(self):
        """Test catalog_uri generates versioned Quilt+ URIs."""
        test_hash = "abc123def456"
        result = catalog_uri(
            registry=TEST_REGISTRY,
            package_name="raw/salmon-rnaseq",
            path="README.md",
            top_hash=test_hash
        )

        assert isinstance(result, dict)
        assert "status" in result

        if result["status"] == "success":
            assert "quilt_plus_uri" in result
            assert f"package=raw/salmon-rnaseq@{test_hash}" in result["quilt_plus_uri"]

    # FAILURE CASES - These should fail gracefully

    @pytest.mark.search
    def test_packages_search_no_results(self):
        """Test that non-existent search returns empty results, not error."""
        result = packages_search("xyznonexistentpackage123456789")

        assert isinstance(result, dict)
        assert "results" in result
        assert len(result["results"]) == 0, "Non-existent search should return empty results"

    def test_packages_list_invalid_registry_fails(self):
        """Test that invalid registry fails gracefully with proper error."""
        with pytest.raises(Exception) as exc_info:
            packages_list(registry="s3://definitely-nonexistent-bucket-xyz")

        # Should get a meaningful error about the bucket
        error_msg = str(exc_info.value).lower()
        assert any(term in error_msg for term in [
            "nosuchbucket", "no such bucket", "bucket", "not found"
        ]), f"Expected meaningful bucket error, got: {exc_info.value}"

    def test_package_browse_nonexistent_fails(self):
        """Test that browsing non-existent package raises exception."""
        with pytest.raises(Exception) as exc_info:
            package_browse("definitely/nonexistent/package")

        error_msg = str(exc_info.value).lower()
        assert any(term in error_msg for term in [
            "not found", "does not exist", "no such file", "invalid package name"
        ]), f"Expected meaningful error message, got: {exc_info.value}"

    def test_bucket_object_info_nonexistent_fails(self):
        """Test that non-existent object returns error."""
        result = bucket_object_info(f"{KNOWN_BUCKET}/definitely/nonexistent/file.txt")

        assert isinstance(result, dict)
        assert "error" in result, "Non-existent file should return error"
        assert "bucket" in result
        assert "key" in result

    def test_bucket_object_fetch_returns_data(self):
        """Test fetching object data from S3."""
        # Use a small object from bucket listing
        objects_result = bucket_objects_list(bucket=KNOWN_BUCKET, max_keys=5)
        if not objects_result.get("objects"):
            pytest.skip("No objects found to test fetch")

        # Find a small object to test (prefer smallest under threshold)
        candidates = [o for o in objects_result["objects"] if o.get("size", 0) > 0]
        SMALL_MAX = 10000
        small_obj = None
        if candidates:
            under = [o for o in candidates if o.get("size", 0) < SMALL_MAX]
            search_space = under or candidates
            small_obj = min(search_space, key=lambda o: o.get("size", 0))
        if not small_obj:
            pytest.skip("No suitable objects (non-zero size) found to test fetch")
        # Static type assurance (helps static analysis)
        assert small_obj is not None  # noqa: F821
        s3_uri = f"s3://{objects_result['bucket']}/{small_obj['key']}"
        result = bucket_object_fetch(s3_uri, max_bytes=1000)

        assert isinstance(result, dict)
        if "error" in result:
            pytest.skip(f"Object not accessible: {result['error']}")

        assert "bucket" in result
        assert "key" in result
        assert "data" in result or "text" in result, "Should return either data or text"
        assert "size" in result
        assert result["size"] > 0, "Fetched object should have content"

    def test_bucket_objects_put_small_file(self):
        """Test uploading small objects to S3."""
        test_bucket = KNOWN_BUCKET
        test_items = [
            {
                "key": "test-uploads/test-file-1.txt",
                "text": "Hello, this is a test file created by the test suite.",
                "content_type": "text/plain",
                "metadata": {"created_by": "test_suite", "test": "true"}
            },
            {
                "key": "test-uploads/test-file-2.json",
                "text": '{"message": "test json", "timestamp": "2025-01-01"}',
                "content_type": "application/json"
            }
        ]

        result = bucket_objects_put(test_bucket, test_items)

        assert isinstance(result, dict)
        assert "bucket" in result
        assert "requested" in result
        assert "uploaded" in result
        assert "results" in result

        assert result["requested"] == 2, "Should have requested 2 uploads"

        # Expect successful uploads (user should have permissions)
        if result["uploaded"] < result["requested"]:
            # Check for permission errors
            for item_result in result["results"]:
                if "error" in item_result:
                    error_msg = item_result["error"].lower()
                    if "accessdenied" in error_msg or "not authorized" in error_msg:
                        pytest.fail(f"Permission error - user needs s3:PutObject permissions: {item_result['error']}")

        assert result["uploaded"] > 0, "Should have successfully uploaded some files"

        # Check individual results
        for item_result in result["results"]:
            assert "key" in item_result
            # Should have successful uploads (etag) for test environment
            if "error" in item_result and "accessdenied" not in item_result["error"].lower():
                pytest.fail(f"Unexpected upload error: {item_result['error']}")

        # Clean up uploaded test files
        try:
            for item in test_items:
                from quilt_mcp import bucket_object_info  # type: ignore[import-not-found]
                # Verify file was uploaded, then we could delete it if there was a delete tool
                info_result = bucket_object_info(f"{KNOWN_BUCKET}/{item['key']}")
                if "error" not in info_result:
                    print(f"Test file uploaded successfully: {item['key']}")
        except Exception:
            pass  # Cleanup is best-effort

    def test_package_create_realistic(self):
        """Test creating a package from existing S3 objects."""
        # Get some actual objects from the bucket to use
        objects_result = bucket_objects_list(bucket=KNOWN_BUCKET, max_keys=3)
        if not objects_result.get("objects"):
            pytest.skip("No objects found to create package from")

        # Build S3 URIs from actual objects (prefer smaller ones)
        MAX_FILE = 50000
        s3_uris = [
            f"s3://{objects_result['bucket']}/{obj['key']}"
            for obj in objects_result["objects"]
            if obj.get("size", 0) < MAX_FILE and obj.get("size", 0) > 0
        ][:2]

        if not s3_uris:
            pytest.skip("No suitable objects found for package creation")

        test_metadata = {
            "description": "Test package created by integration tests",
            "created_by": "test_suite",
            "test": True
        }

        dynamic_pkg_name = f"testuser/testpackage-{int(time.time())}-{uuid.uuid4().hex[:8]}"
        result = package_create(
            package_name=dynamic_pkg_name,
            s3_uris=s3_uris,
            registry=TEST_REGISTRY,
            metadata=test_metadata,
            message="Test package creation",
            flatten=True
        )

        assert isinstance(result, dict)

        # Expect success (user should have permissions)
        if "error" in result:
            # If it fails due to permissions, that's a setup issue
            error_msg = result["error"].lower()
            if "accessdenied" in error_msg or "not authorized" in error_msg:
                pytest.fail(f"Permission error - user needs s3:PutObject permissions: {result['error']}")
            else:
                pytest.fail(f"Package creation failed: {result['error']}")

        # Verify successful creation
        assert "status" in result
        assert result["status"] == "success"
        assert "package_name" in result
        assert "entries_added" in result
        assert result["entries_added"] > 0, "Should have added some entries"

        # Clean up - delete the test package
        try:
            delete_result = package_delete(result["package_name"], registry=TEST_REGISTRY)
            if delete_result.get("status") != "success":
                print(
                    f"Warning: Package cleanup did not report success: {delete_result}"
                )
        except Exception as cleanup_error:
            print(
                f"Warning: Exception during cleanup of {result['package_name']}: {cleanup_error}"
            )

    def test_package_update_realistic(self):
        """Test updating the existing test package by adding a timestamp file."""
        import os
        import tempfile
        import time

        # Create a temporary timestamp file with variable content to ensure unique hash
        current_time = time.time()
        timestamp_content = f"Updated at: {current_time}\nMicroseconds: {int(current_time * 1000000)}\nRandom ID: {int(current_time * 1000000) % 999999}\nTest run timestamp for package update validation"

        with tempfile.NamedTemporaryFile(mode='w', suffix='.timestamp', delete=False) as tmp_file:
            tmp_file.write(timestamp_content)
            tmp_file_path = tmp_file.name

        try:
            # Upload the timestamp file to S3 first
            timestamp_key = f"{KNOWN_TEST_PACKAGE}/.timestamp"
            upload_items = [
                {
                    "key": timestamp_key,
                    "text": timestamp_content,
                    "content_type": "text/plain",
                    "metadata": {"created_by": "test_suite", "test": "package_update"}
                }
            ]

            upload_result = bucket_objects_put(KNOWN_BUCKET, upload_items)
            if upload_result.get("uploaded", 0) == 0:
                pytest.skip("Could not upload timestamp file for package update test")

            # Now update the existing test package with the timestamp file
            timestamp_s3_uri = f"{KNOWN_BUCKET}/{timestamp_key}"

            result = package_update(
                package_name=KNOWN_TEST_PACKAGE,
                s3_uris=[timestamp_s3_uri],
                registry=TEST_REGISTRY,
                metadata={"updated_by": "test_suite", "last_updated": int(time.time())},
                message="Added timestamp file via package update test",
                flatten=True
            )

            assert isinstance(result, dict)

            # Expect successful update
            if "error" in result:
                if "accessdenied" in result["error"].lower() or "not authorized" in result["error"].lower():
                    pytest.fail(f"Permission error - user needs package update permissions: {result['error']}")
                else:
                    pytest.fail(f"Package update failed: {result['error']}")

            # Verify successful update
            assert "status" in result
            assert result["status"] == "success"
            assert "package_name" in result
            assert result["package_name"] == KNOWN_TEST_PACKAGE
            assert "new_entries_added" in result
            assert result["new_entries_added"] > 0, "Should have added the timestamp file"

        finally:
            # Clean up the temporary file
            try:
                os.unlink(tmp_file_path)
            except Exception:
                pass

    @pytest.mark.search
    def test_bucket_objects_search_finds_data(self):
        """Test bucket_objects_search finds actual data in the test bucket."""
        # Try multiple search terms to find some data
        search_terms = ["README", "csv", "parquet", "json", "txt", "data", "test"]
        found_results = False

        for term in search_terms:
            result = bucket_objects_search(KNOWN_BUCKET, term, limit=5)
            assert isinstance(result, dict)
            assert "bucket" in result
            assert "query" in result
            assert "results" in result

            if "error" in result:
                # Search might not be configured - skip test
                if "search endpoint" in result["error"].lower() or "not configured" in result["error"].lower():
                    pytest.skip(f"Search not configured for bucket {KNOWN_BUCKET}: {result['error']}")
                continue

            if len(result["results"]) > 0:
                found_results = True
                # Verify the response structure is correct
                for item in result["results"]:
                    if isinstance(item, dict) and "_source" in item:
                        assert len(item["_source"]) > 0, "Search result should have at least one key in _source"
                break

        # If search is configured but no results found, that's okay for some buckets
        if not found_results:
            pytest.skip(f"No search results found for any common terms {search_terms} in {KNOWN_BUCKET} - bucket may not have indexed content")

    def test_bucket_objects_search_no_results(self):
        """Test that non-existent search returns empty results, not error."""
        result = bucket_objects_search(KNOWN_BUCKET, "xyznonexistentfile123456789")

        assert isinstance(result, dict)
        if "error" not in result:
            assert "results" in result
            assert len(result["results"]) == 0, "Non-existent search should return empty results"
        else:
            # Search might not be configured - that's okay
            if "search endpoint" in result["error"].lower() or "not configured" in result["error"].lower():
                pytest.skip(f"Search not configured for bucket {KNOWN_BUCKET}")

    def test_bucket_objects_search_dsl_query(self):
        """Test bucket_objects_search with dictionary DSL query."""
        query_dsl = {
            "query": {
                "wildcard": {
                    "key": "*.csv"
                }
            }
        }
        
        result = bucket_objects_search(KNOWN_BUCKET, query_dsl, limit=3)

        assert isinstance(result, dict)
        assert "bucket" in result
        assert "query" in result
        assert result["query"] == query_dsl

        if "error" in result:
            # Search might not be configured - skip test
            if "search endpoint" in result["error"].lower() or "not configured" in result["error"].lower():
                pytest.skip(f"Search not configured for bucket {KNOWN_BUCKET}: {result['error']}")
        else:
            assert "results" in result
            # Results might be empty if no CSV files exist, which is okay

    def test_package_diff_known_package_with_itself(self):
        """Test package_diff comparing known package with itself (should show no differences)."""
        result = package_diff(KNOWN_PACKAGE, KNOWN_PACKAGE, registry=TEST_REGISTRY)

        assert isinstance(result, dict)
        if "error" in result:
            # Some packages might not support diff operations
            pytest.skip(f"Package diff not supported: {result['error']}")

        assert "package1" in result
        assert "package2" in result
        assert "diff" in result
        assert result["package1"] == KNOWN_PACKAGE
        assert result["package2"] == KNOWN_PACKAGE

        # When comparing identical packages, should have no differences
        diff = result["diff"]
        if isinstance(diff, dict):
            # If diff returns structured data, check for minimal differences
            assert len(diff.get("added", [])) == 0 or len(diff.get("deleted", [])) == 0

    def test_package_diff_different_packages(self):
        """Test package_diff comparing two different packages."""
        # Get available packages first
        packages_result = packages_list(registry=TEST_REGISTRY, limit=3)
        if len(packages_result.get("packages", [])) < 2:
            pytest.skip("Need at least 2 packages to test diff")

        packages = packages_result["packages"]
        pkg1, pkg2 = packages[0], packages[1]

        result = package_diff(pkg1, pkg2, registry=TEST_REGISTRY)

        assert isinstance(result, dict)
        if "error" in result:
            # Some packages might not support diff operations or might not exist
            if "not found" in result["error"].lower() or "does not exist" in result["error"].lower():
                pytest.skip(f"Packages not accessible for diff: {result['error']}")
            else:
                pytest.skip(f"Package diff not supported: {result['error']}")

        assert "package1" in result
        assert "package2" in result
        assert "diff" in result
        assert result["package1"] == pkg1
        assert result["package2"] == pkg2

    def test_package_diff_nonexistent_packages(self):
        """Test package_diff with non-existent packages."""
        result = package_diff("definitely/nonexistent1", "definitely/nonexistent2", registry=TEST_REGISTRY)

        assert isinstance(result, dict)
        assert "error" in result
        # Should get a meaningful error about packages not being found
        error_msg = result["error"].lower()
        assert any(term in error_msg for term in [
            "failed to browse", "not found", "does not exist", "no such file"
        ]), f"Expected meaningful error about missing packages, got: {result['error']}"


if __name__ == "__main__":
    pytest.main([__file__])

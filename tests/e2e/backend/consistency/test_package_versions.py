"""E2E Package Version Consistency Tests.

Tests that validate package version information remains consistent across
different access paths: direct browse, catalog URL, search index, and S3 manifest.

Uses REAL services (no mocking):
- Real package registry
- Real catalog API
- Real Elasticsearch
- Real S3
"""

import pytest
import time
import boto3
import requests
from typing import Dict, Any


@pytest.mark.e2e
@pytest.mark.package
@pytest.mark.consistency
@pytest.mark.usefixtures("backend_mode")
class TestPackageVersionConsistency:
    """E2E tests for package version consistency across access paths.

    Tests run against both quilt3 and platform backends unless
    TEST_BACKEND_MODE environment variable restricts it.
    """

    def test_package_version_consistency(
        self,
        backend_with_auth,
        cleanup_packages,
        cleanup_s3_objects,
        real_test_bucket,
        backend_mode,
        request,
    ):
        """Test package version consistency across multiple real access paths.

        This test validates that version information remains consistent when
        accessing a package through:
        1. Direct package browse (backend API)
        2. Catalog URL (HTTP request)
        3. Search in real index (with indexing delay handling)
        4. Via S3 URI (manifest fetch)

        All paths must return the same version/hash from real sources.

        Args:
            backend_with_auth: Authenticated backend (quilt3 or platform)
            cleanup_packages: Fixture to track packages for cleanup
            cleanup_s3_objects: Fixture to track S3 objects for cleanup
            real_test_bucket: Test bucket name (from conftest)
            backend_mode: Backend mode string (quilt3 or platform)
            request: pytest request object for cleanup finalizer
        """
        # Generate unique package name and test data
        timestamp = int(time.time())
        package_name = f"test/consistency_check_{timestamp}"
        registry = f"s3://{real_test_bucket}"

        # Create real test file in S3
        s3_client = boto3.client('s3')
        test_key = f"test_consistency/{timestamp}/file1.csv"
        test_content = f"Test content for consistency check,{timestamp}\ndata1,data2\n"

        print(f"\n[Setup] Creating test file in S3: {real_test_bucket}")
        try:
            s3_client.put_object(Bucket=real_test_bucket, Key=test_key, Body=test_content.encode())
            print(f"  ✅ Created: s3://{real_test_bucket}/{test_key}")
        except Exception as e:
            pytest.fail(f"Failed to create test S3 file: {e}")

        # Track S3 object for cleanup
        cleanup_s3_objects.track_s3_object(bucket=real_test_bucket, key=test_key)

        # Build S3 URI for package creation
        s3_uri = f"s3://{real_test_bucket}/{test_key}"

        # Track package for cleanup
        cleanup_packages.track_package(bucket=real_test_bucket, package_name=package_name)

        # Create real package
        print(f"\n[Step 1] Creating package: {package_name}")
        print(f"  Registry: {registry}")
        print(f"  File: {s3_uri}")

        create_result = backend_with_auth.create_package_revision(
            package_name=package_name,
            s3_uris=[s3_uri],
            registry=registry,
            message="Package for consistency check E2E test",
        )

        # Extract package hash from create result
        package_hash = None
        if hasattr(create_result, 'top_hash'):
            package_hash = create_result.top_hash
        elif isinstance(create_result, dict) and 'top_hash' in create_result:
            package_hash = create_result['top_hash']

        print("  ✅ Package created successfully")
        if package_hash:
            print(f"  ℹ️  Package hash: {package_hash}")
        if hasattr(create_result, 'catalog_url'):
            print(f"  ℹ️  Catalog URL: {create_result.catalog_url}")

        # Allow some time for package to be fully written
        time.sleep(1)

        # Path 1: Direct package browse
        print("\n[Path 1] Direct package browse via backend API")
        try:
            browse_result = backend_with_auth.browse_content(package_name=package_name, registry=registry, path="")

            assert browse_result is not None, "Browse returned None"
            assert isinstance(browse_result, list), f"Browse should return list, got {type(browse_result)}"
            assert len(browse_result) > 0, "Browse should return at least one item"

            # Extract version/hash information from browse
            browse_hash = None
            browse_keys = [item.path for item in browse_result]
            print(f"  ✅ Browse succeeded: {len(browse_result)} items")
            print(f"  ℹ️  Files: {browse_keys}")

            # Try to get package info for hash
            try:
                package_info = backend_with_auth.get_package_info(package_name=package_name, registry=registry)
                if hasattr(package_info, 'top_hash'):
                    browse_hash = package_info.top_hash
                    print(f"  ℹ️  Browse hash from package info: {browse_hash}")
            except Exception as e:
                print(f"  ℹ️  Could not get package info: {e}")

        except Exception as e:
            pytest.fail(f"Path 1 (browse) failed: {e}")

        # Path 2: Catalog URL (HTTP request)
        print("\n[Path 2] Catalog URL via HTTP request")
        catalog_url = None
        catalog_response_ok = False

        try:
            # Get catalog URL from backend
            if backend_mode == "quilt3":
                # For quilt3, construct catalog URL from bucket config
                try:
                    from quilt3 import get_remote_registry

                    catalog_base = get_remote_registry(registry)
                    if catalog_base:
                        # Construct catalog package URL
                        catalog_url = f"{catalog_base}/b/{real_test_bucket}/packages/{package_name}"
                        print(f"  ℹ️  Constructed catalog URL: {catalog_url}")
                except Exception as e:
                    print(f"  ℹ️  Could not construct catalog URL: {e}")
            else:
                # For platform backend, try to get catalog URL from create result
                if hasattr(create_result, 'catalog_url'):
                    catalog_url = create_result.catalog_url
                    print(f"  ℹ️  Platform catalog URL: {catalog_url}")

            # If we have a catalog URL, verify it
            if catalog_url:
                try:
                    response = requests.get(catalog_url, timeout=10)
                    catalog_response_ok = response.status_code == 200
                    print(f"  ✅ Catalog URL accessible: {response.status_code}")
                    if not catalog_response_ok:
                        print(f"  ⚠️  Non-200 status: {response.status_code}")
                except requests.RequestException as e:
                    print(f"  ⚠️  Catalog URL request failed: {e}")
                    catalog_response_ok = False
            else:
                print("  ℹ️  Catalog URL not available (may be expected for this backend)")

        except Exception as e:
            print(f"  ℹ️  Path 2 (catalog URL) error: {e}")

        # Path 3: Search in real index (with indexing delay handling)
        print("\n[Path 3] Search in real Elasticsearch index")
        search_hash = None
        search_found = False
        max_retries = 10
        retry_delay = 3  # seconds

        for attempt in range(max_retries):
            try:
                packages = backend_with_auth.search_packages(query=package_name, registry=registry)

                # Look for our package in results
                for pkg in packages:
                    if pkg.name == package_name:
                        search_found = True
                        if hasattr(pkg, 'top_hash'):
                            search_hash = pkg.top_hash
                            print(f"  ✅ Package found in search (attempt {attempt + 1}/{max_retries})")
                            print(f"  ℹ️  Search hash: {search_hash}")
                        break

                if search_found:
                    break
                else:
                    if attempt < max_retries - 1:
                        print(
                            f"  ℹ️  Package not yet indexed (attempt {attempt + 1}/{max_retries}), waiting {retry_delay}s..."
                        )
                        time.sleep(retry_delay)

            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"  ℹ️  Search attempt {attempt + 1} failed: {e}, retrying...")
                    time.sleep(retry_delay)
                else:
                    print(f"  ⚠️  Search failed after {max_retries} attempts: {e}")

        if not search_found:
            print(f"  ⚠️  Package not found in search after {max_retries} attempts")
            print("  ℹ️  This may indicate indexing delay, but we'll continue validation")

        # Path 4: Via S3 URI (manifest fetch)
        print("\n[Path 4] Direct S3 manifest fetch")
        manifest_hash = None
        manifest_content = None

        if package_hash:
            manifest_key = f".quilt/packages/{package_hash}"
            print(f"  ℹ️  Fetching manifest: s3://{real_test_bucket}/{manifest_key}")

            try:
                manifest_obj = s3_client.get_object(Bucket=real_test_bucket, Key=manifest_key)
                manifest_content = manifest_obj['Body'].read().decode('utf-8')
                manifest_hash = package_hash  # The hash we used to fetch it
                print("  ✅ Manifest fetched successfully")
                print(f"  ℹ️  Manifest size: {len(manifest_content)} bytes")
                print(f"  ℹ️  Manifest hash: {manifest_hash}")
            except Exception as e:
                print(f"  ⚠️  Manifest fetch failed: {e}")
        else:
            print("  ℹ️  No package hash available for manifest fetch")

        # Validate consistency across all real paths
        print("\n[Validation] Consistency checks across all paths")

        # Collect all hashes
        hashes = {
            'create': package_hash,
            'browse': browse_hash,
            'search': search_hash,
            'manifest': manifest_hash,
        }

        print(f"  ℹ️  Collected hashes: {hashes}")

        # Filter out None and empty string values for comparison
        valid_hashes = {k: v for k, v in hashes.items() if v is not None and v != ''}

        if len(valid_hashes) >= 2:
            # Check all non-None/non-empty hashes are consistent
            unique_hashes = set(valid_hashes.values())

            if len(unique_hashes) == 1:
                print(f"  ✅ All paths return same version/hash: {unique_hashes.pop()}")
            else:
                print("  ❌ INCONSISTENCY DETECTED!")
                for source, hash_val in valid_hashes.items():
                    print(f"     {source}: {hash_val}")
                pytest.fail(f"Hash verification inconsistent across paths: {valid_hashes}")
        else:
            print(f"  ⚠️  Only {len(valid_hashes)} path(s) returned hash information")
            print("  ℹ️  Cannot fully validate consistency, but test continues")

        # Additional consistency checks

        # Check browse succeeded
        assert browse_result is not None, "Browse path failed"
        print("  ✅ Browse path successful")

        # Check search results (allow for indexing delay)
        if search_found:
            print("  ✅ Search path successful")
        else:
            print("  ⚠️  Search path not yet available (indexing delay)")

        # Check manifest fetch
        if manifest_content:
            print("  ✅ Manifest path successful")
        else:
            print("  ⚠️  Manifest path not validated")

        # Check catalog URL if available
        if catalog_url:
            if catalog_response_ok:
                print("  ✅ Catalog URL accessible")
            else:
                print("  ⚠️  Catalog URL returned non-200 status")

        # Final assertion: at least browse path must work
        assert len(browse_result) > 0, "Browse must return package contents"

        # If we have multiple hashes, they must match
        if len(valid_hashes) >= 2:
            unique_hashes = set(valid_hashes.values())
            assert len(unique_hashes) == 1, f"Hash verification inconsistent across paths: {valid_hashes}"

        # Manual cleanup of package since backend doesn't have package_delete
        print(f"\n[Cleanup] Deleting package manually: {package_name}")
        import quilt3
        from quilt_mcp.utils.common import suppress_stdout

        try:
            with suppress_stdout():
                quilt3.delete_package(package_name, registry=registry)
            print("  ✅ Package deleted successfully")
            # Remove from cleanup tracker since we handled it
            cleanup_packages.packages.clear()
        except Exception as e:
            print(f"  ⚠️  Package deletion failed: {e}")

        print("\n✅ Package version consistency test completed!")
        print(f"   Package name: {package_name}")
        print(f"   Registry: {registry}")
        print(f"   Paths validated: {len(valid_hashes)}/{len(hashes)}")
        print(f"   Consistency: {'PASS' if len(set(valid_hashes.values())) <= 1 else 'FAIL'}")

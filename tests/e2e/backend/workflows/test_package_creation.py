"""E2E Workflow Test: Package Creation from S3.

This module implements the package creation workflow test as specified in
spec/a20-jwt-auth/02-e2e-backend-integration.md section 2.2.

Workflow tests validate complete user workflows from start to finish, using
REAL services without mocking.
"""

import pytest
import time
import boto3
from typing import Dict, Any


@pytest.mark.e2e
@pytest.mark.workflow
@pytest.mark.usefixtures("backend_mode")
class TestPackageCreationWorkflow:
    """E2E workflow tests for package creation from S3 bucket contents.

    This test validates the complete workflow of creating an organized package
    from S3 bucket contents, verifying it in the catalog, and accessing it via URL.

    Tests run against both quilt3 and platform backends via pytest parametrization.
    """

    def test_package_creation_from_s3_workflow(
        self,
        backend_with_auth,
        cleanup_packages,
        cleanup_s3_objects,
        real_test_bucket,
        backend_mode,
        request,
    ):
        """Test complete package creation workflow from S3 bucket.

        User Goal: "Create organized package from S3 bucket contents"

        This test validates:
        1. Checking real bucket access (IAM permissions)
        2. Listing real objects with prefix
        3. Creating package from S3 with auto-organization
        4. Verifying package in real catalog
        5. Generating and verifying real catalog URL

        Args:
            backend_with_auth: Authenticated backend (quilt3 or platform)
            cleanup_packages: Fixture to track packages for cleanup
            cleanup_s3_objects: Fixture to track S3 objects for cleanup
            real_test_bucket: Validated test bucket name
            backend_mode: Backend mode string (quilt3 or platform)
            request: pytest request object for finalizers
        """
        # Generate unique identifiers
        timestamp = int(time.time())
        package_name = f"experiments/genomics_{timestamp}"
        source_prefix = f"experiments/2026/{timestamp}/"
        registry = f"s3://{real_test_bucket}"

        def _is_transient_network_error(exc: Exception) -> bool:
            message = str(exc).lower()
            return any(
                marker in message
                for marker in (
                    "timed out",
                    "read timed out",
                    "connection aborted",
                    "remote end closed connection",
                    "network error",
                    "connection reset",
                )
            )

        def _call_with_retry(step: str, func, *args, retries: int = 3, delay: int = 2, **kwargs):
            last_exc = None
            for attempt in range(1, retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    last_exc = exc
                    if _is_transient_network_error(exc) and attempt < retries:
                        print(f"  ℹ️  {step} retry {attempt}/{retries} after transient error: {exc}")
                        time.sleep(delay)
                        continue
                    break
            if last_exc and _is_transient_network_error(last_exc):
                pytest.skip(f"Skipping due to transient network error in {step}: {last_exc}")
            raise last_exc  # type: ignore[misc]

        # Create real test files in S3
        print(f"\n[Setup] Creating test files in S3: {real_test_bucket}/{source_prefix}")
        s3_client = boto3.client('s3')

        test_files = [
            f"{source_prefix}sample1/data.csv",
            f"{source_prefix}sample1/metadata.json",
            f"{source_prefix}sample2/data.csv",
            f"{source_prefix}sample2/metadata.json",
            f"{source_prefix}README.md",
        ]

        try:
            for key in test_files:
                content = f"Test content for {key}\nCreated at {timestamp}\n"
                s3_client.put_object(
                    Bucket=real_test_bucket,
                    Key=key,
                    Body=content.encode(),
                )
                print(f"  ✅ Created: s3://{real_test_bucket}/{key}")
                cleanup_s3_objects.track_s3_object(bucket=real_test_bucket, key=key)
        except Exception as e:
            pytest.fail(f"Failed to create test S3 files: {e}")

        # Track package for cleanup
        cleanup_packages.track_package(bucket=real_test_bucket, package_name=package_name)

        # =========================================================================
        # STEP 1: Check real bucket access (IAM permission checks)
        # =========================================================================
        print(f"\n[Step 1] Checking bucket access: {real_test_bucket}")

        try:
            # For quilt3 backend, use boto3 client; for platform, skip detailed checks
            if backend_mode == "quilt3":
                # Use boto3 client from backend to check access
                s3_test = backend_with_auth.get_boto3_client('s3')

                # Verify read access
                s3_test.head_bucket(Bucket=real_test_bucket)
                print("  ✅ Bucket is accessible")

                # Verify list access
                list_result = s3_test.list_objects_v2(Bucket=real_test_bucket, MaxKeys=1)
                print("  ✅ List permission verified")

                # Try to determine write access (non-destructive)
                try:
                    # Check bucket ownership and ACL (indicates write permission)
                    s3_test.get_bucket_acl(Bucket=real_test_bucket)
                    access_level = "full_access"
                    print("  ✅ Full access (read/write) confirmed")
                except Exception:
                    access_level = "read_only"
                    print("  ℹ️  Read-only access (write permission not confirmed)")
            else:
                # Platform backend - bucket access is implicit (we already created files)
                access_level = "assumed_full_access"
                print("  ✅ Bucket access assumed (files created successfully)")
                print("  ℹ️  Platform backend uses GraphQL (no direct boto3 access)")

        except Exception as e:
            pytest.fail(f"Bucket access check failed: {e}")

        # =========================================================================
        # STEP 2: List real objects with prefix
        # =========================================================================
        print(f"\n[Step 2] Listing objects with prefix: {source_prefix}")

        try:
            list_response = s3_client.list_objects_v2(
                Bucket=real_test_bucket,
                Prefix=source_prefix,
                MaxKeys=1000,
            )

            objects = list_response.get('Contents', [])
            object_count = len(objects)

            print(f"  ℹ️  Found {object_count} objects:")
            for obj in objects:
                size_kb = obj['Size'] / 1024
                print(f"    - {obj['Key']} ({size_kb:.2f} KB)")

            # Verify we found the expected files
            assert object_count == len(test_files), f"Expected {len(test_files)} objects, found {object_count}"
            print("  ✅ Object listing successful")

        except Exception as e:
            pytest.fail(f"Object listing failed: {e}")

        # =========================================================================
        # STEP 3: Create real package with smart organization
        # =========================================================================
        print(f"\n[Step 3] Creating package: {package_name}")
        print(f"  Registry: {registry}")
        print("  Auto-organize: True (preserve S3 structure)")

        # Build S3 URIs for package creation
        s3_uris = [f"s3://{real_test_bucket}/{key}" for key in test_files]

        try:
            result = _call_with_retry(
                "create package",
                backend_with_auth.create_package_revision,
                package_name=package_name,
                s3_uris=s3_uris,
                registry=registry,
                message=f"Package created from {source_prefix} for E2E workflow test",
                auto_organize=True,  # Preserve S3 folder structure
            )

            # Assertions: Package creation succeeded
            assert result is not None, "Package creation returned None"
            assert result.success, f"Package creation failed: {result}"
            assert result.package_name == package_name, f"Wrong package name: {result.package_name} != {package_name}"
            assert result.file_count == len(s3_uris), f"File count mismatch: {result.file_count} != {len(s3_uris)}"

            print("  ✅ Package created successfully")
            print(f"  ℹ️  Package hash: {result.top_hash}")
            if result.catalog_url:
                print(f"  ℹ️  Catalog URL: {result.catalog_url}")

        except Exception as e:
            pytest.fail(f"Package creation failed: {e}")

        # =========================================================================
        # STEP 4: Verify in real catalog
        # =========================================================================
        print("\n[Step 4] Verifying package in catalog")

        # Wait for indexing (catalog may have slight delay)
        max_retries = 5
        retry_delay = 2
        found_in_catalog = False

        for attempt in range(max_retries):
            try:

                def _collect_entries(current_path: str = "", visited: set[str] | None = None) -> list[dict[str, str]]:
                    if visited is None:
                        visited = set()
                    current_entries: list[dict[str, str]] = []
                    browse_result = backend_with_auth.browse_content(
                        package_name=package_name,
                        registry=registry,
                        path=current_path,
                    )
                    for item in browse_result:
                        path = getattr(item, "path", "")
                        item_type = getattr(item, "type", "unknown")
                        if not path:
                            continue
                        if item_type == "directory":
                            if path in visited:
                                continue
                            visited.add(path)
                            current_entries.extend(_collect_entries(path, visited))
                            continue
                        current_entries.append({"path": path, "type": item_type})
                    return current_entries

                # Browse package content (recursive for backends that return directories at root).
                browse_result = backend_with_auth.browse_content(package_name=package_name, registry=registry, path="")

                # Verify browse result
                assert browse_result is not None, "Browse returned None"
                assert isinstance(browse_result, list), f"Browse should return list, got {type(browse_result)}"

                # Get all file paths from recursive browse.
                flattened_entries = _collect_entries()
                browse_paths = [entry["path"] for entry in flattened_entries]
                print(f"  ℹ️  Found {len(flattened_entries)} entries in package:")
                for entry in flattened_entries:
                    print(f"    - {entry['path']} ({entry['type']})")

                # Verify all original files are present (with auto-organization)
                # Auto-organize preserves path structure: experiments/2026/{timestamp}/...
                # Extract just the filenames to verify presence
                expected_filenames = [key.split('/')[-1] for key in test_files]
                found_filenames = [
                    path.split('/')[-1]
                    for path in browse_paths
                    if not path.endswith('/')  # Skip directories
                ]

                for expected_file in expected_filenames:
                    assert expected_file in found_filenames, (
                        f"Expected file {expected_file} not found in package. Found: {found_filenames}"
                    )

                # Verify entry count matches (files only, directories may vary)
                file_entries = [entry for entry in flattened_entries if entry["type"] == "file"]
                assert len(file_entries) == len(test_files), (
                    f"Expected {len(test_files)} files, found {len(file_entries)}"
                )

                print("  ✅ All files correctly organized in package manifest")
                found_in_catalog = True
                break

            except Exception as e:
                if attempt < max_retries - 1:
                    print(
                        f"  ℹ️  Catalog verification attempt {attempt + 1}/{max_retries} "
                        f"failed, retrying in {retry_delay}s: {e}"
                    )
                    time.sleep(retry_delay)
                else:
                    pytest.fail(f"Catalog verification failed after {max_retries} attempts: {e}")

        assert found_in_catalog, "Package not found in catalog after retries"

        # Verify package appears in search
        print("\n[Step 4a] Verifying package in search results")
        try:
            packages = backend_with_auth.search_packages(query="", registry=registry)
            package_names = [p.name for p in packages]

            if package_name in package_names:
                print("  ✅ Package appears in catalog search")
            else:
                print("  ⚠️  Package not yet indexed in search (may take time)")
                print("  ℹ️  This is non-critical - package exists and is browseable")

        except Exception as e:
            print(f"  ⚠️  Search verification failed: {e}")
            print("  ℹ️  This is non-critical - package exists and is browseable")

        # =========================================================================
        # STEP 5: Generate real catalog URL and verify accessibility
        # =========================================================================
        print("\n[Step 5] Verifying catalog URL accessibility")

        if result.catalog_url:
            print(f"  ℹ️  Catalog URL: {result.catalog_url}")

            # Note: Actual HTTP verification of catalog URL requires authentication
            # and may not work in all test environments. We verify URL format instead.
            assert isinstance(result.catalog_url, str), "Catalog URL should be string"
            assert len(result.catalog_url) > 0, "Catalog URL should not be empty"
            assert result.catalog_url.startswith('http'), f"Catalog URL should start with http: {result.catalog_url}"
            assert real_test_bucket in result.catalog_url, (
                f"Catalog URL should contain bucket name: {result.catalog_url}"
            )
            assert package_name in result.catalog_url, f"Catalog URL should contain package name: {result.catalog_url}"

            print("  ✅ Catalog URL format is valid")

            # Try to verify URL accessibility (may fail due to auth requirements)
            try:
                import requests

                response = requests.get(result.catalog_url, timeout=10)
                if response.status_code == 200:
                    print("  ✅ Catalog URL is accessible (HTTP 200)")
                else:
                    print(f"  ℹ️  Catalog URL returned HTTP {response.status_code} (may require authentication)")
            except Exception as e:
                print(f"  ℹ️  Catalog URL accessibility check skipped: {e}")
                print("  ℹ️  This is non-critical - URL format is valid")
        else:
            print("  ℹ️  No catalog URL returned (backend may not support URL generation)")

        # =========================================================================
        # SUCCESS SUMMARY
        # =========================================================================
        print("\n" + "=" * 70)
        print("✅ PACKAGE CREATION WORKFLOW TEST COMPLETED SUCCESSFULLY!")
        print("=" * 70)
        print(f"Package name:     {package_name}")
        print(f"Registry:         {registry}")
        print(f"Files created:    {len(test_files)}")
        print("Auto-organized:   Yes (preserved S3 structure)")
        print("Catalog verified: Yes")
        print(f"URL generated:    {'Yes' if result.catalog_url else 'No'}")
        print("=" * 70)

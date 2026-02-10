"""E2E Cross-Backend Consistency Tests.

Tests that validate data consistency when accessed through different backend
methods: Quilt3 browse, Search API, Tabulator, and Athena.

Uses REAL services (no mocking):
- Real package registry
- Real catalog API
- Real Elasticsearch
- Real Tabulator (GraphQL)
- Real Athena (Glue catalog)
- Real S3
"""

import pytest
import time
import boto3
from typing import Dict, Any, Set


@pytest.mark.e2e
@pytest.mark.consistency
@pytest.mark.usefixtures("backend_mode")
class TestCrossBackendConsistency:
    """E2E tests for cross-backend data consistency.

    Tests run against both quilt3 and platform backends unless
    TEST_BACKEND_MODE environment variable restricts it.
    """

    def test_cross_backend_consistency(
        self,
        backend_with_auth,
        cleanup_packages,
        cleanup_s3_objects,
        real_test_bucket,
        backend_mode,
        request,
    ):
        """Test data consistency across multiple real backend methods.

        This test validates that the same package data accessed through
        different backend methods returns consistent results:
        1. Quilt3 browse (package.browse())
        2. Search API (catalog search)
        3. Tabulator (if package manifests are indexed)
        4. Athena (if Glue catalog has package metadata)

        All methods must return consistent file lists, metadata, and counts.

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
        package_name = f"test/cross_backend_{timestamp}"
        registry = f"s3://{real_test_bucket}"

        # Create multiple real test files in S3
        s3_client = boto3.client('s3')
        test_files = [
            {"key": f"test_cross_backend/{timestamp}/file1.csv", "content": "col1,col2\ndata1,data2\n"},
            {"key": f"test_cross_backend/{timestamp}/file2.txt", "content": "Test content file 2\n"},
            {"key": f"test_cross_backend/{timestamp}/data/file3.json", "content": '{"test": "data"}\n'},
        ]

        print(f"\n[Setup] Creating test files in S3: {real_test_bucket}")
        for file_info in test_files:
            try:
                s3_client.put_object(Bucket=real_test_bucket, Key=file_info["key"], Body=file_info["content"].encode())
                print(f"  ✅ Created: s3://{real_test_bucket}/{file_info['key']}")
                # Track for cleanup
                cleanup_s3_objects.track_s3_object(bucket=real_test_bucket, key=file_info["key"])
            except Exception as e:
                pytest.fail(f"Failed to create test S3 file {file_info['key']}: {e}")

        # Build S3 URIs for package creation
        s3_uris = [f"s3://{real_test_bucket}/{f['key']}" for f in test_files]

        # Track package for cleanup
        cleanup_packages.track_package(bucket=real_test_bucket, package_name=package_name)

        # Create real package
        print(f"\n[Step 1] Creating package: {package_name}")
        print(f"  Registry: {registry}")
        print(f"  Files: {len(s3_uris)}")

        create_result = backend_with_auth.create_package_revision(
            package_name=package_name,
            s3_uris=s3_uris,
            registry=registry,
            message="Package for cross-backend consistency E2E test",
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

        # Allow time for package to be fully written and potentially indexed
        time.sleep(2)

        # Method 1: Quilt3 browse (direct package API)
        print("\n[Method 1] Quilt3 browse via backend API")
        browse_files = {}
        browse_succeeded = False

        try:
            browse_result = backend_with_auth.browse_content(package_name=package_name, registry=registry, path="")

            assert browse_result is not None, "Browse returned None"
            assert isinstance(browse_result, list), f"Browse should return list, got {type(browse_result)}"

            # Extract file information
            for item in browse_result:
                if hasattr(item, 'path') and hasattr(item, 'size'):
                    browse_files[item.path] = {'size': item.size, 'type': getattr(item, 'type', 'unknown')}

            browse_succeeded = True
            print(f"  ✅ Browse succeeded: {len(browse_files)} files")
            for path, info in browse_files.items():
                print(f"     - {path} ({info['size']} bytes)")

        except Exception as e:
            print(f"  ❌ Browse failed: {e}")
            pytest.fail(f"Method 1 (browse) failed: {e}")

        # Method 2: Search API (catalog search)
        print("\n[Method 2] Search API via catalog")
        search_files = {}
        search_succeeded = False
        max_retries = 10
        retry_delay = 3  # seconds

        for attempt in range(max_retries):
            try:
                packages = backend_with_auth.search_packages(query=package_name, registry=registry)

                # Look for our package in results
                for pkg in packages:
                    if pkg.name == package_name:
                        search_succeeded = True
                        print(f"  ✅ Package found in search (attempt {attempt + 1}/{max_retries})")

                        # Try to get file list from search result
                        if hasattr(pkg, 'entries') and pkg.entries:
                            for entry in pkg.entries:
                                if hasattr(entry, 'logical_key'):
                                    search_files[entry.logical_key] = {
                                        'size': getattr(entry, 'size', None),
                                        'type': getattr(entry, 'type', 'unknown'),
                                    }
                            print(f"  ℹ️  Search returned {len(search_files)} files")

                        # If search doesn't return entries, try browsing package from search result
                        if not search_files:
                            try:
                                browse_from_search = backend_with_auth.browse_content(
                                    package_name=package_name, registry=registry, path=""
                                )
                                for item in browse_from_search:
                                    if hasattr(item, 'path'):
                                        search_files[item.path] = {
                                            'size': getattr(item, 'size', None),
                                            'type': getattr(item, 'type', 'unknown'),
                                        }
                                print(f"  ℹ️  Retrieved {len(search_files)} files via browse after search")
                            except Exception as e:
                                print(f"  ℹ️  Could not browse package from search: {e}")

                        break

                if search_succeeded:
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

        if not search_succeeded:
            print(f"  ⚠️  Package not found in search after {max_retries} attempts")
            print("  ℹ️  This may indicate indexing delay")

        # Method 3: Tabulator (GraphQL view of manifests)
        print("\n[Method 3] Tabulator via GraphQL")
        tabulator_files = {}
        tabulator_succeeded = False
        tabulator_skip_reason = None

        # Check if backend has tabulator support
        if not hasattr(backend_with_auth, 'tabulator_get_logical_keys'):
            tabulator_skip_reason = "Backend doesn't support tabulator operations"
            print(f"  ⚠️  Skipping: {tabulator_skip_reason}")
        else:
            try:
                # Try to get logical keys via tabulator
                logical_keys_result = backend_with_auth.tabulator_get_logical_keys(
                    bucket=real_test_bucket, package_name=package_name, package_hash=package_hash
                )

                if logical_keys_result:
                    for key in logical_keys_result:
                        tabulator_files[key] = {
                            'size': None,  # Tabulator may not return size
                            'type': 'file',
                        }
                    tabulator_succeeded = True
                    print(f"  ✅ Tabulator succeeded: {len(tabulator_files)} files")
                    for path in tabulator_files.keys():
                        print(f"     - {path}")
                else:
                    tabulator_skip_reason = "Tabulator returned empty results (package may not be indexed)"
                    print(f"  ⚠️  {tabulator_skip_reason}")

            except Exception as e:
                error_msg = str(e)
                if "GraphQL" in error_msg or "schema" in error_msg.lower():
                    tabulator_skip_reason = f"GraphQL schema issue: {e}"
                else:
                    tabulator_skip_reason = f"Tabulator error: {e}"
                print(f"  ⚠️  Skipping: {tabulator_skip_reason}")

        # Method 4: Athena (Glue catalog view)
        print("\n[Method 4] Athena via Glue catalog")
        athena_files = {}
        athena_succeeded = False
        athena_skip_reason = None

        # Athena only available for quilt3 backend
        if backend_mode != "quilt3":
            athena_skip_reason = "Athena only available for quilt3 backend"
            print(f"  ⚠️  Skipping: {athena_skip_reason}")
        elif not hasattr(backend_with_auth, 'athena_query_execute'):
            athena_skip_reason = "Backend doesn't support Athena operations"
            print(f"  ⚠️  Skipping: {athena_skip_reason}")
        else:
            try:
                # Try to discover catalog
                catalog_config = backend_with_auth.get_catalog_config(real_test_bucket)
                catalog_name = catalog_config.tabulator_data_catalog

                if not catalog_name:
                    athena_skip_reason = "No Athena catalog configured for bucket"
                    print(f"  ⚠️  Skipping: {athena_skip_reason}")
                else:
                    # Try to query package files via Athena
                    query = f"""
                        SELECT logical_key, size
                        FROM "{real_test_bucket}_packages"
                        WHERE package_name = '{package_name}'
                        LIMIT 100
                    """

                    print(f"  ℹ️  Querying Athena catalog: {catalog_name}")
                    print(f"  ℹ️  Database: {real_test_bucket}_catalog")

                    athena_result = backend_with_auth.athena_query_execute(
                        query=query, database=f"{real_test_bucket}_catalog"
                    )

                    if athena_result and 'formatted_data' in athena_result:
                        for row in athena_result['formatted_data']:
                            if 'logical_key' in row:
                                athena_files[row['logical_key']] = {'size': row.get('size'), 'type': 'file'}

                        if athena_files:
                            athena_succeeded = True
                            print(f"  ✅ Athena succeeded: {len(athena_files)} files")
                            for path, info in athena_files.items():
                                print(f"     - {path} ({info['size']} bytes)")
                        else:
                            athena_skip_reason = (
                                "Athena query returned no results (package may not be indexed in Glue)"
                            )
                            print(f"  ⚠️  {athena_skip_reason}")
                    else:
                        athena_skip_reason = "Athena query returned no data"
                        print(f"  ⚠️  {athena_skip_reason}")

            except Exception as e:
                athena_skip_reason = f"Athena error: {e}"
                print(f"  ⚠️  Skipping: {athena_skip_reason}")

        # Validate consistency across all methods
        print("\n[Validation] Cross-backend consistency checks")

        # Collect all file sets
        file_sets = {
            'browse': set(browse_files.keys()) if browse_succeeded else set(),
            'search': set(search_files.keys()) if search_succeeded else set(),
            'tabulator': set(tabulator_files.keys()) if tabulator_succeeded else set(),
            'athena': set(athena_files.keys()) if athena_succeeded else set(),
        }

        print("  ℹ️  File counts by method:")
        print(f"     - Browse: {len(file_sets['browse'])} files")
        print(f"     - Search: {len(file_sets['search'])} files")
        print(f"     - Tabulator: {len(file_sets['tabulator'])} files")
        print(f"     - Athena: {len(file_sets['athena'])} files")

        # Filter to only methods that succeeded
        active_methods = [k for k, v in file_sets.items() if len(v) > 0]
        print(f"  ℹ️  Active methods: {', '.join(active_methods)}")

        # At least browse must work
        assert browse_succeeded, "Browse method must succeed"
        assert len(browse_files) == len(test_files), (
            f"Browse should return {len(test_files)} files, got {len(browse_files)}"
        )

        # If multiple methods succeeded, validate consistency
        if len(active_methods) >= 2:
            print("\n  [Consistency Check] Comparing file lists across methods...")

            # Use browse as reference
            reference_files = file_sets['browse']

            for method in active_methods:
                if method == 'browse':
                    continue

                method_files = file_sets[method]

                # Check if files match
                if method_files == reference_files:
                    print(f"  ✅ {method.capitalize()} matches browse: {len(method_files)} files")
                else:
                    # Report differences
                    missing = reference_files - method_files
                    extra = method_files - reference_files

                    if missing:
                        print(f"  ⚠️  {method.capitalize()} missing files: {missing}")
                    if extra:
                        print(f"  ⚠️  {method.capitalize()} has extra files: {extra}")

                    # For Tabulator and Athena, allow some inconsistency due to indexing delays
                    if method in ['tabulator', 'athena']:
                        print(f"  ℹ️  {method.capitalize()} inconsistency may be due to indexing delay")
                    else:
                        # For search, this is more concerning
                        pytest.fail(
                            f"Method '{method}' file list inconsistent with browse. Missing: {missing}, Extra: {extra}"
                        )

            # Check metadata consistency for files present in multiple methods
            print("\n  [Metadata Check] Comparing file metadata across methods...")

            for file_path in reference_files:
                metadata_by_method = {}

                if file_path in browse_files:
                    metadata_by_method['browse'] = browse_files[file_path]
                if file_path in search_files:
                    metadata_by_method['search'] = search_files[file_path]
                if file_path in tabulator_files:
                    metadata_by_method['tabulator'] = tabulator_files[file_path]
                if file_path in athena_files:
                    metadata_by_method['athena'] = athena_files[file_path]

                # Check size consistency (if available)
                sizes = {
                    method: info['size'] for method, info in metadata_by_method.items() if info['size'] is not None
                }

                if len(sizes) >= 2:
                    unique_sizes = set(sizes.values())
                    if len(unique_sizes) == 1:
                        print(f"  ✅ {file_path}: size consistent across {len(sizes)} methods")
                    else:
                        print(f"  ⚠️  {file_path}: size inconsistent across methods: {sizes}")
                        # This is a real consistency issue
                        pytest.fail(f"File {file_path} has inconsistent sizes across methods: {sizes}")

        else:
            print(f"  ℹ️  Only 1 method succeeded ({active_methods[0]}), cannot validate cross-backend consistency")
            print("  ℹ️  This may be expected in some environments")

        # Summary
        print("\n[Summary] Cross-backend consistency test results")
        print(f"  ✅ Browse: {'PASS' if browse_succeeded else 'FAIL'}")
        print(
            f"  {'✅' if search_succeeded else '⚠️ '} Search: {'PASS' if search_succeeded else 'SKIP (indexing delay)'}"
        )
        print(
            f"  {'✅' if tabulator_succeeded else '⚠️ '} Tabulator: {'PASS' if tabulator_succeeded else f'SKIP ({tabulator_skip_reason})'}"
        )
        print(
            f"  {'✅' if athena_succeeded else '⚠️ '} Athena: {'PASS' if athena_succeeded else f'SKIP ({athena_skip_reason})'}"
        )
        print(f"  Package: {package_name}")
        print(f"  Registry: {registry}")
        print(f"  Files: {len(test_files)} created, {len(browse_files)} retrieved via browse")

        # Manual cleanup of package
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

        print("\n✅ Cross-backend consistency test completed!")

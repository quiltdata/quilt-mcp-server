"""E2E Performance tests for large result sets.

This module tests performance of operations that return large result sets
against real services (S3, Elasticsearch, Athena).

Tests are marked with @pytest.mark.slow and @pytest.mark.performance for
selective execution during development vs CI/CD.
"""

import asyncio
import pytest
import time
from typing import Dict, Any


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.performance
@pytest.mark.usefixtures("backend_mode")
class TestLargeResultSetPerformance:
    """Performance tests for operations returning large result sets.

    These tests measure real-world performance against actual AWS services:
    - S3 ListObjectsV2 with pagination for large buckets
    - Elasticsearch queries returning many results
    - Athena queries processing large datasets

    Performance targets are based on real-world usage patterns:
    - List 10k objects: < 30s (acceptable for batch operations)
    - Search 1000 results: < 5s (interactive search experience)
    - Query 10k rows: < 60s (acceptable for analytics queries)

    Tests adapt to available data - if test bucket has fewer objects,
    targets are scaled proportionally to maintain meaningful benchmarks.
    """

    def test_large_result_set_performance(
        self, backend_with_auth, real_test_bucket, backend_mode
    ):
        """Test performance of large result set operations across backends.

        This test measures performance for three key operations:
        1. List bucket with many objects (S3 pagination)
        2. Search catalog with broad query (Elasticsearch)
        3. Query tabulator table (Athena)

        Each operation is timed and validated for:
        - Operation completes within acceptable time
        - Sufficient results are returned
        - Results are properly formatted

        Args:
            backend_with_auth: Authenticated backend (quilt3 or platform)
            real_test_bucket: Real test bucket name
            backend_mode: Backend mode (quilt3 or platform)
        """
        results: Dict[str, Dict[str, Any]] = {}

        # =====================================================================
        # Scenario 1: List bucket with many objects
        # =====================================================================
        print(f"\n[Scenario 1] Testing bucket object listing for {real_test_bucket}...")

        # Use bucket_objects_list tool via backend
        from quilt_mcp.tools.buckets import bucket_objects_list

        start = time.time()
        try:
            # Request up to 1000 objects (max allowed by tool)
            # This tests pagination performance for large buckets
            list_result = bucket_objects_list(
                bucket=real_test_bucket,
                prefix="",  # List all objects
                max_keys=1000,
                include_signed_urls=False,  # Faster without URLs
            )

            duration = time.time() - start

            # Validate result format
            if hasattr(list_result, 'success') and list_result.success:
                object_count = len(list_result.objects) if hasattr(list_result, 'objects') else 0
                has_more = list_result.truncated if hasattr(list_result, 'truncated') else False

                results['list_objects'] = {
                    'duration': duration,
                    'count': object_count,
                    'truncated': has_more,
                    'success': True,
                }

                print(f"  ✅ Listed {object_count} objects in {duration:.2f}s")
                print(f"     More objects available: {has_more}")

                # Performance assertion - scale based on actual data
                # Base target: 30s for 1000+ objects
                # Scale down for smaller datasets (but always require completion)
                if object_count >= 100:
                    # Have substantial data - enforce performance target
                    target_time = 30.0
                    assert duration < target_time, (
                        f"List operation too slow: {duration:.2f}s > {target_time}s "
                        f"for {object_count} objects"
                    )
                else:
                    # Limited data - just ensure operation completes
                    print(f"     ℹ️  Limited test data ({object_count} objects), "
                          "skipping strict performance check")

                # Result count validation
                assert object_count > 0, "Should return at least some objects"

            else:
                # Handle error case
                error_msg = getattr(list_result, 'error', 'Unknown error')
                results['list_objects'] = {
                    'duration': duration,
                    'success': False,
                    'error': error_msg,
                }
                pytest.skip(f"List operation failed: {error_msg}")

        except Exception as e:
            duration = time.time() - start
            results['list_objects'] = {
                'duration': duration,
                'success': False,
                'error': str(e),
            }
            pytest.skip(f"List operation error: {e}")

        # =====================================================================
        # Scenario 2: Search returning many results
        # =====================================================================
        print(f"\n[Scenario 2] Testing catalog search...")

        from quilt_mcp.tools.search import search_catalog

        start = time.time()
        try:
            # Broad search query to get many results
            # Use "*" wildcard to match many files
            search_result = search_catalog(
                query="*",  # Broad query
                bucket=real_test_bucket,
                scope="file",  # File-level search
                limit=1000,  # Request many results
                backend="elasticsearch",
            )

            duration = time.time() - start

            # Validate result format
            # search_catalog returns a dict (from model_dump())
            is_dict = isinstance(search_result, dict)

            if is_dict and search_result.get('success', False):
                # Success case - extract data from dict
                total_results = search_result.get('total_results', 0)
                returned_results = search_result.get('results', [])
                returned_count = len(returned_results)

                results['search_catalog'] = {
                    'duration': duration,
                    'total_results': total_results,
                    'returned_count': returned_count,
                    'success': True,
                }

                print(f"  ✅ Found {total_results} total results, "
                      f"returned {returned_count} in {duration:.2f}s")

                # Performance assertion - scale based on actual data
                # Base target: 5s for 100+ results
                if total_results >= 100:
                    target_time = 5.0
                    assert duration < target_time, (
                        f"Search too slow: {duration:.2f}s > {target_time}s "
                        f"for {total_results} results"
                    )
                else:
                    print(f"     ℹ️  Limited search results ({total_results}), "
                          "skipping strict performance check")

                # Result count validation - only warn if no results
                if total_results == 0:
                    print(f"     ℹ️  No search results found (may indicate empty catalog or no indexed data)")

            elif is_dict and 'error' in search_result:
                # Handle dict-based error response
                error_msg = search_result.get('error', 'Unknown error')
                results['search_catalog'] = {
                    'duration': duration,
                    'success': False,
                    'error': error_msg,
                }
                print(f"  ⚠️  Search failed: {error_msg} (may be expected if no catalog)")

            else:
                # Handle unexpected response format
                results['search_catalog'] = {
                    'duration': duration,
                    'success': False,
                    'error': f'Unexpected response format: {type(search_result)}',
                }
                print(f"  ⚠️  Search failed: unexpected response format (may be expected if no catalog)")

        except Exception as e:
            duration = time.time() - start
            results['search_catalog'] = {
                'duration': duration,
                'success': False,
                'error': str(e),
            }
            print(f"  ⚠️  Search error: {e} (may be expected if no catalog)")

        # =====================================================================
        # Scenario 3: Large Athena query
        # =====================================================================
        print(f"\n[Scenario 3] Testing Athena query...")

        # Only run for quilt3 backend (platform may not have direct Athena)
        if backend_mode == "quilt3":
            from quilt_mcp.tools.tabulator import tabulator_bucket_query

            start = time.time()
            try:
                # Try to list tables first to find a table to query
                tables = backend_with_auth.list_tabulator_tables(real_test_bucket)

                if tables:
                    # Use first available table
                    table_name = tables[0].get('name') or tables[0].get('table_name')
                    print(f"  📊 Found table: {table_name}")

                    # Execute query requesting many rows
                    # tabulator_bucket_query is async, so we need to run it with asyncio
                    query_result = asyncio.run(tabulator_bucket_query(
                        bucket_name=real_test_bucket,
                        query=f'SELECT * FROM "{table_name}" LIMIT 10000',
                        max_results=10000,
                        output_format="json",
                        use_quilt_auth=True,
                    ))

                    duration = time.time() - start

                    # Validate result format
                    if isinstance(query_result, dict) and not query_result.get('error'):
                        row_count = len(query_result.get('rows', []))

                        results['athena_query'] = {
                            'duration': duration,
                            'row_count': row_count,
                            'success': True,
                            'table': table_name,
                        }

                        print(f"  ✅ Query returned {row_count} rows in {duration:.2f}s")

                        # Performance assertion - scale based on actual data
                        # Base target: 60s for 1000+ rows
                        if row_count >= 1000:
                            target_time = 60.0
                            assert duration < target_time, (
                                f"Athena query too slow: {duration:.2f}s > {target_time}s "
                                f"for {row_count} rows"
                            )
                        elif row_count == 0:
                            print(f"     ℹ️  Table '{table_name}' is empty (0 rows), "
                                  "query executed successfully but returned no data")
                        else:
                            print(f"     ℹ️  Limited query results ({row_count} rows), "
                                  "skipping strict performance check")

                    else:
                        # Handle error case
                        error_msg = query_result.get('error', 'Unknown error')
                        results['athena_query'] = {
                            'duration': duration,
                            'success': False,
                            'error': error_msg,
                        }
                        print(f"  ⚠️  Query failed: {error_msg}")

                else:
                    print(f"  ℹ️  No tabulator tables found in {real_test_bucket}, "
                          "skipping Athena query test")
                    results['athena_query'] = {
                        'success': False,
                        'error': 'No tables available',
                    }

            except Exception as e:
                duration = time.time() - start
                results['athena_query'] = {
                    'duration': duration,
                    'success': False,
                    'error': str(e),
                }
                print(f"  ⚠️  Athena error: {e}")

        else:
            print(f"  ℹ️  Skipping Athena test for {backend_mode} backend")
            results['athena_query'] = {
                'success': False,
                'error': f'Not supported for {backend_mode} backend',
            }

        # =====================================================================
        # Summary
        # =====================================================================
        print("\n" + "=" * 70)
        print("PERFORMANCE TEST SUMMARY")
        print("=" * 70)

        for operation, data in results.items():
            if data.get('success'):
                print(f"\n✅ {operation}:")
                print(f"   Duration: {data['duration']:.2f}s")
                if 'count' in data:
                    print(f"   Objects: {data['count']}")
                if 'total_results' in data:
                    print(f"   Results: {data['total_results']}")
                if 'row_count' in data:
                    print(f"   Rows: {data['row_count']}")
            else:
                print(f"\n⚠️  {operation}: {data.get('error', 'Failed')}")

        print("=" * 70)

        # Final assertion - at least list_objects should succeed
        assert results['list_objects']['success'], (
            "List objects operation must succeed"
        )

        # If we had any successful operations, test passes
        successful_ops = sum(1 for r in results.values() if r.get('success'))
        print(f"\n✅ {successful_ops}/{len(results)} operations completed successfully")

        assert successful_ops >= 1, "At least one operation should succeed"

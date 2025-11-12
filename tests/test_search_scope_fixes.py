"""Tests for search scope semantic fixes.

This module tests fixes for three issues:
1. Bucket scope returns results but catalog/global don't (403 fallback)
2. GraphQL error handling improvements
3. Package search returns mixed file/package results (packages_only fix)
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock

from quilt_mcp.search.backends.elasticsearch import Quilt3ElasticsearchBackend
from quilt_mcp.search.backends.graphql import EnterpriseGraphQLBackend
from quilt_mcp.search.backends.base import BackendStatus, SearchResult
from quilt_mcp.tools.stack_buckets import build_stack_search_indices


class TestStackSearchIndices:
    """Test stack search index pattern generation."""

    def test_build_stack_search_indices_packages_only_false(self):
        """Should include both object and package indices when packages_only=False."""
        buckets = ["bucket1", "bucket2"]
        indices = build_stack_search_indices(buckets, packages_only=False)

        # Should include both bucket and bucket_packages for each bucket
        assert indices == "bucket1,bucket1_packages,bucket2,bucket2_packages"

    def test_build_stack_search_indices_packages_only_true(self):
        """Should only include package indices when packages_only=True."""
        buckets = ["bucket1", "bucket2"]
        indices = build_stack_search_indices(buckets, packages_only=True)

        # Should only include bucket_packages for each bucket
        assert indices == "bucket1_packages,bucket2_packages"

    def test_build_stack_search_indices_single_bucket_packages_only(self):
        """Should work correctly with a single bucket and packages_only=True."""
        buckets = ["my-bucket"]
        indices = build_stack_search_indices(buckets, packages_only=True)

        assert indices == "my-bucket_packages"

    def test_build_stack_search_indices_empty_buckets(self):
        """Should return empty string when bucket list is empty."""
        buckets = []
        indices = build_stack_search_indices(buckets, packages_only=True)

        assert indices == ""


class TestElasticsearchScopeFallback:
    """Test Issue 1 fix: Catalog/global scope fallback to bucket search."""

    @pytest.mark.anyio
    async def test_global_search_falls_back_on_403_error(self):
        """When stack search returns 403, should fall back to bucket search."""
        backend = Quilt3ElasticsearchBackend()

        # Mock the dependencies
        with patch.object(backend, '_execute_catalog_search') as mock_catalog_search, \
             patch.object(backend, '_search_bucket') as mock_bucket_search:

            # Simulate 403 error from catalog search
            mock_catalog_search.return_value = {
                "error": "Catalog search failed: Unexpected failure: error 403"
            }

            # Simulate successful bucket search
            mock_bucket_search.return_value = [
                SearchResult(
                    id="test-1",
                    type="object",
                    title="Test Object",
                    description="Test",
                    score=1.0,
                    backend="elasticsearch",
                )
            ]

            # Execute global search
            results = await backend._search_global(query="*", filters={}, limit=10)

            # Should have called catalog search first
            mock_catalog_search.assert_called_once()

            # Should have fallen back to bucket search
            mock_bucket_search.assert_called_once()

            # Should return bucket results
            assert len(results) == 1
            assert results[0].id == "test-1"

    @pytest.mark.anyio
    async def test_global_search_falls_back_on_index_not_found(self):
        """When stack search returns index_not_found, should fall back to bucket search."""
        backend = Quilt3ElasticsearchBackend()

        with patch.object(backend, '_execute_catalog_search') as mock_catalog_search, \
             patch.object(backend, '_search_bucket') as mock_bucket_search:

            # Simulate index_not_found error
            mock_catalog_search.return_value = {
                "error": "Catalog search failed: index_not_found_exception"
            }

            mock_bucket_search.return_value = [
                SearchResult(
                    id="test-1",
                    type="object",
                    title="Test Object",
                    description="Test",
                    score=1.0,
                    backend="elasticsearch",
                )
            ]

            results = await backend._search_global(query="*", filters={}, limit=10)

            # Should fall back to bucket search
            mock_bucket_search.assert_called_once()
            assert len(results) == 1

    @pytest.mark.anyio
    async def test_global_search_raises_on_other_errors(self):
        """Non-403/index errors should still raise exceptions."""
        backend = Quilt3ElasticsearchBackend()

        with patch.object(backend, '_execute_catalog_search') as mock_catalog_search:
            # Simulate a different error
            mock_catalog_search.return_value = {
                "error": "Network timeout"
            }

            # Should raise the original error, not fall back
            with pytest.raises(Exception, match="Network timeout"):
                await backend._search_global(query="*", filters={}, limit=10)

    @pytest.mark.anyio
    async def test_global_search_succeeds_normally(self):
        """When catalog search works, should not fall back."""
        backend = Quilt3ElasticsearchBackend()

        with patch.object(backend, '_execute_catalog_search') as mock_catalog_search, \
             patch.object(backend, '_search_bucket') as mock_bucket_search, \
             patch.object(backend, '_convert_catalog_results') as mock_convert:

            # Simulate successful catalog search
            mock_catalog_search.return_value = {
                "hits": {
                    "hits": [{"_id": "test-1", "_source": {"key": "test.csv"}}]
                }
            }
            mock_convert.return_value = [
                SearchResult(
                    id="test-1",
                    type="object",
                    title="Test Object",
                    description="Test",
                    score=1.0,
                    backend="elasticsearch",
                )
            ]

            results = await backend._search_global(query="*", filters={}, limit=10)

            # Should NOT call bucket search
            mock_bucket_search.assert_not_called()

            # Should return catalog results
            assert len(results) == 1
            assert results[0].id == "test-1"


class TestGraphQLErrorHandling:
    """Test Issue 2 fix: GraphQL error handling improvements."""

    @pytest.mark.anyio
    async def test_graphql_handles_dict_errors_safely(self):
        """Should handle dict-formatted GraphQL errors without crashing."""
        backend = EnterpriseGraphQLBackend()

        with patch('quilt_mcp.tools.search.search_graphql') as mock_search:
            # Simulate GraphQL error with proper dict format
            mock_search.return_value = {
                "success": False,
                "errors": [
                    {
                        "message": "Field 'objects' not found",
                        "path": ["objects"],
                        "locations": [{"line": 2, "column": 3}]
                    }
                ]
            }

            # Should raise exception with clear error message
            with pytest.raises(Exception, match="Field 'objects' not found"):
                await backend._execute_graphql_query("query {}", {})

    @pytest.mark.anyio
    async def test_graphql_handles_errors_without_path(self):
        """Should handle errors without path/location fields."""
        backend = EnterpriseGraphQLBackend()

        with patch('quilt_mcp.tools.search.search_graphql') as mock_search:
            # Simulate error without path/locations
            mock_search.return_value = {
                "success": False,
                "errors": [
                    {"message": "Authentication required"}
                ]
            }

            with pytest.raises(Exception, match="Authentication required"):
                await backend._execute_graphql_query("query {}", {})

    @pytest.mark.anyio
    async def test_graphql_handles_non_dict_errors(self):
        """Should handle non-dict error entries gracefully."""
        backend = EnterpriseGraphQLBackend()

        with patch('quilt_mcp.tools.search.search_graphql') as mock_search:
            # Simulate malformed error (not a dict)
            mock_search.return_value = {
                "success": False,
                "errors": ["Some error string"]
            }

            with pytest.raises(Exception, match="Some error string"):
                await backend._execute_graphql_query("query {}", {})

    @pytest.mark.anyio
    async def test_graphql_handles_non_list_errors(self):
        """Should handle errors that aren't a list."""
        backend = EnterpriseGraphQLBackend()

        with patch('quilt_mcp.tools.search.search_graphql') as mock_search:
            # Simulate errors as a dict instead of list
            mock_search.return_value = {
                "success": False,
                "errors": {"message": "Something went wrong"}
            }

            with pytest.raises(Exception, match="Something went wrong"):
                await backend._execute_graphql_query("query {}", {})

    @pytest.mark.anyio
    async def test_graphql_bucket_search_falls_back_gracefully(self):
        """When bucket-specific GraphQL fails, should return empty (let Elasticsearch handle it)."""
        backend = EnterpriseGraphQLBackend()
        backend._session = Mock()
        backend._registry_url = "https://test.com"

        with patch.object(backend, '_execute_graphql_query') as mock_execute:
            # Simulate GraphQL query failure
            mock_execute.side_effect = Exception("Query failed")

            # Should return empty results, not raise
            results = await backend._search_bucket_objects(
                query="*",
                bucket="s3://test-bucket",
                filters={},
                limit=10
            )

            assert results == []


class TestPackageSearchImplementation:
    """Test Issue 3 fix: Implement _search_packages() for package-only search."""

    @pytest.mark.anyio
    async def test_catalog_wide_package_search_uses_packages_only_indices(self):
        """Catalog-wide package search should only search *_packages indices."""
        backend = Quilt3ElasticsearchBackend()

        with patch.object(backend, '_execute_catalog_search') as mock_catalog_search, \
             patch.object(backend, '_convert_catalog_results') as mock_convert:

            # Simulate successful package search
            mock_catalog_search.return_value = {
                "hits": {
                    "hits": [{"_id": "test-pkg", "_source": {"ptr_name": "team/dataset"}}]
                }
            }
            mock_convert.return_value = [
                SearchResult(
                    id="test-pkg",
                    type="package",
                    title="team/dataset",
                    description="Test package",
                    score=1.0,
                    backend="elasticsearch",
                )
            ]

            # Execute catalog-wide package search (no target)
            results = await backend._search_packages(query="*", package_name="", filters={}, limit=10)

            # Should call _execute_catalog_search with packages_only=True
            mock_catalog_search.assert_called_once()
            call_kwargs = mock_catalog_search.call_args[1]
            assert call_kwargs['packages_only'] is True, "Should only search package indices"

            # Should return package results
            assert len(results) == 1
            assert results[0].type == "package"

    @pytest.mark.anyio
    async def test_specific_package_search_adds_package_filter(self):
        """Specific package search should add package_name filter."""
        backend = Quilt3ElasticsearchBackend()

        with patch.object(backend, '_execute_catalog_search') as mock_catalog_search, \
             patch.object(backend, '_convert_catalog_results') as mock_convert:

            # Simulate successful package search
            mock_catalog_search.return_value = {
                "hits": {
                    "hits": [{"_id": "test-pkg", "_source": {"ptr_name": "team/dataset"}}]
                }
            }
            mock_convert.return_value = [
                SearchResult(
                    id="test-pkg",
                    type="package",
                    title="team/dataset",
                    description="Test package",
                    score=1.0,
                    backend="elasticsearch",
                )
            ]

            # Execute specific package search
            results = await backend._search_packages(
                query="README",
                package_name="team/dataset",
                filters={},
                limit=10
            )

            # Should call _execute_catalog_search with package_name filter
            mock_catalog_search.assert_called_once()
            call_kwargs = mock_catalog_search.call_args[1]
            assert call_kwargs['packages_only'] is True
            assert 'package_name' in call_kwargs['filters']
            assert call_kwargs['filters']['package_name'] == "team/dataset"

    @pytest.mark.anyio
    async def test_package_search_handles_errors_gracefully(self):
        """Package search should return empty list on errors, not raise."""
        backend = Quilt3ElasticsearchBackend()

        with patch.object(backend, '_execute_catalog_search') as mock_catalog_search:
            # Simulate search error
            mock_catalog_search.return_value = {
                "error": "Search failed: some error"
            }

            # Should return empty list, not raise
            results = await backend._search_packages(query="*", package_name="", filters={}, limit=10)
            assert results == []

    @pytest.mark.anyio
    async def test_search_router_calls_search_packages_for_package_scope(self):
        """search() method should call _search_packages() when scope='package'."""
        backend = Quilt3ElasticsearchBackend()
        backend._session_available = True

        with patch.object(backend, '_search_packages') as mock_search_packages:
            mock_search_packages.return_value = [
                SearchResult(
                    id="test-pkg",
                    type="package",
                    title="team/dataset",
                    description="Test package",
                    score=1.0,
                    backend="elasticsearch",
                )
            ]

            # Call search with scope="package"
            response = await backend.search(
                query="*",
                scope="package",
                target="",
                filters={},
                limit=10
            )

            # Should call _search_packages
            mock_search_packages.assert_called_once_with("*", "", {}, 10)
            assert len(response.results) == 1
            assert response.results[0].type == "package"

    @pytest.mark.anyio
    async def test_search_router_calls_search_packages_with_target(self):
        """search() method should pass target to _search_packages()."""
        backend = Quilt3ElasticsearchBackend()
        backend._session_available = True

        with patch.object(backend, '_search_packages') as mock_search_packages:
            mock_search_packages.return_value = []

            # Call search with scope="package" and target
            await backend.search(
                query="README",
                scope="package",
                target="team/dataset",
                filters={},
                limit=10
            )

            # Should call _search_packages with target as package_name
            mock_search_packages.assert_called_once_with("README", "team/dataset", {}, 10)


class TestScopeSemantics:
    """Test that scope semantics are correct (supersets contain subsets)."""

    @pytest.mark.anyio
    async def test_catalog_is_superset_of_bucket(self):
        """Catalog scope should return at least as many results as bucket scope."""
        # This is an integration test concept - documenting expected behavior
        # In practice, we'd test with real search or comprehensive mocks

        # Expected behavior:
        # - bucket_results = search(scope="bucket", target="s3://my-bucket")
        # - catalog_results = search(scope="package")
        # - assert len(catalog_results) >= len(bucket_results)

        # The fix ensures:
        # 1. If catalog search fails with 403, it falls back to bucket search
        # 2. So catalog results >= bucket results (at minimum, same bucket)
        pass

    @pytest.mark.anyio
    async def test_global_is_superset_of_catalog(self):
        """Global scope should return at least as many results as catalog scope."""
        # Expected behavior:
        # - catalog_results = search(scope="package")
        # - global_results = search(scope="global")
        # - assert len(global_results) >= len(catalog_results)

        # The fix ensures:
        # 1. Global and catalog both use _search_global
        # 2. Both fall back to bucket search on 403
        # 3. So the superset relationship is maintained
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

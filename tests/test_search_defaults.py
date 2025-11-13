"""Tests for search_catalog default parameters."""

from unittest.mock import patch

from quilt_mcp.tools.search import search_catalog


class TestSearchDefaults:
    """Test that search_catalog has sensible defaults."""

    def _create_mock_response(self, query, scope, target, backend):
        """Helper to create a mock search response."""
        return {
            "success": True,
            "query": query,
            "scope": scope,
            "target": target,
            "results": [],
            "total_results": 0,
            "query_time_ms": 10.0,
            "backend_used": backend,
        }

    @patch("quilt_mcp.tools.search.DEFAULT_BUCKET", "s3://test-bucket")
    @patch("quilt_mcp.tools.search.asyncio.run")
    @patch("quilt_mcp.tools.search._unified_search")
    def test_default_scope_is_bucket(self, mock_unified, mock_asyncio_run):
        """Test that default scope is 'bucket' not 'global'."""
        # Setup mocks
        mock_asyncio_run.return_value = self._create_mock_response(
            "test", "bucket", "s3://test-bucket", "elasticsearch"
        )

        # Call without specifying scope
        result = search_catalog(query="test")

        # Verify scope defaulted to "bucket"
        mock_unified.assert_called_once()
        call_kwargs = mock_unified.call_args.kwargs
        assert call_kwargs["scope"] == "bucket", "Default scope should be 'bucket'"
        assert result["success"] is True

    @patch("quilt_mcp.tools.search.DEFAULT_BUCKET", "s3://test-bucket")
    @patch("quilt_mcp.tools.search.asyncio.run")
    @patch("quilt_mcp.tools.search._unified_search")
    def test_default_backend_is_elasticsearch(self, mock_unified, mock_asyncio_run):
        """Test that default backend is 'elasticsearch' not 'auto'."""
        # Setup mocks
        mock_asyncio_run.return_value = self._create_mock_response(
            "test", "bucket", "s3://test-bucket", "elasticsearch"
        )

        # Call without specifying backend
        result = search_catalog(query="test")

        # Verify backend defaulted to "elasticsearch"
        mock_unified.assert_called_once()
        call_kwargs = mock_unified.call_args.kwargs
        assert call_kwargs["backend"] == "elasticsearch", "Default backend should be 'elasticsearch'"

    @patch("quilt_mcp.tools.search.DEFAULT_BUCKET", "s3://my-default-bucket")
    @patch("quilt_mcp.tools.search.asyncio.run")
    @patch("quilt_mcp.tools.search._unified_search")
    def test_default_target_uses_env_bucket(self, mock_unified, mock_asyncio_run):
        """Test that when scope=bucket and target='', it uses DEFAULT_BUCKET from env."""
        # Setup mocks
        mock_asyncio_run.return_value = self._create_mock_response(
            "test", "bucket", "s3://my-default-bucket", "elasticsearch"
        )

        # Call without specifying target (should use DEFAULT_BUCKET)
        result = search_catalog(query="test")

        # Verify target was set to DEFAULT_BUCKET
        mock_unified.assert_called_once()
        call_kwargs = mock_unified.call_args.kwargs
        assert call_kwargs["target"] == "s3://my-default-bucket", "Should use DEFAULT_BUCKET as target"

    @patch("quilt_mcp.tools.search.DEFAULT_BUCKET", "")
    @patch("quilt_mcp.tools.search.asyncio.run")
    @patch("quilt_mcp.tools.search._unified_search")
    def test_empty_target_when_no_default_bucket(self, mock_unified, mock_asyncio_run):
        """Test that target remains empty when DEFAULT_BUCKET is not set."""
        # Setup mocks
        mock_asyncio_run.return_value = self._create_mock_response("test", "bucket", "", "elasticsearch")

        # Call without specifying target
        result = search_catalog(query="test")

        # Verify target remained empty
        mock_unified.assert_called_once()
        call_kwargs = mock_unified.call_args.kwargs
        assert call_kwargs["target"] == "", "Target should remain empty when no DEFAULT_BUCKET"

    @patch("quilt_mcp.tools.search.DEFAULT_BUCKET", "s3://default-bucket")
    @patch("quilt_mcp.tools.search.asyncio.run")
    @patch("quilt_mcp.tools.search._unified_search")
    def test_explicit_target_overrides_default(self, mock_unified, mock_asyncio_run):
        """Test that explicitly provided target overrides DEFAULT_BUCKET."""
        # Setup mocks
        mock_asyncio_run.return_value = self._create_mock_response(
            "test", "bucket", "s3://explicit-bucket", "elasticsearch"
        )

        # Call with explicit target
        result = search_catalog(query="test", target="s3://explicit-bucket")

        # Verify explicit target was used
        mock_unified.assert_called_once()
        call_kwargs = mock_unified.call_args.kwargs
        assert call_kwargs["target"] == "s3://explicit-bucket", "Should use explicit target"

    @patch("quilt_mcp.tools.search.DEFAULT_BUCKET", "s3://default-bucket")
    @patch("quilt_mcp.tools.search.asyncio.run")
    @patch("quilt_mcp.tools.search._unified_search")
    def test_catalog_scope_doesnt_set_default_target(self, mock_unified, mock_asyncio_run):
        """Test that DEFAULT_BUCKET is NOT used when scope is 'package'."""
        # Setup mocks
        mock_asyncio_run.return_value = self._create_mock_response("test", "package", "", "elasticsearch")

        # Call with catalog scope, no target
        result = search_catalog(query="test", scope="package")

        # Verify target remained empty (not set to DEFAULT_BUCKET)
        mock_unified.assert_called_once()
        call_kwargs = mock_unified.call_args.kwargs
        assert call_kwargs["target"] == "", "Catalog scope should not auto-set target"

    @patch("quilt_mcp.tools.search.DEFAULT_BUCKET", "s3://combo-bucket")
    @patch("quilt_mcp.tools.search.asyncio.run")
    @patch("quilt_mcp.tools.search._unified_search")
    def test_all_defaults_together(self, mock_unified, mock_asyncio_run):
        """Test that all defaults work together correctly."""
        # Setup mocks
        mock_asyncio_run.return_value = self._create_mock_response(
            "CSV files", "bucket", "s3://combo-bucket", "elasticsearch"
        )

        # Call with only query (all other params use defaults)
        result = search_catalog(query="CSV files")

        # Verify all defaults were applied
        mock_unified.assert_called_once()
        call_kwargs = mock_unified.call_args.kwargs
        assert call_kwargs["scope"] == "bucket", "Should default to bucket scope"
        assert call_kwargs["target"] == "s3://combo-bucket", "Should default to DEFAULT_BUCKET"
        assert call_kwargs["backend"] == "elasticsearch", "Should default to elasticsearch"
        assert call_kwargs["limit"] == 50, "Should default to limit=50"
        assert call_kwargs["include_metadata"] is True, "Should default to include_metadata=True"

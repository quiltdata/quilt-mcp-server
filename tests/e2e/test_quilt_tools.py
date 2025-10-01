import os
from contextlib import contextmanager
from unittest.mock import Mock, patch

from quilt_mcp.tools.auth import (
    auth_status,
    catalog_info,
    catalog_name,
    catalog_uri,
    catalog_url,
)
from quilt_mcp.tools.buckets import bucket_objects_search
from quilt_mcp.tools.packages import packages_search
from quilt_mcp.runtime import request_context


@contextmanager
def runtime_token(token: str):
    with request_context(token, metadata={"session_id": "e2e"}):
        yield


class TestQuiltTools:
    """Test suite for Quilt MCP tools."""

    def test_auth_status_authenticated(self):
        """Test auth_status when user is authenticated."""
        with runtime_token("token"), patch.dict(os.environ, {"QUILT_CATALOG_URL": "https://open.quiltdata.com"}):
            result = auth_status()

        assert result["status"] == "authenticated"
        assert result["catalog_url"] == "https://open.quiltdata.com"
        assert result["search_available"] is True

    def test_auth_status_not_authenticated(self):
        """Test auth_status when user is not authenticated."""
        with runtime_token(None), patch.dict(os.environ, {}, clear=True):
            result = auth_status()

        assert result["status"] == "not_authenticated"
        assert result["search_available"] is False

    def test_catalog_info_updates_with_env(self):
        """Test catalog_info reflects resolved catalog URL and token status."""
        with runtime_token("token"), patch.dict(os.environ, {"QUILT_CATALOG_URL": "https://test.catalog.com"}):
            result = catalog_info()

        assert result["status"] == "success"
        assert result["catalog_name"] == "test.catalog.com"
        assert result["is_authenticated"] is True

    def test_catalog_info_without_token(self):
        """Test catalog_info when no token is present."""
        with runtime_token(None), patch.dict(os.environ, {"QUILT_CATALOG_URL": "https://test.catalog.com"}):
            result = catalog_info()

        assert result["status"] == "success"
        assert result["catalog_name"] == "test.catalog.com"
        assert result["is_authenticated"] is False

    def test_catalog_name_uses_environment(self):
        """Test catalog_name uses environment-derived host."""
        with runtime_token("token"), patch.dict(os.environ, {"QUILT_CATALOG_URL": "https://test.catalog.com"}):
            result = catalog_name()

        assert isinstance(result, dict)
        assert result["status"] == "success"
        assert result["catalog_name"] == "test.catalog.com"
        assert result["detection_method"] == "environment"
        assert result["is_authenticated"] is True

    def test_catalog_url_package_view(self):
        """Test catalog_url for package view using environment host."""
        with patch.dict(os.environ, {"QUILT_CATALOG_URL": "https://test.catalog.com"}):
            result = catalog_url(
                registry="s3://test-bucket",
                package_name="user/package",
                path="data.csv",
            )

        assert isinstance(result, dict)
        assert result["status"] == "success"
        assert result["view_type"] == "package"
        assert (
            result["catalog_url"]
            == "https://test.catalog.com/b/test-bucket/packages/user/package/tree/latest/data.csv"
        )
        assert result["bucket"] == "test-bucket"

    def test_catalog_url_bucket_view(self):
        """Test catalog_url for bucket view using environment host."""
        with patch.dict(os.environ, {"QUILT_CATALOG_URL": "https://test.catalog.com"}):
            result = catalog_url(registry="s3://test-bucket", path="data/file.csv")

        assert isinstance(result, dict)
        assert result["status"] == "success"
        assert result["view_type"] == "bucket"
        assert result["catalog_url"] == "https://test.catalog.com/b/test-bucket/tree/data/file.csv"
        assert result["bucket"] == "test-bucket"

    def test_catalog_uri_basic(self):
        """Test catalog_uri with basic parameters."""
        with patch.dict(os.environ, {"QUILT_CATALOG_URL": "https://test.catalog.com"}):
            result = catalog_uri(
                registry="s3://test-bucket",
                package_name="user/package",
                path="data.csv",
            )

        assert isinstance(result, dict)
        assert result["status"] == "success"
        assert (
            result["quilt_plus_uri"]
            == "quilt+s3://test-bucket#package=user/package&path=data.csv&catalog=test.catalog.com"
        )
        assert result["bucket"] == "test-bucket"

    def test_catalog_uri_with_version(self):
        """Test catalog_uri with version hash."""
        with patch.dict(os.environ, {"QUILT_CATALOG_URL": "https://test.catalog.com"}):
            result = catalog_uri(
                registry="s3://test-bucket",
                package_name="user/package",
                top_hash="abc123def456",
            )

        assert isinstance(result, dict)
        assert result["status"] == "success"
        assert "package=user/package@abc123def456" in result["quilt_plus_uri"]
        assert result["top_hash"] == "abc123def456"

    def test_catalog_uri_with_tag(self):
        """Test catalog_uri with version tag."""
        with patch.dict(os.environ, {"QUILT_CATALOG_URL": "https://test.catalog.com"}):
            result = catalog_uri(registry="s3://test-bucket", package_name="user/package", tag="v1.0")

        assert isinstance(result, dict)
        assert result["status"] == "success"
        assert "package=user/package:v1.0" in result["quilt_plus_uri"]
        assert result["tag"] == "v1.0"

    def test_bucket_objects_search_success(self):
        """Test bucket_objects_search with successful results."""
        mock_payload = {"results": ["hit1", "hit2"]}

        with (
            patch(
                "quilt_mcp.clients.catalog.catalog_bucket_search",
                return_value=mock_payload,
            ) as mock_search,
            runtime_token("token"),
        ):
            result = bucket_objects_search("test-bucket", "data", limit=10, registry_url="https://catalog")

        mock_search.assert_called_once_with(
            registry_url="https://catalog",
            bucket="test-bucket",
            query="data",
            limit=10,
            auth_token="token",
        )

        assert isinstance(result, dict)
        assert result["bucket"] == "test-bucket"
        assert result["query"] == "data"
        assert result["limit"] == 10
        assert result["results"] == ["hit1", "hit2"]

    def test_bucket_objects_search_with_dict_query(self):
        """Test bucket_objects_search with dictionary DSL query."""
        query_dsl = {"query": {"match": {"key": "test"}}}
        mock_payload = {"results": ["hit"]}

        with (
            patch(
                "quilt_mcp.clients.catalog.catalog_bucket_search",
                return_value=mock_payload,
            ) as mock_search,
            runtime_token("token"),
        ):
            result = bucket_objects_search("test-bucket", query_dsl, limit=5, registry_url="https://catalog")

        mock_search.assert_called_once()
        assert isinstance(result, dict)
        assert result["bucket"] == "test-bucket"
        assert result["query"] == query_dsl
        assert result["limit"] == 5
        assert result["results"] == ["hit"]

    def test_bucket_objects_search_s3_uri_normalization(self):
        """Test bucket_objects_search normalizes s3:// URI to bucket name."""
        mock_payload = {"results": []}

        with (
            patch(
                "quilt_mcp.clients.catalog.catalog_bucket_search",
                return_value=mock_payload,
            ),
            runtime_token("token"),
        ):
            result = bucket_objects_search("s3://test-bucket", "query", registry_url="https://catalog")

        assert result["bucket"] == "test-bucket"

    def test_bucket_objects_search_error(self):
        """Test bucket_objects_search with search error."""
        with (
            patch(
                "quilt_mcp.clients.catalog.catalog_bucket_search",
                side_effect=RuntimeError("Search endpoint not configured"),
            ),
            runtime_token("token"),
        ):
            result = bucket_objects_search("test-bucket", "query", registry_url="https://catalog")

        assert isinstance(result, dict)
        assert "error" in result
        assert "Failed to search bucket" in result["error"]
        assert result["bucket"] == "test-bucket"
        assert result["query"] == "query"

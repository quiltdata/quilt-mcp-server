"""Tests for catalog.py - Test-Driven Development Implementation."""

from __future__ import annotations

from unittest.mock import Mock, patch

from quilt_mcp.models import (
    CatalogUrlParams,
    CatalogUriParams,
)
from quilt_mcp.services.auth_metadata import (
    _extract_catalog_name_from_url,
    _extract_bucket_from_registry,
    _get_catalog_host_from_config,
    _get_catalog_info,
)
from quilt_mcp.tools.catalog import catalog_url, catalog_uri, catalog_configure


class TestExtractCatalogNameFromUrl:
    """Test _extract_catalog_name_from_url function - targeting missing lines 23, 31, 33-35."""

    def test_extract_catalog_name_with_valid_url(self):
        """Test extracting catalog name from valid URL."""
        result = _extract_catalog_name_from_url("https://demo.quiltdata.com")
        assert result == "demo.quiltdata.com"

    def test_extract_catalog_name_from_empty_url(self):
        """Test empty URL returns 'unknown' - covers line 23."""
        result = _extract_catalog_name_from_url("")
        assert result == "unknown"

    def test_extract_catalog_name_from_none_url(self):
        """Test None URL returns 'unknown' - covers line 23."""
        result = _extract_catalog_name_from_url(None)
        assert result == "unknown"

    def test_extract_catalog_name_removes_www_prefix(self):
        """Test www. prefix removal - covers line 31."""
        result = _extract_catalog_name_from_url("https://www.example.com")
        assert result == "example.com"

    def test_extract_catalog_name_with_no_hostname(self):
        """Test URL parsing with no hostname - covers line 33."""
        # This will cause parsed.hostname to be None, triggering the fallback
        result = _extract_catalog_name_from_url("not-a-valid-url")
        assert result == "not-a-valid-url"

    def test_extract_catalog_name_with_parsing_exception(self):
        """Test exception handling during URL parsing - covers lines 34-35."""
        with patch('quilt_mcp.services.auth_metadata.urlparse', side_effect=Exception("Parse error")):
            result = _extract_catalog_name_from_url("https://example.com")
            assert result == "https://example.com"

    def test_extract_catalog_name_with_netloc_fallback(self):
        """Test using netloc when hostname is None."""
        # Create a mock parsed result where hostname is None but netloc exists
        with patch('quilt_mcp.services.auth_metadata.urlparse') as mock_urlparse:
            mock_parsed = Mock()
            mock_parsed.hostname = None
            mock_parsed.netloc = "example.com:8080"
            mock_urlparse.return_value = mock_parsed

            result = _extract_catalog_name_from_url("https://example.com:8080")
            assert result == "example.com:8080"


class TestGetCatalogHostFromConfig:
    """Test _get_catalog_host_from_config function - targeting missing lines 79-88."""

    def test_get_catalog_host_when_logged_in_url_available(self):
        """Test getting catalog host from logged_in_url."""
        with patch('quilt_mcp.services.auth_metadata.QuiltService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_logged_in_url.return_value = "https://demo.quiltdata.com"
            mock_service_class.return_value = mock_service

            result = _get_catalog_host_from_config()
            assert result == "demo.quiltdata.com"

    def test_get_catalog_host_falls_back_to_navigator_url(self):
        """Test fallback to navigator_url from config - covers lines 79-85."""
        with patch('quilt_mcp.services.auth_metadata.QuiltService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_logged_in_url.return_value = None
            mock_service.get_config.return_value = {"navigator_url": "https://nightly.quilttest.com"}
            mock_service_class.return_value = mock_service

            result = _get_catalog_host_from_config()
            assert result == "nightly.quilttest.com"

    def test_get_catalog_host_with_no_navigator_url(self):
        """Test when config has no navigator_url - covers lines 79-85."""
        with patch('quilt_mcp.services.auth_metadata.QuiltService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_logged_in_url.return_value = None
            mock_service.get_config.return_value = {}
            mock_service_class.return_value = mock_service

            result = _get_catalog_host_from_config()
            assert result is None

    def test_get_catalog_host_with_none_config(self):
        """Test when get_config returns None - covers lines 79-80."""
        with patch('quilt_mcp.services.auth_metadata.QuiltService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_logged_in_url.return_value = None
            mock_service.get_config.return_value = None
            mock_service_class.return_value = mock_service

            result = _get_catalog_host_from_config()
            assert result is None

    def test_get_catalog_host_with_empty_navigator_url(self):
        """Test when navigator_url is empty string - covers lines 82-85."""
        with patch('quilt_mcp.services.auth_metadata.QuiltService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_logged_in_url.return_value = None
            mock_service.get_config.return_value = {"navigator_url": ""}
            mock_service_class.return_value = mock_service

            result = _get_catalog_host_from_config()
            assert result is None

    def test_get_catalog_host_with_exception(self):
        """Test exception handling - covers lines 86-88."""
        with patch('quilt_mcp.services.auth_metadata.QuiltService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_logged_in_url.side_effect = Exception("Service error")
            mock_service_class.return_value = mock_service

            result = _get_catalog_host_from_config()
            assert result is None


class TestCatalogUrl:
    """Test catalog_url function - targeting missing exception handling lines 115-118, 162-163."""

    def test_catalog_url_success_package_view(self):
        """Test successful catalog URL generation for package view."""
        with patch('quilt_mcp.tools.catalog._get_catalog_host_from_config', return_value="demo.quiltdata.com"):
            params = CatalogUrlParams(registry="s3://test-bucket", package_name="user/package")
            result = catalog_url(params)

            assert isinstance(result, dict) or hasattr(result, 'status')
            assert result.status == "success"
            assert result.view_type == "package"
            assert "demo.quiltdata.com" in result.catalog_url
            assert result.bucket == "test-bucket"

    def test_catalog_url_success_bucket_view(self):
        """Test successful catalog URL generation for bucket view - covers lines 144-150."""
        with patch('quilt_mcp.tools.catalog._get_catalog_host_from_config', return_value="demo.quiltdata.com"):
            params = CatalogUrlParams(registry="s3://test-bucket", package_name=None)
            result = catalog_url(params)

            assert result.status == "success"
            assert result.view_type == "bucket"
            assert "demo.quiltdata.com" in result.catalog_url
            assert result.bucket == "test-bucket"

    def test_catalog_url_bucket_view_with_path(self):
        """Test bucket view with path - covers lines 144-150."""
        with patch('quilt_mcp.tools.catalog._get_catalog_host_from_config', return_value="demo.quiltdata.com"):
            params = CatalogUrlParams(registry="s3://test-bucket", package_name=None, path="data/files")
            result = catalog_url(params)

            assert result.status == "success"
            assert result.view_type == "bucket"
            assert "data" in result.catalog_url
            assert "files" in result.catalog_url

    def test_catalog_url_package_view_with_path(self):
        """Test package view with path - covers lines 138-139."""
        with patch('quilt_mcp.tools.catalog._get_catalog_host_from_config', return_value="demo.quiltdata.com"):
            params = CatalogUrlParams(registry="s3://test-bucket", package_name="user/package", path="data/files")
            result = catalog_url(params)

            assert result.status == "success"
            assert result.view_type == "package"
            assert "data" in result.catalog_url
            assert "files" in result.catalog_url

    def test_catalog_url_no_catalog_host_error(self):
        """Test error when catalog host cannot be determined - covers lines 115-118."""
        with patch('quilt_mcp.tools.catalog._get_catalog_host_from_config', return_value=None):
            params = CatalogUrlParams(registry="s3://test-bucket", package_name="user/package")
            result = catalog_url(params)

            assert result.status == "error"
            assert "Could not determine catalog host" in result.error

    def test_catalog_url_with_exception(self):
        """Test exception handling in catalog_url - covers lines 162-163."""
        with patch('quilt_mcp.tools.catalog._extract_bucket_from_registry', side_effect=Exception("Bucket error")):
            params = CatalogUrlParams(registry="s3://test-bucket", package_name="user/package")
            result = catalog_url(params)

            assert result.status == "error"
            assert "Failed to generate catalog URL" in result.error
            assert "Bucket error" in result.error


class TestCatalogUri:
    """Test catalog_uri function - targeting missing exception handling."""

    def test_catalog_uri_with_package_name(self):
        """Test catalog_uri with package name - covers lines 191-223."""
        with patch('quilt_mcp.tools.catalog._get_catalog_host_from_config', return_value="demo.quiltdata.com"):
            params = CatalogUriParams(registry="s3://test-bucket", package_name="user/package")
            result = catalog_uri(params)

            assert result.status == "success"
            assert "quilt+s3://test-bucket" in result.quilt_plus_uri
            assert "package=user/package" in result.quilt_plus_uri
            assert "catalog=demo.quiltdata.com" in result.quilt_plus_uri

    def test_catalog_uri_with_top_hash(self):
        """Test catalog_uri with top_hash - covers lines 199-200."""
        with patch('quilt_mcp.tools.catalog._get_catalog_host_from_config', return_value="demo.quiltdata.com"):
            params = CatalogUriParams(registry="s3://test-bucket", package_name="user/package", top_hash="abc123")
            result = catalog_uri(params)

            assert result.status == "success"
            assert "package=user/package@abc123" in result.quilt_plus_uri

    def test_catalog_uri_with_tag(self):
        """Test catalog_uri with tag - covers lines 201-202."""
        with patch('quilt_mcp.tools.catalog._get_catalog_host_from_config', return_value="demo.quiltdata.com"):
            params = CatalogUriParams(registry="s3://test-bucket", package_name="user/package", tag="v1.0")
            result = catalog_uri(params)

            assert result.status == "success"
            assert "package=user/package:v1.0" in result.quilt_plus_uri

    def test_catalog_uri_with_path(self):
        """Test catalog_uri with path - covers lines 205-206."""
        with patch('quilt_mcp.tools.catalog._get_catalog_host_from_config', return_value="demo.quiltdata.com"):
            params = CatalogUriParams(registry="s3://test-bucket", package_name="user/package", path="data/file.csv")
            result = catalog_uri(params)

            assert result.status == "success"
            assert "path=data/file.csv" in result.quilt_plus_uri

    def test_catalog_uri_no_catalog_host(self):
        """Test catalog_uri without catalog host - covers lines 209-215."""
        with patch('quilt_mcp.tools.catalog._get_catalog_host_from_config', return_value=None):
            params = CatalogUriParams(registry="s3://test-bucket", package_name="user/package")
            result = catalog_uri(params)

            assert result.status == "success"
            # Should not contain catalog parameter when no host available
            assert "catalog=" not in result.quilt_plus_uri

    def test_catalog_uri_with_protocol_removal(self):
        """Test catalog_uri with protocol removal - covers lines 213-215."""
        with patch('quilt_mcp.tools.catalog._get_catalog_host_from_config', return_value="https://demo.quiltdata.com"):
            params = CatalogUriParams(registry="s3://test-bucket", package_name="user/package")
            result = catalog_uri(params)

            assert result.status == "success"
            assert "catalog=demo.quiltdata.com" in result.quilt_plus_uri
            # Should not contain https:// in the catalog parameter
            assert "https://" not in result.quilt_plus_uri.split("catalog=")[1]

    def test_catalog_uri_bucket_only(self):
        """Test catalog_uri with bucket only (no package) - covers lines 191-223."""
        with patch('quilt_mcp.tools.catalog._get_catalog_host_from_config', return_value="demo.quiltdata.com"):
            params = CatalogUriParams(registry="s3://test-bucket")
            result = catalog_uri(params)

            assert result.status == "success"
            assert "quilt+s3://test-bucket" in result.quilt_plus_uri
            assert "package=" not in result.quilt_plus_uri

    def test_catalog_uri_with_exception(self):
        """Test exception handling in catalog_uri - covers line 234-235."""
        with patch('quilt_mcp.tools.catalog._extract_bucket_from_registry', side_effect=Exception("URI error")):
            params = CatalogUriParams(registry="s3://test-bucket", package_name="user/package")
            result = catalog_uri(params)

            assert result.status == "error"
            assert "Failed to generate Quilt+ URI" in result.error
            assert "URI error" in result.error


class TestConfigureCatalog:
    """Test configure_catalog function - targeting missing exception handling."""

    def test_configure_catalog_with_friendly_name(self):
        """Test configuration with friendly name like 'demo'."""
        with patch('quilt_mcp.services.auth_metadata.QuiltService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_config.return_value = {"navigator_url": "https://demo.quiltdata.com"}
            mock_service_class.return_value = mock_service

            result = catalog_configure("demo")

            assert result["status"] == "success"
            assert result["catalog_url"] == "https://demo.quiltdata.com"
            mock_service.set_config.assert_called_with("https://demo.quiltdata.com")

    def test_configure_catalog_success(self):
        """Test successful configuration - covers lines 541-547."""
        with patch('quilt_mcp.services.auth_metadata.QuiltService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_config.return_value = {"navigator_url": "https://demo.quiltdata.com"}
            mock_service_class.return_value = mock_service

            result = catalog_configure("https://demo.quiltdata.com")

            assert result["status"] == "success"
            assert result["catalog_url"] == "https://demo.quiltdata.com"
            mock_service.set_config.assert_called_with("https://demo.quiltdata.com")

    def test_configure_catalog_with_exception(self):
        """Test exception handling in configure_catalog - covers lines 564-581."""
        with patch('quilt_mcp.services.auth_metadata.QuiltService', side_effect=Exception("Config error")):
            result = catalog_configure("https://demo.quiltdata.com")

            assert result["status"] == "error"
            assert "Failed to configure catalog" in result["error"]
            assert "troubleshooting" in result
            assert "Config error" in result["error"]


class TestExtractBucketFromRegistry:
    """Test _extract_bucket_from_registry function for completeness."""

    def test_extract_bucket_with_s3_prefix(self):
        """Test extracting bucket name from s3:// URL."""
        result = _extract_bucket_from_registry("s3://my-bucket-name")
        assert result == "my-bucket-name"

    def test_extract_bucket_without_s3_prefix(self):
        """Test extracting bucket name without s3:// prefix."""
        result = _extract_bucket_from_registry("my-bucket-name")
        assert result == "my-bucket-name"


class TestGetCatalogInfo:
    """Test _get_catalog_info function for completeness."""

    def test_get_catalog_info_delegates_to_service(self):
        """Test that _get_catalog_info properly delegates to QuiltService."""
        mock_info = {"catalog_name": "test", "is_authenticated": True}

        with (
            patch('quilt_mcp.services.quilt_service.QuiltService') as base_service_class,
            patch('quilt_mcp.services.auth_metadata.QuiltService') as mock_service_class,
        ):
            mock_service = Mock()
            mock_service.get_catalog_info.return_value = mock_info
            mock_service_class.return_value = mock_service
            base_service_class.return_value = mock_service

            result = _get_catalog_info()

            assert result == mock_info
            mock_service.get_catalog_info.assert_called_once()

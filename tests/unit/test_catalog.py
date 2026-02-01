"""Tests for catalog.py - Test-Driven Development Implementation."""

from __future__ import annotations

from unittest.mock import Mock, patch

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
        # This will cause parsed.hostname to be None, returning "unknown"
        result = _extract_catalog_name_from_url("not-a-valid-url")
        assert result == "unknown"

    def test_extract_catalog_name_with_port(self):
        """Test URL with port - hostname is extracted without port."""
        # The utility extracts DNS hostname which doesn't include port numbers
        result = _extract_catalog_name_from_url("https://example.com:8080")
        assert result == "example.com"


class TestGetCatalogHostFromConfig:
    """Test _get_catalog_host_from_config function - targeting missing lines 79-88."""

    def test_get_catalog_host_falls_back_to_navigator_url(self):
        """Test fallback to navigator_url from config - covers lines 79-85."""
        with patch('quilt_mcp.services.auth_metadata.QuiltOpsFactory') as mock_factory_class:
            mock_factory = Mock()
            mock_quilt_ops = Mock()
            mock_auth_status = Mock()
            mock_auth_status.logged_in_url = None
            mock_auth_status.navigator_url = "https://nightly.quilttest.com"
            mock_quilt_ops.get_auth_status.return_value = mock_auth_status
            mock_factory.create.return_value = mock_quilt_ops
            mock_factory_class.return_value = mock_factory

            result = _get_catalog_host_from_config()
            assert result == "nightly.quilttest.com"

    def test_get_catalog_host_with_no_navigator_url(self):
        """Test when config has no navigator_url - covers lines 79-85."""
        with patch('quilt_mcp.services.auth_metadata.QuiltOpsFactory') as mock_factory_class:
            mock_factory = Mock()
            mock_quilt_ops = Mock()
            mock_auth_status = Mock()
            mock_auth_status.logged_in_url = None
            mock_auth_status.navigator_url = None
            mock_quilt_ops.get_auth_status.return_value = mock_auth_status
            mock_factory.create.return_value = mock_quilt_ops
            mock_factory_class.return_value = mock_factory

            result = _get_catalog_host_from_config()
            assert result is None

    def test_get_catalog_host_with_none_config(self):
        """Test when get_config returns None - covers lines 79-80."""
        with patch('quilt_mcp.services.auth_metadata.QuiltOpsFactory') as mock_factory_class:
            mock_factory = Mock()
            mock_quilt_ops = Mock()
            mock_auth_status = Mock()
            mock_auth_status.logged_in_url = None
            mock_auth_status.navigator_url = None
            mock_quilt_ops.get_auth_status.return_value = mock_auth_status
            mock_factory.create.return_value = mock_quilt_ops
            mock_factory_class.return_value = mock_factory

            result = _get_catalog_host_from_config()
            assert result is None

    def test_get_catalog_host_with_empty_navigator_url(self):
        """Test when navigator_url is empty string - covers lines 82-85."""
        with patch('quilt_mcp.services.auth_metadata.QuiltOpsFactory') as mock_factory_class:
            mock_factory = Mock()
            mock_quilt_ops = Mock()
            mock_auth_status = Mock()
            mock_auth_status.logged_in_url = None
            mock_auth_status.navigator_url = ""
            mock_quilt_ops.get_auth_status.return_value = mock_auth_status
            mock_factory.create.return_value = mock_quilt_ops
            mock_factory_class.return_value = mock_factory

            result = _get_catalog_host_from_config()
            assert result is None

    def test_get_catalog_host_with_exception(self):
        """Test exception handling - covers lines 86-88."""
        with patch('quilt_mcp.services.auth_metadata.QuiltOpsFactory') as mock_factory_class:
            mock_factory = Mock()
            mock_factory.create.side_effect = Exception("Service error")
            mock_factory_class.return_value = mock_factory

            result = _get_catalog_host_from_config()
            assert result is None


class TestCatalogUrl:
    """Test catalog_url function - targeting missing exception handling lines 115-118, 162-163."""

    def test_catalog_url_success_package_view(self):
        """Test successful catalog URL generation for package view."""
        with patch('quilt_mcp.tools.catalog._get_catalog_host_from_config', return_value="demo.quiltdata.com"):
            result = catalog_url(registry="s3://test-bucket", package_name="user/package")

            assert isinstance(result, dict) or hasattr(result, 'status')
            assert result.success is True
            assert result.view_type == "package"
            assert "demo.quiltdata.com" in result.catalog_url
            assert result.bucket == "test-bucket"

    def test_catalog_url_success_bucket_view(self):
        """Test successful catalog URL generation for bucket view - covers lines 144-150."""
        with patch('quilt_mcp.tools.catalog._get_catalog_host_from_config', return_value="demo.quiltdata.com"):
            result = catalog_url(registry="s3://test-bucket")

            assert result.success is True
            assert result.view_type == "bucket"
            assert "demo.quiltdata.com" in result.catalog_url
            assert result.bucket == "test-bucket"

    def test_catalog_url_bucket_view_with_path(self):
        """Test bucket view with path - covers lines 144-150."""
        with patch('quilt_mcp.tools.catalog._get_catalog_host_from_config', return_value="demo.quiltdata.com"):
            result = catalog_url(registry="s3://test-bucket", path="data/files")

            assert result.success is True
            assert result.view_type == "bucket"
            assert "data" in result.catalog_url
            assert "files" in result.catalog_url

    def test_catalog_url_package_view_with_path(self):
        """Test package view with path - covers lines 138-139."""
        with patch('quilt_mcp.tools.catalog._get_catalog_host_from_config', return_value="demo.quiltdata.com"):
            result = catalog_url(registry="s3://test-bucket", package_name="user/package", path="data/files")

            assert result.success is True
            assert result.view_type == "package"
            assert "data" in result.catalog_url
            assert "files" in result.catalog_url

    def test_catalog_url_no_catalog_host_error(self):
        """Test error when catalog host cannot be determined - covers lines 115-118."""
        with patch('quilt_mcp.tools.catalog._get_catalog_host_from_config', return_value=None):
            result = catalog_url(registry="s3://test-bucket", package_name="user/package")

            assert result.success is False
            assert "Could not determine catalog host" in result.error

    def test_catalog_url_with_exception(self):
        """Test exception handling in catalog_url - covers lines 162-163."""
        with patch('quilt_mcp.tools.catalog._extract_bucket_from_registry', side_effect=Exception("Bucket error")):
            result = catalog_url(registry="s3://test-bucket", package_name="user/package")

            assert result.success is False
            assert "Failed to generate catalog URL" in result.error
            assert "Bucket error" in result.error


class TestCatalogUri:
    """Test catalog_uri function - targeting missing exception handling."""

    def test_catalog_uri_with_package_name(self):
        """Test catalog_uri with package name - covers lines 191-223."""
        with patch('quilt_mcp.tools.catalog._get_catalog_host_from_config', return_value="demo.quiltdata.com"):
            result = catalog_uri(registry="s3://test-bucket", package_name="user/package")

            assert result.success is True
            assert "quilt+s3://test-bucket" in result.quilt_plus_uri
            assert "package=user/package" in result.quilt_plus_uri
            assert "catalog=demo.quiltdata.com" in result.quilt_plus_uri

    def test_catalog_uri_with_top_hash(self):
        """Test catalog_uri with top_hash - covers lines 199-200."""
        with patch('quilt_mcp.tools.catalog._get_catalog_host_from_config', return_value="demo.quiltdata.com"):
            result = catalog_uri(registry="s3://test-bucket", package_name="user/package", top_hash="abc123")

            assert result.success is True
            assert "package=user/package@abc123" in result.quilt_plus_uri

    def test_catalog_uri_with_tag(self):
        """Test catalog_uri with tag - covers lines 201-202."""
        with patch('quilt_mcp.tools.catalog._get_catalog_host_from_config', return_value="demo.quiltdata.com"):
            result = catalog_uri(registry="s3://test-bucket", package_name="user/package", tag="v1.0")

            assert result.success is True
            assert "package=user/package:v1.0" in result.quilt_plus_uri

    def test_catalog_uri_with_path(self):
        """Test catalog_uri with path - covers lines 205-206."""
        with patch('quilt_mcp.tools.catalog._get_catalog_host_from_config', return_value="demo.quiltdata.com"):
            result = catalog_uri(registry="s3://test-bucket", package_name="user/package", path="data/file.csv")

            assert result.success is True
            assert "path=data/file.csv" in result.quilt_plus_uri

    def test_catalog_uri_no_catalog_host(self):
        """Test catalog_uri without catalog host - covers lines 209-215."""
        with patch('quilt_mcp.tools.catalog._get_catalog_host_from_config', return_value=None):
            result = catalog_uri(registry="s3://test-bucket", package_name="user/package")

            assert result.success is True
            # Should not contain catalog parameter when no host available
            assert "catalog=" not in result.quilt_plus_uri

    def test_catalog_uri_with_protocol_removal(self):
        """Test catalog_uri with protocol removal - covers lines 213-215."""
        with patch('quilt_mcp.tools.catalog._get_catalog_host_from_config', return_value="https://demo.quiltdata.com"):
            result = catalog_uri(registry="s3://test-bucket", package_name="user/package")

            assert result.success is True
            assert "catalog=demo.quiltdata.com" in result.quilt_plus_uri
            # Should not contain https:// in the catalog parameter
            assert "https://" not in result.quilt_plus_uri.split("catalog=")[1]

    def test_catalog_uri_bucket_only(self):
        """Test catalog_uri with bucket only (no package) - covers lines 191-223."""
        with patch('quilt_mcp.tools.catalog._get_catalog_host_from_config', return_value="demo.quiltdata.com"):
            result = catalog_uri(registry="s3://test-bucket")

            assert result.success is True
            assert "quilt+s3://test-bucket" in result.quilt_plus_uri
            assert "package=" not in result.quilt_plus_uri

    def test_catalog_uri_with_exception(self):
        """Test exception handling in catalog_uri - covers line 234-235."""
        with patch('quilt_mcp.tools.catalog._extract_bucket_from_registry', side_effect=Exception("URI error")):
            result = catalog_uri(registry="s3://test-bucket", package_name="user/package")

            assert result.success is False
            assert "Failed to generate Quilt+ URI" in result.error
            assert "URI error" in result.error


class TestConfigureCatalog:
    """Test configure_catalog function - targeting missing exception handling."""

    def test_configure_catalog_with_exception(self):
        """Test exception handling in configure_catalog - covers lines 564-581."""
        with patch('quilt_mcp.services.auth_metadata.QuiltOpsFactory', side_effect=Exception("Config error")):
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

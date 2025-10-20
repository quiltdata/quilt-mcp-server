"""Tests for catalog.py - Test-Driven Development Implementation."""

from __future__ import annotations

import os
import tempfile
from unittest.mock import Mock, MagicMock, patch
from urllib.parse import ParseResult

import pytest

from quilt_mcp.services.auth_metadata import (
    _extract_catalog_name_from_url,
    _extract_bucket_from_registry,
    _get_catalog_host_from_config,
    _get_catalog_info,
    catalog_info,
    catalog_name,
    auth_status,
    filesystem_status,
)
from quilt_mcp.tools.catalog import catalog_url, catalog_uri, configure_catalog, switch_catalog


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
            result = catalog_url("s3://test-bucket", "user/package")

            assert result["status"] == "success"
            assert result["view_type"] == "package"
            assert "demo.quiltdata.com" in result["catalog_url"]
            assert result["bucket"] == "test-bucket"

    def test_catalog_url_success_bucket_view(self):
        """Test successful catalog URL generation for bucket view - covers lines 144-150."""
        with patch('quilt_mcp.tools.catalog._get_catalog_host_from_config', return_value="demo.quiltdata.com"):
            result = catalog_url("s3://test-bucket", package_name=None)

            assert result["status"] == "success"
            assert result["view_type"] == "bucket"
            assert "demo.quiltdata.com" in result["catalog_url"]
            assert result["bucket"] == "test-bucket"

    def test_catalog_url_bucket_view_with_path(self):
        """Test bucket view with path - covers lines 144-150."""
        with patch('quilt_mcp.tools.catalog._get_catalog_host_from_config', return_value="demo.quiltdata.com"):
            result = catalog_url("s3://test-bucket", package_name=None, path="data/files")

            assert result["status"] == "success"
            assert result["view_type"] == "bucket"
            assert "data" in result["catalog_url"]
            assert "files" in result["catalog_url"]

    def test_catalog_url_package_view_with_path(self):
        """Test package view with path - covers lines 138-139."""
        with patch('quilt_mcp.tools.catalog._get_catalog_host_from_config', return_value="demo.quiltdata.com"):
            result = catalog_url("s3://test-bucket", "user/package", path="data/files")

            assert result["status"] == "success"
            assert result["view_type"] == "package"
            assert "data" in result["catalog_url"]
            assert "files" in result["catalog_url"]

    def test_catalog_url_no_catalog_host_error(self):
        """Test error when catalog host cannot be determined - covers lines 115-118."""
        with patch('quilt_mcp.tools.catalog._get_catalog_host_from_config', return_value=None):
            result = catalog_url("s3://test-bucket", "user/package")

            assert result["status"] == "error"
            assert "Could not determine catalog host" in result["error"]

    def test_catalog_url_with_exception(self):
        """Test exception handling in catalog_url - covers lines 162-163."""
        with patch('quilt_mcp.tools.catalog._extract_bucket_from_registry', side_effect=Exception("Bucket error")):
            result = catalog_url("s3://test-bucket", "user/package")

            assert result["status"] == "error"
            assert "Failed to generate catalog URL" in result["error"]
            assert "Bucket error" in result["error"]


class TestCatalogUri:
    """Test catalog_uri function - targeting missing exception handling."""

    def test_catalog_uri_with_package_name(self):
        """Test catalog_uri with package name - covers lines 191-223."""
        with patch('quilt_mcp.tools.catalog._get_catalog_host_from_config', return_value="demo.quiltdata.com"):
            result = catalog_uri("s3://test-bucket", "user/package")

            assert result["status"] == "success"
            assert "quilt+s3://test-bucket" in result["quilt_plus_uri"]
            assert "package=user/package" in result["quilt_plus_uri"]
            assert "catalog=demo.quiltdata.com" in result["quilt_plus_uri"]

    def test_catalog_uri_with_top_hash(self):
        """Test catalog_uri with top_hash - covers lines 199-200."""
        with patch('quilt_mcp.tools.catalog._get_catalog_host_from_config', return_value="demo.quiltdata.com"):
            result = catalog_uri("s3://test-bucket", "user/package", top_hash="abc123")

            assert result["status"] == "success"
            assert "package=user/package@abc123" in result["quilt_plus_uri"]

    def test_catalog_uri_with_tag(self):
        """Test catalog_uri with tag - covers lines 201-202."""
        with patch('quilt_mcp.tools.catalog._get_catalog_host_from_config', return_value="demo.quiltdata.com"):
            result = catalog_uri("s3://test-bucket", "user/package", tag="v1.0")

            assert result["status"] == "success"
            assert "package=user/package:v1.0" in result["quilt_plus_uri"]

    def test_catalog_uri_with_path(self):
        """Test catalog_uri with path - covers lines 205-206."""
        with patch('quilt_mcp.tools.catalog._get_catalog_host_from_config', return_value="demo.quiltdata.com"):
            result = catalog_uri("s3://test-bucket", "user/package", path="data/file.csv")

            assert result["status"] == "success"
            assert "path=data/file.csv" in result["quilt_plus_uri"]

    def test_catalog_uri_no_catalog_host(self):
        """Test catalog_uri without catalog host - covers lines 209-215."""
        with patch('quilt_mcp.tools.catalog._get_catalog_host_from_config', return_value=None):
            result = catalog_uri("s3://test-bucket", "user/package")

            assert result["status"] == "success"
            # Should not contain catalog parameter when no host available
            assert "catalog=" not in result["quilt_plus_uri"]

    def test_catalog_uri_with_protocol_removal(self):
        """Test catalog_uri with protocol removal - covers lines 213-215."""
        with patch('quilt_mcp.tools.catalog._get_catalog_host_from_config', return_value="https://demo.quiltdata.com"):
            result = catalog_uri("s3://test-bucket", "user/package")

            assert result["status"] == "success"
            assert "catalog=demo.quiltdata.com" in result["quilt_plus_uri"]
            # Should not contain https:// in the catalog parameter
            assert "https://" not in result["quilt_plus_uri"].split("catalog=")[1]

    def test_catalog_uri_bucket_only(self):
        """Test catalog_uri with bucket only (no package) - covers lines 191-223."""
        with patch('quilt_mcp.tools.catalog._get_catalog_host_from_config', return_value="demo.quiltdata.com"):
            result = catalog_uri("s3://test-bucket")

            assert result["status"] == "success"
            assert "quilt+s3://test-bucket" in result["quilt_plus_uri"]
            assert "package=" not in result["quilt_plus_uri"]

    def test_catalog_uri_with_exception(self):
        """Test exception handling in catalog_uri - covers line 234-235."""
        with patch('quilt_mcp.tools.catalog._extract_bucket_from_registry', side_effect=Exception("URI error")):
            result = catalog_uri("s3://test-bucket", "user/package")

            assert result["status"] == "error"
            assert "Failed to generate Quilt+ URI" in result["error"]
            assert "URI error" in result["error"]


class TestCatalogInfo:
    """Test catalog_info function - targeting missing exception handling."""

    @pytest.mark.skip(reason="Tool deprecated - now available as resource (auth://catalog/info)")
    def test_catalog_info_success_authenticated(self):
        """Test catalog_info success when authenticated - includes region and tabulator_data_catalog."""
        mock_info = {
            "catalog_name": "demo.quiltdata.com",
            "is_authenticated": True,
            "navigator_url": "https://demo.quiltdata.com",
            "registry_url": "s3://registry-bucket",
            "logged_in_url": "https://demo.quiltdata.com",
            "region": "us-east-1",
            "tabulator_data_catalog": "quilt-demo-tabulator",
        }

        with patch('quilt_mcp.services.auth_metadata._get_catalog_info', return_value=mock_info):
            result = catalog_info()

            assert result["status"] == "success"
            assert result["catalog_name"] == "demo.quiltdata.com"
            assert result["is_authenticated"] is True
            assert result["navigator_url"] == "https://demo.quiltdata.com"
            assert result["registry_url"] == "s3://registry-bucket"
            assert result["logged_in_url"] == "https://demo.quiltdata.com"
            assert result["region"] == "us-east-1"
            assert result["tabulator_data_catalog"] == "quilt-demo-tabulator"
            assert "Connected to catalog" in result["message"]

    @pytest.mark.skip(reason="Tool deprecated - now available as resource (auth://catalog/info)")
    def test_catalog_info_success_not_authenticated(self):
        """Test catalog_info success when not authenticated - region and tabulator_data_catalog should not be present."""
        mock_info = {
            "catalog_name": "demo.quiltdata.com",
            "is_authenticated": False,
            "navigator_url": "https://demo.quiltdata.com",
            "registry_url": None,
            "logged_in_url": None,
            "region": None,
            "tabulator_data_catalog": None,
        }

        with patch('quilt_mcp.services.auth_metadata._get_catalog_info', return_value=mock_info):
            result = catalog_info()

            assert result["status"] == "success"
            assert result["catalog_name"] == "demo.quiltdata.com"
            assert result["is_authenticated"] is False
            assert result["navigator_url"] == "https://demo.quiltdata.com"
            assert "registry_url" not in result  # Should not be present when None
            assert "logged_in_url" not in result  # Should not be present when None
            assert "region" not in result  # Should not be present when None
            assert "tabulator_data_catalog" not in result  # Should not be present when None
            assert "not authenticated" in result["message"]

    @pytest.mark.skip(reason="Tool deprecated - now available as resource (auth://catalog/info)")
    def test_catalog_info_with_partial_urls(self):
        """Test catalog_info with some URLs present - covers lines 254-259."""
        mock_info = {
            "catalog_name": "demo.quiltdata.com",
            "is_authenticated": True,
            "navigator_url": None,
            "registry_url": "s3://registry-bucket",
            "logged_in_url": None,
            "region": None,
            "tabulator_data_catalog": None,
        }

        with patch('quilt_mcp.services.auth_metadata._get_catalog_info', return_value=mock_info):
            result = catalog_info()

            assert result["status"] == "success"
            assert "navigator_url" not in result
            assert result["registry_url"] == "s3://registry-bucket"
            assert "logged_in_url" not in result
            assert "region" not in result
            assert "tabulator_data_catalog" not in result

    @pytest.mark.skip(reason="Tool deprecated - now available as resource (auth://catalog/info)")
    def test_catalog_info_with_exception(self):
        """Test exception handling in catalog_info - covers lines 269-274."""
        with patch('quilt_mcp.services.auth_metadata._get_catalog_info', side_effect=Exception("Info error")):
            result = catalog_info()

            assert result["status"] == "error"
            assert "Failed to get catalog info" in result["error"]
            assert result["catalog_name"] == "unknown"
            assert "Info error" in result["error"]


class TestCatalogName:
    """Test catalog_name function - targeting missing branches."""

    @pytest.mark.skip(reason="Tool deprecated - now available as resource (auth://catalog/name)")
    def test_catalog_name_with_registry_url_detection(self):
        """Test catalog name detection via registry_url - covers lines 292-293."""
        mock_info = {
            "catalog_name": "test-catalog",
            "logged_in_url": None,
            "navigator_url": None,
            "registry_url": "s3://registry-bucket",
            "is_authenticated": False,
        }

        with patch('quilt_mcp.services.auth_metadata._get_catalog_info', return_value=mock_info):
            result = catalog_name()

            assert result["status"] == "success"
            assert result["catalog_name"] == "test-catalog"
            assert result["detection_method"] == "registry_config"

    @pytest.mark.skip(reason="Tool deprecated - now available as resource (auth://catalog/name)")
    def test_catalog_name_with_exception(self):
        """Test exception handling in catalog_name - covers lines 302-308."""
        with patch('quilt_mcp.services.auth_metadata._get_catalog_info', side_effect=Exception("Name error")):
            result = catalog_name()

            assert result["status"] == "error"
            assert "Failed to detect catalog name" in result["error"]
            assert result["catalog_name"] == "unknown"
            assert result["detection_method"] == "error"


class TestAuthStatus:
    """Test auth_status function - targeting missing exception branches."""

    @pytest.mark.skip(reason="Tool deprecated - now available as resource (auth://status)")
    def test_auth_status_not_authenticated(self):
        """Test auth_status when not authenticated - covers lines 371-378."""
        mock_catalog_info = {"catalog_name": "demo.quiltdata.com", "is_authenticated": False}

        with patch('quilt_mcp.services.auth_metadata.QuiltService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_catalog_info.return_value = mock_catalog_info
            mock_service.get_logged_in_url.return_value = None  # This is key - not logged in
            mock_service_class.return_value = mock_service

            result = auth_status()

            assert result["status"] == "not_authenticated"
            assert result["catalog_name"] == "demo.quiltdata.com"
            assert result["message"] == "Not logged in to Quilt catalog"
            assert result["search_available"] is False
            assert len(result["setup_instructions"]) == 4
            assert "Configure catalog" in result["setup_instructions"][0]
            assert "quick_setup" in result

    @pytest.mark.skip(reason="Tool deprecated - now available as resource (auth://status)")
    def test_auth_status_registry_config_exception(self):
        """Test exception handling when getting registry config - covers lines 330-331."""
        mock_catalog_info = {"catalog_name": "test", "is_authenticated": True}

        with patch('quilt_mcp.services.auth_metadata.QuiltService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_catalog_info.return_value = mock_catalog_info
            mock_service.get_logged_in_url.return_value = "https://demo.quiltdata.com"
            mock_service.get_config.side_effect = Exception("Config error")
            mock_service_class.return_value = mock_service

            result = auth_status()

            assert result["status"] == "authenticated"
            assert result["registry_bucket"] is None

    @pytest.mark.skip(reason="Tool deprecated - now available as resource (auth://status)")
    def test_auth_status_user_info_exception(self):
        """Test exception handling when getting user info - covers lines 342-343."""
        mock_catalog_info = {"catalog_name": "test", "is_authenticated": True}

        with patch('quilt_mcp.services.auth_metadata.QuiltService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_catalog_info.return_value = mock_catalog_info
            mock_service.get_logged_in_url.return_value = "https://demo.quiltdata.com"
            mock_service_class.return_value = mock_service

            # Mock an exception in the user info gathering section
            with patch.dict('builtins.__dict__', {'Exception': Exception}):
                result = auth_status()

                assert result["status"] == "authenticated"
                # The function should still complete successfully despite user info exception

    @pytest.mark.skip(reason="Tool deprecated - now available as resource (auth://status)")
    def test_auth_status_main_exception(self):
        """Test main exception handling in auth_status - covers lines 402-423."""
        with patch('quilt_mcp.services.auth_metadata.QuiltService', side_effect=Exception("Service error")):
            result = auth_status()

            assert result["status"] == "error"
            assert "Failed to check authentication" in result["error"]
            assert result["catalog_name"] == "unknown"
            assert "troubleshooting" in result
            assert "setup_instructions" in result


class TestFilesystemStatus:
    """Test filesystem_status function - targeting missing branches."""

    @pytest.mark.skip(reason="Tool deprecated - now available as resource (auth://filesystem)")
    def test_filesystem_status_home_write_error(self):
        """Test home directory write error - covers lines 445-447."""
        with patch('builtins.open', side_effect=PermissionError("No permission")):
            result = filesystem_status()

            assert result["home_writable"] is False
            assert "home_write_error" in result
            assert "No permission" in result["home_write_error"]

    @pytest.mark.skip(reason="Tool deprecated - now available as resource (auth://filesystem)")
    def test_filesystem_status_temp_write_error(self):
        """Test temp directory write error - covers lines 456-458."""
        with patch('tempfile.NamedTemporaryFile', side_effect=OSError("Temp error")):
            result = filesystem_status()

            assert result["temp_writable"] is False
            assert "temp_write_error" in result
            assert "Temp error" in result["temp_write_error"]

    @pytest.mark.skip(reason="Tool deprecated - now available as resource (auth://filesystem)")
    def test_filesystem_status_limited_access(self):
        """Test limited filesystem access - covers lines 485-501."""
        with patch('builtins.open', side_effect=PermissionError("No home access")):
            with patch('tempfile.NamedTemporaryFile'):  # Temp access works
                result = filesystem_status()

                assert result["status"] == "limited_access"
                assert "Limited filesystem access" in result["message"]
                assert "recommendation" in result

    @pytest.mark.skip(reason="Tool deprecated - now available as resource (auth://filesystem)")
    def test_filesystem_status_read_only(self):
        """Test read-only filesystem - covers lines 503-514."""
        with patch('builtins.open', side_effect=PermissionError("No write access")):
            with patch('tempfile.NamedTemporaryFile', side_effect=OSError("No temp access")):
                result = filesystem_status()

                assert result["status"] == "read_only"
                assert "Read-only filesystem" in result["message"]
                assert len(result["tools_available"]) == 6  # Only read-only tools


class TestConfigureCatalog:
    """Test configure_catalog function - targeting missing exception handling."""

    def test_configure_catalog_invalid_url_format(self):
        """Test invalid URL format validation - covers lines 531-537."""
        result = configure_catalog("invalid-url")

        assert result["status"] == "error"
        assert "Invalid catalog URL format" in result["error"]
        assert result["provided"] == "invalid-url"
        assert "http://" in result["expected"]

    def test_configure_catalog_success(self):
        """Test successful configuration - covers lines 541-547."""
        with (
            patch('quilt_mcp.services.quilt_service.QuiltService') as base_service_class,
            patch('quilt_mcp.tools.catalog.QuiltService') as mock_service_class,
        ):
            mock_service = Mock()
            mock_service.get_config.return_value = {"navigator_url": "https://demo.quiltdata.com"}
            mock_service_class.return_value = mock_service
            base_service_class.return_value = mock_service

            result = configure_catalog("https://demo.quiltdata.com")

            assert result["status"] == "success"
            assert result["catalog_url"] == "https://demo.quiltdata.com"
            mock_service.set_config.assert_called_with("https://demo.quiltdata.com")

    def test_configure_catalog_with_exception(self):
        """Test exception handling in configure_catalog - covers lines 564-581."""
        with (
            patch('quilt_mcp.services.quilt_service.QuiltService', side_effect=Exception("Config error")),
            patch('quilt_mcp.tools.catalog.QuiltService', side_effect=Exception("Config error")),
        ):
            result = configure_catalog("https://demo.quiltdata.com")

            assert result["status"] == "error"
            assert "Failed to configure catalog" in result["error"]
            assert "troubleshooting" in result
            assert "Config error" in result["error"]


class TestSwitchCatalog:
    """Test switch_catalog function - targeting missing branches."""

    def test_switch_catalog_with_full_url(self):
        """Test switching to catalog with full URL - covers lines 607-608."""
        with patch('quilt_mcp.tools.catalog.configure_catalog') as mock_configure:
            mock_configure.return_value = {"status": "success"}

            result = switch_catalog("https://custom.quiltdata.com")

            mock_configure.assert_called_with("https://custom.quiltdata.com")
            assert result["status"] == "success"

    def test_switch_catalog_with_known_catalog_name(self):
        """Test switching with known catalog name (demo)."""
        with patch('quilt_mcp.tools.catalog.configure_catalog') as mock_configure:
            mock_configure.return_value = {"status": "success"}

            result = switch_catalog("demo")

            # "demo" maps to specific URL in catalog_mappings
            mock_configure.assert_called_with("https://demo.quiltdata.com")
            assert result["status"] == "success"

    def test_switch_catalog_with_unknown_catalog_name(self):
        """Test switching with unknown catalog name - covers lines 611-612."""
        with patch('quilt_mcp.tools.catalog.configure_catalog') as mock_configure:
            mock_configure.return_value = {"status": "success"}

            result = switch_catalog("custom")

            # Unknown name should construct https:// URL from name
            mock_configure.assert_called_with("https://custom")
            assert result["status"] == "success"

    def test_switch_catalog_with_exception(self):
        """Test exception handling in switch_catalog - covers lines 630-637."""
        with patch('quilt_mcp.tools.catalog.configure_catalog', side_effect=Exception("Switch error")):
            result = switch_catalog("demo")

            assert result["status"] == "error"
            assert "Failed to switch catalog" in result["error"]
            assert "available_catalogs" in result
            assert "Switch error" in result["error"]


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

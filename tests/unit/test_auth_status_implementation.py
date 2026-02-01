"""Test get_auth_status() implementation in Quilt3_Backend_Session."""

import pytest
from unittest.mock import Mock, MagicMock
from quilt_mcp.backends.quilt3_backend_session import Quilt3_Backend_Session
from quilt_mcp.domain.auth_status import Auth_Status
from quilt_mcp.utils import get_dns_name_from_url


class TestAuthStatusImplementation:
    """Test suite for get_auth_status() method."""

    @pytest.fixture
    def mock_backend(self):
        """Create a mock backend with necessary attributes."""
        backend = Quilt3_Backend_Session()
        backend.quilt3 = MagicMock()
        backend.requests = MagicMock()
        backend.boto3 = MagicMock()
        return backend

    def test_get_auth_status_when_authenticated(self, mock_backend):
        """Test get_auth_status returns correct status when user is authenticated."""
        # Setup mock
        from quilt_mcp.domain.catalog_config import Catalog_Config

        mock_backend.quilt3.logged_in.return_value = "https://example.quiltdata.com"

        # Mock get_catalog_config to return a Catalog_Config with registry URL
        mock_catalog_config = Catalog_Config(
            region="us-east-1",
            api_gateway_endpoint="https://api.example.com",
            registry_url="https://example-registry.quiltdata.com",  # HTTPS URL, not S3!
            analytics_bucket="my-analytics-bucket",
            stack_prefix="example",
            tabulator_data_catalog="quilt-example-tabulator",
        )
        mock_backend.get_catalog_config = Mock(return_value=mock_catalog_config)

        # Execute
        result = mock_backend.get_auth_status()

        # Verify
        assert isinstance(result, Auth_Status)
        assert result.is_authenticated is True
        assert result.logged_in_url == "https://example.quiltdata.com"
        assert result.catalog_name == "example.quiltdata.com"
        assert result.registry_url == "https://example-registry.quiltdata.com"  # HTTPS, not S3

    def test_get_auth_status_when_not_authenticated(self, mock_backend):
        """Test get_auth_status returns correct status when user is not authenticated."""
        # Setup mock - logged_in returns None
        mock_backend.quilt3.logged_in.return_value = None

        # Execute
        result = mock_backend.get_auth_status()

        # Verify
        assert isinstance(result, Auth_Status)
        assert result.is_authenticated is False
        assert result.logged_in_url is None
        assert result.catalog_name is None
        assert result.registry_url is None

    def test_get_auth_status_handles_logged_in_exception(self, mock_backend):
        """Test get_auth_status handles exceptions from logged_in()."""
        # Setup mock - logged_in raises exception
        mock_backend.quilt3.logged_in.side_effect = Exception("Auth error")

        # Execute
        result = mock_backend.get_auth_status()

        # Verify - should treat as not authenticated
        assert isinstance(result, Auth_Status)
        assert result.is_authenticated is False
        assert result.logged_in_url is None

    def test_get_auth_status_handles_catalog_config_exception(self, mock_backend):
        """Test get_auth_status handles exceptions from get_catalog_config()."""
        # Setup mock
        mock_backend.quilt3.logged_in.return_value = "https://example.quiltdata.com"
        mock_backend.get_catalog_config = Mock(side_effect=Exception("Catalog config error"))

        # Execute
        result = mock_backend.get_auth_status()

        # Verify - should still be authenticated but without registry URL
        assert isinstance(result, Auth_Status)
        assert result.is_authenticated is True
        assert result.logged_in_url == "https://example.quiltdata.com"
        assert result.registry_url is None

    def test_get_dns_name_from_url_simple_hostname(self):
        """Test get_dns_name_from_url extracts hostname correctly."""
        result = get_dns_name_from_url("https://nightly.quilttest.com")
        assert result == "nightly.quilttest.com"

    def test_get_dns_name_from_url_removes_www(self):
        """Test get_dns_name_from_url removes www prefix."""
        result = get_dns_name_from_url("https://www.example.com")
        assert result == "example.com"

    def test_get_dns_name_from_url_empty_string(self):
        """Test get_dns_name_from_url handles empty string."""
        result = get_dns_name_from_url("")
        assert result == "unknown"

    def test_get_dns_name_from_url_invalid_url(self):
        """Test get_dns_name_from_url handles invalid URLs gracefully."""
        result = get_dns_name_from_url("not a url")
        # Should return "unknown" or the netloc part depending on parsing
        assert isinstance(result, str)

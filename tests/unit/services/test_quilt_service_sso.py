"""Tests for QuiltService SSO configuration operations (Phase 3.2).

This module tests SSO configuration operations (get, set, remove), ensuring
proper error handling when admin modules are unavailable.
"""

from unittest.mock import Mock, patch
import pytest

from quilt_mcp.services.quilt_service import QuiltService
from quilt_mcp.services.exceptions import AdminNotAvailableError


class TestGetSSOConfig:
    """Test get_sso_config() method."""

    def test_get_sso_config_returns_config_string_when_configured(self):
        """Test that get_sso_config() returns config string when SSO is configured."""
        service = QuiltService()

        # Mock SSO admin module with a get() method that returns config
        mock_sso_module = Mock()
        mock_sso_module.get.return_value = "saml:\n  provider: okta\n  issuer: https://example.okta.com"

        with patch.object(service, '_get_sso_admin_module', return_value=mock_sso_module):
            config = service.get_sso_config()

            # Verify it's a string with expected content
            assert isinstance(config, str)
            assert "saml:" in config
            mock_sso_module.get.assert_called_once()

    def test_get_sso_config_returns_none_when_not_configured(self):
        """Test that get_sso_config() returns None when SSO is not configured."""
        service = QuiltService()

        # Mock SSO admin module with get() returning None
        mock_sso_module = Mock()
        mock_sso_module.get.return_value = None

        with patch.object(service, '_get_sso_admin_module', return_value=mock_sso_module):
            config = service.get_sso_config()

            # Verify None is returned
            assert config is None
            mock_sso_module.get.assert_called_once()

    def test_get_sso_config_raises_admin_not_available(self):
        """Test that get_sso_config() raises AdminNotAvailableError when admin unavailable."""
        service = QuiltService()

        # Mock is_admin_available to return False
        with patch.object(service, 'is_admin_available', return_value=False):
            with pytest.raises(AdminNotAvailableError) as exc_info:
                service.get_sso_config()

            # Verify error message is descriptive
            assert "Admin operations not available" in str(exc_info.value)


class TestSetSSOConfig:
    """Test set_sso_config() method."""

    def test_set_sso_config_returns_success_dict(self):
        """Test that set_sso_config() returns success dict with config details."""
        service = QuiltService()

        config_text = "saml:\n  provider: okta\n  issuer: https://example.okta.com"

        # Mock SSO admin module with a set() method
        mock_sso_module = Mock()
        mock_sso_module.set.return_value = {"status": "success", "config": config_text}

        with patch.object(service, '_get_sso_admin_module', return_value=mock_sso_module):
            result = service.set_sso_config(config_text)

            # Verify it's a dict with expected structure
            assert isinstance(result, dict)
            assert "status" in result or "success" in result or "config" in result
            mock_sso_module.set.assert_called_once_with(config_text)

    def test_set_sso_config_raises_admin_not_available(self):
        """Test that set_sso_config() raises AdminNotAvailableError when admin unavailable."""
        service = QuiltService()

        config_text = "saml:\n  provider: okta"

        # Mock is_admin_available to return False
        with patch.object(service, 'is_admin_available', return_value=False):
            with pytest.raises(AdminNotAvailableError) as exc_info:
                service.set_sso_config(config_text)

            # Verify error message is descriptive
            assert "Admin operations not available" in str(exc_info.value)

    def test_set_sso_config_with_empty_string(self):
        """Test that set_sso_config() handles empty string config."""
        service = QuiltService()

        # Mock SSO admin module
        mock_sso_module = Mock()
        mock_sso_module.set.return_value = {"status": "success", "config": ""}

        with patch.object(service, '_get_sso_admin_module', return_value=mock_sso_module):
            result = service.set_sso_config("")

            # Should still call the module and return result
            mock_sso_module.set.assert_called_once_with("")
            assert isinstance(result, dict)

    def test_set_sso_config_fallback_when_module_returns_none(self):
        """Test that set_sso_config() creates fallback dict when module returns None."""
        service = QuiltService()

        config_text = "saml:\n  provider: okta"

        # Mock SSO admin module returning None
        mock_sso_module = Mock()
        mock_sso_module.set.return_value = None

        with patch.object(service, '_get_sso_admin_module', return_value=mock_sso_module):
            result = service.set_sso_config(config_text)

            # Should return fallback dict
            assert isinstance(result, dict)
            assert result["status"] == "success"
            assert result["config"] == config_text


class TestRemoveSSOConfig:
    """Test remove_sso_config() method."""

    def test_remove_sso_config_returns_success_dict(self):
        """Test that remove_sso_config() returns success dict."""
        service = QuiltService()

        # Mock SSO admin module with a remove() method
        mock_sso_module = Mock()
        mock_sso_module.remove.return_value = {"status": "success", "message": "SSO config removed"}

        with patch.object(service, '_get_sso_admin_module', return_value=mock_sso_module):
            result = service.remove_sso_config()

            # Verify it's a dict with expected structure
            assert isinstance(result, dict)
            assert "status" in result or "success" in result or "message" in result
            mock_sso_module.remove.assert_called_once()

    def test_remove_sso_config_raises_admin_not_available(self):
        """Test that remove_sso_config() raises AdminNotAvailableError when admin unavailable."""
        service = QuiltService()

        # Mock is_admin_available to return False
        with patch.object(service, 'is_admin_available', return_value=False):
            with pytest.raises(AdminNotAvailableError) as exc_info:
                service.remove_sso_config()

            # Verify error message is descriptive
            assert "Admin operations not available" in str(exc_info.value)

    def test_remove_sso_config_when_not_configured(self):
        """Test that remove_sso_config() handles case when SSO not configured."""
        service = QuiltService()

        # Mock SSO admin module - remove should still work
        mock_sso_module = Mock()
        mock_sso_module.remove.return_value = {"status": "success", "message": "No config to remove"}

        with patch.object(service, '_get_sso_admin_module', return_value=mock_sso_module):
            result = service.remove_sso_config()

            # Should still call remove and return result
            mock_sso_module.remove.assert_called_once()
            assert isinstance(result, dict)

    def test_remove_sso_config_fallback_when_module_returns_none(self):
        """Test that remove_sso_config() creates fallback dict when module returns None."""
        service = QuiltService()

        # Mock SSO admin module returning None
        mock_sso_module = Mock()
        mock_sso_module.remove.return_value = None

        with patch.object(service, '_get_sso_admin_module', return_value=mock_sso_module):
            result = service.remove_sso_config()

            # Should return fallback dict
            assert isinstance(result, dict)
            assert result["status"] == "success"
            assert "message" in result


class TestGetSSOAdminModuleHelper:
    """Test _get_sso_admin_module() helper method."""

    def test_get_sso_admin_module_returns_module_when_available(self):
        """Test that _get_sso_admin_module() returns module when admin is available."""
        service = QuiltService()

        # Mock is_admin_available to return True
        with patch.object(service, 'is_admin_available', return_value=True):
            # Mock the quilt3.admin.sso_config module
            with patch('quilt3.admin.sso_config') as mock_sso:
                result = service._get_sso_admin_module()

                # Verify we got the mocked module
                assert result == mock_sso

    def test_get_sso_admin_module_raises_when_unavailable(self):
        """Test that _get_sso_admin_module() raises AdminNotAvailableError when unavailable."""
        service = QuiltService()

        # Mock is_admin_available to return False
        with patch.object(service, 'is_admin_available', return_value=False):
            with pytest.raises(AdminNotAvailableError):
                service._get_sso_admin_module()

    def test_get_sso_admin_module_includes_context_in_error(self):
        """Test that _get_sso_admin_module() includes SSO context in error message."""
        service = QuiltService()

        # Mock is_admin_available to return False
        with patch.object(service, 'is_admin_available', return_value=False):
            with pytest.raises(AdminNotAvailableError) as exc_info:
                service._get_sso_admin_module()

            # Error message should mention SSO operations
            error_msg = str(exc_info.value)
            assert "SSO" in error_msg or "sso" in error_msg or "Admin" in error_msg

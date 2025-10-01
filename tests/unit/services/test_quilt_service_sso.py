"""Tests for QuiltService SSO configuration operations (Phase 3.2).

This module tests SSO configuration operations (get, set, remove), ensuring
proper error handling when admin modules are unavailable.
"""

from unittest.mock import Mock, patch
import pytest

from quilt_mcp.services.quilt_service import QuiltService


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
        """Test that set_sso_config() returns None when module returns None."""
        service = QuiltService()

        config_text = "saml:\n  provider: okta"

        # Mock SSO admin module returning None
        mock_sso_module = Mock()
        mock_sso_config_object = None
        mock_sso_module.set.return_value = mock_sso_config_object

        with patch.object(service, '_get_sso_admin_module', return_value=mock_sso_module):
            result = service.set_sso_config(config_text)

            # Should return None (matches new implementation that returns object directly)
            assert result is None


class TestRemoveSSOConfig:
    """Test remove_sso_config() method."""

    def test_remove_sso_config_returns_success_dict(self):
        """Test that remove_sso_config() calls set(None) and returns result."""
        service = QuiltService()

        # Mock SSO admin module with a set() method that's called with None
        mock_sso_module = Mock()
        mock_sso_module.set.return_value = {"status": "success", "message": "SSO config removed"}

        with patch.object(service, '_get_sso_admin_module', return_value=mock_sso_module):
            result = service.remove_sso_config()

            # Verify set was called with None
            mock_sso_module.set.assert_called_once_with(None)
            # Result can be dict or object, depending on what module returns
            assert result is not None


    def test_remove_sso_config_when_not_configured(self):
        """Test that remove_sso_config() handles case when SSO not configured."""
        service = QuiltService()

        # Mock SSO admin module - set(None) should still work
        mock_sso_module = Mock()
        mock_sso_module.set.return_value = {"status": "success", "message": "No config to remove"}

        with patch.object(service, '_get_sso_admin_module', return_value=mock_sso_module):
            result = service.remove_sso_config()

            # Should call set with None and return result
            mock_sso_module.set.assert_called_once_with(None)
            assert result is not None

    def test_remove_sso_config_fallback_when_module_returns_none(self):
        """Test that remove_sso_config() returns None when module returns None."""
        service = QuiltService()

        # Mock SSO admin module returning None
        mock_sso_module = Mock()
        mock_sso_module.set.return_value = None

        with patch.object(service, '_get_sso_admin_module', return_value=mock_sso_module):
            result = service.remove_sso_config()

            # Should call set with None and return whatever it returns (None in this case)
            mock_sso_module.set.assert_called_once_with(None)
            assert result is None


class TestGetSSOAdminModuleHelper:
    """Test _get_sso_admin_module() helper method."""




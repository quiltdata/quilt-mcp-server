"""Tests for auth tools.

This test file covers the auth tools in the tools layer including:
- auth_status function uses operations layer instead of direct quilt3 calls
- Configuration loading from environment via Quilt3Config
- No direct quilt3.logged_in() or quilt3.config() calls in tools layer
- Backward compatibility - same behavior as before

Following BDD (Behavior-Driven Development) principles:
- Tests describe expected behavior from user perspective
- Tests cover integration between tools layer and operations layer
- Tests validate that tools layer is decoupled from direct quilt3 calls
- Tests ensure backward compatibility is maintained
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
from typing import Any, Dict


class TestAuthStatusToolsLayerDecoupling:
    """Test that auth_status tool is properly decoupled from direct quilt3 calls."""

    def test_auth_status_does_not_call_quilt3_directly(self):
        """auth_status tool should not call quilt3.logged_in() or quilt3.config() directly."""
        from quilt_mcp.tools.auth import auth_status

        # Mock the operations layer function
        with patch('quilt_mcp.operations.quilt3.auth.check_auth_status') as mock_check_auth:
            mock_check_auth.return_value = {"status": "not_authenticated", "catalog_name": "test"}

            # Mock quilt3 functions to ensure they're NOT called by the tool
            with patch('quilt3.logged_in') as mock_logged_in, \
                 patch('quilt3.config') as mock_config:

                result = auth_status()

                # The tool should NOT call these directly
                mock_logged_in.assert_not_called()
                mock_config.assert_not_called()

                # The tool SHOULD call the operations layer
                mock_check_auth.assert_called_once()

                assert isinstance(result, dict)

    def test_auth_status_loads_config_from_environment(self):
        """auth_status tool should load configuration from Quilt3Config.from_environment()."""
        from quilt_mcp.tools.auth import auth_status

        # Mock the config loading
        with patch('quilt_mcp.config.quilt3.Quilt3Config.from_environment') as mock_from_env:
            mock_config = MagicMock()
            mock_config.registry_url = "s3://test-bucket"
            mock_config.catalog_url = "https://test-catalog.com"
            mock_from_env.return_value = mock_config

            # Mock the operations layer
            with patch('quilt_mcp.operations.quilt3.auth.check_auth_status') as mock_check_auth:
                mock_check_auth.return_value = {"status": "not_authenticated"}

                result = auth_status()

                # Should load config from environment
                mock_from_env.assert_called_once()

                # Should pass config to operations layer
                mock_check_auth.assert_called_once_with(
                    registry_url="s3://test-bucket",
                    catalog_url="https://test-catalog.com"
                )

    def test_auth_status_handles_missing_config_gracefully(self):
        """auth_status tool should handle missing configuration gracefully."""
        from quilt_mcp.tools.auth import auth_status

        # Mock config with None values
        with patch('quilt_mcp.config.quilt3.Quilt3Config.from_environment') as mock_from_env:
            mock_config = MagicMock()
            mock_config.registry_url = None
            mock_config.catalog_url = None
            mock_from_env.return_value = mock_config

            # Mock operations layer
            with patch('quilt_mcp.operations.quilt3.auth.check_auth_status') as mock_check_auth:
                mock_check_auth.return_value = {"status": "error", "error": "No configuration"}

                result = auth_status()

                # Should still call operations layer with None values
                mock_check_auth.assert_called_once_with(
                    registry_url=None,
                    catalog_url=None
                )

                assert isinstance(result, dict)


class TestAuthStatusBackwardCompatibility:
    """Test that auth_status maintains backward compatibility."""

    def test_auth_status_returns_same_format_as_before(self):
        """auth_status should return the same format as before the refactoring."""
        from quilt_mcp.tools.auth import auth_status

        # Mock operations layer to return expected format
        expected_response = {
            "status": "authenticated",
            "catalog_url": "https://catalog.example.com",
            "catalog_name": "catalog.example.com",
            "registry_bucket": "test-bucket",
            "message": "Successfully authenticated"
        }

        with patch('quilt_mcp.operations.quilt3.auth.check_auth_status') as mock_check_auth:
            mock_check_auth.return_value = expected_response

            with patch('quilt_mcp.config.quilt3.Quilt3Config.from_environment'):
                result = auth_status()

                # Should return exactly what operations layer returns
                assert result == expected_response

    def test_auth_status_preserves_all_response_fields(self):
        """auth_status should preserve all response fields from operations layer."""
        from quilt_mcp.tools.auth import auth_status

        # Mock a comprehensive response
        comprehensive_response = {
            "status": "authenticated",
            "catalog_url": "https://catalog.example.com",
            "catalog_name": "catalog.example.com",
            "registry_bucket": "test-bucket",
            "write_permissions": "unknown",
            "user_info": {"username": "test", "email": "test@example.com"},
            "suggested_actions": ["action1", "action2"],
            "message": "test message",
            "search_available": True,
            "next_steps": {"immediate": "test"}
        }

        with patch('quilt_mcp.operations.quilt3.auth.check_auth_status') as mock_check_auth:
            mock_check_auth.return_value = comprehensive_response

            with patch('quilt_mcp.config.quilt3.Quilt3Config.from_environment'):
                result = auth_status()

                # All fields should be preserved
                for key, value in comprehensive_response.items():
                    assert result[key] == value


class TestAuthStatusIntegration:
    """Test auth_status integration with configuration and operations layers."""

    def test_auth_status_full_integration_flow(self):
        """Test the complete flow from tool → config → operations → response."""
        from quilt_mcp.tools.auth import auth_status

        # Mock environment config
        with patch.dict('os.environ', {
            'QUILT_REGISTRY_URL': 's3://env-bucket',
            'QUILT_CATALOG_URL': 'https://env-catalog.com'
        }):
            # Mock operations layer response
            expected_response = {"status": "not_authenticated", "catalog_name": "env-catalog.com"}
            with patch('quilt_mcp.operations.quilt3.auth.check_auth_status') as mock_check_auth:
                mock_check_auth.return_value = expected_response

                result = auth_status()

                # Should pass environment config to operations layer
                mock_check_auth.assert_called_once_with(
                    registry_url='s3://env-bucket',
                    catalog_url='https://env-catalog.com'
                )

                # Should return operations layer response
                assert result == expected_response

    def test_auth_status_error_handling_from_operations_layer(self):
        """auth_status should properly handle errors from operations layer."""
        from quilt_mcp.tools.auth import auth_status

        # Mock operations layer to raise an exception
        with patch('quilt_mcp.operations.quilt3.auth.check_auth_status') as mock_check_auth:
            mock_check_auth.side_effect = Exception("Operations error")

            with patch('quilt_mcp.config.quilt3.Quilt3Config.from_environment'):
                # Should handle the error gracefully
                result = auth_status()

                # Should return an error response (implementation will determine format)
                assert isinstance(result, dict)
                # Specific error handling format will be determined by implementation
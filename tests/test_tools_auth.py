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

        # Mock config object
        mock_config = MagicMock()
        mock_config.registry_url = "s3://test-bucket"
        mock_config.catalog_url = "https://test-catalog.com"

        with patch('quilt_mcp.config.quilt3.Quilt3Config.from_environment') as mock_from_env, \
             patch('quilt_mcp.operations.quilt3.auth.check_auth_status') as mock_check_auth:

            mock_from_env.return_value = mock_config
            mock_check_auth.return_value = {"status": "not_authenticated", "catalog_name": "test"}

            result = auth_status()

            # The tool SHOULD call the operations layer
            mock_check_auth.assert_called_once_with(
                registry_url="s3://test-bucket",
                catalog_url="https://test-catalog.com"
            )

            assert isinstance(result, dict)

    def test_auth_status_loads_config_from_environment(self):
        """auth_status tool should load configuration from Quilt3Config.from_environment()."""
        from quilt_mcp.tools.auth import auth_status

        # Mock the config loading
        mock_config = MagicMock()
        mock_config.registry_url = "s3://test-bucket"
        mock_config.catalog_url = "https://test-catalog.com"

        with patch('quilt_mcp.config.quilt3.Quilt3Config.from_environment') as mock_from_env, \
             patch('quilt_mcp.operations.quilt3.auth.check_auth_status') as mock_check_auth, \
             patch('quilt_mcp.operations.quilt3.auth.quilt3.logged_in') as mock_logged_in, \
             patch('quilt_mcp.operations.quilt3.auth.quilt3.config') as mock_quilt_config:

            mock_from_env.return_value = mock_config
            mock_check_auth.return_value = {"status": "not_authenticated"}
            mock_logged_in.return_value = None
            mock_quilt_config.return_value = None

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
        mock_config = MagicMock()
        mock_config.registry_url = None
        mock_config.catalog_url = None

        with patch('quilt_mcp.config.quilt3.Quilt3Config.from_environment') as mock_from_env, \
             patch('quilt_mcp.operations.quilt3.auth.check_auth_status') as mock_check_auth, \
             patch('quilt_mcp.operations.quilt3.auth.quilt3.logged_in') as mock_logged_in, \
             patch('quilt_mcp.operations.quilt3.auth.quilt3.config') as mock_quilt_config:

            mock_from_env.return_value = mock_config
            mock_check_auth.return_value = {"status": "error", "error": "No configuration"}
            mock_logged_in.return_value = None
            mock_quilt_config.return_value = None

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

        # Properly mock the config object
        mock_config = MagicMock()
        mock_config.registry_url = "s3://test-bucket"
        mock_config.catalog_url = "https://catalog.example.com"

        with patch('quilt_mcp.config.quilt3.Quilt3Config.from_environment') as mock_from_env, \
             patch('quilt_mcp.operations.quilt3.auth.quilt3.logged_in') as mock_logged_in, \
             patch('quilt_mcp.operations.quilt3.auth.quilt3.config') as mock_quilt_config:

            mock_from_env.return_value = mock_config
            mock_logged_in.return_value = "https://catalog.example.com"
            mock_quilt_config.return_value = None

            result = auth_status()

            # Should return expected format
            assert result["status"] == "authenticated"
            assert "catalog_url" in result
            assert "catalog_name" in result
            assert "message" in result

    def test_auth_status_preserves_all_response_fields(self):
        """auth_status should preserve all response fields from operations layer."""
        from quilt_mcp.tools.auth import auth_status

        # Properly mock the config object
        mock_config = MagicMock()
        mock_config.registry_url = "s3://test-bucket"
        mock_config.catalog_url = "https://catalog.example.com"

        with patch('quilt_mcp.config.quilt3.Quilt3Config.from_environment') as mock_from_env, \
             patch('quilt_mcp.operations.quilt3.auth.quilt3.logged_in') as mock_logged_in, \
             patch('quilt_mcp.operations.quilt3.auth.quilt3.config') as mock_quilt_config:

            mock_from_env.return_value = mock_config
            mock_logged_in.return_value = "https://catalog.example.com"
            mock_quilt_config.return_value = None

            result = auth_status()

            # Should return authenticated response with expected fields
            assert result["status"] == "authenticated"
            assert "catalog_url" in result
            assert "catalog_name" in result
            assert "registry_bucket" in result
            assert "message" in result


class TestAuthStatusIntegration:
    """Test auth_status integration with configuration and operations layers."""

    def test_auth_status_full_integration_flow(self):
        """Test the complete flow from tool → config → operations → response."""
        from quilt_mcp.tools.auth import auth_status

        # Mock config with environment values
        mock_config = MagicMock()
        mock_config.registry_url = 's3://env-bucket'
        mock_config.catalog_url = 'https://env-catalog.com'

        with patch('quilt_mcp.config.quilt3.Quilt3Config.from_environment') as mock_from_env, \
             patch('quilt_mcp.operations.quilt3.auth.quilt3.logged_in') as mock_logged_in, \
             patch('quilt_mcp.operations.quilt3.auth.quilt3.config') as mock_quilt_config:

            mock_from_env.return_value = mock_config
            mock_logged_in.return_value = None  # Not authenticated
            mock_quilt_config.return_value = None

            result = auth_status()

            # Should return not authenticated status
            assert result["status"] == "not_authenticated"
            assert "catalog_name" in result

    def test_auth_status_error_handling_from_operations_layer(self):
        """auth_status should properly handle errors from operations layer."""
        from quilt_mcp.tools.auth import auth_status

        # Mock operations layer to raise an exception
        with patch('quilt_mcp.operations.quilt3.auth.check_auth_status') as mock_check_auth:
            mock_check_auth.side_effect = Exception("Operations error")

            # Mock config object
            mock_config = MagicMock()
            mock_config.registry_url = "s3://test-bucket"
            mock_config.catalog_url = "https://test-catalog.com"

            with patch('quilt_mcp.config.quilt3.Quilt3Config.from_environment') as mock_from_env:
                mock_from_env.return_value = mock_config

                # Should handle the error gracefully
                result = auth_status()

                # Should return an error response
                assert isinstance(result, dict)
                assert result["status"] == "error"
                assert "Failed to check authentication" in result["error"]
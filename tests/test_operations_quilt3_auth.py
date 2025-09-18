"""Tests for Quilt3 auth operations.

This test file covers the isolated Quilt3 auth operations including:
- check_auth_status function with registry and catalog URL parameters
- Configuration-driven execution with different registry/catalog combinations
- Same output format as existing auth_status tool for backward compatibility
- No dependency on tools layer - this is the operations layer

Following BDD (Behavior-Driven Development) principles:
- Tests describe expected behavior from user perspective
- Tests cover all business scenarios and edge cases
- Tests validate the public API contracts without implementation details
- Tests ensure function can be called with different configurations independently
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
from typing import Any, Dict


class TestCheckAuthStatusFunctionExists:
    """Test that check_auth_status function can be imported and called."""

    def test_check_auth_status_can_be_imported(self):
        """check_auth_status function should be importable from operations.quilt3.auth."""
        from quilt_mcp.operations.quilt3.auth import check_auth_status

        assert check_auth_status is not None
        assert callable(check_auth_status)

    def test_check_auth_status_accepts_required_parameters(self):
        """check_auth_status should accept registry_url and optional catalog_url parameters."""
        from quilt_mcp.operations.quilt3.auth import check_auth_status

        # Mock quilt3.logged_in to avoid actual network calls during testing
        with patch('quilt3.logged_in') as mock_logged_in:
            mock_logged_in.return_value = None  # Simulate not logged in

            # Should accept registry_url (required) and catalog_url (optional)
            result = check_auth_status(registry_url="s3://test-bucket", catalog_url=None)
            assert isinstance(result, dict)

            # Should also work with catalog_url provided
            result = check_auth_status(registry_url="s3://test-bucket", catalog_url="https://catalog.example.com")
            assert isinstance(result, dict)


class TestCheckAuthStatusParameterUsage:
    """Test that check_auth_status uses provided parameters correctly."""

    def test_check_auth_status_uses_provided_registry_url_in_response(self):
        """check_auth_status should incorporate the provided registry_url in its response."""
        from quilt_mcp.operations.quilt3.auth import check_auth_status

        with patch('quilt3.logged_in') as mock_logged_in:
            mock_logged_in.return_value = "https://catalog.example.com"

            result = check_auth_status(registry_url="s3://provided-bucket", catalog_url=None)

            # Should use the provided registry_url
            assert result.get("registry_bucket") == "provided-bucket"

    def test_check_auth_status_uses_provided_catalog_url_in_response(self):
        """check_auth_status should use the provided catalog_url when available."""
        from quilt_mcp.operations.quilt3.auth import check_auth_status

        with patch('quilt3.logged_in') as mock_logged_in:
            mock_logged_in.return_value = "https://different-catalog.com"

            result = check_auth_status(
                registry_url="s3://test-bucket",
                catalog_url="https://provided-catalog.com"
            )

            # Should use the provided catalog_url, not the logged_in one
            assert result.get("catalog_url") == "https://provided-catalog.com"
            assert "provided-catalog.com" in result.get("catalog_name", "")

    def test_check_auth_status_can_be_called_with_different_configs_independently(self):
        """check_auth_status should handle different configs independently without state pollution."""
        from quilt_mcp.operations.quilt3.auth import check_auth_status

        with patch('quilt3.logged_in') as mock_logged_in:
            mock_logged_in.return_value = None  # Not logged in

            # Call with first config
            result1 = check_auth_status(registry_url="s3://bucket-1", catalog_url="https://catalog1.example.com")

            # Call with second config
            result2 = check_auth_status(registry_url="s3://bucket-2", catalog_url="https://catalog2.example.com")

            # Results should be independent and reflect their respective configs
            assert result1.get("catalog_name") != result2.get("catalog_name")
            assert "catalog1.example.com" in result1.get("catalog_name", "")
            assert "catalog2.example.com" in result2.get("catalog_name", "")


class TestCheckAuthStatusReturnFormat:
    """Test check_auth_status return format matches existing auth_status tool."""

    def test_check_auth_status_returns_dict_with_status_field(self):
        """check_auth_status should return a dict with a status field like existing auth_status tool."""
        from quilt_mcp.operations.quilt3.auth import check_auth_status

        with patch('quilt3.logged_in') as mock_logged_in:
            mock_logged_in.return_value = None

            result = check_auth_status(registry_url="s3://test-bucket", catalog_url=None)

            assert isinstance(result, dict)
            assert "status" in result
            # Status should be one of the expected values from existing auth_status
            assert result["status"] in ["authenticated", "not_authenticated", "error"]

    def test_check_auth_status_authenticated_response_has_required_fields(self):
        """When authenticated, check_auth_status should return same fields as existing auth_status tool."""
        from quilt_mcp.operations.quilt3.auth import check_auth_status

        # Mock quilt3 to simulate authenticated state
        with patch('quilt_mcp.operations.quilt3.auth.quilt3.logged_in') as mock_logged_in, \
             patch('quilt_mcp.operations.quilt3.auth.quilt3.config') as mock_config:

            mock_logged_in.return_value = "https://catalog.example.com"
            mock_config.return_value = None  # config() doesn't return anything meaningful

            result = check_auth_status(registry_url="s3://test-bucket", catalog_url="https://catalog.example.com")

            # Should match existing auth_status format for authenticated users
            assert result["status"] == "authenticated"
            assert "catalog_url" in result
            assert "catalog_name" in result
            assert "message" in result
            assert "registry_bucket" in result

    def test_check_auth_status_not_authenticated_response_has_required_fields(self):
        """When not authenticated, check_auth_status should return same fields as existing auth_status tool."""
        from quilt_mcp.operations.quilt3.auth import check_auth_status

        # Mock quilt3 to simulate not authenticated state
        with patch('quilt3.logged_in') as mock_logged_in:
            mock_logged_in.return_value = None  # Not logged in

            result = check_auth_status(registry_url="s3://test-bucket", catalog_url=None)

            # Should match existing auth_status format for non-authenticated users
            assert result["status"] == "not_authenticated"
            assert "catalog_name" in result
            assert "message" in result
            # Should include setup instructions like existing tool
            assert "setup_instructions" in result

    def test_check_auth_status_error_response_has_required_fields(self):
        """When an error occurs, check_auth_status should return same error format as existing auth_status tool."""
        from quilt_mcp.operations.quilt3.auth import check_auth_status

        # Mock quilt3 to simulate an error
        with patch('quilt3.logged_in') as mock_logged_in:
            mock_logged_in.side_effect = Exception("Network error")

            result = check_auth_status(registry_url="s3://test-bucket", catalog_url=None)

            # Should match existing auth_status error format
            assert result["status"] == "error"
            assert "error" in result
            assert "troubleshooting" in result or "setup_instructions" in result


class TestCheckAuthStatusBehaviorSpecification:
    """Test the specific behavior specification for check_auth_status."""

    def test_check_auth_status_extracts_bucket_name_correctly(self):
        """check_auth_status should correctly extract bucket name from s3:// URLs."""
        from quilt_mcp.operations.quilt3.auth import check_auth_status

        with patch('quilt3.logged_in') as mock_logged_in:
            mock_logged_in.return_value = "https://catalog.example.com"

            result = check_auth_status(registry_url="s3://my-test-bucket", catalog_url=None)

            assert result.get("registry_bucket") == "my-test-bucket"

    def test_check_auth_status_handles_missing_catalog_url_gracefully(self):
        """check_auth_status should handle None catalog_url gracefully."""
        from quilt_mcp.operations.quilt3.auth import check_auth_status

        with patch('quilt3.logged_in') as mock_logged_in:
            mock_logged_in.return_value = None

            result = check_auth_status(registry_url="s3://test-bucket", catalog_url=None)

            assert isinstance(result, dict)
            assert "status" in result
            # Should not crash and should return valid response

    def test_check_auth_status_preserves_catalog_name_extraction(self):
        """check_auth_status should extract catalog names from URLs like existing tool."""
        from quilt_mcp.operations.quilt3.auth import check_auth_status

        with patch('quilt3.logged_in') as mock_logged_in:
            mock_logged_in.return_value = None

            result = check_auth_status(
                registry_url="s3://test-bucket",
                catalog_url="https://nightly.quilttest.com"
            )

            # Should extract hostname without protocol
            assert result.get("catalog_name") == "nightly.quilttest.com"
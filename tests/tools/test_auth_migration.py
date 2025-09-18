"""Tests for auth.py migration to QuiltService - TDD Implementation."""

from __future__ import annotations

import pytest
from unittest.mock import Mock, patch, MagicMock

# Import the original auth functions to test migration
from quilt_mcp.tools.auth import auth_status, _get_catalog_info


class TestAuthMigrationToQuiltService:
    """Test migration of auth.py functions to use QuiltService instead of direct quilt3."""

    def test_auth_status_uses_quilt_service_when_authenticated(self):
        """Test that auth_status function uses QuiltService instead of direct quilt3 calls."""

        # Mock the QuiltService responses
        mock_service = Mock()
        mock_service.get_logged_in_url.return_value = 'https://example.quiltdata.com'
        mock_service.get_config.return_value = {
            'registryUrl': 's3://example-bucket',
            'navigator_url': 'https://example.quiltdata.com'
        }
        mock_service.get_catalog_info.return_value = {
            'catalog_name': 'example.quiltdata.com',
            'is_authenticated': True,
            'logged_in_url': 'https://example.quiltdata.com',
            'registry_url': 's3://example-bucket'
        }

        # Patch QuiltService to return our mock
        with patch('quilt_mcp.tools.auth.QuiltService', return_value=mock_service):
            result = auth_status()

            # Verify the result structure
            assert result['status'] == 'authenticated'
            assert result['catalog_url'] == 'https://example.quiltdata.com'
            assert result['catalog_name'] == 'example.quiltdata.com'
            assert result['registry_bucket'] == 'example-bucket'
            assert 'suggested_actions' in result
            assert 'message' in result

            # Verify QuiltService methods were called
            mock_service.get_logged_in_url.assert_called_once()
            mock_service.get_config.assert_called_once()
            mock_service.get_catalog_info.assert_called_once()

    def test_get_catalog_info_uses_quilt_service(self):
        """Test that _get_catalog_info function uses QuiltService instead of direct quilt3 calls."""

        # Mock the QuiltService
        mock_service = Mock()
        mock_service.get_catalog_info.return_value = {
            'catalog_name': 'test.quiltdata.com',
            'is_authenticated': True,
            'logged_in_url': 'https://test.quiltdata.com',
            'navigator_url': 'https://test.quiltdata.com',
            'registry_url': 's3://test-bucket'
        }

        # Patch QuiltService in the _get_catalog_info function
        with patch('quilt_mcp.tools.auth.QuiltService', return_value=mock_service):
            result = _get_catalog_info()

            # Verify the result
            assert result['catalog_name'] == 'test.quiltdata.com'
            assert result['is_authenticated'] is True
            assert result['logged_in_url'] == 'https://test.quiltdata.com'

            # Verify QuiltService was used
            mock_service.get_catalog_info.assert_called_once()

    def test_no_direct_quilt3_imports_after_migration(self):
        """Test that auth.py has no direct quilt3 imports after migration."""
        # This test will initially fail, which is expected in RED phase
        # After migration, auth.py should not import quilt3 directly

        import ast
        import inspect
        from quilt_mcp.tools import auth

        # Get the source code of the auth module
        source = inspect.getsource(auth)
        tree = ast.parse(source)

        # Check for direct quilt3 imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name != 'quilt3', f"Found direct quilt3 import: {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                assert node.module != 'quilt3', f"Found direct quilt3 import: from {node.module}"
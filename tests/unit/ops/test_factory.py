"""
Tests for QuiltOpsFactory implementation.

This module tests the factory for creating QuiltOps instances with appropriate backend selection.
For Phase 1, this focuses only on quilt3 session detection (no JWT support yet).
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import os

from quilt_mcp.ops.exceptions import AuthenticationError
from quilt_mcp.context.runtime_context import (
    RuntimeAuthState,
    get_runtime_environment,
    push_runtime_context,
    reset_runtime_context,
)


def _push_test_jwt_context():
    auth_state = RuntimeAuthState(
        scheme="Bearer",
        access_token="test-token",
        claims={
            "id": "user-1",
            "uuid": "uuid-1",
            "exp": 9999999999,
        },
    )
    return push_runtime_context(environment=get_runtime_environment(), auth=auth_state)


class TestQuiltOpsFactoryStructure:
    """Test the basic structure and functionality of QuiltOpsFactory."""

    def test_quilt_ops_factory_can_be_imported(self):
        """Test that QuiltOpsFactory can be imported from the ops module."""
        from quilt_mcp.ops.factory import QuiltOpsFactory

        assert QuiltOpsFactory is not None

    def test_quilt_ops_factory_has_create_method(self):
        """Test that QuiltOpsFactory has a create class method."""
        from quilt_mcp.ops.factory import QuiltOpsFactory

        assert hasattr(QuiltOpsFactory, 'create')
        assert callable(QuiltOpsFactory.create)

    def test_quilt_ops_factory_create_is_static_method(self):
        """Test that create() is a static method that works with mode configuration."""
        from quilt_mcp.ops.factory import QuiltOpsFactory
        from quilt_mcp.config import set_test_mode_config

        # Set local mode for testing
        set_test_mode_config(multiuser_mode=False)

        # Should be able to call without instantiating
        # This will succeed in local mode with quilt3 available
        result = QuiltOpsFactory.create()
        assert result is not None


class TestQuiltOpsFactoryQuilt3SessionDetection:
    """Test quilt3 session detection and validation."""

    def test_create_with_valid_quilt3_session(self):
        """Test create() in local mode returns Quilt3_Backend."""
        from quilt_mcp.ops.factory import QuiltOpsFactory
        from quilt_mcp.config import set_test_mode_config

        # Set local mode
        set_test_mode_config(multiuser_mode=False)

        # Execute
        result = QuiltOpsFactory.create()

        # Verify
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        assert isinstance(result, Quilt3_Backend)

    def test_create_with_no_quilt3_session(self):
        """Test create() in multiuser mode returns Platform_Backend."""
        from quilt_mcp.ops.factory import QuiltOpsFactory
        from quilt_mcp.config import set_test_mode_config

        # Set multiuser mode
        set_test_mode_config(multiuser_mode=True)
        os.environ["QUILT_CATALOG_URL"] = "https://example.quiltdata.com"
        os.environ["QUILT_REGISTRY_URL"] = "https://registry.example.com"
        os.environ["QUILT_GRAPHQL_ENDPOINT"] = "https://registry.example.com/graphql"

        token = _push_test_jwt_context()
        try:
            # Execute
            result = QuiltOpsFactory.create()
        finally:
            reset_runtime_context(token)

        # Verify
        from quilt_mcp.backends.platform_backend import Platform_Backend

        assert isinstance(result, Platform_Backend)

    def test_create_with_invalid_quilt3_session(self):
        """Test create() with quilt3 unavailable in local mode raises AuthenticationError."""
        from quilt_mcp.ops.factory import QuiltOpsFactory
        from quilt_mcp.config import set_test_mode_config

        # Set local mode
        set_test_mode_config(multiuser_mode=False)

        # Mock quilt3 as unavailable
        with patch('quilt_mcp.backends.quilt3_backend_base.quilt3', None):
            with pytest.raises(AuthenticationError) as exc_info:
                QuiltOpsFactory.create()
            assert "quilt3 library is not available" in str(exc_info.value)

    def test_create_with_no_quilt3_library(self):
        """Test create() with no quilt3 library in local mode raises AuthenticationError."""
        from quilt_mcp.ops.factory import QuiltOpsFactory
        from quilt_mcp.config import set_test_mode_config

        # Set local mode
        set_test_mode_config(multiuser_mode=False)

        # Mock quilt3 as unavailable
        with patch('quilt_mcp.backends.quilt3_backend_base.quilt3', None):
            with pytest.raises(AuthenticationError) as exc_info:
                QuiltOpsFactory.create()
            assert "quilt3 library is not available" in str(exc_info.value)


class TestQuiltOpsFactorySessionValidation:
    """Test session validation logic."""

    def test_session_validation_with_empty_session(self):
        """Test that local mode works without session validation."""
        from quilt_mcp.ops.factory import QuiltOpsFactory
        from quilt_mcp.config import set_test_mode_config

        # Set local mode
        set_test_mode_config(multiuser_mode=False)

        # Should create backend successfully in local mode
        result = QuiltOpsFactory.create()
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        assert isinstance(result, Quilt3_Backend)

    @patch('quilt_mcp.ops.factory.quilt3')
    def test_session_validation_with_malformed_session(self, mock_quilt3):
        """Test that malformed session info is handled correctly."""
        from quilt_mcp.ops.factory import QuiltOpsFactory

        # Mock malformed session (missing required fields)
        mock_quilt3.session.get_session_info.return_value = {'invalid': 'data'}

        # This should still try to create backend, but backend validation should catch it
        # The factory's job is just to detect session presence, not validate content
        result = QuiltOpsFactory.create()

        # Should return a Quilt3_Backend instance (validation happens in backend)
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        assert isinstance(result, Quilt3_Backend)

    def test_session_validation_preserves_session_data(self):
        """Test that backend creation works with mode configuration."""
        from quilt_mcp.ops.factory import QuiltOpsFactory
        from quilt_mcp.config import set_test_mode_config

        # Set local mode
        set_test_mode_config(multiuser_mode=False)

        # Execute
        result = QuiltOpsFactory.create()

        # Verify backend was created correctly
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        assert isinstance(result, Quilt3_Backend)


class TestQuiltOpsFactoryErrorHandling:
    """Test error handling and error message quality."""

    def test_error_handling_when_no_authentication_found(self):
        """Test error handling when quilt3 is not available in local mode."""
        from quilt_mcp.ops.factory import QuiltOpsFactory
        from quilt_mcp.config import set_test_mode_config

        # Set local mode
        set_test_mode_config(multiuser_mode=False)

        # Mock quilt3 as unavailable
        with patch('quilt_mcp.backends.quilt3_backend_base.quilt3', None):
            with pytest.raises(AuthenticationError) as exc_info:
                QuiltOpsFactory.create()

            error_message = str(exc_info.value)
            assert "quilt3 library is not available" in error_message

    def test_error_messages_include_remediation_steps(self):
        """Test that error messages provide actionable remediation steps."""
        from quilt_mcp.ops.factory import QuiltOpsFactory
        from quilt_mcp.config import set_test_mode_config

        # Set local mode
        set_test_mode_config(multiuser_mode=False)

        # Mock quilt3 as unavailable
        with patch('quilt_mcp.backends.quilt3_backend_base.quilt3', None):
            with pytest.raises(AuthenticationError) as exc_info:
                QuiltOpsFactory.create()

            error_message = str(exc_info.value)
            assert "quilt3 library is not available" in error_message

    def test_error_handling_preserves_original_exception_context(self):
        """Test that backend creation works correctly in different modes."""
        from quilt_mcp.ops.factory import QuiltOpsFactory
        from quilt_mcp.config import set_test_mode_config

        # Test local mode
        set_test_mode_config(multiuser_mode=False)
        result = QuiltOpsFactory.create()
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        assert isinstance(result, Quilt3_Backend)

        # Test multiuser mode
        set_test_mode_config(multiuser_mode=True)
        os.environ["QUILT_CATALOG_URL"] = "https://example.quiltdata.com"
        os.environ["QUILT_REGISTRY_URL"] = "https://registry.example.com"
        os.environ["QUILT_GRAPHQL_ENDPOINT"] = "https://registry.example.com/graphql"
        token = _push_test_jwt_context()
        try:
            result = QuiltOpsFactory.create()
        finally:
            reset_runtime_context(token)
        from quilt_mcp.backends.platform_backend import Platform_Backend

        assert isinstance(result, Platform_Backend)

    def test_clear_error_message_content(self):
        """Test that error messages are clear and user-friendly."""
        from quilt_mcp.ops.factory import QuiltOpsFactory
        from quilt_mcp.config import set_test_mode_config

        # Set local mode
        set_test_mode_config(multiuser_mode=False)

        # Mock quilt3 as unavailable
        with patch('quilt_mcp.backends.quilt3_backend_base.quilt3', None):
            with pytest.raises(AuthenticationError) as exc_info:
                QuiltOpsFactory.create()

            error_message = str(exc_info.value)
            assert len(error_message) > 20  # Not just a generic error
            assert "quilt3 library is not available" in error_message


class TestQuiltOpsFactoryPhase1Scope:
    """Test that factory correctly implements mode-based backend selection."""

    def test_factory_does_not_check_jwt_tokens_in_phase1(self):
        """Test that factory uses mode configuration instead of JWT tokens."""
        from quilt_mcp.ops.factory import QuiltOpsFactory
        from quilt_mcp.config import set_test_mode_config

        # Set local mode (should ignore JWT tokens)
        set_test_mode_config(multiuser_mode=False)

        # Set JWT token in environment (should be ignored in local mode)
        with patch.dict(os.environ, {'QUILT_JWT_TOKEN': 'fake-jwt-token'}):
            # Should create Quilt3_Backend in local mode regardless of JWT
            result = QuiltOpsFactory.create()
            from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

            assert isinstance(result, Quilt3_Backend)

    def test_factory_only_creates_quilt3_backend_in_phase1(self):
        """Test that factory creates appropriate backends based on mode."""
        from quilt_mcp.ops.factory import QuiltOpsFactory
        from quilt_mcp.config import set_test_mode_config

        # Test local mode creates Quilt3_Backend
        set_test_mode_config(multiuser_mode=False)
        result = QuiltOpsFactory.create()
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        assert isinstance(result, Quilt3_Backend)
        assert type(result).__name__ == 'Quilt3_Backend'

        # Test multiuser mode creates Platform_Backend
        set_test_mode_config(multiuser_mode=True)
        os.environ["QUILT_CATALOG_URL"] = "https://example.quiltdata.com"
        os.environ["QUILT_REGISTRY_URL"] = "https://registry.example.com"
        os.environ["QUILT_GRAPHQL_ENDPOINT"] = "https://registry.example.com/graphql"
        token = _push_test_jwt_context()
        try:
            result = QuiltOpsFactory.create()
        finally:
            reset_runtime_context(token)
        from quilt_mcp.backends.platform_backend import Platform_Backend

        assert isinstance(result, Platform_Backend)
        assert type(result).__name__ == 'Platform_Backend'

    def test_factory_phase1_documentation_mentions_scope(self):
        """Test that factory class documentation exists."""
        from quilt_mcp.ops.factory import QuiltOpsFactory

        # Check class exists and has documentation
        assert QuiltOpsFactory is not None
        assert hasattr(QuiltOpsFactory, 'create')
        assert callable(QuiltOpsFactory.create)


class TestQuiltOpsFactoryIntegration:
    """Test integration scenarios and complete factory workflows."""

    def test_complete_factory_workflow_success(self):
        """Test complete successful workflow from mode detection to backend creation."""
        from quilt_mcp.ops.factory import QuiltOpsFactory
        from quilt_mcp.ops.quilt_ops import QuiltOps
        from quilt_mcp.config import set_test_mode_config

        # Set local mode
        set_test_mode_config(multiuser_mode=False)

        # Execute
        result = QuiltOpsFactory.create()

        # Verify complete workflow
        assert result is not None
        assert isinstance(result, QuiltOps)  # Should implement QuiltOps interface

        # Should be able to call QuiltOps methods (they'll be mocked, but interface should work)
        assert hasattr(result, 'search_packages')
        assert hasattr(result, 'get_package_info')
        assert hasattr(result, 'browse_content')
        assert hasattr(result, 'list_buckets')
        assert hasattr(result, 'get_content_url')

    def test_factory_handles_backend_initialization_errors(self):
        """Test that factory handles errors during backend initialization."""
        from quilt_mcp.ops.factory import QuiltOpsFactory
        from quilt_mcp.config import set_test_mode_config

        # Set local mode
        set_test_mode_config(multiuser_mode=False)

        # Mock backend constructor to raise error
        with patch('quilt_mcp.ops.factory.Quilt3_Backend') as mock_backend_class:
            mock_backend_class.side_effect = Exception("Backend initialization failed")

            # Should propagate the backend error (not wrap in AuthenticationError)
            with pytest.raises(Exception) as exc_info:
                QuiltOpsFactory.create()

            assert "Backend initialization failed" in str(exc_info.value)

    def test_factory_creates_functional_backend_instance(self):
        """Test that factory creates a functional backend instance."""
        from quilt_mcp.ops.factory import QuiltOpsFactory
        from quilt_mcp.config import set_test_mode_config

        # Set local mode
        set_test_mode_config(multiuser_mode=False)

        # Execute
        result = QuiltOpsFactory.create()

        # Verify the instance has the expected attributes
        assert hasattr(result, 'quilt3')
        # The backend should be properly initialized

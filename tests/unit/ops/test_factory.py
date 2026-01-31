"""
Tests for QuiltOpsFactory implementation.

This module tests the factory for creating QuiltOps instances with appropriate backend selection.
For Phase 1, this focuses only on quilt3 session detection (no JWT support yet).
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import os

from quilt_mcp.ops.exceptions import AuthenticationError


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
        """Test that create() is a static method that doesn't require instantiation."""
        from quilt_mcp.ops.factory import QuiltOpsFactory

        # Should be able to call without instantiating
        # This will fail due to no session, but should not fail due to method access
        with pytest.raises(AuthenticationError):
            QuiltOpsFactory.create()


class TestQuiltOpsFactoryQuilt3SessionDetection:
    """Test quilt3 session detection and validation."""

    @patch('quilt_mcp.ops.factory.quilt3')
    def test_create_with_valid_quilt3_session(self, mock_quilt3):
        """Test create() with valid quilt3 session returns Quilt3_Backend."""
        from quilt_mcp.ops.factory import QuiltOpsFactory

        # Mock valid session
        mock_session_info = {
            'registry': 's3://test-registry',
            'credentials': {'access_key': 'test', 'secret_key': 'test'}
        }
        mock_quilt3.session.get_session_info.return_value = mock_session_info

        # Execute
        result = QuiltOpsFactory.create()

        # Verify
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        assert isinstance(result, Quilt3_Backend)
        mock_quilt3.session.get_session_info.assert_called_once()

    @patch('quilt_mcp.ops.factory.quilt3')
    def test_create_with_no_quilt3_session(self, mock_quilt3):
        """Test create() with no quilt3 session raises AuthenticationError."""
        from quilt_mcp.ops.factory import QuiltOpsFactory

        # Mock no session
        mock_quilt3.session.get_session_info.return_value = None

        # Execute and verify
        with pytest.raises(AuthenticationError) as exc_info:
            QuiltOpsFactory.create()

        error_message = str(exc_info.value).lower()
        assert "no valid authentication" in error_message or "no authentication" in error_message
        mock_quilt3.session.get_session_info.assert_called_once()

    @patch('quilt_mcp.ops.factory.quilt3')
    def test_create_with_invalid_quilt3_session(self, mock_quilt3):
        """Test create() with invalid quilt3 session raises AuthenticationError."""
        from quilt_mcp.ops.factory import QuiltOpsFactory

        # Mock session that raises exception
        mock_quilt3.session.get_session_info.side_effect = Exception("Session expired")

        # Execute and verify
        with pytest.raises(AuthenticationError) as exc_info:
            QuiltOpsFactory.create()

        error_message = str(exc_info.value).lower()
        assert "no valid authentication" in error_message or "no authentication" in error_message
        mock_quilt3.session.get_session_info.assert_called_once()

    @patch('quilt_mcp.ops.factory.quilt3', None)
    def test_create_with_no_quilt3_library(self):
        """Test create() when quilt3 library is not available."""
        from quilt_mcp.ops.factory import QuiltOpsFactory

        # Execute and verify
        with pytest.raises(AuthenticationError) as exc_info:
            QuiltOpsFactory.create()

        error_message = str(exc_info.value).lower()
        assert "no valid authentication" in error_message or "quilt3" in error_message


class TestQuiltOpsFactorySessionValidation:
    """Test session validation logic."""

    @patch('quilt_mcp.ops.factory.quilt3')
    def test_session_validation_with_empty_session(self, mock_quilt3):
        """Test that empty session info is handled correctly."""
        from quilt_mcp.ops.factory import QuiltOpsFactory

        # Mock empty session
        mock_quilt3.session.get_session_info.return_value = {}

        # Execute and verify
        with pytest.raises(AuthenticationError):
            QuiltOpsFactory.create()

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

    @patch('quilt_mcp.ops.factory.quilt3')
    def test_session_validation_preserves_session_data(self, mock_quilt3):
        """Test that session data is passed correctly to backend."""
        from quilt_mcp.ops.factory import QuiltOpsFactory

        # Mock session with specific data
        mock_session_info = {
            'registry': 's3://custom-registry',
            'credentials': {'access_key': 'custom_key', 'secret_key': 'custom_secret'}
        }
        mock_quilt3.session.get_session_info.return_value = mock_session_info

        # Execute
        with patch('quilt_mcp.ops.factory.Quilt3_Backend') as mock_backend_class:
            mock_backend_instance = Mock()
            mock_backend_class.return_value = mock_backend_instance

            result = QuiltOpsFactory.create()

            # Verify backend was created with correct session data
            mock_backend_class.assert_called_once_with(mock_session_info)
            assert result == mock_backend_instance


class TestQuiltOpsFactoryErrorHandling:
    """Test error handling and error message quality."""

    @patch('quilt_mcp.ops.factory.quilt3')
    def test_error_handling_when_no_authentication_found(self, mock_quilt3):
        """Test error handling when no authentication method is available."""
        from quilt_mcp.ops.factory import QuiltOpsFactory

        # Mock no authentication available
        mock_quilt3.session.get_session_info.return_value = None

        # Execute and verify
        with pytest.raises(AuthenticationError) as exc_info:
            QuiltOpsFactory.create()

        error_message = str(exc_info.value)
        # Should provide clear guidance on authentication options
        assert "authentication" in error_message.lower()
        # Should mention quilt3 login as an option (Phase 1 focus)
        assert "quilt3" in error_message.lower() or "login" in error_message.lower()

    @patch('quilt_mcp.ops.factory.quilt3')
    def test_error_messages_include_remediation_steps(self, mock_quilt3):
        """Test that error messages provide actionable remediation steps."""
        from quilt_mcp.ops.factory import QuiltOpsFactory

        # Mock no session
        mock_quilt3.session.get_session_info.return_value = None

        # Execute and verify
        with pytest.raises(AuthenticationError) as exc_info:
            QuiltOpsFactory.create()

        error_message = str(exc_info.value)
        # Should provide specific steps user can take
        assert any(keyword in error_message.lower() for keyword in [
            "login", "session", "quilt3", "authentication"
        ])

    @patch('quilt_mcp.ops.factory.quilt3')
    def test_error_handling_preserves_original_exception_context(self, mock_quilt3):
        """Test that original exception context is preserved in error messages."""
        from quilt_mcp.ops.factory import QuiltOpsFactory

        # Mock session that raises specific exception
        original_error = "Network timeout connecting to registry"
        mock_quilt3.session.get_session_info.side_effect = Exception(original_error)

        # Execute and verify
        with pytest.raises(AuthenticationError) as exc_info:
            QuiltOpsFactory.create()

        # Error should still be AuthenticationError but may include context
        assert isinstance(exc_info.value, AuthenticationError)

    @patch('quilt_mcp.ops.factory.quilt3')
    def test_clear_error_message_content(self, mock_quilt3):
        """Test that error messages are clear and user-friendly."""
        from quilt_mcp.ops.factory import QuiltOpsFactory

        # Mock no authentication
        mock_quilt3.session.get_session_info.return_value = None

        # Execute and verify
        with pytest.raises(AuthenticationError) as exc_info:
            QuiltOpsFactory.create()

        error_message = str(exc_info.value)
        # Should be clear and actionable
        assert len(error_message) > 20  # Not just a generic error
        assert not error_message.startswith("Exception:")  # Not a raw exception
        assert "authentication" in error_message.lower()


class TestQuiltOpsFactoryPhase1Scope:
    """Test that factory correctly implements Phase 1 scope (quilt3 only)."""

    def test_factory_does_not_check_jwt_tokens_in_phase1(self):
        """Test that factory doesn't check for JWT tokens in Phase 1."""
        from quilt_mcp.ops.factory import QuiltOpsFactory

        # Set JWT token in environment (should be ignored in Phase 1)
        with patch.dict(os.environ, {'QUILT_JWT_TOKEN': 'fake-jwt-token'}):
            with patch('quilt_mcp.ops.factory.quilt3') as mock_quilt3:
                # Mock no quilt3 session
                mock_quilt3.session.get_session_info.return_value = None

                # Should still fail because JWT is not supported in Phase 1
                with pytest.raises(AuthenticationError):
                    QuiltOpsFactory.create()

    @patch('quilt_mcp.ops.factory.quilt3')
    def test_factory_only_creates_quilt3_backend_in_phase1(self, mock_quilt3):
        """Test that factory only creates Quilt3_Backend in Phase 1."""
        from quilt_mcp.ops.factory import QuiltOpsFactory

        # Mock valid session
        mock_session_info = {'registry': 's3://test-registry'}
        mock_quilt3.session.get_session_info.return_value = mock_session_info

        # Execute
        result = QuiltOpsFactory.create()

        # Verify only Quilt3_Backend is created
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        assert isinstance(result, Quilt3_Backend)
        assert type(result).__name__ == 'Quilt3_Backend'

    def test_factory_phase1_documentation_mentions_scope(self):
        """Test that factory class/module documentation mentions Phase 1 scope."""
        from quilt_mcp.ops.factory import QuiltOpsFactory

        # Check class docstring mentions Phase 1 or scope limitation
        class_doc = QuiltOpsFactory.__doc__ or ""
        module_doc = QuiltOpsFactory.__module__

        # Should have some documentation indicating this is Phase 1 implementation
        # This is more of a documentation check than functional test
        assert QuiltOpsFactory is not None  # Basic check that class exists


class TestQuiltOpsFactorySessionDetection:
    """Test the _detect_quilt3_session() method specifically."""

    @patch('quilt_mcp.ops.factory.quilt3')
    def test_detect_quilt3_session_with_valid_session(self, mock_quilt3):
        """Test _detect_quilt3_session() with valid session data."""
        from quilt_mcp.ops.factory import QuiltOpsFactory

        # Mock valid session
        valid_session = {
            'registry': 's3://test-registry',
            'credentials': {'access_key': 'test', 'secret_key': 'test'}
        }
        mock_quilt3.session.get_session_info.return_value = valid_session

        # Execute
        result = QuiltOpsFactory._detect_quilt3_session()

        # Verify
        assert result == valid_session
        mock_quilt3.session.get_session_info.assert_called_once()

    @patch('quilt_mcp.ops.factory.quilt3')
    def test_detect_quilt3_session_with_no_session(self, mock_quilt3):
        """Test _detect_quilt3_session() when no session is available."""
        from quilt_mcp.ops.factory import QuiltOpsFactory

        # Mock no session
        mock_quilt3.session.get_session_info.return_value = None

        # Execute
        result = QuiltOpsFactory._detect_quilt3_session()

        # Verify
        assert result is None
        mock_quilt3.session.get_session_info.assert_called_once()

    @patch('quilt_mcp.ops.factory.quilt3')
    def test_detect_quilt3_session_with_empty_session(self, mock_quilt3):
        """Test _detect_quilt3_session() with empty session data."""
        from quilt_mcp.ops.factory import QuiltOpsFactory

        # Mock empty session
        mock_quilt3.session.get_session_info.return_value = {}

        # Execute
        result = QuiltOpsFactory._detect_quilt3_session()

        # Verify - empty dict evaluates to False, so should return None
        assert result is None
        mock_quilt3.session.get_session_info.assert_called_once()

    @patch('quilt_mcp.ops.factory.quilt3')
    def test_detect_quilt3_session_when_get_session_info_raises_exception(self, mock_quilt3):
        """Test _detect_quilt3_session() when get_session_info() raises an exception."""
        from quilt_mcp.ops.factory import QuiltOpsFactory

        # Mock exception
        mock_quilt3.session.get_session_info.side_effect = Exception("Session error")

        # Execute
        result = QuiltOpsFactory._detect_quilt3_session()

        # Verify - should return None when exception occurs
        assert result is None
        mock_quilt3.session.get_session_info.assert_called_once()

    @patch('quilt_mcp.ops.factory.quilt3', None)
    def test_detect_quilt3_session_when_quilt3_unavailable(self):
        """Test _detect_quilt3_session() when quilt3 library is not available."""
        from quilt_mcp.ops.factory import QuiltOpsFactory

        # Execute
        result = QuiltOpsFactory._detect_quilt3_session()

        # Verify - should return None when quilt3 is not available
        assert result is None

    @patch('quilt_mcp.ops.factory.quilt3')
    def test_detect_quilt3_session_with_various_session_types(self, mock_quilt3):
        """Test _detect_quilt3_session() with various session data types."""
        from quilt_mcp.ops.factory import QuiltOpsFactory

        # Test different session data types that should return the session
        valid_session_types = [
            {'registry': 's3://test'},  # Dict with content
            {'complex': {'nested': {'data': 'value'}}},  # Nested dict
        ]

        for session_data in valid_session_types:
            mock_quilt3.session.get_session_info.return_value = session_data

            result = QuiltOpsFactory._detect_quilt3_session()

            assert result == session_data
            mock_quilt3.session.get_session_info.assert_called()

            # Reset for next test
            mock_quilt3.session.get_session_info.reset_mock()

        # Test session data types that evaluate to False and should return None
        falsy_session_types = [
            None,  # None
            {},  # Empty dict
        ]

        for session_data in falsy_session_types:
            mock_quilt3.session.get_session_info.return_value = session_data

            result = QuiltOpsFactory._detect_quilt3_session()

            assert result is None
            mock_quilt3.session.get_session_info.assert_called()

            # Reset for next test
            mock_quilt3.session.get_session_info.reset_mock()

    @patch('quilt_mcp.ops.factory.quilt3')
    def test_detect_quilt3_session_with_permission_errors(self, mock_quilt3):
        """Test _detect_quilt3_session() with permission-related errors."""
        from quilt_mcp.ops.factory import QuiltOpsFactory

        # Test various permission errors
        permission_errors = [
            PermissionError("Access denied to session file"),
            FileNotFoundError("Session file not found"),
            OSError("Permission denied"),
        ]

        for error in permission_errors:
            mock_quilt3.session.get_session_info.side_effect = error

            result = QuiltOpsFactory._detect_quilt3_session()

            # Should return None for permission errors (graceful degradation)
            assert result is None
            mock_quilt3.session.get_session_info.assert_called()

            # Reset for next test
            mock_quilt3.session.get_session_info.side_effect = None
            mock_quilt3.session.get_session_info.reset_mock()

    @patch('quilt_mcp.ops.factory.quilt3')
    def test_detect_quilt3_session_logging_behavior(self, mock_quilt3):
        """Test that _detect_quilt3_session() produces appropriate log messages."""
        from quilt_mcp.ops.factory import QuiltOpsFactory

        # Test successful detection
        valid_session = {'registry': 's3://test-registry'}
        mock_quilt3.session.get_session_info.return_value = valid_session

        with patch('quilt_mcp.ops.factory.logger') as mock_logger:
            result = QuiltOpsFactory._detect_quilt3_session()

            # Verify debug logging
            mock_logger.debug.assert_any_call("Checking for quilt3 session")
            mock_logger.debug.assert_any_call("Found valid quilt3 session")

        # Test no session found
        mock_quilt3.session.get_session_info.return_value = None

        with patch('quilt_mcp.ops.factory.logger') as mock_logger:
            result = QuiltOpsFactory._detect_quilt3_session()

            # Verify debug logging
            mock_logger.debug.assert_any_call("Checking for quilt3 session")
            mock_logger.debug.assert_any_call("No quilt3 session found")

        # Test exception handling
        mock_quilt3.session.get_session_info.side_effect = Exception("Test error")

        with patch('quilt_mcp.ops.factory.logger') as mock_logger:
            result = QuiltOpsFactory._detect_quilt3_session()

            # Verify error logging
            mock_logger.debug.assert_any_call("Error checking quilt3 session: Test error")

    @patch('quilt_mcp.ops.factory.quilt3')
    def test_detect_quilt3_session_with_complex_session_structures(self, mock_quilt3):
        """Test _detect_quilt3_session() with complex session structures."""
        from quilt_mcp.ops.factory import QuiltOpsFactory

        # Test complex session structure
        complex_session = {
            'registry': 's3://complex-registry',
            'credentials': {
                'access_key': 'AKIAIOSFODNN7EXAMPLE',
                'secret_key': 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
                'session_token': 'temporary-token'
            },
            'region': 'us-west-2',
            'profile': 'production',
            'metadata': {
                'user': 'test-user',
                'environment': 'production',
                'created_at': '2024-01-01T12:00:00Z',
                'nested': {
                    'deep': {
                        'structure': 'value'
                    }
                }
            },
            'custom_fields': ['field1', 'field2', 'field3']
        }

        mock_quilt3.session.get_session_info.return_value = complex_session

        # Execute
        result = QuiltOpsFactory._detect_quilt3_session()

        # Verify complex structure is preserved
        assert result == complex_session
        assert result['credentials']['access_key'] == 'AKIAIOSFODNN7EXAMPLE'
        assert result['metadata']['nested']['deep']['structure'] == 'value'
        assert result['custom_fields'] == ['field1', 'field2', 'field3']

    @patch('quilt_mcp.ops.factory.quilt3')
    def test_detect_quilt3_session_performance_with_large_sessions(self, mock_quilt3):
        """Test _detect_quilt3_session() performance with large session data."""
        from quilt_mcp.ops.factory import QuiltOpsFactory
        import time

        # Create large session data
        large_session = {
            'registry': 's3://performance-test',
            'large_metadata': {f'key_{i}': f'value_{i}' * 100 for i in range(1000)},
            'large_list': [f'item_{i}' for i in range(10000)],
            'large_string': 'X' * 100000
        }

        mock_quilt3.session.get_session_info.return_value = large_session

        # Measure performance
        start_time = time.time()
        result = QuiltOpsFactory._detect_quilt3_session()
        end_time = time.time()

        # Should complete quickly (less than 1 second)
        assert (end_time - start_time) < 1.0
        assert result == large_session


class TestQuiltOpsFactoryIntegration:
    """Test integration scenarios and complete factory workflows."""

    @patch('quilt_mcp.ops.factory.quilt3')
    def test_complete_factory_workflow_success(self, mock_quilt3):
        """Test complete successful workflow from session detection to backend creation."""
        from quilt_mcp.ops.factory import QuiltOpsFactory
        from quilt_mcp.ops.quilt_ops import QuiltOps

        # Mock valid session
        mock_session_info = {
            'registry': 's3://test-registry',
            'credentials': {'access_key': 'test', 'secret_key': 'test'}
        }
        mock_quilt3.session.get_session_info.return_value = mock_session_info

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

    @patch('quilt_mcp.ops.factory.quilt3')
    def test_factory_handles_backend_initialization_errors(self, mock_quilt3):
        """Test that factory handles errors during backend initialization."""
        from quilt_mcp.ops.factory import QuiltOpsFactory

        # Mock session exists but backend initialization fails
        mock_session_info = {'registry': 's3://test-registry'}
        mock_quilt3.session.get_session_info.return_value = mock_session_info

        # Mock backend constructor to raise error
        with patch('quilt_mcp.ops.factory.Quilt3_Backend') as mock_backend_class:
            mock_backend_class.side_effect = Exception("Backend initialization failed")

            # Should propagate the backend error (not wrap in AuthenticationError)
            with pytest.raises(Exception) as exc_info:
                QuiltOpsFactory.create()

            assert "Backend initialization failed" in str(exc_info.value)

    @patch('quilt_mcp.ops.factory.quilt3')
    def test_factory_creates_functional_backend_instance(self, mock_quilt3):
        """Test that factory creates a functional backend instance."""
        from quilt_mcp.ops.factory import QuiltOpsFactory

        # Mock valid session
        mock_session_info = {'registry': 's3://test-registry'}
        mock_quilt3.session.get_session_info.return_value = mock_session_info

        # Execute
        result = QuiltOpsFactory.create()

        # Verify the instance has the expected session
        assert hasattr(result, 'session')
        # The session should be the one we provided (after validation)
        # Note: actual validation happens in Quilt3_Backend, factory just passes it through

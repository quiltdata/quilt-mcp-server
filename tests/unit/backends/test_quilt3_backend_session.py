"""
Tests for Quilt3_Backend session and authentication.

This module tests session validation, authentication, catalog configuration,
and GraphQL query operations for the Quilt3_Backend implementation.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime
from typing import List, Optional

from quilt_mcp.ops.exceptions import AuthenticationError, BackendError, NotFoundError, ValidationError
from quilt_mcp.domain.package_info import Package_Info
from quilt_mcp.domain.content_info import Content_Info
from quilt_mcp.domain.bucket_info import Bucket_Info


class TestQuilt3BackendSessionDetectionAndValidation:
    """Test quilt3 session detection and validation functionality."""

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_session_detection_with_valid_session_info(self, mock_quilt3):
        """Test session detection when quilt3.session.get_session_info() returns valid data."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        # Mock valid session info
        valid_session = {
            'registry': 's3://test-registry',
            'credentials': {
                'access_key': 'AKIAIOSFODNN7EXAMPLE',
                'secret_key': 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
            },
            'region': 'us-east-1',
            'profile': 'default',
        }
        mock_quilt3.session.get_session_info.return_value = valid_session

        # Create backend instance
        backend = Quilt3_Backend(valid_session)

        # Verify session was properly stored
        assert backend.session == valid_session
        assert backend.session['registry'] == 's3://test-registry'
        assert backend.session['credentials']['access_key'] == 'AKIAIOSFODNN7EXAMPLE'

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_session_detection_with_minimal_valid_session(self, mock_quilt3):
        """Test session detection with minimal valid session configuration."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        # Mock minimal valid session
        minimal_session = {'registry': 's3://minimal-registry'}
        mock_quilt3.session.get_session_info.return_value = minimal_session

        # Create backend instance
        backend = Quilt3_Backend(minimal_session)

        # Verify minimal session works
        assert backend.session == minimal_session
        assert backend.session['registry'] == 's3://minimal-registry'

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_session_detection_with_empty_session_info(self, mock_quilt3):
        """Test session detection when get_session_info() returns empty data."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        # Test various empty session scenarios
        empty_scenarios = [
            None,  # No session
            {},  # Empty dict
            "",  # Empty string
            [],  # Empty list
        ]

        for empty_session in empty_scenarios:
            mock_quilt3.session.get_session_info.return_value = empty_session

            with pytest.raises(AuthenticationError) as exc_info:
                Quilt3_Backend(empty_session)

            error_message = str(exc_info.value)
            assert "session configuration is empty" in error_message

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_session_detection_when_get_session_info_raises_exception(self, mock_quilt3):
        """Test session detection when get_session_info() raises various exceptions."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        # Test different exception scenarios
        exception_scenarios = [
            Exception("Session expired"),
            PermissionError("Access denied to session file"),
            FileNotFoundError("Session file not found"),
            ValueError("Invalid session format"),
            ConnectionError("Cannot connect to authentication server"),
            TimeoutError("Session validation timeout"),
        ]

        for exception in exception_scenarios:
            mock_quilt3.session.get_session_info.side_effect = exception

            with pytest.raises(AuthenticationError) as exc_info:
                # Try to create backend with a dummy session, but get_session_info will fail
                Quilt3_Backend({'registry': 's3://test'})

            error_message = str(exc_info.value)
            assert "Invalid quilt3 session" in error_message
            assert str(exception) in error_message

            # Reset side effect for next test
            mock_quilt3.session.get_session_info.side_effect = None

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_session_validation_with_various_registry_formats(self, mock_quilt3):
        """Test session validation with different registry URL formats."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        # Test various valid registry formats
        registry_formats = [
            's3://simple-bucket',
            's3://bucket-with-dashes',
            's3://bucket.with.dots',
            's3://bucket_with_underscores',
            's3://123numeric-bucket',
            's3://very-long-bucket-name-with-many-characters-for-testing',
            's3://a',  # Single character
        ]

        for registry in registry_formats:
            session_config = {'registry': registry}
            mock_quilt3.session.get_session_info.return_value = session_config

            # Should create backend successfully
            backend = Quilt3_Backend(session_config)
            assert backend.session['registry'] == registry

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_session_validation_with_complex_credentials(self, mock_quilt3):
        """Test session validation with complex credential configurations."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        # Test various credential configurations
        credential_configs = [
            # AWS access keys
            {
                'registry': 's3://test-registry',
                'credentials': {
                    'access_key': 'AKIAIOSFODNN7EXAMPLE',
                    'secret_key': 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
                },
            },
            # AWS profile-based
            {'registry': 's3://test-registry', 'profile': 'my-aws-profile', 'region': 'us-west-2'},
            # Session token
            {
                'registry': 's3://test-registry',
                'credentials': {
                    'access_key': 'AKIAIOSFODNN7EXAMPLE',
                    'secret_key': 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
                    'session_token': 'AQoEXAMPLEH4aoAH0gNCAPyJxz4BlCFFxWNE1OPTgk5TthT+FvwqnKwRcOIfrRh3c/LTo6UDdyJwOOvEVPvLXCrrrUtdnniCEXAMPLE/IvU1dYUg2RVAJBanLiHb4IgRmpRV3zrkuWJOgQs8IZZaIv2BXIa2R4OlgkBN9bkUDNCJiBeb/AXlzBBko7b15fjrBs2+cTQtpZ3CYWFXG8C5zqx37wnOE49mRl/+OtkIKGO7fAE',
                },
            },
            # Minimal configuration
            {'registry': 's3://minimal-registry'},
        ]

        for config in credential_configs:
            mock_quilt3.session.get_session_info.return_value = config

            # Should create backend successfully
            backend = Quilt3_Backend(config)
            assert backend.session == config

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_session_validation_preserves_all_session_data(self, mock_quilt3):
        """Test that session validation preserves all provided session data."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        # Comprehensive session configuration
        comprehensive_session = {
            'registry': 's3://comprehensive-registry',
            'credentials': {
                'access_key': 'AKIAIOSFODNN7EXAMPLE',
                'secret_key': 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
                'session_token': 'temporary-session-token',
            },
            'region': 'us-west-2',
            'profile': 'production',
            'endpoint_url': 'https://custom-s3-endpoint.example.com',
            'metadata': {'user': 'test-user', 'environment': 'testing', 'created_at': '2024-01-01T12:00:00Z'},
            'custom_field': 'custom_value',
        }

        mock_quilt3.session.get_session_info.return_value = comprehensive_session

        # Create backend
        backend = Quilt3_Backend(comprehensive_session)

        # Verify all data is preserved
        assert backend.session == comprehensive_session
        assert backend.session['registry'] == 's3://comprehensive-registry'
        assert backend.session['credentials']['access_key'] == 'AKIAIOSFODNN7EXAMPLE'
        assert backend.session['region'] == 'us-west-2'
        assert backend.session['profile'] == 'production'
        assert backend.session['endpoint_url'] == 'https://custom-s3-endpoint.example.com'
        assert backend.session['metadata']['user'] == 'test-user'
        assert backend.session['custom_field'] == 'custom_value'

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_session_validation_with_invalid_session_formats(self, mock_quilt3):
        """Test session validation with various invalid session formats."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        # Test invalid session formats that should be rejected
        invalid_sessions = [
            None,  # None session
            "",  # Empty string
            [],  # List instead of dict
        ]

        for invalid_session in invalid_sessions:
            with pytest.raises(AuthenticationError) as exc_info:
                Quilt3_Backend(invalid_session)

            error_message = str(exc_info.value)
            assert "session configuration is empty" in error_message

        # Test non-dict types that will cause AttributeError in validation
        non_dict_sessions = [
            "invalid_string",  # String instead of dict
            123,  # Number instead of dict
            True,  # Boolean instead of dict
        ]

        for invalid_session in non_dict_sessions:
            with pytest.raises((AuthenticationError, AttributeError)):
                Quilt3_Backend(invalid_session)

    def test_session_detection_when_quilt3_library_unavailable(self):
        """Test session detection behavior when quilt3 library is not available."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        # Mock quilt3 as None (library not available)
        with patch('quilt_mcp.backends.quilt3_backend_base.quilt3', None):
            with pytest.raises(AuthenticationError) as exc_info:
                Quilt3_Backend({'registry': 's3://test'})

            error_message = str(exc_info.value)
            assert "quilt3 library is not available" in error_message

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_session_validation_with_get_session_info_method_missing(self, mock_quilt3):
        """Test session validation when get_session_info method is not available."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        # Mock quilt3.session without get_session_info method
        mock_session = Mock()
        if hasattr(mock_session, 'get_session_info'):
            delattr(mock_session, 'get_session_info')
        mock_quilt3.session = mock_session

        # Should still work if session config is provided directly
        session_config = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(session_config)
        assert backend.session == session_config

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_session_validation_error_context_preservation(self, mock_quilt3):
        """Test that session validation errors preserve context for debugging."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        # Test with exception that has detailed context
        detailed_error = Exception("Session validation failed: Invalid credentials for registry s3://test-registry")
        mock_quilt3.session.get_session_info.side_effect = detailed_error

        with pytest.raises(AuthenticationError) as exc_info:
            Quilt3_Backend({'registry': 's3://test-registry'})

        error_message = str(exc_info.value)
        # Should preserve original error context
        assert "Invalid credentials for registry s3://test-registry" in error_message

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_session_validation_with_concurrent_access_scenarios(self, mock_quilt3):
        """Test session validation under concurrent access scenarios."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        import threading
        import time

        # Mock session that simulates concurrent access
        session_config = {'registry': 's3://concurrent-test'}
        mock_quilt3.session.get_session_info.return_value = session_config

        results = []
        errors = []

        def create_backend():
            try:
                backend = Quilt3_Backend(session_config)
                results.append(backend)
            except Exception as e:
                errors.append(e)

        # Create multiple threads to test concurrent access
        threads = []
        for i in range(5):
            thread = threading.Thread(target=create_backend)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify all backends were created successfully
        assert len(results) == 5
        assert len(errors) == 0
        for backend in results:
            assert backend.session == session_config

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_session_validation_performance_with_large_session_data(self, mock_quilt3):
        """Test session validation performance with large session configurations."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        import time

        # Create large session configuration
        large_session = {
            'registry': 's3://performance-test',
            'credentials': {
                'access_key': 'A' * 1000,  # Large access key
                'secret_key': 'S' * 1000,  # Large secret key
            },
            'metadata': {
                f'key_{i}': f'value_{i}' * 100
                for i in range(1000)  # Large metadata
            },
            'large_list': [f'item_{i}' for i in range(10000)],  # Large list
            'large_string': 'X' * 100000,  # Large string
        }

        mock_quilt3.session.get_session_info.return_value = large_session

        # Measure performance
        start_time = time.time()
        backend = Quilt3_Backend(large_session)
        end_time = time.time()

        # Should complete within reasonable time (less than 1 second)
        assert (end_time - start_time) < 1.0
        assert backend.session == large_session


class TestQuilt3BackendSessionValidation:
    """Test comprehensive session validation scenarios."""

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_session_validation_with_corrupted_session_data(self, mock_quilt3):
        """Test session validation with corrupted session data."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        # Test with corrupted session data that causes validation to fail
        corrupted_sessions = [
            {'registry': 'invalid-uri-format'},
            {'credentials': 'not-a-dict'},
            {'registry': 's3://test', 'credentials': {'malformed': True}},
            {'registry': None},
            {'registry': ''},
        ]

        for corrupted_session in corrupted_sessions:
            mock_quilt3.session.get_session_info.side_effect = ValueError("Corrupted session data")

            with pytest.raises(AuthenticationError) as exc_info:
                Quilt3_Backend(corrupted_session)

            assert "Invalid quilt3 session" in str(exc_info.value)
            assert "Corrupted session data" in str(exc_info.value)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_session_validation_with_expired_credentials(self, mock_quilt3):
        """Test session validation with expired credentials."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        expired_session = {
            'registry': 's3://test-registry',
            'credentials': {'access_key': 'expired', 'secret_key': 'expired'},
        }

        # Mock expired credentials error
        mock_quilt3.session.get_session_info.side_effect = Exception("Token has expired")

        with pytest.raises(AuthenticationError) as exc_info:
            Quilt3_Backend(expired_session)

        assert "Invalid quilt3 session" in str(exc_info.value)
        assert "Token has expired" in str(exc_info.value)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_session_validation_with_network_errors(self, mock_quilt3):
        """Test session validation with network connectivity issues."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        import socket

        session_config = {'registry': 's3://test-registry'}

        # Test various network-related errors
        network_errors = [
            TimeoutError("Connection timeout"),
            ConnectionError("Network unreachable"),
            OSError("Name resolution failed"),
        ]

        for network_error in network_errors:
            mock_quilt3.session.get_session_info.side_effect = network_error

            with pytest.raises(AuthenticationError) as exc_info:
                Quilt3_Backend(session_config)

            assert "Invalid quilt3 session" in str(exc_info.value)
            assert str(network_error) in str(exc_info.value)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_session_validation_with_permission_errors(self, mock_quilt3):
        """Test session validation with various permission-related errors."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        session_config = {'registry': 's3://restricted-registry'}

        # Test various permission errors
        permission_errors = [
            PermissionError("Access denied to registry"),
            Exception("Forbidden: Insufficient permissions"),
            Exception("403 Forbidden"),
            Exception("UnauthorizedOperation"),
        ]

        for permission_error in permission_errors:
            mock_quilt3.session.get_session_info.side_effect = permission_error

            with pytest.raises(AuthenticationError) as exc_info:
                Quilt3_Backend(session_config)

            assert "Invalid quilt3 session" in str(exc_info.value)
            assert str(permission_error) in str(exc_info.value)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_session_validation_error_message_clarity(self, mock_quilt3):
        """Test that session validation errors provide clear, actionable messages."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        session_config = {'registry': 's3://test-registry'}
        mock_quilt3.session.get_session_info.side_effect = Exception("Invalid API key")

        with pytest.raises(AuthenticationError) as exc_info:
            Quilt3_Backend(session_config)

        error_message = str(exc_info.value)

        # Verify error message contains helpful information
        assert "Invalid quilt3 session" in error_message
        assert "Invalid API key" in error_message

        # Should provide context about what went wrong
        assert any(
            keyword in error_message.lower() for keyword in ["session", "authentication", "credentials", "login"]
        )

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_session_validation_with_malformed_registry_urls(self, mock_quilt3):
        """Test session validation with malformed registry URLs."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        malformed_registries = [
            {'registry': 'not-a-url'},
            {'registry': 'http://insecure-registry'},  # Should be s3://
            {'registry': 's3://'},  # Missing bucket name
            {'registry': 's3://bucket/with/path'},  # Invalid format
            {'registry': 'ftp://wrong-protocol'},
        ]

        for malformed_config in malformed_registries:
            mock_quilt3.session.get_session_info.side_effect = ValueError("Invalid registry URL")

            with pytest.raises(AuthenticationError) as exc_info:
                Quilt3_Backend(malformed_config)

            assert "Invalid quilt3 session" in str(exc_info.value)
            assert "Invalid registry URL" in str(exc_info.value)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_session_validation_edge_cases(self, mock_quilt3):
        """Test session validation edge cases and boundary conditions."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        # Test with very large session config
        large_session = {
            'registry': 's3://test-registry',
            'metadata': {'key' + str(i): 'value' + str(i) for i in range(1000)},
        }
        mock_quilt3.session.get_session_info.return_value = large_session

        # Should handle large configs without issues
        backend = Quilt3_Backend(large_session)
        assert backend.session == large_session

        # Test with unicode characters in session
        unicode_session = {'registry': 's3://test-registry', 'user': 'üser_nämé', 'description': '测试用户'}
        mock_quilt3.session.get_session_info.return_value = unicode_session

        backend = Quilt3_Backend(unicode_session)
        assert backend.session == unicode_session

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_session_validation_with_timeout_scenarios(self, mock_quilt3):
        """Test session validation with various timeout scenarios."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        import socket

        session_config = {'registry': 's3://test-registry'}

        # Test different timeout scenarios
        timeout_errors = [
            TimeoutError("Connection timed out"),
            TimeoutError("Operation timed out"),
            Exception("Read timeout"),
            Exception("Connection timeout after 30 seconds"),
        ]

        for timeout_error in timeout_errors:
            mock_quilt3.session.get_session_info.side_effect = timeout_error

            with pytest.raises(AuthenticationError) as exc_info:
                Quilt3_Backend(session_config)

            assert "Invalid quilt3 session" in str(exc_info.value)
            assert any(keyword in str(exc_info.value).lower() for keyword in ["timeout", "timed out"])

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_session_validation_with_ssl_errors(self, mock_quilt3):
        """Test session validation with SSL/TLS related errors."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        import ssl

        session_config = {'registry': 's3://test-registry'}

        # Test SSL-related errors
        ssl_errors = [
            ssl.SSLError("SSL certificate verification failed"),
            ssl.SSLCertVerificationError("Certificate verification failed"),
            Exception("SSL: CERTIFICATE_VERIFY_FAILED"),
            Exception("SSL handshake failed"),
        ]

        for ssl_error in ssl_errors:
            mock_quilt3.session.get_session_info.side_effect = ssl_error

            with pytest.raises(AuthenticationError) as exc_info:
                Quilt3_Backend(session_config)

            assert "Invalid quilt3 session" in str(exc_info.value)
            assert any(keyword in str(exc_info.value).lower() for keyword in ["ssl", "certificate", "handshake"])


class TestQuilt3BackendCatalogConfigMethods:
    """Test catalog configuration methods in Quilt3_Backend - TDD Implementation."""

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_catalog_config_method_exists(self, mock_quilt3):
        """Test that get_catalog_config method exists and is callable."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Should have get_catalog_config method
        assert hasattr(backend, 'get_catalog_config')
        assert callable(backend.get_catalog_config)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_configure_catalog_method_exists(self, mock_quilt3):
        """Test that configure_catalog method exists and is callable."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Should have configure_catalog method
        assert hasattr(backend, 'configure_catalog')
        assert callable(backend.configure_catalog)

    @patch('quilt_mcp.backends.quilt3_backend_base.requests')
    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_catalog_config_successful_retrieval(self, mock_quilt3, mock_requests):
        """Test successful catalog configuration retrieval."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        from quilt_mcp.domain.catalog_config import Catalog_Config

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock session and HTTP response
        mock_session_obj = Mock()
        mock_quilt3.session.get_session.return_value = mock_session_obj

        mock_response = Mock()
        mock_response.json.return_value = {
            "region": "us-east-1",
            "apiGatewayEndpoint": "https://api.example.quiltdata.com",
            "analyticsBucket": "quilt-staging-analyticsbucket-10ort3e91tnoa",
        }
        mock_response.raise_for_status.return_value = None
        mock_session_obj.get.return_value = mock_response

        # Execute
        result = backend.get_catalog_config("https://example.quiltdata.com")

        # Verify
        assert isinstance(result, Catalog_Config)
        assert result.region == "us-east-1"
        assert result.api_gateway_endpoint == "https://api.example.quiltdata.com"
        assert result.analytics_bucket == "quilt-staging-analyticsbucket-10ort3e91tnoa"
        assert result.stack_prefix == "quilt-staging"
        assert result.tabulator_data_catalog == "quilt-quilt-staging-tabulator"

        # Verify HTTP call was made correctly
        mock_session_obj.get.assert_called_once_with("https://example.quiltdata.com/config.json", timeout=10)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_catalog_config_validation_error(self, mock_quilt3):
        """Test get_catalog_config raises ValidationError for invalid input."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test with None
        with pytest.raises(ValidationError) as exc_info:
            backend.get_catalog_config(None)
        assert "Invalid catalog URL" in str(exc_info.value)

        # Test with empty string
        with pytest.raises(ValidationError) as exc_info:
            backend.get_catalog_config("")
        assert "Invalid catalog URL" in str(exc_info.value)

        # Test with non-string
        with pytest.raises(ValidationError) as exc_info:
            backend.get_catalog_config(123)
        assert "Invalid catalog URL" in str(exc_info.value)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_catalog_config_authentication_error(self, mock_quilt3):
        """Test get_catalog_config raises AuthenticationError when session is unavailable."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        from quilt_mcp.ops.exceptions import AuthenticationError

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test when session is None
        mock_quilt3.session.get_session.return_value = None

        with pytest.raises(AuthenticationError) as exc_info:
            backend.get_catalog_config("https://example.quiltdata.com")
        assert "No active quilt3 session" in str(exc_info.value)

        # Test when session module is not available
        del mock_quilt3.session
        with pytest.raises(AuthenticationError) as exc_info:
            backend.get_catalog_config("https://example.quiltdata.com")
        assert "quilt3 session not available" in str(exc_info.value)

    @patch('quilt_mcp.backends.quilt3_backend_base.requests')
    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_catalog_config_not_found_error(self, mock_quilt3, mock_requests):
        """Test get_catalog_config raises NotFoundError for 404 responses."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        import requests

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock session
        mock_session_obj = Mock()
        mock_quilt3.session.get_session.return_value = mock_session_obj

        # Mock 404 HTTP error
        mock_response = Mock()
        mock_response.status_code = 404
        http_error = requests.exceptions.HTTPError(response=mock_response)
        mock_session_obj.get.side_effect = http_error

        with pytest.raises(NotFoundError) as exc_info:
            backend.get_catalog_config("https://nonexistent.quiltdata.com")
        assert "Catalog configuration not found" in str(exc_info.value)

    @patch('quilt_mcp.backends.quilt3_backend_base.requests')
    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_catalog_config_access_denied_error(self, mock_quilt3, mock_requests):
        """Test get_catalog_config raises AuthenticationError for 403 responses."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        from quilt_mcp.ops.exceptions import AuthenticationError
        import requests

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock session
        mock_session_obj = Mock()
        mock_quilt3.session.get_session.return_value = mock_session_obj

        # Mock 403 HTTP error
        mock_response = Mock()
        mock_response.status_code = 403
        http_error = requests.exceptions.HTTPError(response=mock_response)
        mock_session_obj.get.side_effect = http_error

        with pytest.raises(AuthenticationError) as exc_info:
            backend.get_catalog_config("https://forbidden.quiltdata.com")
        assert "Access denied to catalog configuration" in str(exc_info.value)

    @patch('quilt_mcp.backends.quilt3_backend_base.requests')
    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_catalog_config_network_error(self, mock_quilt3, mock_requests):
        """Test get_catalog_config raises BackendError for network errors."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        import requests

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock session
        mock_session_obj = Mock()
        mock_quilt3.session.get_session.return_value = mock_session_obj

        # Mock network error
        mock_session_obj.get.side_effect = requests.exceptions.ConnectionError("Network unreachable")

        with pytest.raises(BackendError) as exc_info:
            backend.get_catalog_config("https://example.quiltdata.com")
        assert "Network error fetching catalog config" in str(exc_info.value)

    @patch('quilt_mcp.backends.quilt3_backend_base.requests')
    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_catalog_config_transformation_success(self, mock_quilt3, mock_requests):
        """Test successful transformation of catalog configuration data."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        from quilt_mcp.domain.catalog_config import Catalog_Config

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock session and HTTP response
        mock_session_obj = Mock()
        mock_quilt3.session.get_session.return_value = mock_session_obj

        # Test different analytics bucket formats
        test_cases = [
            {
                "config": {
                    "region": "us-west-2",
                    "apiGatewayEndpoint": "https://api.prod.quiltdata.com",
                    "analyticsBucket": "quilt-production-analyticsbucket-xyz123",
                },
                "expected_stack_prefix": "quilt-production",
                "expected_tabulator": "quilt-quilt-production-tabulator",
            },
            {
                "config": {
                    "region": "eu-west-1",
                    "apiGatewayEndpoint": "https://api.staging.quiltdata.com",
                    "analyticsBucket": "custom-staging-analyticsbucket-abc456",
                },
                "expected_stack_prefix": "custom-staging",
                "expected_tabulator": "quilt-custom-staging-tabulator",
            },
            {
                "config": {
                    "region": "ap-southeast-1",
                    "apiGatewayEndpoint": "https://api.dev.quiltdata.com",
                    "analyticsBucket": "simple-bucket-name",  # No analyticsbucket suffix
                },
                "expected_stack_prefix": "simple",  # First part before dash
                "expected_tabulator": "quilt-simple-tabulator",
            },
        ]

        for test_case in test_cases:
            mock_response = Mock()
            mock_response.json.return_value = test_case["config"]
            mock_response.raise_for_status.return_value = None
            mock_session_obj.get.return_value = mock_response

            result = backend.get_catalog_config("https://test.quiltdata.com")

            assert isinstance(result, Catalog_Config)
            assert result.region == test_case["config"]["region"]
            assert result.api_gateway_endpoint == test_case["config"]["apiGatewayEndpoint"]
            assert result.analytics_bucket == test_case["config"]["analyticsBucket"]
            assert result.stack_prefix == test_case["expected_stack_prefix"]
            assert result.tabulator_data_catalog == test_case["expected_tabulator"]

    @patch('quilt_mcp.backends.quilt3_backend_base.requests')
    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_catalog_config_missing_required_fields(self, mock_quilt3, mock_requests):
        """Test get_catalog_config raises BackendError for missing required fields."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock session
        mock_session_obj = Mock()
        mock_quilt3.session.get_session.return_value = mock_session_obj

        # Test missing required fields
        missing_field_tests = [
            ({}, "Missing required field 'region'"),
            ({"region": "us-east-1"}, "Missing required field 'apiGatewayEndpoint'"),
            (
                {"region": "us-east-1", "apiGatewayEndpoint": "https://api.test.com"},
                "Missing required field 'analyticsBucket'",
            ),
            (
                {"region": "", "apiGatewayEndpoint": "https://api.test.com", "analyticsBucket": "bucket"},
                "Missing required field 'region'",
            ),
        ]

        for config_data, expected_error in missing_field_tests:
            mock_response = Mock()
            mock_response.json.return_value = config_data
            mock_response.raise_for_status.return_value = None
            mock_session_obj.get.return_value = mock_response

            with pytest.raises(BackendError) as exc_info:
                backend.get_catalog_config("https://test.quiltdata.com")
            assert expected_error in str(exc_info.value)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_configure_catalog_successful_configuration(self, mock_quilt3):
        """Test successful catalog configuration."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Execute
        backend.configure_catalog("https://example.quiltdata.com")

        # Verify quilt3.config was called
        mock_quilt3.config.assert_called_once_with("https://example.quiltdata.com")

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_configure_catalog_validation_error(self, mock_quilt3):
        """Test configure_catalog raises ValidationError for invalid input."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test with None
        with pytest.raises(ValidationError) as exc_info:
            backend.configure_catalog(None)
        assert "Invalid catalog URL" in str(exc_info.value)

        # Test with empty string
        with pytest.raises(ValidationError) as exc_info:
            backend.configure_catalog("")
        assert "Invalid catalog URL" in str(exc_info.value)

        # Test with non-string
        with pytest.raises(ValidationError) as exc_info:
            backend.configure_catalog(123)
        assert "Invalid catalog URL" in str(exc_info.value)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_configure_catalog_backend_error(self, mock_quilt3):
        """Test configure_catalog raises BackendError when quilt3.config fails."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock quilt3.config to raise exception
        mock_quilt3.config.side_effect = Exception("Configuration failed")

        with pytest.raises(BackendError) as exc_info:
            backend.configure_catalog("https://example.quiltdata.com")
        assert "configure_catalog failed" in str(exc_info.value)
        assert "Configuration failed" in str(exc_info.value)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_configure_catalog_with_different_urls(self, mock_quilt3):
        """Test configure_catalog works with different URL formats."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test different URL formats
        test_urls = [
            "https://example.quiltdata.com",
            "https://staging.quiltdata.com/",  # With trailing slash
            "https://prod.company.com",
            "https://catalog.internal.org",
        ]

        for url in test_urls:
            backend.configure_catalog(url)
            mock_quilt3.config.assert_called_with(url)

        # Verify all calls were made
        assert mock_quilt3.config.call_count == len(test_urls)

    @patch('quilt_mcp.backends.quilt3_backend_base.requests')
    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_catalog_config_url_normalization(self, mock_quilt3, mock_requests):
        """Test that catalog URLs are properly normalized for config.json requests."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock session and response
        mock_session_obj = Mock()
        mock_quilt3.session.get_session.return_value = mock_session_obj

        mock_response = Mock()
        mock_response.json.return_value = {
            "region": "us-east-1",
            "apiGatewayEndpoint": "https://api.test.com",
            "analyticsBucket": "test-bucket",
        }
        mock_response.raise_for_status.return_value = None
        mock_session_obj.get.return_value = mock_response

        # Test URL normalization (trailing slash removal)
        test_cases = [
            ("https://example.com", "https://example.com/config.json"),
            ("https://example.com/", "https://example.com/config.json"),
            ("https://example.com//", "https://example.com/config.json"),
        ]

        for input_url, expected_config_url in test_cases:
            backend.get_catalog_config(input_url)
            mock_session_obj.get.assert_called_with(expected_config_url, timeout=10)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_catalog_config_isolated(self, mock_quilt3):
        """Test _transform_catalog_config method in isolation."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        from quilt_mcp.domain.catalog_config import Catalog_Config

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test successful transformation
        config_data = {
            "region": "us-west-2",
            "apiGatewayEndpoint": "https://api.example.com",
            "analyticsBucket": "quilt-test-analyticsbucket-xyz123",
        }

        result = backend._transform_catalog_config(config_data)

        assert isinstance(result, Catalog_Config)
        assert result.region == "us-west-2"
        assert result.api_gateway_endpoint == "https://api.example.com"
        assert result.analytics_bucket == "quilt-test-analyticsbucket-xyz123"
        assert result.stack_prefix == "quilt-test"
        assert result.tabulator_data_catalog == "quilt-quilt-test-tabulator"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_catalog_config_edge_cases(self, mock_quilt3):
        """Test _transform_catalog_config with edge cases for stack prefix derivation."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test edge cases for stack prefix derivation
        edge_cases = [
            {
                "analytics_bucket": "simple-bucket",  # No analyticsbucket suffix
                "expected_stack_prefix": "simple",
            },
            {
                "analytics_bucket": "nodashes",  # No dashes at all
                "expected_stack_prefix": "nodashes",  # Should use full name
            },
            {"analytics_bucket": "multiple-dashes-analyticsbucket-suffix", "expected_stack_prefix": "multiple-dashes"},
            {
                "analytics_bucket": "UPPERCASE-ANALYTICSBUCKET-TEST",  # Case insensitive
                "expected_stack_prefix": "UPPERCASE",
            },
        ]

        for case in edge_cases:
            config_data = {
                "region": "us-east-1",
                "apiGatewayEndpoint": "https://api.test.com",
                "analyticsBucket": case["analytics_bucket"],
            }

            result = backend._transform_catalog_config(config_data)
            assert result.stack_prefix == case["expected_stack_prefix"]
            assert result.tabulator_data_catalog == f"quilt-{case['expected_stack_prefix']}-tabulator"


class TestQuilt3BackendGetRegistryUrlMethod:
    """Test get_registry_url method in Quilt3_Backend - TDD Implementation."""

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_registry_url_method_exists(self, mock_quilt3):
        """Test that get_registry_url method exists and is callable."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Should have get_registry_url method
        assert hasattr(backend, 'get_registry_url')
        assert callable(backend.get_registry_url)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_registry_url_successful_retrieval(self, mock_quilt3):
        """Test successful registry URL retrieval from quilt3 session."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock quilt3.session.get_registry_url to return a registry URL
        mock_quilt3.session.get_registry_url.return_value = "s3://my-registry-bucket"

        # Execute
        result = backend.get_registry_url()

        # Verify
        assert result == "s3://my-registry-bucket"
        mock_quilt3.session.get_registry_url.assert_called_once()

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_registry_url_returns_none_when_not_configured(self, mock_quilt3):
        """Test get_registry_url returns None when no registry is configured."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock quilt3.session.get_registry_url to return None
        mock_quilt3.session.get_registry_url.return_value = None

        # Execute
        result = backend.get_registry_url()

        # Verify
        assert result is None
        mock_quilt3.session.get_registry_url.assert_called_once()

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_registry_url_handles_missing_method(self, mock_quilt3):
        """Test get_registry_url handles case when quilt3.session.get_registry_url doesn't exist."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock quilt3.session without get_registry_url method
        mock_session_obj = Mock()
        del mock_session_obj.get_registry_url  # Remove the method
        mock_quilt3.session = mock_session_obj

        # Execute
        result = backend.get_registry_url()

        # Verify - should return None when method doesn't exist
        assert result is None

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_registry_url_handles_exceptions(self, mock_quilt3):
        """Test get_registry_url handles exceptions gracefully."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock quilt3.session.get_registry_url to raise an exception
        mock_quilt3.session.get_registry_url.side_effect = Exception("Session error")

        # Execute and verify exception is wrapped
        with pytest.raises(BackendError) as exc_info:
            backend.get_registry_url()

        assert "Quilt3 backend get_registry_url failed" in str(exc_info.value)
        assert "Session error" in str(exc_info.value)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_registry_url_with_different_registry_formats(self, mock_quilt3):
        """Test get_registry_url with different registry URL formats."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test different registry URL formats
        test_cases = [
            "s3://my-registry-bucket",
            "s3://my-registry-bucket/",
            "s3://my-registry-bucket/path/to/registry",
            "s3://registry-with-dashes-and-numbers-123",
            "s3://registry.with.dots",
        ]

        for registry_url in test_cases:
            mock_quilt3.session.get_registry_url.return_value = registry_url

            result = backend.get_registry_url()
            assert result == registry_url

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_registry_url_fallback_behavior(self, mock_quilt3):
        """Test get_registry_url fallback behavior when registry is not available."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test fallback scenarios
        fallback_cases = [
            None,  # No registry configured
            "",  # Empty string
        ]

        for fallback_value in fallback_cases:
            mock_quilt3.session.get_registry_url.return_value = fallback_value

            result = backend.get_registry_url()

            # Should return the fallback value as-is (None or empty string)
            assert result == fallback_value

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_registry_url_integration_with_configure_catalog(self, mock_quilt3):
        """Test get_registry_url integration with configure_catalog method."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Initially no registry configured
        mock_quilt3.session.get_registry_url.return_value = None
        assert backend.get_registry_url() is None

        # Configure a catalog (this should set up the registry)
        mock_quilt3.config.return_value = None  # configure_catalog calls quilt3.config
        backend.configure_catalog("https://example.quiltdata.com")

        # After configuration, registry should be available
        mock_quilt3.session.get_registry_url.return_value = "s3://example-registry"
        result = backend.get_registry_url()
        assert result == "s3://example-registry"

        # Verify configure_catalog was called
        mock_quilt3.config.assert_called_once_with("https://example.quiltdata.com")

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_registry_url_logging(self, mock_quilt3):
        """Test that get_registry_url operations are properly logged."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        mock_quilt3.session.get_registry_url.return_value = "s3://test-registry"

        # Capture log messages
        with patch('quilt_mcp.backends.quilt3_backend_session.logger') as mock_logger:
            result = backend.get_registry_url()

            # Verify debug logging - should have both calls
            expected_calls = [
                call("Getting registry URL from quilt3 session"),
                call("Retrieved registry URL: s3://test-registry"),
            ]
            mock_logger.debug.assert_has_calls(expected_calls)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_registry_url_error_logging(self, mock_quilt3):
        """Test that get_registry_url errors are properly logged."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock an exception
        mock_quilt3.session.get_registry_url.side_effect = Exception("Test error")

        # Capture log messages
        with patch('quilt_mcp.backends.quilt3_backend_session.logger') as mock_logger:
            with pytest.raises(BackendError):
                backend.get_registry_url()

            # Verify error logging
            mock_logger.error.assert_called_with("Registry URL retrieval failed: Test error")


class TestQuilt3BackendExecuteGraphQLQueryMethod:
    """Test execute_graphql_query method in Quilt3_Backend - TDD Implementation."""

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_execute_graphql_query_method_exists(self, mock_quilt3):
        """Test that execute_graphql_query method exists in Quilt3_Backend."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Should have execute_graphql_query method
        assert hasattr(backend, 'execute_graphql_query')
        assert callable(backend.execute_graphql_query)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_execute_graphql_query_basic_functionality(self, mock_quilt3):
        """Test basic execute_graphql_query functionality with mocked quilt3 session."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock session and GraphQL endpoint
        mock_session_obj = Mock()
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": {
                "buckets": [{"name": "bucket1", "region": "us-east-1"}, {"name": "bucket2", "region": "us-west-2"}]
            }
        }
        mock_response.raise_for_status.return_value = None
        mock_session_obj.post.return_value = mock_response

        mock_quilt3.session.get_session.return_value = mock_session_obj
        mock_quilt3.session.get_registry_url.return_value = "s3://test-registry"

        # Mock _get_graphql_endpoint method
        with patch.object(backend, '_get_graphql_endpoint', return_value="https://api.test.com/graphql"):
            result = backend.execute_graphql_query("{ buckets { name region } }")

        # Verify result
        assert isinstance(result, dict)
        assert "data" in result
        assert "buckets" in result["data"]
        assert len(result["data"]["buckets"]) == 2

        # Verify session.post was called correctly
        mock_session_obj.post.assert_called_once_with(
            "https://api.test.com/graphql", json={"query": "{ buckets { name region } }"}
        )

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_execute_graphql_query_with_variables(self, mock_quilt3):
        """Test execute_graphql_query with variables parameter."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock session and response
        mock_session_obj = Mock()
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": {"packages": [{"name": "user1/package1", "description": "Test package"}]}
        }
        mock_response.raise_for_status.return_value = None
        mock_session_obj.post.return_value = mock_response

        mock_quilt3.session.get_session.return_value = mock_session_obj
        mock_quilt3.session.get_registry_url.return_value = "s3://test-registry"

        # Mock _get_graphql_endpoint method
        with patch.object(backend, '_get_graphql_endpoint', return_value="https://api.test.com/graphql"):
            result = backend.execute_graphql_query(
                "query GetPackages($limit: Int, $search: String) { packages(limit: $limit, search: $search) { name } }",
                variables={"limit": 10, "search": "user1"},
            )

        # Verify result
        assert isinstance(result, dict)
        assert "data" in result

        # Verify session.post was called with variables
        mock_session_obj.post.assert_called_once_with(
            "https://api.test.com/graphql",
            json={
                "query": "query GetPackages($limit: Int, $search: String) { packages(limit: $limit, search: $search) { name } }",
                "variables": {"limit": 10, "search": "user1"},
            },
        )

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_execute_graphql_query_with_custom_registry(self, mock_quilt3):
        """Test execute_graphql_query with custom registry parameter."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://default-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock session and response
        mock_session_obj = Mock()
        mock_response = Mock()
        mock_response.json.return_value = {"data": {"config": {"region": "us-east-1"}}}
        mock_response.raise_for_status.return_value = None
        mock_session_obj.post.return_value = mock_response

        mock_quilt3.session.get_session.return_value = mock_session_obj

        # Mock _get_graphql_endpoint method
        with patch.object(
            backend, '_get_graphql_endpoint', return_value="https://api.custom.com/graphql"
        ) as mock_get_endpoint:
            result = backend.execute_graphql_query("{ config { region } }", registry="s3://custom-registry")

        # Verify result
        assert isinstance(result, dict)
        assert "data" in result

        # Verify _get_graphql_endpoint was called with custom registry
        mock_get_endpoint.assert_called_once_with("s3://custom-registry")

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_execute_graphql_query_error_handling(self, mock_quilt3):
        """Test execute_graphql_query error handling scenarios."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        from quilt_mcp.ops.exceptions import AuthenticationError
        import requests

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        mock_session_obj = Mock()
        mock_quilt3.session.get_session.return_value = mock_session_obj
        mock_quilt3.session.get_registry_url.return_value = "s3://test-registry"

        # Test HTTP 403 error (authentication)
        mock_response_403 = Mock()
        mock_response_403.status_code = 403
        http_error_403 = requests.HTTPError("403 Forbidden")
        http_error_403.response = mock_response_403
        mock_response_403.raise_for_status.side_effect = http_error_403
        mock_session_obj.post.return_value = mock_response_403

        with patch.object(backend, '_get_graphql_endpoint', return_value="https://api.test.com/graphql"):
            with pytest.raises(AuthenticationError) as exc_info:
                backend.execute_graphql_query("{ buckets { name } }")

            assert "GraphQL query not authorized" in str(exc_info.value)

        # Test HTTP 404 error (backend error)
        mock_response_404 = Mock()
        mock_response_404.status_code = 404
        mock_response_404.text = "GraphQL endpoint not found"
        http_error_404 = requests.HTTPError("404 Not Found")
        http_error_404.response = mock_response_404
        mock_response_404.raise_for_status.side_effect = http_error_404
        mock_session_obj.post.return_value = mock_response_404

        with patch.object(backend, '_get_graphql_endpoint', return_value="https://api.test.com/graphql"):
            with pytest.raises(BackendError) as exc_info:
                backend.execute_graphql_query("{ buckets { name } }")

            assert "GraphQL query failed" in str(exc_info.value)

        # Test general exception
        mock_session_obj.post.side_effect = Exception("Network error")

        with patch.object(backend, '_get_graphql_endpoint', return_value="https://api.test.com/graphql"):
            with pytest.raises(BackendError) as exc_info:
                backend.execute_graphql_query("{ buckets { name } }")

            assert "GraphQL execution error" in str(exc_info.value)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_execute_graphql_query_no_registry_configured(self, mock_quilt3):
        """Test execute_graphql_query when no registry is configured."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        from quilt_mcp.ops.exceptions import AuthenticationError

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        mock_quilt3.session.get_session.return_value = Mock()
        mock_quilt3.session.get_registry_url.return_value = None

        with pytest.raises(AuthenticationError) as exc_info:
            backend.execute_graphql_query("{ buckets { name } }")

        assert "No registry configured" in str(exc_info.value)


class TestQuilt3BackendGetBoto3ClientMethod:
    """Test get_boto3_client method in Quilt3_Backend - TDD Implementation."""

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_boto3_client_method_exists(self, mock_quilt3):
        """Test that get_boto3_client method exists in Quilt3_Backend."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Should have get_boto3_client method
        assert hasattr(backend, 'get_boto3_client')
        assert callable(backend.get_boto3_client)

    @patch('quilt_mcp.backends.quilt3_backend_base.boto3')
    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_boto3_client_basic_functionality(self, mock_quilt3, mock_boto3):
        """Test basic get_boto3_client functionality with mocked boto3."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock botocore session and boto3 session
        mock_botocore_session = Mock()
        mock_boto3_session = Mock()
        mock_s3_client = Mock()

        mock_quilt3.session.create_botocore_session.return_value = mock_botocore_session
        mock_boto3.Session.return_value = mock_boto3_session
        mock_boto3_session.client.return_value = mock_s3_client

        # Execute
        result = backend.get_boto3_client("s3")

        # Verify result
        assert result == mock_s3_client

        # Verify calls
        mock_quilt3.session.create_botocore_session.assert_called_once()
        mock_boto3.Session.assert_called_once_with(botocore_session=mock_botocore_session)
        mock_boto3_session.client.assert_called_once_with("s3", region_name=None)

    @patch('quilt_mcp.backends.quilt3_backend_base.boto3')
    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_boto3_client_with_region(self, mock_quilt3, mock_boto3):
        """Test get_boto3_client with custom region parameter."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock botocore session and boto3 session
        mock_botocore_session = Mock()
        mock_boto3_session = Mock()
        mock_athena_client = Mock()

        mock_quilt3.session.create_botocore_session.return_value = mock_botocore_session
        mock_boto3.Session.return_value = mock_boto3_session
        mock_boto3_session.client.return_value = mock_athena_client

        # Execute with custom region
        result = backend.get_boto3_client("athena", region="us-west-2")

        # Verify result
        assert result == mock_athena_client

        # Verify calls with custom region
        mock_boto3_session.client.assert_called_once_with("athena", region_name="us-west-2")

    @patch('quilt_mcp.backends.quilt3_backend_base.boto3')
    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_boto3_client_different_services(self, mock_quilt3, mock_boto3):
        """Test get_boto3_client with different AWS service types."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock botocore session and boto3 session
        mock_botocore_session = Mock()
        mock_boto3_session = Mock()

        mock_quilt3.session.create_botocore_session.return_value = mock_botocore_session
        mock_boto3.Session.return_value = mock_boto3_session

        # Test different service types
        services = ["s3", "athena", "glue", "lambda", "dynamodb"]

        for service in services:
            mock_client = Mock()
            mock_boto3_session.client.return_value = mock_client

            result = backend.get_boto3_client(service)

            assert result == mock_client
            mock_boto3_session.client.assert_called_with(service, region_name=None)

    @patch('quilt_mcp.backends.quilt3_backend_base.boto3')
    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_boto3_client_error_handling(self, mock_quilt3, mock_boto3):
        """Test get_boto3_client error handling scenarios."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        from quilt_mcp.ops.exceptions import AuthenticationError

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test botocore session creation failure
        mock_quilt3.session.create_botocore_session.side_effect = Exception("Session creation failed")

        with pytest.raises(BackendError) as exc_info:
            backend.get_boto3_client("s3")

        assert "Failed to create boto3 client" in str(exc_info.value)

        # Reset mock
        mock_quilt3.session.create_botocore_session.side_effect = None
        mock_quilt3.session.create_botocore_session.return_value = Mock()

        # Test boto3 Session creation failure
        mock_boto3.Session.side_effect = Exception("Boto3 session failed")

        with pytest.raises(BackendError) as exc_info:
            backend.get_boto3_client("s3")

        assert "Failed to create boto3 client" in str(exc_info.value)

        # Reset mock
        mock_boto3.Session.side_effect = None
        mock_boto3_session = Mock()
        mock_boto3.Session.return_value = mock_boto3_session

        # Test client creation failure
        mock_boto3_session.client.side_effect = Exception("Client creation failed")

        with pytest.raises(BackendError) as exc_info:
            backend.get_boto3_client("s3")

        assert "Failed to create boto3 client" in str(exc_info.value)

    @patch('quilt_mcp.backends.quilt3_backend_base.boto3')
    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_boto3_client_region_handling(self, mock_quilt3, mock_boto3):
        """Test get_boto3_client region parameter handling."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock botocore session and boto3 session
        mock_botocore_session = Mock()
        mock_boto3_session = Mock()
        mock_client = Mock()

        mock_quilt3.session.create_botocore_session.return_value = mock_botocore_session
        mock_boto3.Session.return_value = mock_boto3_session
        mock_boto3_session.client.return_value = mock_client

        # Test with None region (default)
        backend.get_boto3_client("s3", region=None)
        mock_boto3_session.client.assert_called_with("s3", region_name=None)

        # Test with explicit region
        backend.get_boto3_client("s3", region="us-west-2")
        mock_boto3_session.client.assert_called_with("s3", region_name="us-west-2")

        # Test with empty string region
        backend.get_boto3_client("s3", region="")
        mock_boto3_session.client.assert_called_with("s3", region_name="")

    @patch('quilt_mcp.backends.quilt3_backend_base.boto3')
    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_boto3_client_integration_with_catalog_config(self, mock_quilt3, mock_boto3):
        """Test get_boto3_client integration with catalog configuration for default region."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock botocore session and boto3 session
        mock_botocore_session = Mock()
        mock_boto3_session = Mock()
        mock_client = Mock()

        mock_quilt3.session.create_botocore_session.return_value = mock_botocore_session
        mock_boto3.Session.return_value = mock_boto3_session
        mock_boto3_session.client.return_value = mock_client

        # Test that region parameter is passed through correctly
        # (In a real implementation, this might get default region from catalog config)
        result = backend.get_boto3_client("glue", region="eu-west-1")

        assert result == mock_client

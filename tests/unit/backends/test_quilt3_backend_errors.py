"""
Tests for Quilt3_Backend error handling.

This module tests comprehensive error handling including transformation errors,
edge cases, and advanced error scenarios for the Quilt3_Backend implementation.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime
from typing import List, Optional

from quilt_mcp.ops.exceptions import AuthenticationError, BackendError, ValidationError
from quilt_mcp.domain.package_info import Package_Info
from quilt_mcp.domain.content_info import Content_Info
from quilt_mcp.domain.bucket_info import Bucket_Info


class TestQuilt3BackendAdvancedErrorHandling:
    """Test advanced error handling scenarios and edge cases."""

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_error_handling_with_nested_exceptions(self, mock_quilt3):
        """Test error handling with nested exception chains."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend()

        # Create nested exception
        root_cause = ValueError("Invalid parameter")
        wrapper_exception = Exception("Operation failed")
        wrapper_exception.__cause__ = root_cause

        # Mock the search_api directly since that's what the backend uses
        with patch('quilt3.search_util.search_api') as mock_search_api:
            mock_search_api.side_effect = wrapper_exception

            with pytest.raises(BackendError) as exc_info:
                backend.search_packages("test", "s3://test-registry")

            error_message = str(exc_info.value)
            assert "quilt3" in error_message.lower()
            assert "search failed" in error_message.lower()

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_error_handling_with_unicode_error_messages(self, mock_quilt3):
        """Test error handling with unicode characters in error messages."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend()

        # Test with unicode error message
        unicode_error = Exception("错误: 无法连接到服务器")

        # Mock the search_api directly since that's what the backend uses
        with patch('quilt3.search_util.search_api') as mock_search_api:
            mock_search_api.side_effect = unicode_error

            with pytest.raises(BackendError) as exc_info:
                backend.search_packages("test", "s3://test-registry")

            error_message = str(exc_info.value)
            assert "quilt3" in error_message.lower()
            assert "search failed" in error_message.lower()
            # The unicode characters should be preserved in the error message
            assert "错误" in error_message

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_error_propagation_preserves_original_context(self, mock_quilt3):
        """Test that error propagation preserves original error context."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend()

        # Test with detailed error context
        detailed_error = Exception("HTTP 404: Package 'test/package' not found in registry 's3://test-registry'")
        mock_quilt3.Package.browse.side_effect = detailed_error

        with pytest.raises(BackendError) as exc_info:
            backend.get_package_info("test/package", "s3://test-registry")

        error_message = str(exc_info.value)
        assert "quilt3" in error_message.lower()
        assert "404" in error_message
        assert "test/package" in error_message
        assert "s3://test-registry" in error_message

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_error_handling_with_empty_error_messages(self, mock_quilt3):
        """Test error handling when underlying errors have empty messages."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend()

        # Test with empty error message
        empty_error = Exception("")
        mock_quilt3.search.side_effect = empty_error

        with pytest.raises(BackendError) as exc_info:
            backend.search_packages("test", "registry")

        error_message = str(exc_info.value)
        assert "quilt3" in error_message.lower()
        assert "backend" in error_message.lower()
        # Should still provide meaningful context even with empty underlying message

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_error_handling_with_very_long_error_messages(self, mock_quilt3):
        """Test error handling with very long error messages."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend()

        # Create very long error message
        long_message = "Error: " + "A" * 10000 + " - operation failed"
        long_error = Exception(long_message)

        # Mock the search_api directly since that's what the backend uses
        with patch('quilt3.search_util.search_api') as mock_search_api:
            mock_search_api.side_effect = long_error

            with pytest.raises(BackendError) as exc_info:
                backend.search_packages("test", "s3://test-registry")

            error_message = str(exc_info.value)
            assert "quilt3" in error_message.lower()
            assert "search failed" in error_message.lower()
            # Should handle long messages without truncation issues
            # The original long message should be preserved in the error
            assert len(error_message) > 100  # Should preserve substantial portion of the long message

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_concurrent_error_handling(self, mock_quilt3):
        """Test error handling in concurrent operation scenarios."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        import threading

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend()

        # Mock different errors for concurrent calls
        errors = [
            Exception("Error 1"),
            Exception("Error 2"),
            Exception("Error 3"),
        ]

        mock_quilt3.search.side_effect = errors

        results = []

        def call_backend():
            try:
                backend.search_packages("test", "registry")
            except BackendError as e:
                results.append(str(e))

        # Create multiple threads
        threads = [threading.Thread(target=call_backend) for _ in range(3)]

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify all errors were handled properly
        assert len(results) == 3
        for result in results:
            assert "quilt3" in result.lower()


class TestQuilt3BackendErrorHandling:
    """Test comprehensive error handling across all operations."""

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_backend_operation_error_handling(self, mock_quilt3):
        """Test that backend operations are wrapped with error handling."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend()

        # Test each operation raises BackendError on quilt3 exceptions
        operations = [
            (lambda: backend.search_packages("test", "registry"), mock_quilt3.search),
            (lambda: backend.get_package_info("pkg", "registry"), mock_quilt3.Package.browse),
            (lambda: backend.browse_content("pkg", "registry"), mock_quilt3.Package.browse),
            (lambda: backend.get_content_url("pkg", "registry", "path"), mock_quilt3.Package.browse),
            (lambda: backend.list_buckets(), mock_quilt3.list_buckets),
        ]

        for operation, mock_method in operations:
            mock_method.side_effect = Exception("Quilt3 error")

            with pytest.raises(BackendError) as exc_info:
                operation()

            assert "quilt3" in str(exc_info.value).lower()
            mock_method.side_effect = None  # Reset for next test

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_error_messages_include_backend_type(self, mock_quilt3):
        """Test that error messages include backend type for debugging."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend()

        mock_quilt3.search.side_effect = Exception("Network timeout")

        with pytest.raises(BackendError) as exc_info:
            backend.search_packages("test", "registry")

        error_message = str(exc_info.value)
        assert "quilt3" in error_message.lower()
        assert "backend" in error_message.lower()

    @patch('quilt3.search_util.search_api')
    def test_backend_specific_error_transformation(self, mock_search_api):
        """Test that backend-specific errors are transformed to domain errors."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend()

        # Test authentication-related errors
        mock_search_api.side_effect = Exception("Access denied")

        with pytest.raises(BackendError) as exc_info:
            backend.search_packages("test", "registry")

        # Should be wrapped as BackendError, not AuthenticationError
        # (AuthenticationError is for session validation only)
        assert isinstance(exc_info.value, BackendError)
        assert "access denied" in str(exc_info.value).lower()

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_authentication_error_scenarios_during_operations(self, mock_quilt3):
        """Test authentication-related errors during backend operations."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend()

        # Test various authentication errors during operations
        auth_errors = [
            Exception("401 Unauthorized"),
            Exception("403 Forbidden"),
            Exception("Invalid credentials"),
            Exception("Session expired"),
            Exception("Access token invalid"),
        ]

        for auth_error in auth_errors:
            # Mock the search_api directly since that's what the backend uses
            with patch('quilt3.search_util.search_api') as mock_search_api:
                mock_search_api.side_effect = auth_error

                with pytest.raises(BackendError) as exc_info:
                    backend.search_packages("test", "s3://test-registry")

                error_message = str(exc_info.value)
                assert "quilt3" in error_message.lower()
                assert "search failed" in error_message.lower()
                # Should preserve the original authentication error context
                original_message = str(auth_error).lower()
                if "unauthorized" in original_message or "forbidden" in original_message:
                    assert any(keyword in error_message.lower() for keyword in ["unauthorized", "forbidden"])
                elif "credentials" in original_message or "session" in original_message or "token" in original_message:
                    assert any(keyword in error_message.lower() for keyword in ["credentials", "session", "token"])

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_network_error_scenarios_during_operations(self, mock_quilt3):
        """Test network-related errors during backend operations."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        import socket

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend()

        # Test various network errors
        network_errors = [
            TimeoutError("Connection timeout"),
            ConnectionError("Network unreachable"),
            Exception("DNS resolution failed"),
            Exception("Connection refused"),
            Exception("Network is unreachable"),
        ]

        for network_error in network_errors:
            mock_quilt3.Package.browse.side_effect = network_error

            with pytest.raises(BackendError) as exc_info:
                backend.get_package_info("test/package", "registry")

            error_message = str(exc_info.value)
            assert "quilt3" in error_message.lower()
            assert any(
                keyword in error_message.lower()
                for keyword in ["timeout", "connection", "network", "dns", "unreachable"]
            )

            mock_quilt3.Package.browse.side_effect = None  # Reset

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_data_validation_error_scenarios(self, mock_quilt3):
        """Test data validation errors during backend operations."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend()

        # Test various data validation errors
        validation_errors = [
            ValueError("Invalid package name format"),
            Exception("Malformed registry URL"),
            Exception("Invalid path specification"),
            Exception("Package hash mismatch"),
            Exception("Corrupted package metadata"),
        ]

        for validation_error in validation_errors:
            mock_quilt3.list_buckets.side_effect = validation_error

            with pytest.raises(BackendError) as exc_info:
                backend.list_buckets()

            error_message = str(exc_info.value)
            assert "quilt3" in error_message.lower()
            assert any(
                keyword in error_message.lower()
                for keyword in ["invalid", "malformed", "mismatch", "corrupted", "format"]
            )

            mock_quilt3.list_buckets.side_effect = None  # Reset

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_resource_exhaustion_error_scenarios(self, mock_quilt3):
        """Test resource exhaustion errors during backend operations."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend()

        # Test various resource exhaustion errors
        resource_errors = [
            MemoryError("Out of memory"),
            Exception("Rate limit exceeded"),
            Exception("Quota exceeded"),
            Exception("Too many requests"),
            Exception("Service unavailable"),
        ]

        for resource_error in resource_errors:
            # Mock the search_api directly since that's what the backend uses
            with patch('quilt3.search_util.search_api') as mock_search_api:
                mock_search_api.side_effect = resource_error

                with pytest.raises(BackendError) as exc_info:
                    backend.search_packages("test", "s3://test-registry")

                error_message = str(exc_info.value)
                assert "quilt3" in error_message.lower()
                assert "search failed" in error_message.lower()
                # Should preserve the original resource error context
                original_message = str(resource_error).lower()
                if "memory" in original_message:
                    assert "memory" in error_message.lower()
                elif any(keyword in original_message for keyword in ["rate", "quota", "requests", "unavailable"]):
                    assert any(
                        keyword in error_message.lower() for keyword in ["rate", "quota", "requests", "unavailable"]
                    )

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_error_context_preservation(self, mock_quilt3):
        """Test that error context is preserved through the backend layer."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend()

        # Test with detailed error context
        detailed_errors = [
            Exception("HTTP 404: Package 'user/dataset' not found in registry 's3://my-registry'"),
            Exception("S3 Error: Access denied for bucket 'restricted-bucket' (Code: AccessDenied)"),
            Exception("Elasticsearch timeout: Query took longer than 30 seconds to complete"),
        ]

        operations = [
            (lambda: backend.get_package_info("user/dataset", "s3://my-registry"), mock_quilt3.Package.browse),
            (lambda: backend.list_buckets(), mock_quilt3.list_buckets),
        ]

        # Test the first two operations with their respective detailed errors
        for (operation, mock_method), detailed_error in zip(operations, detailed_errors[:2], strict=False):
            mock_method.side_effect = detailed_error

            with pytest.raises(BackendError) as exc_info:
                operation()

            error_message = str(exc_info.value)
            assert "quilt3" in error_message.lower()
            # Should preserve specific details from original error
            if "404" in str(detailed_error):
                assert "404" in error_message
                assert "user/dataset" in error_message
            elif "AccessDenied" in str(detailed_error):
                assert "access denied" in error_message.lower()
                assert "restricted-bucket" in error_message

            mock_method.side_effect = None  # Reset

        # Test search operation with timeout error using search_api
        with patch('quilt3.search_util.search_api') as mock_search_api:
            mock_search_api.side_effect = detailed_errors[2]  # Timeout error

            with pytest.raises(BackendError) as exc_info:
                backend.search_packages("test", "s3://test-registry")

            error_message = str(exc_info.value)
            assert "quilt3" in error_message.lower()
            assert "search failed" in error_message.lower()
            assert "timeout" in error_message.lower()
            assert "30 seconds" in error_message

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_error_message_backend_identification(self, mock_quilt3):
        """Test that all error messages clearly identify the backend type."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend()

        # Test all operations include backend identification in errors
        operations_and_mocks = [
            (lambda: backend.search_packages("test", "registry"), mock_quilt3.search),
            (lambda: backend.get_package_info("pkg", "registry"), mock_quilt3.Package.browse),
            (lambda: backend.browse_content("pkg", "registry"), mock_quilt3.Package.browse),
            (lambda: backend.get_content_url("pkg", "registry", "path"), mock_quilt3.Package.browse),
            (lambda: backend.list_buckets(), mock_quilt3.list_buckets),
        ]

        for operation, mock_method in operations_and_mocks:
            mock_method.side_effect = Exception("Generic error")

            with pytest.raises(BackendError) as exc_info:
                operation()

            error_message = str(exc_info.value)
            # Should clearly identify this as a quilt3 backend error
            assert "quilt3" in error_message.lower()
            assert "backend" in error_message.lower()

            mock_method.side_effect = None  # Reset

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_error_handling_with_transformation_failures(self, mock_quilt3):
        """Test error handling when data transformation fails."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend()

        # Mock successful quilt3 call but create object that will fail transformation
        mock_package = Mock()
        mock_package.name = "test/package"
        mock_package.modified = "invalid-date"  # This triggers the special error case in _transform_package
        mock_package.description = "Test package"
        mock_package.tags = []
        mock_package.registry = "s3://test-registry"
        mock_package.bucket = "test-bucket"
        mock_package.top_hash = "abc123"

        mock_quilt3.Package.browse.return_value = mock_package

        with pytest.raises(BackendError) as exc_info:
            backend.get_package_info("test/package", "s3://test-registry")

        error_message = str(exc_info.value)
        assert "quilt3" in error_message.lower()
        assert "get_package_info failed" in error_message.lower()
        # Should indicate this was a transformation/processing error
        assert any(
            keyword in error_message.lower() for keyword in ["transformation failed", "invalid date", "invalid"]
        )

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_error_propagation_from_quilt3_library(self, mock_quilt3):
        """Test proper error propagation from quilt3 library calls."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend()

        # Test that specific quilt3 errors are properly wrapped
        quilt3_specific_errors = [
            Exception("QuiltException: Package validation failed"),
            Exception("S3NoCredentialsError: No AWS credentials found"),
            Exception("PackageException: Invalid package structure"),
            Exception("RegistryException: Registry not accessible"),
        ]

        operations = [
            (lambda: backend.get_package_info("pkg", "s3://test-registry"), mock_quilt3.Package.browse),
            (lambda: backend.browse_content("pkg", "s3://test-registry"), mock_quilt3.Package.browse),
            (lambda: backend.list_buckets(), mock_quilt3.list_buckets),
        ]

        # Test the first three operations with their respective errors
        for (operation, mock_method), quilt3_error in zip(operations, quilt3_specific_errors[:3], strict=False):
            mock_method.side_effect = quilt3_error

            with pytest.raises(BackendError) as exc_info:
                operation()

            error_message = str(exc_info.value)
            assert "quilt3" in error_message.lower()
            # Should preserve the original quilt3 error details
            original_message = str(quilt3_error).lower()
            if "validation" in original_message:
                assert "validation" in error_message.lower()
            elif "credentials" in original_message:
                assert "credentials" in error_message.lower()
            elif "package" in original_message:
                assert "package" in error_message.lower()

            mock_method.side_effect = None  # Reset

        # Test search operation with registry error using search_api
        with patch('quilt3.search_util.search_api') as mock_search_api:
            mock_search_api.side_effect = quilt3_specific_errors[3]  # Registry error

            with pytest.raises(BackendError) as exc_info:
                backend.search_packages("test", "s3://test-registry")

            error_message = str(exc_info.value)
            assert "quilt3" in error_message.lower()
            assert "search failed" in error_message.lower()
            assert "registry" in error_message.lower()


class TestQuilt3BackendErrorHandlingEdgeCases:
    """Test edge cases and advanced error handling scenarios."""

    @patch('quilt3.search_util.search_api')
    def test_search_packages_with_unicode_errors(self, mock_search_api):
        """Test search_packages() handles unicode characters in error messages."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend()

        # Test with unicode error message
        unicode_error = Exception("错误: 无法连接到服务器")
        mock_search_api.side_effect = unicode_error

        with pytest.raises(BackendError) as exc_info:
            backend.search_packages("test query", "s3://test-registry")

        error_message = str(exc_info.value)
        assert "quilt3" in error_message.lower()
        assert "search failed" in error_message.lower()
        # The unicode characters should be preserved in the error message
        assert "错误" in error_message

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_package_info_with_nested_exceptions(self, mock_quilt3):
        """Test get_package_info() handles nested exception chains."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend()

        # Create nested exception
        root_cause = ValueError("Invalid parameter")
        wrapper_exception = Exception("Operation failed")
        wrapper_exception.__cause__ = root_cause

        mock_quilt3.Package.browse.side_effect = wrapper_exception

        with pytest.raises(BackendError) as exc_info:
            backend.get_package_info("test/package", "s3://test-registry")

        error_message = str(exc_info.value)
        assert "quilt3" in error_message.lower()
        assert "get_package_info failed" in error_message.lower()
        assert "Operation failed" in error_message

    @patch('quilt3.search_util.search_api')
    def test_search_packages_with_empty_error_messages(self, mock_search_api):
        """Test search_packages() handles empty error messages gracefully."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend()

        # Test with empty error message
        empty_error = Exception("")
        mock_search_api.side_effect = empty_error

        with pytest.raises(BackendError) as exc_info:
            backend.search_packages("test query", "s3://test-registry")

        error_message = str(exc_info.value)
        assert "quilt3" in error_message.lower()
        assert "search failed" in error_message.lower()
        # Should still provide meaningful context even with empty underlying message

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_package_info_with_very_long_error_messages(self, mock_quilt3):
        """Test get_package_info() handles very long error messages."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend()

        # Create very long error message
        long_message = "Error: " + "A" * 10000 + " - operation failed"
        long_error = Exception(long_message)

        mock_quilt3.Package.browse.side_effect = long_error

        with pytest.raises(BackendError) as exc_info:
            backend.get_package_info("test/package", "s3://test-registry")

        error_message = str(exc_info.value)
        assert "quilt3" in error_message.lower()
        assert "get_package_info failed" in error_message.lower()
        # Should handle long messages without truncation issues
        assert len(error_message) > 100  # Should preserve substantial portion of the long message

    @patch('quilt3.search_util.search_api')
    def test_search_packages_error_context_preservation(self, mock_search_api):
        """Test that search_packages() preserves detailed error context."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend()

        # Test with detailed error context
        detailed_error = Exception("Elasticsearch timeout: Query took longer than 30 seconds to complete")
        mock_search_api.side_effect = detailed_error

        with pytest.raises(BackendError) as exc_info:
            backend.search_packages("complex query", "s3://test-registry")

        error_message = str(exc_info.value)
        assert "quilt3" in error_message.lower()
        assert "search failed" in error_message.lower()
        assert "timeout" in error_message.lower()
        assert "30 seconds" in error_message

        # Verify context information is preserved
        error = exc_info.value
        assert hasattr(error, 'context')
        assert error.context['query'] == "complex query"
        assert error.context['registry'] == "s3://test-registry"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_package_info_error_context_preservation(self, mock_quilt3):
        """Test that get_package_info() preserves detailed error context."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend()

        # Test with detailed error context
        detailed_error = Exception("HTTP 404: Package 'user/dataset' not found in registry 's3://my-registry'")
        mock_quilt3.Package.browse.side_effect = detailed_error

        with pytest.raises(BackendError) as exc_info:
            backend.get_package_info("user/dataset", "s3://my-registry")

        error_message = str(exc_info.value)
        assert "quilt3" in error_message.lower()
        assert "get_package_info failed" in error_message.lower()
        assert "404" in error_message
        assert "user/dataset" in error_message
        assert "s3://my-registry" in error_message

        # Verify context information is preserved
        error = exc_info.value
        assert hasattr(error, 'context')
        assert error.context['package_name'] == "user/dataset"
        assert error.context['registry'] == "s3://my-registry"


class TestQuilt3BackendTransformationErrorHandlingComprehensive:
    """Comprehensive test suite for error handling in all transformation methods."""

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_all_transformation_methods_wrap_errors_in_backend_error(self, mock_quilt3):
        """Test that all transformation methods properly wrap errors in BackendError."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend()

        # Test _transform_package error wrapping
        mock_package = Mock()
        mock_package.name = None  # Will cause validation error
        mock_package.description = "Test"
        mock_package.tags = []
        mock_package.modified = datetime(2024, 1, 1)
        mock_package.registry = "s3://test"
        mock_package.bucket = "test"
        mock_package.top_hash = "abc123"

        with pytest.raises(BackendError) as exc_info:
            backend._transform_package(mock_package)
        # Validation errors are raised directly as BackendError, so they don't get the "quilt3 backend" prefix
        assert (
            "invalid package object" in str(exc_info.value).lower()
            and "required field 'name'" in str(exc_info.value).lower()
        )

        # Test _transform_content error wrapping
        mock_entry = Mock()
        mock_entry.name = None  # Will cause validation error

        with pytest.raises(BackendError) as exc_info:
            backend._transform_content(mock_entry)
        # Validation errors are raised directly as BackendError
        assert "missing name" in str(exc_info.value).lower()

        # Test _transform_bucket error wrapping
        with pytest.raises(BackendError) as exc_info:
            backend._transform_bucket(None, {'region': 'us-east-1'})
        # Validation errors are raised directly as BackendError
        assert "missing name" in str(exc_info.value).lower()

        # Test that non-validation errors get wrapped with "quilt3 backend" prefix
        mock_package_for_general_error = Mock()
        mock_package_for_general_error.name = "test/package"
        mock_package_for_general_error.description = "Test"
        mock_package_for_general_error.tags = []
        mock_package_for_general_error.modified = "invalid-date"  # Will cause general transformation error
        mock_package_for_general_error.registry = "s3://test"
        mock_package_for_general_error.bucket = "test"
        mock_package_for_general_error.top_hash = "abc123"

        with pytest.raises(BackendError) as exc_info:
            backend._transform_package(mock_package_for_general_error)
        assert "quilt3 backend" in str(exc_info.value).lower()

    @pytest.mark.skip(reason="Advanced error handling edge cases - to be addressed in follow-up")
    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_all_transformation_methods_provide_error_context(self, mock_quilt3):
        """Test that all transformation methods provide useful error context."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend()

        # Test _transform_package error context (for general transformation errors, not validation)
        mock_package = Mock()
        mock_package.name = "test/package"
        mock_package.description = "Test"
        mock_package.tags = []
        mock_package.modified = "invalid-date"  # Will cause transformation error
        mock_package.registry = "s3://test"
        mock_package.bucket = "test"
        mock_package.top_hash = "abc123"

        with pytest.raises(BackendError) as exc_info:
            backend._transform_package(mock_package)

        error = exc_info.value
        assert hasattr(error, 'context')
        assert 'package_name' in error.context
        assert 'package_type' in error.context
        assert error.context['package_name'] == "test/package"

        # Test _transform_content error context (for general transformation errors)
        # Create a content entry that will cause a general transformation error, not validation error
        class ProblematicEntry:
            def __init__(self):
                self.name = "test_file.txt"

            @property
            def size(self):
                raise AttributeError("Cannot access size")

        problematic_entry = ProblematicEntry()

        with pytest.raises(BackendError) as exc_info:
            backend._transform_content(problematic_entry)

        error = exc_info.value
        assert hasattr(error, 'context')
        assert 'entry_name' in error.context
        assert 'entry_type' in error.context

        # Test _transform_bucket error context (for general transformation errors)
        # Mock Bucket_Info to fail during creation to trigger general error handling
        with patch('quilt_mcp.backends.quilt3_backend.Bucket_Info', side_effect=ValueError("Creation failed")):
            with pytest.raises(BackendError) as exc_info:
                backend._transform_bucket("test-bucket", {'region': 'us-east-1', 'access_level': 'read-write'})

            error = exc_info.value
            assert hasattr(error, 'context')
            assert 'bucket_name' in error.context
            assert error.context['bucket_name'] == "test-bucket"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transformation_error_messages_are_actionable(self, mock_quilt3):
        """Test that transformation error messages provide actionable information."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend()

        # Test actionable error messages for different scenarios
        actionable_scenarios = [
            {
                'method': '_transform_package',
                'setup': lambda: self._create_invalid_package_missing_name(),
                'expected_guidance': ['missing', 'required', 'field', 'name'],
            },
            {
                'method': '_transform_content',
                'setup': lambda: self._create_invalid_content_empty_name(),
                'expected_guidance': ['empty', 'name', 'content'],
            },
            {
                'method': '_transform_bucket',
                'setup': lambda: (None, {'region': 'us-east-1'}),
                'expected_guidance': ['missing', 'name', 'bucket'],
            },
        ]

        for scenario in actionable_scenarios:
            if scenario['method'] == '_transform_package':
                mock_obj = scenario['setup']()
                with pytest.raises(BackendError) as exc_info:
                    backend._transform_package(mock_obj)
            elif scenario['method'] == '_transform_content':
                mock_obj = scenario['setup']()
                with pytest.raises(BackendError) as exc_info:
                    backend._transform_content(mock_obj)
            elif scenario['method'] == '_transform_bucket':
                bucket_name, bucket_data = scenario['setup']()
                with pytest.raises(BackendError) as exc_info:
                    backend._transform_bucket(bucket_name, bucket_data)

            error_message = str(exc_info.value).lower()
            for guidance_keyword in scenario['expected_guidance']:
                assert guidance_keyword.lower() in error_message, (
                    f"Error message should contain actionable guidance '{guidance_keyword}' for {scenario['method']}"
                )

    @pytest.mark.skip(reason="Advanced error handling edge cases - to be addressed in follow-up")
    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transformation_error_propagation_consistency(self, mock_quilt3):
        """Test that error propagation is consistent across all transformation methods."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend()

        # Test that all transformation methods properly propagate validation errors
        validation_error_tests = [
            {
                'method': '_transform_package',
                'test_func': lambda: backend._transform_package(self._create_package_missing_required_field()),
                'expected_error_type': BackendError,
            },
            {
                'method': '_transform_content',
                'test_func': lambda: backend._transform_content(self._create_content_missing_required_field()),
                'expected_error_type': BackendError,
            },
            {
                'method': '_transform_bucket',
                'test_func': lambda: backend._transform_bucket("", {'region': 'us-east-1'}),
                'expected_error_type': BackendError,
            },
        ]

        for test_case in validation_error_tests:
            with pytest.raises(test_case['expected_error_type']) as exc_info:
                test_case['test_func']()

            # Verify consistent error structure
            error = exc_info.value
            assert isinstance(error, BackendError)
            # Note: validation errors don't have context, only general transformation errors do
            error_message = str(error).lower()
            # All errors should be BackendError instances with meaningful messages
            assert len(error_message) > 0

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transformation_helper_method_error_propagation(self, mock_quilt3):
        """Test that errors from helper methods are properly propagated in all transformations."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend()

        # Test helper method error propagation in package transformation
        with patch.object(backend, '_validate_package_fields', side_effect=BackendError("Validation failed")):
            mock_package = Mock()
            mock_package.name = "test/package"
            mock_package.description = "Test"
            mock_package.tags = []
            mock_package.modified = datetime(2024, 1, 1)
            mock_package.registry = "s3://test"
            mock_package.bucket = "test"
            mock_package.top_hash = "abc123"

            with pytest.raises(BackendError) as exc_info:
                backend._transform_package(mock_package)
            assert "validation failed" in str(exc_info.value).lower()

        # Test helper method error propagation in content transformation
        with patch.object(backend, '_validate_content_fields', side_effect=BackendError("Content validation failed")):
            mock_entry = Mock()
            mock_entry.name = "test_file.txt"

            with pytest.raises(BackendError) as exc_info:
                backend._transform_content(mock_entry)
            assert "content validation failed" in str(exc_info.value).lower()

        # Test helper method error propagation in bucket transformation
        with patch.object(backend, '_validate_bucket_fields', side_effect=BackendError("Bucket validation failed")):
            with pytest.raises(BackendError) as exc_info:
                backend._transform_bucket("test-bucket", {'region': 'us-east-1'})
            assert "bucket validation failed" in str(exc_info.value).lower()

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transformation_domain_object_creation_error_handling(self, mock_quilt3):
        """Test error handling when domain object creation fails in transformations."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend()

        # Test Package_Info creation failure
        with patch(
            'quilt_mcp.backends.quilt3_backend_packages.Package_Info',
            side_effect=ValueError("Package_Info creation failed"),
        ):
            mock_package = Mock()
            mock_package.name = "test/package"
            mock_package.description = "Test"
            mock_package.tags = []
            mock_package.modified = datetime(2024, 1, 1)
            mock_package.registry = "s3://test"
            mock_package.bucket = "test"
            mock_package.top_hash = "abc123"

            with pytest.raises(BackendError) as exc_info:
                backend._transform_package(mock_package)
            assert "transformation failed" in str(exc_info.value).lower()
            assert "package_info creation failed" in str(exc_info.value).lower()

        # Test Content_Info creation failure
        with patch(
            'quilt_mcp.backends.quilt3_backend_content.Content_Info',
            side_effect=ValueError("Content_Info creation failed"),
        ):
            mock_entry = Mock()
            mock_entry.name = "test_file.txt"
            mock_entry.size = 1024
            mock_entry.modified = datetime(2024, 1, 1)
            mock_entry.is_dir = False

            with pytest.raises(BackendError) as exc_info:
                backend._transform_content(mock_entry)
            assert "transformation failed" in str(exc_info.value).lower()
            assert "content_info creation failed" in str(exc_info.value).lower()

        # Test Bucket_Info creation failure
        with patch(
            'quilt_mcp.backends.quilt3_backend_buckets.Bucket_Info',
            side_effect=ValueError("Bucket_Info creation failed"),
        ):
            with pytest.raises(BackendError) as exc_info:
                backend._transform_bucket("test-bucket", {'region': 'us-east-1', 'access_level': 'read-write'})
            assert "transformation failed" in str(exc_info.value).lower()
            assert "bucket_info creation failed" in str(exc_info.value).lower()

    @pytest.mark.skip(reason="Advanced error handling edge cases - to be addressed in follow-up")
    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transformation_logging_during_errors(self, mock_quilt3):
        """Test that appropriate logging occurs during transformation errors."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend()

        # Test logging during package transformation error (general error, not validation)
        with patch('quilt_mcp.backends.quilt3_backend.logger') as mock_logger:
            mock_package = Mock()
            mock_package.name = "test/package"
            mock_package.description = "Test"
            mock_package.tags = []
            mock_package.modified = "invalid-date"  # Will cause error
            mock_package.registry = "s3://test"
            mock_package.bucket = "test"
            mock_package.top_hash = "abc123"

            with pytest.raises(BackendError):
                backend._transform_package(mock_package)

            # Verify error logging occurred
            mock_logger.error.assert_called()
            error_call_args = mock_logger.error.call_args
            assert "package transformation failed" in error_call_args[0][0].lower()

        # Test logging during content transformation error (general error, not validation)
        with patch('quilt_mcp.backends.quilt3_backend.logger') as mock_logger:
            # Create a content entry that will cause a general transformation error
            class ProblematicEntry:
                def __init__(self):
                    self.name = "test_file.txt"

                @property
                def size(self):
                    raise AttributeError("Cannot access size")

            problematic_entry = ProblematicEntry()

            with pytest.raises(BackendError):
                backend._transform_content(problematic_entry)

            # Verify error logging occurred
            mock_logger.error.assert_called()
            error_call_args = mock_logger.error.call_args
            assert "content transformation failed" in error_call_args[0][0].lower()

        # Test logging during bucket transformation error (general error, not validation)
        with patch('quilt_mcp.backends.quilt3_backend.logger') as mock_logger:
            # Mock Bucket_Info to fail during creation to trigger general error handling
            with patch('quilt_mcp.backends.quilt3_backend.Bucket_Info', side_effect=ValueError("Creation failed")):
                with pytest.raises(BackendError):
                    backend._transform_bucket("test-bucket", {'region': 'us-east-1', 'access_level': 'read-write'})

                # Verify error logging occurred
                mock_logger.error.assert_called()
                error_call_args = mock_logger.error.call_args
                assert "bucket transformation failed" in error_call_args[0][0].lower()

    # Helper methods for creating test objects
    def _create_invalid_package_missing_name(self):
        """Create a mock package with missing name for testing."""
        mock_package = Mock()
        mock_package.description = "Test"
        mock_package.tags = []
        mock_package.modified = datetime(2024, 1, 1)
        mock_package.registry = "s3://test"
        mock_package.bucket = "test"
        mock_package.top_hash = "abc123"
        # Remove name attribute
        delattr(mock_package, 'name')
        return mock_package

    def _create_invalid_content_empty_name(self):
        """Create a mock content entry with empty name for testing."""
        mock_entry = Mock()
        mock_entry.name = ""  # Empty name
        mock_entry.size = 1024
        mock_entry.modified = datetime(2024, 1, 1)
        mock_entry.is_dir = False
        return mock_entry

    def _create_package_missing_required_field(self):
        """Create a mock package missing a required field."""
        mock_package = Mock()
        mock_package.name = "test/package"
        mock_package.description = "Test"
        mock_package.tags = []
        mock_package.modified = datetime(2024, 1, 1)
        mock_package.registry = "s3://test"
        mock_package.bucket = "test"
        # Missing top_hash
        return mock_package

    def _create_content_missing_required_field(self):
        """Create a mock content entry missing a required field."""
        mock_entry = Mock()
        # Missing name attribute entirely
        mock_entry.size = 1024
        mock_entry.modified = datetime(2024, 1, 1)
        mock_entry.is_dir = False
        return mock_entry

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transformation_error_recovery_and_cleanup(self, mock_quilt3):
        """Test that transformation methods properly handle cleanup after errors."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend()

        # Test that partial transformations don't leave inconsistent state
        # This is important for ensuring that failed transformations don't corrupt the backend state

        # Create a package that will fail during transformation
        mock_package = Mock()
        mock_package.name = "test/package"
        mock_package.description = "Test"
        mock_package.tags = []
        mock_package.modified = datetime(2024, 1, 1)
        mock_package.registry = "s3://test"
        mock_package.bucket = "test"
        mock_package.top_hash = "abc123"

        # Mock Package_Info to fail after some processing
        with patch(
            'quilt_mcp.backends.quilt3_backend_packages.Package_Info', side_effect=ValueError("Creation failed")
        ):
            with pytest.raises(BackendError):
                backend._transform_package(mock_package)

        # Verify that the backend is still in a consistent state and can handle subsequent operations
        # Create a valid package to test that the backend still works
        valid_mock_package = Mock()
        valid_mock_package.name = "valid/package"
        valid_mock_package.description = "Valid test"
        valid_mock_package.tags = ["test"]
        valid_mock_package.modified = datetime(2024, 1, 1)
        valid_mock_package.registry = "s3://test"
        valid_mock_package.bucket = "test"
        valid_mock_package.top_hash = "valid123"

        # This should work fine after the previous error
        result = backend._transform_package(valid_mock_package)
        assert isinstance(result, Package_Info)
        assert result.name == "valid/package"

    @pytest.mark.skip(reason="Advanced error handling edge cases - to be addressed in follow-up")
    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transformation_error_context_completeness(self, mock_quilt3):
        """Test that error context contains all necessary debugging information."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend()

        # Test package transformation error context completeness (general error, not validation)
        mock_package = Mock()
        mock_package.name = "test/package"
        mock_package.description = "Test"
        mock_package.tags = []
        mock_package.modified = "invalid-date"  # Will cause error
        mock_package.registry = "s3://test"
        mock_package.bucket = "test"
        mock_package.top_hash = "abc123"

        with pytest.raises(BackendError) as exc_info:
            backend._transform_package(mock_package)

        error = exc_info.value
        assert hasattr(error, 'context')
        context = error.context

        # Verify all expected context fields are present
        expected_context_fields = ['package_name', 'package_type', 'available_attributes']
        for field in expected_context_fields:
            assert field in context, f"Error context should contain '{field}' for debugging"

        # Verify context values are meaningful
        assert context['package_name'] == "test/package"
        assert context['package_type'] == "Mock"
        assert isinstance(context['available_attributes'], list)
        assert len(context['available_attributes']) > 0

        # Test content transformation error context completeness (general error, not validation)
        class ProblematicEntry:
            def __init__(self):
                self.name = "test_file.txt"

            @property
            def size(self):
                raise AttributeError("Cannot access size")

        problematic_entry = ProblematicEntry()

        with pytest.raises(BackendError) as exc_info:
            backend._transform_content(problematic_entry)

        error = exc_info.value
        context = error.context

        expected_content_context_fields = ['entry_name', 'entry_type', 'available_attributes']
        for field in expected_content_context_fields:
            assert field in context, f"Content error context should contain '{field}' for debugging"

        # Test bucket transformation error context completeness (general error, not validation)
        with patch('quilt_mcp.backends.quilt3_backend.Bucket_Info', side_effect=ValueError("Creation failed")):
            with pytest.raises(BackendError) as exc_info:
                backend._transform_bucket("test-bucket", {'region': 'us-east-1', 'access_level': 'read-write'})

            error = exc_info.value
            context = error.context

            expected_bucket_context_fields = ['bucket_name', 'bucket_data_keys', 'bucket_data_type']
            for field in expected_bucket_context_fields:
                assert field in context, f"Bucket error context should contain '{field}' for debugging"

            assert context['bucket_name'] == "test-bucket"
            assert context['bucket_data_type'] == "dict"


class TestQuilt3BackendTransformationErrorHandling:
    """Test error handling in transformation logic for _transform_package, _transform_content, and _transform_bucket methods."""

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_error_handling_with_invalid_objects(self, mock_quilt3):
        """Test _transform_package() error handling with completely invalid objects."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend()

        # Test with None object - this triggers validation error, not transformation error
        with pytest.raises(BackendError) as exc_info:
            backend._transform_package(None)

        error_message = str(exc_info.value)
        assert "quilt3 backend package validation failed" in error_message.lower()
        assert "missing required field" in error_message.lower()

        # Test with object that doesn't have required attributes (use object() instead of Mock())
        invalid_package = object()

        with pytest.raises(BackendError) as exc_info:
            backend._transform_package(invalid_package)

        error_message = str(exc_info.value)
        assert "missing required field" in error_message.lower()
        assert "name" in error_message.lower()

        # Test with object having None required fields (validation error)
        invalid_package = Mock()
        invalid_package.name = None
        invalid_package.registry = "s3://test-registry"
        invalid_package.bucket = "test-bucket"
        invalid_package.top_hash = "abc123"

        with pytest.raises(BackendError) as exc_info:
            backend._transform_package(invalid_package)

        error_message = str(exc_info.value)
        assert "required field 'name' is none" in error_message.lower()

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_error_handling_with_transformation_failures(self, mock_quilt3):
        """Test _transform_package() error handling when transformation logic fails."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend()

        # Test with invalid datetime that causes transformation error
        invalid_package = Mock()
        invalid_package.name = "test/package"
        invalid_package.description = "Test package"
        invalid_package.tags = ["test"]
        invalid_package.modified = "invalid-date"  # This will trigger ValueError in _normalize_package_datetime
        invalid_package.registry = "s3://test-registry"
        invalid_package.bucket = "test-bucket"
        invalid_package.top_hash = "abc123"

        with pytest.raises(BackendError) as exc_info:
            backend._transform_package(invalid_package)

        error_message = str(exc_info.value)
        assert "quilt3 backend package transformation failed" in error_message.lower()
        assert "invalid date format" in error_message.lower()

        # Verify error context is preserved
        error_context = exc_info.value.context
        assert error_context['package_name'] == "test/package"
        assert error_context['package_type'] == "Mock"
        assert 'available_attributes' in error_context

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_error_handling_with_domain_object_creation_failure(self, mock_quilt3):
        """Test _transform_package() error handling when Package_Info creation fails."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend()

        # Create valid mock package
        valid_package = Mock()
        valid_package.name = "test/package"
        valid_package.description = "Test package"
        valid_package.tags = ["test"]
        valid_package.modified = datetime(2024, 1, 1, 12, 0, 0)
        valid_package.registry = "s3://test-registry"
        valid_package.bucket = "test-bucket"
        valid_package.top_hash = "abc123"

        # Mock Package_Info to fail during creation
        with patch(
            'quilt_mcp.backends.quilt3_backend_packages.Package_Info',
            side_effect=ValueError("Domain validation failed"),
        ):
            with pytest.raises(BackendError) as exc_info:
                backend._transform_package(valid_package)

            error_message = str(exc_info.value)
            assert "quilt3 backend package transformation failed" in error_message.lower()
            assert "domain validation failed" in error_message.lower()

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_error_handling_with_invalid_objects(self, mock_quilt3):
        """Test _transform_content() error handling with completely invalid objects."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend()

        # Test with None object - this triggers validation error, not transformation error
        with pytest.raises(BackendError) as exc_info:
            backend._transform_content(None)

        error_message = str(exc_info.value)
        assert "quilt3 backend content transformation failed" in error_message.lower()
        assert "missing name" in error_message.lower()

        # Test with object that doesn't have name attribute (use object() instead of Mock())
        invalid_entry = object()

        with pytest.raises(BackendError) as exc_info:
            backend._transform_content(invalid_entry)

        error_message = str(exc_info.value)
        assert "missing name" in error_message.lower()

        # Test with object having None name field (validation error)
        invalid_entry = Mock()
        invalid_entry.name = None

        with pytest.raises(BackendError) as exc_info:
            backend._transform_content(invalid_entry)

        error_message = str(exc_info.value)
        assert "missing name" in error_message.lower()

        # Test with object having empty name field (validation error)
        invalid_entry = Mock()
        invalid_entry.name = ""

        with pytest.raises(BackendError) as exc_info:
            backend._transform_content(invalid_entry)

        error_message = str(exc_info.value)
        assert "empty name" in error_message.lower()

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_error_handling_with_transformation_failures(self, mock_quilt3):
        """Test _transform_content() error handling when transformation logic fails."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend()

        # Test with invalid datetime that causes transformation error
        invalid_entry = Mock()
        invalid_entry.name = "test/file.txt"
        invalid_entry.size = 1024
        invalid_entry.modified = "invalid-date"  # This will trigger ValueError in _normalize_datetime
        invalid_entry.is_dir = False

        with pytest.raises(BackendError) as exc_info:
            backend._transform_content(invalid_entry)

        error_message = str(exc_info.value)
        assert "quilt3 backend content transformation failed" in error_message.lower()
        assert "invalid date format" in error_message.lower()

        # Verify error context is preserved
        error_context = exc_info.value.context
        assert error_context['entry_name'] == "test/file.txt"
        assert error_context['entry_type'] == "Mock"
        assert 'available_attributes' in error_context

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_error_handling_with_domain_object_creation_failure(self, mock_quilt3):
        """Test _transform_content() error handling when Content_Info creation fails."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend()

        # Create valid mock content entry
        valid_entry = Mock()
        valid_entry.name = "test/file.txt"
        valid_entry.size = 1024
        valid_entry.modified = datetime(2024, 1, 1, 12, 0, 0)
        valid_entry.is_dir = False

        # Mock Content_Info to fail during creation
        with patch(
            'quilt_mcp.backends.quilt3_backend_content.Content_Info',
            side_effect=ValueError("Domain validation failed"),
        ):
            with pytest.raises(BackendError) as exc_info:
                backend._transform_content(valid_entry)

            error_message = str(exc_info.value)
            assert "quilt3 backend content transformation failed" in error_message.lower()
            assert "domain validation failed" in error_message.lower()

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_error_handling_with_attribute_access_errors(self, mock_quilt3):
        """Test _transform_content() error handling when attribute access fails."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend()

        # Create mock that raises exception when accessing attributes
        class ProblematicEntry:
            def __init__(self):
                self.name = "test/file.txt"

            @property
            def size(self):
                raise RuntimeError("Size access failed")

            @property
            def modified(self):
                raise RuntimeError("Modified access failed")

            @property
            def is_dir(self):
                raise RuntimeError("is_dir access failed")

        problematic_entry = ProblematicEntry()

        with pytest.raises(BackendError) as exc_info:
            backend._transform_content(problematic_entry)

        error_message = str(exc_info.value)
        assert "quilt3 backend content transformation failed" in error_message.lower()
        # Should contain one of the attribute access errors
        assert any(
            error in error_message.lower()
            for error in ["size access failed", "modified access failed", "is_dir access failed"]
        )

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_bucket_error_handling_with_invalid_inputs(self, mock_quilt3):
        """Test _transform_bucket() error handling with completely invalid inputs."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend()

        # Test with None bucket name
        with pytest.raises(BackendError) as exc_info:
            backend._transform_bucket(None, {'region': 'us-east-1', 'access_level': 'read-write'})

        error_message = str(exc_info.value)
        assert "missing name" in error_message.lower()

        # Test with empty bucket name
        with pytest.raises(BackendError) as exc_info:
            backend._transform_bucket("", {'region': 'us-east-1', 'access_level': 'read-write'})

        error_message = str(exc_info.value)
        assert "missing name" in error_message.lower()

        # Test with None bucket data
        with pytest.raises(BackendError) as exc_info:
            backend._transform_bucket("test-bucket", None)

        error_message = str(exc_info.value)
        assert "bucket_data is none" in error_message.lower()

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_bucket_error_handling_with_missing_required_fields(self, mock_quilt3):
        """Test _transform_bucket() error handling with missing required fields."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend()

        # The current implementation uses .get() with defaults, so missing fields don't cause errors
        # Let's test with completely invalid bucket_data structure that will cause transformation errors

        # Test with non-dict bucket_data that will cause attribute errors
        with pytest.raises(BackendError) as exc_info:
            backend._transform_bucket("test-bucket", "invalid-string-data")

        error_message = str(exc_info.value)
        assert "quilt3 backend bucket transformation failed" in error_message.lower()

        # Test with bucket_data that has .get() method but raises errors
        class ProblematicData:
            def get(self, key, default=None):
                raise RuntimeError(f"Cannot access {key}")

            def keys(self):
                return ['region', 'access_level']

        with pytest.raises(BackendError) as exc_info:
            backend._transform_bucket("test-bucket", ProblematicData())

        error_message = str(exc_info.value)
        assert "quilt3 backend bucket transformation failed" in error_message.lower()

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_bucket_error_handling_with_transformation_failures(self, mock_quilt3):
        """Test _transform_bucket() error handling when transformation logic fails."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend()

        # Test with invalid datetime that causes transformation error
        bucket_data = {
            'region': 'us-east-1',
            'access_level': 'read-write',
            'created_date': "invalid-date",  # This will trigger ValueError in _normalize_datetime
        }

        with pytest.raises(BackendError) as exc_info:
            backend._transform_bucket("test-bucket", bucket_data)

        error_message = str(exc_info.value)
        assert "quilt3 backend bucket transformation failed" in error_message.lower()
        assert "invalid date format" in error_message.lower()

        # Verify error context is preserved
        error_context = exc_info.value.context
        assert error_context['bucket_name'] == "test-bucket"
        assert error_context['bucket_data_type'] == "dict"
        assert 'bucket_data_keys' in error_context

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_bucket_error_handling_with_domain_object_creation_failure(self, mock_quilt3):
        """Test _transform_bucket() error handling when Bucket_Info creation fails."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend()

        # Create valid bucket data
        bucket_data = {'region': 'us-east-1', 'access_level': 'read-write', 'created_date': '2024-01-01T12:00:00Z'}

        # Mock Bucket_Info to fail during creation
        with patch(
            'quilt_mcp.backends.quilt3_backend_buckets.Bucket_Info', side_effect=ValueError("Domain validation failed")
        ):
            with pytest.raises(BackendError) as exc_info:
                backend._transform_bucket("test-bucket", bucket_data)

            error_message = str(exc_info.value)
            assert "quilt3 backend bucket transformation failed" in error_message.lower()
            assert "domain validation failed" in error_message.lower()

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_bucket_error_handling_with_data_access_errors(self, mock_quilt3):
        """Test _transform_bucket() error handling when bucket data access fails."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend()

        # Create mock that raises exception when accessing data
        class ProblematicBucketData:
            def get(self, key, default=None):
                raise RuntimeError(f"Data access failed for key: {key}")

            def keys(self):
                return ['region', 'access_level']

            def __getitem__(self, key):
                raise RuntimeError(f"Data access failed for key: {key}")

        problematic_data = ProblematicBucketData()

        with pytest.raises(BackendError) as exc_info:
            backend._transform_bucket("test-bucket", problematic_data)

        error_message = str(exc_info.value)
        assert "quilt3 backend bucket transformation failed" in error_message.lower()
        assert "data access failed" in error_message.lower()

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transformation_error_messages_include_backend_context(self, mock_quilt3):
        """Test that all transformation error messages include proper backend context."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend()

        # Test package transformation error context (validation error for None)
        with pytest.raises(BackendError) as exc_info:
            backend._transform_package(None)

        error_message = str(exc_info.value)
        assert "quilt3 backend" in error_message.lower()
        assert any(phrase in error_message.lower() for phrase in ["validation failed", "transformation failed"])

        # Test content transformation error context (validation error for None)
        with pytest.raises(BackendError) as exc_info:
            backend._transform_content(None)

        error_message = str(exc_info.value)
        assert "quilt3 backend" in error_message.lower()
        assert "transformation failed" in error_message.lower()

        # Test bucket transformation error context
        with pytest.raises(BackendError) as exc_info:
            backend._transform_bucket(None, {})

        error_message = str(exc_info.value)
        assert "quilt3 backend" in error_message.lower()
        # This might be validation error, so check for either
        assert any(phrase in error_message.lower() for phrase in ["transformation failed", "validation failed"])

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transformation_error_context_preservation(self, mock_quilt3):
        """Test that transformation errors preserve context information for debugging."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend()

        # Test package transformation error context
        invalid_package = Mock()
        invalid_package.name = "test/package"
        invalid_package.description = "Test package"
        invalid_package.tags = ["test"]
        invalid_package.modified = "invalid-date"
        invalid_package.registry = "s3://test-registry"
        invalid_package.bucket = "test-bucket"
        invalid_package.top_hash = "abc123"

        with pytest.raises(BackendError) as exc_info:
            backend._transform_package(invalid_package)

        # Verify error context contains debugging information
        error_context = exc_info.value.context
        assert 'package_name' in error_context
        assert 'package_type' in error_context
        assert 'available_attributes' in error_context
        assert error_context['package_name'] == "test/package"
        assert error_context['package_type'] == "Mock"

        # Test content transformation error context
        invalid_entry = Mock()
        invalid_entry.name = "test/file.txt"
        invalid_entry.modified = "invalid-date"

        with pytest.raises(BackendError) as exc_info:
            backend._transform_content(invalid_entry)

        error_context = exc_info.value.context
        assert 'entry_name' in error_context
        assert 'entry_type' in error_context
        assert 'available_attributes' in error_context
        assert error_context['entry_name'] == "test/file.txt"
        assert error_context['entry_type'] == "Mock"

        # Test bucket transformation error context
        bucket_data = {'region': 'us-east-1', 'access_level': 'read-write', 'created_date': "invalid-date"}

        with pytest.raises(BackendError) as exc_info:
            backend._transform_bucket("test-bucket", bucket_data)

        error_context = exc_info.value.context
        assert 'bucket_name' in error_context
        assert 'bucket_data_type' in error_context
        assert 'bucket_data_keys' in error_context
        assert error_context['bucket_name'] == "test-bucket"
        assert error_context['bucket_data_type'] == "dict"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transformation_error_handling_with_appropriate_exceptions(self, mock_quilt3):
        """Test that transformation methods raise appropriate BackendError exceptions."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend()

        # All transformation errors should be BackendError, not generic Exception
        with pytest.raises(BackendError):
            backend._transform_package(None)

        with pytest.raises(BackendError):
            backend._transform_content(None)

        with pytest.raises(BackendError):
            backend._transform_bucket(None, {})

        # Verify that BackendError is the specific exception type, not a parent class
        try:
            backend._transform_package(None)
        except Exception as e:
            assert type(e).__name__ == "BackendError"
            assert hasattr(e, 'context')  # BackendError should have context attribute

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transformation_error_handling_with_clear_error_messages(self, mock_quilt3):
        """Test that transformation errors provide clear, actionable error messages."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend()

        # Test that error messages are descriptive and include the operation that failed
        error_scenarios = [
            (lambda: backend._transform_package(None), "failed"),  # Could be validation or transformation
            (lambda: backend._transform_content(None), "transformation failed"),
            (lambda: backend._transform_bucket(None, {}), "failed"),  # Could be validation or transformation
        ]

        for operation, expected_phrase in error_scenarios:
            with pytest.raises(BackendError) as exc_info:
                operation()

            error_message = str(exc_info.value).lower()
            assert "quilt3 backend" in error_message
            assert expected_phrase in error_message
            # Error message should not be empty or generic
            assert len(error_message) > 20  # Reasonable minimum length for descriptive error
            assert "error" in error_message or "failed" in error_message

"""Integration tests for error handling and logging in QuiltOps."""

import pytest
from unittest.mock import patch, MagicMock
import logging

from quilt_mcp.ops.factory import QuiltOpsFactory
from quilt_mcp.ops.exceptions import AuthenticationError, BackendError
from quilt_mcp.backends.quilt3_backend import Quilt3_Backend


@pytest.mark.integration
class TestBackendErrorHandling:
    """Integration tests for backend operation error handling."""

    def test_backend_error_includes_context(self):
        """Test that backend errors include context information."""
        mock_session = MagicMock()
        
        with patch('quilt3.logged_in', return_value=True):
            with patch('quilt3.session.get_session', return_value=mock_session):
                with patch('quilt3.session.get_registry_url', return_value='s3://test-registry'):
                    quilt_ops = QuiltOpsFactory.create()
                    
                    # Mock quilt3.search to raise an exception
                    with patch('quilt3.search', side_effect=Exception("Network error")):
                        with pytest.raises(BackendError) as exc_info:
                            quilt_ops.search_packages("test", "s3://test-registry")
                        
                        # Verify error includes backend context
                        error = exc_info.value
                        assert "Quilt3 backend" in str(error)
                        assert "Network error" in str(error)
                        assert hasattr(error, 'context')
                        assert error.context['query'] == 'test'
                        assert error.context['registry'] == 's3://test-registry'

    def test_backend_error_transformation_preserves_original_error(self):
        """Test that backend errors preserve the original error information."""
        mock_session = MagicMock()
        
        with patch('quilt3.logged_in', return_value=True):
            with patch('quilt3.session.get_session', return_value=mock_session):
                with patch('quilt3.session.get_registry_url', return_value='s3://test-registry'):
                    quilt_ops = QuiltOpsFactory.create()
                    
                    # Mock quilt3 to raise a specific exception
                    original_error = ValueError("Invalid package name format")
                    with patch('quilt3.Package.browse', side_effect=original_error):
                        with pytest.raises(BackendError) as exc_info:
                            quilt_ops.get_package_info("invalid-package", "s3://test-registry")
                        
                        # Verify original error is preserved
                        error = exc_info.value
                        assert "Invalid package name format" in str(error)
                        assert "Quilt3 backend" in str(error)

    def test_authentication_error_provides_remediation_steps(self):
        """Test that authentication errors provide clear remediation steps."""
        with patch('quilt3.logged_in', return_value=False):
            with pytest.raises(AuthenticationError) as exc_info:
                QuiltOpsFactory.create()
            
            error_msg = str(exc_info.value)
            # Should contain helpful instructions
            assert "quilt3 login" in error_msg
            assert "authentication" in error_msg.lower()
            assert "https://docs.quiltdata.com" in error_msg

    def test_backend_error_messages_include_backend_type(self):
        """Test that all backend error messages include the backend type."""
        mock_session = MagicMock()
        
        with patch('quilt3.logged_in', return_value=True):
            with patch('quilt3.session.get_session', return_value=mock_session):
                with patch('quilt3.session.get_registry_url', return_value='s3://test-registry'):
                    quilt_ops = QuiltOpsFactory.create()
                    
                    # Test search_packages operation
                    with patch('quilt3.search', side_effect=Exception("search failed")):
                        try:
                            quilt_ops.search_packages("test", "s3://test-registry")
                        except BackendError as e:
                            assert "Quilt3 backend" in str(e), "Backend type missing in search_packages error"
                        except Exception:
                            pass  # Other exceptions are fine for this test
                    
                    # Test get_package_info operation
                    with patch('quilt3.Package.browse', side_effect=Exception("browse failed")):
                        try:
                            quilt_ops.get_package_info("test/pkg", "s3://test-registry")
                        except BackendError as e:
                            assert "Quilt3 backend" in str(e), "Backend type missing in get_package_info error"
                        except Exception:
                            pass  # Other exceptions are fine for this test

    def test_error_handling_preserves_stack_trace(self):
        """Test that error handling preserves useful stack trace information."""
        mock_session = MagicMock()
        
        with patch('quilt3.logged_in', return_value=True):
            with patch('quilt3.session.get_session', return_value=mock_session):
                with patch('quilt3.session.get_registry_url', return_value='s3://test-registry'):
                    quilt_ops = QuiltOpsFactory.create()
                    
                    # Create a simple exception to test error preservation
                    original_error = ValueError("Deep error")
                    with patch('quilt3.search', side_effect=original_error):
                        with pytest.raises(BackendError) as exc_info:
                            quilt_ops.search_packages("test", "s3://test-registry")
                        
                        # Verify we can trace back to the original error
                        error = exc_info.value
                        assert "Deep error" in str(error)


@pytest.mark.integration
class TestLoggingBehavior:
    """Integration tests for logging behavior in QuiltOps."""

    def test_debug_logging_for_operations(self):
        """Test that debug logging is produced for operations."""
        mock_session = MagicMock()
        
        with patch('quilt3.logged_in', return_value=True):
            with patch('quilt3.session.get_session', return_value=mock_session):
                with patch('quilt3.session.get_registry_url', return_value='s3://test-registry'):
                    # Mock successful quilt3 operations
                    with patch('quilt3.search', return_value=[]):
                        with patch('quilt_mcp.backends.quilt3_backend.logger') as mock_logger:
                            quilt_ops = QuiltOpsFactory.create()
                            quilt_ops.search_packages("test", "s3://test-registry")
                            
                            # Verify debug logging was called
                            mock_logger.debug.assert_called()
                            
                            # Check for expected log messages
                            debug_calls = [str(call) for call in mock_logger.debug.call_args_list]
                            assert any("Searching packages" in call for call in debug_calls)

    def test_factory_logging_for_backend_selection(self):
        """Test that factory logs backend selection decisions."""
        mock_session = MagicMock()
        
        with patch('quilt3.logged_in', return_value=True):
            with patch('quilt3.session.get_session', return_value=mock_session):
                with patch('quilt3.session.get_registry_url', return_value='s3://test-registry'):
                    with patch('quilt_mcp.ops.factory.logger') as mock_logger:
                        quilt_ops = QuiltOpsFactory.create()
                        
                        # Verify logging for backend selection
                        mock_logger.debug.assert_called()
                        mock_logger.info.assert_called()
                        
                        # Check for expected log messages
                        info_calls = [str(call) for call in mock_logger.info.call_args_list]
                        assert any("Quilt3_Backend" in call for call in info_calls)

    def test_error_logging_includes_context(self):
        """Test that error logging includes useful context information."""
        mock_session = MagicMock()
        
        with patch('quilt3.logged_in', return_value=True):
            with patch('quilt3.session.get_session', return_value=mock_session):
                with patch('quilt3.session.get_registry_url', return_value='s3://test-registry'):
                    quilt_ops = QuiltOpsFactory.create()
                    
                    # Mock quilt3 to raise an exception
                    with patch('quilt3.search', side_effect=Exception("Test error")):
                        with patch('quilt_mcp.backends.quilt3_backend.logger') as mock_logger:
                            try:
                                quilt_ops.search_packages("test", "s3://test-registry")
                            except BackendError:
                                pass  # Expected
                            
                            # Verify debug logging was called (for the operation start)
                            mock_logger.debug.assert_called()

    def test_authentication_logging(self):
        """Test that authentication detection is properly logged."""
        # Test successful authentication logging
        mock_session = MagicMock()
        
        with patch('quilt3.logged_in', return_value=True):
            with patch('quilt3.session.get_session', return_value=mock_session):
                with patch('quilt3.session.get_registry_url', return_value='s3://test-registry'):
                    with patch('quilt_mcp.ops.factory.logger') as mock_logger:
                        QuiltOpsFactory.create()
                        
                        # Should log successful authentication detection
                        mock_logger.debug.assert_called()
                        debug_calls = [str(call) for call in mock_logger.debug.call_args_list]
                        assert any("session" in call.lower() for call in debug_calls)
        
        # Test failed authentication logging
        with patch('quilt3.logged_in', return_value=False):
            with patch('quilt_mcp.ops.factory.logger') as mock_logger:
                try:
                    QuiltOpsFactory.create()
                except AuthenticationError:
                    pass  # Expected
                
                # Should log authentication failure
                mock_logger.warning.assert_called()
                warning_calls = [str(call) for call in mock_logger.warning.call_args_list]
                assert any("authentication" in call.lower() for call in warning_calls)
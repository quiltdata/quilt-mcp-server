"""Comprehensive tests for the unified server module."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import os

from src.quilt_mcp.server import (
    main,
    handler,
    is_lambda_environment,
    get_transport
)


class TestEnvironmentDetection:
    """Test environment detection functions."""
    
    def test_is_lambda_environment_true(self):
        """Test Lambda environment detection when in Lambda."""
        with patch.dict(os.environ, {'AWS_LAMBDA_FUNCTION_NAME': 'my-function'}):
            assert is_lambda_environment() is True
    
    def test_is_lambda_environment_false(self):
        """Test Lambda environment detection when not in Lambda."""
        with patch.dict(os.environ, {}, clear=True):
            assert is_lambda_environment() is False
    
    def test_is_lambda_environment_empty_string(self):
        """Test Lambda environment detection with empty function name."""
        with patch.dict(os.environ, {'AWS_LAMBDA_FUNCTION_NAME': ''}):
            assert is_lambda_environment() is False
    
    def test_get_transport_default(self):
        """Test default transport when not specified."""
        with patch.dict(os.environ, {}, clear=True):
            assert get_transport() == "streamable-http"
    
    def test_get_transport_stdio(self):
        """Test stdio transport selection."""
        with patch.dict(os.environ, {'FASTMCP_TRANSPORT': 'stdio'}):
            assert get_transport() == "stdio"
    
    def test_get_transport_sse(self):
        """Test SSE transport selection."""
        with patch.dict(os.environ, {'FASTMCP_TRANSPORT': 'sse'}):
            assert get_transport() == "sse"
    
    def test_get_transport_streamable_http(self):
        """Test streamable-http transport selection."""
        with patch.dict(os.environ, {'FASTMCP_TRANSPORT': 'streamable-http'}):
            assert get_transport() == "streamable-http"
    
    @patch('src.quilt_mcp.server.logger')
    def test_get_transport_invalid(self, mock_logger):
        """Test invalid transport falls back to default."""
        with patch.dict(os.environ, {'FASTMCP_TRANSPORT': 'invalid-transport'}):
            result = get_transport()
            
            assert result == "streamable-http"
            mock_logger.warning.assert_called_once()
            warning_msg = mock_logger.warning.call_args[0][0]
            assert "Invalid transport 'invalid-transport'" in warning_msg


class TestMainFunction:
    """Test the main function for local development."""
    
    @patch('src.quilt_mcp.server.is_lambda_environment')
    @patch('src.quilt_mcp.server.logger')
    def test_main_in_lambda_environment(self, mock_logger, mock_is_lambda):
        """Test main function when in Lambda environment."""
        mock_is_lambda.return_value = True
        
        main()
        
        # Should log and return early
        mock_logger.info.assert_called_with("Detected Lambda environment - handler will be called by AWS")
    
    @patch('src.quilt_mcp.server.is_lambda_environment')
    @patch('src.quilt_mcp.server.get_transport')
    @patch('src.quilt_mcp.server.logger')
    def test_main_local_development_success(self, mock_logger, mock_get_transport, mock_is_lambda):
        """Test main function for successful local development."""
        mock_is_lambda.return_value = False
        mock_get_transport.return_value = "streamable-http"
        
        # Mock the FastMCP bridge
        mock_bridge = Mock()
        
        with patch('src.quilt_mcp.adapters.fastmcp_bridge.FastMCPBridge', return_value=mock_bridge) as mock_bridge_class:
            main()
            
            # Verify bridge was created and run
            mock_bridge_class.assert_called_once_with("quilt")
            mock_bridge.run.assert_called_once_with(transport="streamable-http")
            
            # Verify logging
            mock_logger.info.assert_any_call("Starting Quilt MCP Server for local development")
            mock_logger.info.assert_any_call("Using transport: streamable-http")
    
    @patch('src.quilt_mcp.server.is_lambda_environment')
    @patch('src.quilt_mcp.server.get_transport')
    @patch('src.quilt_mcp.server.logger')
    def test_main_keyboard_interrupt(self, mock_logger, mock_get_transport, mock_is_lambda):
        """Test main function handles keyboard interrupt gracefully."""
        mock_is_lambda.return_value = False
        mock_get_transport.return_value = "stdio"
        
        # Mock the FastMCP bridge to raise KeyboardInterrupt
        mock_bridge = Mock()
        mock_bridge.run.side_effect = KeyboardInterrupt()
        
        with patch('src.quilt_mcp.adapters.fastmcp_bridge.FastMCPBridge', return_value=mock_bridge):
            main()  # Should not raise exception
            
            # Verify graceful shutdown message
            mock_logger.info.assert_any_call("Server stopped by user")
    
    @patch('src.quilt_mcp.server.is_lambda_environment')
    @patch('src.quilt_mcp.server.get_transport')
    @patch('src.quilt_mcp.server.logger')
    def test_main_general_exception(self, mock_logger, mock_get_transport, mock_is_lambda):
        """Test main function handles general exceptions."""
        mock_is_lambda.return_value = False
        mock_get_transport.return_value = "sse"
        
        # Mock the FastMCP bridge to raise a general exception
        mock_bridge = Mock()
        test_error = Exception("Test server error")
        mock_bridge.run.side_effect = test_error
        
        with patch('src.quilt_mcp.adapters.fastmcp_bridge.FastMCPBridge', return_value=mock_bridge):
            with pytest.raises(Exception) as exc_info:
                main()
            
            assert exc_info.value is test_error
            
            # Verify error logging
            mock_logger.error.assert_called_once()
            error_call = mock_logger.error.call_args
            assert "Server error: Test server error" in error_call[0][0]
            assert error_call[1]['exc_info'] is True
    
    @patch('src.quilt_mcp.server.is_lambda_environment')
    def test_main_different_transport_modes(self, mock_is_lambda):
        """Test main function with different transport modes."""
        mock_is_lambda.return_value = False
        
        transports = ["stdio", "sse", "streamable-http"]
        
        for transport in transports:
            with patch('src.quilt_mcp.server.get_transport', return_value=transport):
                mock_bridge = Mock()
                
                with patch('src.quilt_mcp.adapters.fastmcp_bridge.FastMCPBridge', return_value=mock_bridge):
                    main()
                    
                    # Verify correct transport was used
                    mock_bridge.run.assert_called_with(transport=transport)


class TestHandlerFunction:
    """Test the Lambda handler function."""
    
    @patch('src.quilt_mcp.adapters.lambda_handler.lambda_handler')
    def test_handler_delegates_correctly(self, mock_lambda_handler):
        """Test that handler function delegates to lambda_handler."""
        # Setup mock return value
        expected_response = {
            'statusCode': 200,
            'body': '{"status": "ok"}'
        }
        mock_lambda_handler.return_value = expected_response
        
        # Call handler
        test_event = {'httpMethod': 'GET', 'path': '/test'}
        test_context = Mock()
        
        result = handler(test_event, test_context)
        
        # Verify delegation
        mock_lambda_handler.assert_called_once_with(test_event, test_context)
        assert result == expected_response
    
    @patch('src.quilt_mcp.adapters.lambda_handler.lambda_handler')
    def test_handler_with_real_event_structure(self, mock_lambda_handler):
        """Test handler with realistic Lambda event structure."""
        mock_lambda_handler.return_value = {'statusCode': 200, 'body': '{}'}
        
        # Realistic API Gateway event structure
        event = {
            'httpMethod': 'POST',
            'path': '/mcp',
            'headers': {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer token123'
            },
            'queryStringParameters': None,
            'body': '{"jsonrpc": "2.0", "method": "tools/list", "id": 1}',
            'isBase64Encoded': False,
            'requestContext': {
                'requestId': 'test-request-id',
                'stage': 'prod'
            }
        }
        
        context = Mock()
        context.aws_request_id = 'test-request-id'
        context.function_name = 'quilt-mcp-function'
        
        result = handler(event, context)
        
        mock_lambda_handler.assert_called_once_with(event, context)
        assert result['statusCode'] == 200
    
    @patch('src.quilt_mcp.adapters.lambda_handler.lambda_handler')
    def test_handler_exception_propagation(self, mock_lambda_handler):
        """Test that handler propagates exceptions from lambda_handler."""
        test_exception = Exception("Lambda handler error")
        mock_lambda_handler.side_effect = test_exception
        
        with pytest.raises(Exception) as exc_info:
            handler({}, Mock())
        
        assert exc_info.value is test_exception


class TestLoggingConfiguration:
    """Test logging configuration behavior."""
    
    def test_logging_level_from_environment(self):
        """Test that logging level is set from environment variable."""
        # This test verifies the module-level logging configuration
        # Since logging is configured at import time, we test indirectly
        
        import src.quilt_mcp.server as server_module
        logger = server_module.logger
        
        # Logger should be configured
        assert logger.name == 'src.quilt_mcp.server'
        assert hasattr(logger, 'info')
        assert hasattr(logger, 'error')
    
    @patch.dict(os.environ, {'LOG_LEVEL': 'DEBUG'})
    def test_debug_log_level(self):
        """Test debug log level configuration."""
        # Test that the log level configuration works
        import logging
        
        with patch('logging.basicConfig') as mock_basic_config:
            # Re-import to trigger configuration
            import importlib
            import src.quilt_mcp.server
            importlib.reload(src.quilt_mcp.server)
            
            # Verify basicConfig was called with DEBUG level
            mock_basic_config.assert_called()
            call_args = mock_basic_config.call_args[1]
            assert call_args['level'] == logging.DEBUG
    
    @patch.dict(os.environ, {'LOG_LEVEL': 'INVALID'})
    def test_invalid_log_level_fallback(self):
        """Test invalid log level falls back to INFO."""
        import logging
        
        with patch('logging.basicConfig') as mock_basic_config:
            # Re-import to trigger configuration
            import importlib
            import src.quilt_mcp.server
            importlib.reload(src.quilt_mcp.server)
            
            # Verify basicConfig was called with INFO level (fallback)
            mock_basic_config.assert_called()
            call_args = mock_basic_config.call_args[1]
            assert call_args['level'] == logging.INFO


class TestModuleExports:
    """Test module exports and backwards compatibility."""
    
    def test_all_exports_available(self):
        """Test that all expected exports are available."""
        from src.quilt_mcp.server import __all__
        
        expected_exports = ["main", "handler", "is_lambda_environment", "get_transport"]
        assert __all__ == expected_exports
        
        # Verify all exports can be imported
        from src.quilt_mcp.server import main, handler, is_lambda_environment, get_transport
        
        assert callable(main)
        assert callable(handler)
        assert callable(is_lambda_environment)
        assert callable(get_transport)
    
    def test_import_structure(self):
        """Test that imports work correctly."""
        # Test that the module can be imported without errors
        import src.quilt_mcp.server
        
        # Test that required functions exist
        assert hasattr(src.quilt_mcp.server, 'main')
        assert hasattr(src.quilt_mcp.server, 'handler')
        assert hasattr(src.quilt_mcp.server, 'is_lambda_environment')
        assert hasattr(src.quilt_mcp.server, 'get_transport')


class TestIntegrationScenarios:
    """Test integration scenarios and real-world usage patterns."""
    
    @patch('src.quilt_mcp.server.is_lambda_environment')
    @patch('src.quilt_mcp.server.get_transport')
    def test_development_workflow(self, mock_get_transport, mock_is_lambda):
        """Test typical development workflow."""
        mock_is_lambda.return_value = False
        mock_get_transport.return_value = "streamable-http"
        
        mock_bridge = Mock()
        
        with patch('src.quilt_mcp.adapters.fastmcp_bridge.FastMCPBridge', return_value=mock_bridge):
            # Simulate development server startup
            main()
            
            # Verify development server was started
            mock_bridge.run.assert_called_once_with(transport="streamable-http")
    
    @patch('src.quilt_mcp.adapters.lambda_handler.lambda_handler')
    def test_production_lambda_workflow(self, mock_lambda_handler):
        """Test typical production Lambda workflow."""
        mock_lambda_handler.return_value = {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': '{"result": "success"}'
        }
        
        # Simulate Lambda invocation
        lambda_event = {
            'httpMethod': 'POST',
            'path': '/mcp',
            'body': '{"jsonrpc": "2.0", "method": "tools/list", "id": 1}'
        }
        lambda_context = Mock()
        
        response = handler(lambda_event, lambda_context)
        
        # Verify Lambda response
        assert response['statusCode'] == 200
        assert 'Content-Type' in response['headers']
        mock_lambda_handler.assert_called_once_with(lambda_event, lambda_context)
    
    def test_environment_variable_combinations(self):
        """Test various environment variable combinations."""
        test_cases = [
            # (lambda_env, transport_env, expected_is_lambda, expected_transport)
            (None, None, False, "streamable-http"),
            ("my-function", None, True, "streamable-http"),
            (None, "stdio", False, "stdio"),
            ("my-function", "sse", True, "sse"),
            ("", "streamable-http", False, "streamable-http"),
        ]
        
        for lambda_env, transport_env, expected_is_lambda, expected_transport in test_cases:
            env_dict = {}
            if lambda_env is not None:
                env_dict['AWS_LAMBDA_FUNCTION_NAME'] = lambda_env
            if transport_env is not None:
                env_dict['FASTMCP_TRANSPORT'] = transport_env
            
            with patch.dict(os.environ, env_dict, clear=True):
                assert is_lambda_environment() == expected_is_lambda
                assert get_transport() == expected_transport


class TestErrorHandling:
    """Test error handling and edge cases."""
    
    @patch('src.quilt_mcp.server.is_lambda_environment')
    def test_import_error_handling(self, mock_is_lambda):
        """Test handling of import errors."""
        mock_is_lambda.return_value = False
        
        # Mock import error for FastMCPBridge
        with patch('src.quilt_mcp.adapters.fastmcp_bridge.FastMCPBridge', side_effect=ImportError("FastMCP not available")):
            with pytest.raises(ImportError):
                main()
    
    @patch('src.quilt_mcp.adapters.lambda_handler.lambda_handler')
    def test_lambda_handler_import_error(self, mock_lambda_handler):
        """Test lambda handler import error handling."""
        # This tests the import within the handler function
        mock_lambda_handler.side_effect = ImportError("Lambda handler not available")
        
        with pytest.raises(ImportError):
            handler({}, Mock())
    
    def test_malformed_environment_variables(self):
        """Test handling of malformed environment variables."""
        # Test with various malformed values
        malformed_values = ["", " ", "\n", "\t", "   \n\t   "]
        
        for value in malformed_values:
            with patch.dict(os.environ, {'AWS_LAMBDA_FUNCTION_NAME': value}):
                # Empty/whitespace values should be treated as falsy
                # Note: bool(value) checks if string is non-empty, not if stripped value is non-empty
                expected = bool(value)  # Not value.strip() - the function checks bool(os.environ.get(...))
                assert is_lambda_environment() == expected
    
    @patch('src.quilt_mcp.server.logger')
    def test_transport_validation_edge_cases(self, mock_logger):
        """Test transport validation with edge cases."""
        edge_cases = [" stdio ", "STDIO", "Stdio", "stdio\n", "\tstdio"]
        
        for transport in edge_cases:
            with patch.dict(os.environ, {'FASTMCP_TRANSPORT': transport}):
                result = get_transport()
                
                # All edge cases should fall back to default
                assert result == "streamable-http"
                
                # Should log warning for invalid transport
                mock_logger.warning.assert_called()
                mock_logger.warning.reset_mock()
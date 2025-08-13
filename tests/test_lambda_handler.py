"""Comprehensive tests for the AWS Lambda handler module."""

import base64
import json
import pytest
from unittest.mock import Mock, patch, MagicMock

from src.quilt_mcp.adapters.lambda_handler import (
    LambdaHandler,
    lambda_handler,
    get_lambda_handler,
    _handler_instance
)


class TestLambdaHandler:
    """Test the LambdaHandler class comprehensively."""
    
    def setup_method(self):
        """Reset global handler instance before each test."""
        # Clear the global handler instance
        import src.quilt_mcp.adapters.lambda_handler
        src.quilt_mcp.adapters.lambda_handler._handler_instance = None
    
    @patch('os.chdir')
    @patch('os.makedirs')
    def test_lambda_environment_setup_success(self, mock_makedirs, mock_chdir):
        """Test successful Lambda environment setup."""
        handler = LambdaHandler()
        
        # Verify environment setup calls
        mock_chdir.assert_called_once_with('/tmp')
        expected_dirs = ['/tmp/.config', '/tmp/.cache', '/tmp/quilt']
        assert mock_makedirs.call_count == len(expected_dirs)
        for call, expected_dir in zip(mock_makedirs.call_args_list, expected_dirs):
            assert call[0][0] == expected_dir
            assert call[1]['exist_ok'] is True
    
    @patch('os.chdir', side_effect=Exception("Permission denied"))
    @patch('src.quilt_mcp.adapters.lambda_handler.logger')
    def test_lambda_environment_setup_failure(self, mock_logger, mock_chdir):
        """Test Lambda environment setup failure handling."""
        handler = LambdaHandler()
        
        # Verify warning was logged
        mock_logger.warning.assert_called_once()
        warning_call = mock_logger.warning.call_args[0][0]
        assert "Lambda environment setup failed" in warning_call
        assert "Permission denied" in warning_call
    
    def test_handler_initialization(self):
        """Test handler initializes correctly."""
        handler = LambdaHandler()
        assert handler.processor is not None
        assert hasattr(handler.processor, 'process_request')
    
    def test_cors_preflight_request(self):
        """Test CORS preflight request handling."""
        handler = LambdaHandler()
        
        event = {
            'httpMethod': 'OPTIONS',
            'path': '/mcp',
            'headers': {}
        }
        
        response = handler.handle_event(event, None)
        
        assert response['statusCode'] == 200
        assert response['headers']['Access-Control-Allow-Origin'] == '*'
        assert response['headers']['Access-Control-Allow-Methods'] == 'GET,POST,OPTIONS'
        assert response['headers']['Access-Control-Max-Age'] == '86400'
        assert response['body'] == ''
    
    @patch('src.quilt_mcp.adapters.lambda_handler.LambdaHandler._get_timestamp')
    def test_health_check_request(self, mock_timestamp):
        """Test health check request handling."""
        mock_timestamp.return_value = '2024-01-01T00:00:00Z'
        handler = LambdaHandler()
        
        event = {
            'httpMethod': 'GET',
            'path': '/health',
            'headers': {}
        }
        
        response = handler.handle_event(event, None)
        
        assert response['statusCode'] == 200
        assert response['headers']['Content-Type'] == 'application/json'
        
        body = json.loads(response['body'])
        assert body['status'] == 'ok'
        assert body['server'] == 'quilt-mcp-server'
        assert body['version'] == '0.1.0'
        assert body['timestamp'] == '2024-01-01T00:00:00Z'
    
    def test_mcp_request_processing_success(self):
        """Test successful MCP request processing."""
        handler = LambdaHandler()
        
        # Mock the processor
        mock_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"tools": []}
        }
        handler.processor.process_request = Mock(return_value=mock_response)
        
        mcp_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {}
        }
        
        event = {
            'httpMethod': 'POST',
            'path': '/mcp',
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(mcp_request),
            'isBase64Encoded': False
        }
        
        response = handler.handle_event(event, None)
        
        assert response['statusCode'] == 200
        assert response['headers']['Content-Type'] == 'application/json'
        
        response_body = json.loads(response['body'])
        assert response_body == mock_response
        
        # Verify processor was called correctly
        handler.processor.process_request.assert_called_once_with(mcp_request)
    
    def test_base64_encoded_request(self):
        """Test handling of base64 encoded request body."""
        handler = LambdaHandler()
        
        # Mock the processor
        mock_response = {"jsonrpc": "2.0", "id": 1, "result": {}}
        handler.processor.process_request = Mock(return_value=mock_response)
        
        mcp_request = {"jsonrpc": "2.0", "id": 1, "method": "initialize"}
        request_body = json.dumps(mcp_request)
        encoded_body = base64.b64encode(request_body.encode('utf-8')).decode('utf-8')
        
        event = {
            'httpMethod': 'POST',
            'path': '/mcp',
            'headers': {'Content-Type': 'application/json'},
            'body': encoded_body,
            'isBase64Encoded': True
        }
        
        response = handler.handle_event(event, None)
        
        assert response['statusCode'] == 200
        handler.processor.process_request.assert_called_once_with(mcp_request)
    
    def test_invalid_json_request(self):
        """Test handling of invalid JSON in request."""
        handler = LambdaHandler()
        
        event = {
            'httpMethod': 'POST',
            'path': '/mcp',
            'headers': {'Content-Type': 'application/json'},
            'body': 'invalid json {',
            'isBase64Encoded': False
        }
        
        response = handler.handle_event(event, None)
        
        assert response['statusCode'] == 400
        
        response_body = json.loads(response['body'])
        assert 'error' in response_body
        assert response_body['error']['message'] == 'Invalid request body'
    
    def test_empty_request_body(self):
        """Test handling of empty request body."""
        handler = LambdaHandler()
        
        event = {
            'httpMethod': 'POST',
            'path': '/mcp',
            'headers': {'Content-Type': 'application/json'},
            'body': '',
            'isBase64Encoded': False
        }
        
        response = handler.handle_event(event, None)
        
        assert response['statusCode'] == 400
        
        response_body = json.loads(response['body'])
        assert 'error' in response_body
        assert response_body['error']['message'] == 'Invalid request body'
    
    def test_non_dict_json_request(self):
        """Test handling of non-object JSON in request."""
        handler = LambdaHandler()
        
        event = {
            'httpMethod': 'POST',
            'path': '/mcp',
            'headers': {'Content-Type': 'application/json'},
            'body': '["array", "not", "object"]',
            'isBase64Encoded': False
        }
        
        response = handler.handle_event(event, None)
        
        assert response['statusCode'] == 400
        
        response_body = json.loads(response['body'])
        assert 'error' in response_body
        assert response_body['error']['message'] == 'Invalid request body'
    
    def test_processor_exception_handling(self):
        """Test handling of processor exceptions."""
        handler = LambdaHandler()
        
        # Mock processor to raise exception
        handler.processor.process_request = Mock(side_effect=Exception("Processor error"))
        
        mcp_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {}
        }
        
        event = {
            'httpMethod': 'POST',
            'path': '/mcp',
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(mcp_request),
            'isBase64Encoded': False
        }
        
        response = handler.handle_event(event, None)
        
        assert response['statusCode'] == 500
        
        response_body = json.loads(response['body'])
        assert 'error' in response_body
        assert 'Internal server error' in response_body['error']['message']
        assert 'Processor error' in response_body['error']['message']
    
    def test_malformed_base64_request(self):
        """Test handling of malformed base64 encoded request."""
        handler = LambdaHandler()
        
        event = {
            'httpMethod': 'POST',
            'path': '/mcp',
            'headers': {'Content-Type': 'application/json'},
            'body': 'invalid-base64!@#',
            'isBase64Encoded': True
        }
        
        response = handler.handle_event(event, None)
        
        # Base64 decode error is caught and treated as invalid request body
        assert response['statusCode'] == 400
        response_body = json.loads(response['body'])
        assert 'error' in response_body
        assert response_body['error']['message'] == 'Invalid request body'
    
    @patch('src.quilt_mcp.adapters.lambda_handler.logger')
    def test_logging_behavior(self, mock_logger):
        """Test that appropriate logging occurs."""
        handler = LambdaHandler()
        
        event = {
            'httpMethod': 'GET',
            'path': '/health'
        }
        
        handler.handle_event(event, None)
        
        # Verify info logging occurred
        mock_logger.info.assert_called()
        log_message = mock_logger.info.call_args[0][0]
        assert 'Processing Lambda event' in log_message
        assert 'GET' in log_message
    
    def test_get_timestamp_format(self):
        """Test timestamp format is correct."""
        handler = LambdaHandler()
        timestamp = handler._get_timestamp()
        
        # Should be ISO format ending with Z
        assert timestamp.endswith('Z')
        assert 'T' in timestamp
        
        # Should be parseable as ISO datetime
        from datetime import datetime
        parsed = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        assert parsed is not None
    
    def test_error_response_structure(self):
        """Test error response has correct structure."""
        handler = LambdaHandler()
        
        response = handler._error_response(404, "Not found")
        
        assert response['statusCode'] == 404
        assert response['headers']['Content-Type'] == 'application/json'
        assert response['headers']['Access-Control-Allow-Origin'] == '*'
        
        body = json.loads(response['body'])
        assert body['error']['code'] == -32603
        assert body['error']['message'] == "Not found"
    
    def test_success_response_structure(self):
        """Test success response has correct structure."""
        handler = LambdaHandler()
        
        mcp_data = {"jsonrpc": "2.0", "id": 1, "result": {"status": "ok"}}
        response = handler._success_response(mcp_data)
        
        assert response['statusCode'] == 200
        assert response['headers']['Content-Type'] == 'application/json'
        assert response['headers']['Access-Control-Allow-Origin'] == '*'
        
        body = json.loads(response['body'])
        assert body == mcp_data


class TestGlobalHandlerFunctions:
    """Test the global handler functions."""
    
    def setup_method(self):
        """Reset global handler instance before each test."""
        import src.quilt_mcp.adapters.lambda_handler
        src.quilt_mcp.adapters.lambda_handler._handler_instance = None
    
    def test_get_lambda_handler_singleton(self):
        """Test that get_lambda_handler returns singleton instance."""
        handler1 = get_lambda_handler()
        handler2 = get_lambda_handler()
        
        assert handler1 is handler2
        assert isinstance(handler1, LambdaHandler)
    
    def test_lambda_handler_function(self):
        """Test the lambda_handler function entry point."""
        event = {
            'httpMethod': 'GET',
            'path': '/health'
        }
        context = Mock()
        
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['status'] == 'ok'
        assert body['server'] == 'quilt-mcp-server'
    
    def test_lambda_handler_with_mcp_request(self):
        """Test lambda_handler with actual MCP request."""
        mcp_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "clientInfo": {"name": "test", "version": "1.0"}
            }
        }
        
        event = {
            'httpMethod': 'POST',
            'path': '/mcp',
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(mcp_request),
            'isBase64Encoded': False
        }
        context = Mock()
        
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 200
        response_body = json.loads(response['body'])
        assert response_body['jsonrpc'] == '2.0'
        assert response_body['id'] == 1
        assert 'result' in response_body
    
    def test_lambda_handler_error_propagation(self):
        """Test that lambda_handler properly propagates errors."""
        # Create an event that will cause an error
        event = {
            'httpMethod': 'POST',
            'path': '/mcp',
            'body': 'invalid json'
        }
        context = Mock()
        
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 400
        response_body = json.loads(response['body'])
        assert 'error' in response_body


class TestLambdaHandlerEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_missing_http_method(self):
        """Test handling of event missing httpMethod."""
        handler = LambdaHandler()
        
        # Mock the processor to return a valid response
        mock_response = {"jsonrpc": "2.0", "id": 1, "result": {}}
        handler.processor.process_request = Mock(return_value=mock_response)
        
        event = {
            'path': '/mcp',
            'body': '{"jsonrpc": "2.0", "id": 1, "method": "initialize"}'
        }
        
        # Should not crash, should treat as non-GET/OPTIONS and process as MCP request
        response = handler.handle_event(event, None)
        
        # Should successfully process the MCP request
        assert response['statusCode'] == 200
    
    def test_missing_path(self):
        """Test handling of event missing path."""
        handler = LambdaHandler()
        
        event = {
            'httpMethod': 'GET'
        }
        
        response = handler.handle_event(event, None)
        
        # Should still work as health check
        assert response['statusCode'] == 200
    
    def test_extract_mcp_request_exception(self):
        """Test _extract_mcp_request with unexpected exception."""
        handler = LambdaHandler()
        
        # Create an event that will cause an unexpected error
        event = Mock()
        event.get.side_effect = Exception("Unexpected error")
        
        result = handler._extract_mcp_request(event)
        
        assert result is None
    
    @patch('json.dumps', side_effect=Exception("JSON serialization error"))
    def test_response_serialization_error(self, mock_dumps):
        """Test handling of JSON serialization errors in responses."""
        handler = LambdaHandler()
        
        # This should handle the serialization error gracefully
        with pytest.raises(Exception):
            handler._success_response({"test": "data"})
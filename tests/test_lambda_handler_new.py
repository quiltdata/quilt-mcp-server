"""Test the new Lambda event handler architecture."""

import json
import pytest
from unittest.mock import patch, MagicMock

from src.quilt_mcp.adapters.lambda_handler import LambdaHandler, lambda_handler


class TestLambdaHandler:
    """Test the LambdaHandler class."""
    
    def test_handler_initialization(self):
        """Test handler initializes correctly."""
        handler_instance = LambdaHandler()
        assert handler_instance is not None
        assert handler_instance.processor is not None
    
    def test_cors_preflight_request(self):
        """Test CORS preflight request handling."""
        handler_instance = LambdaHandler()
        
        event = {
            'httpMethod': 'OPTIONS',
            'path': '/mcp'
        }
        
        response = handler_instance.handle_event(event, None)
        
        assert response['statusCode'] == 200
        assert 'Access-Control-Allow-Origin' in response['headers']
        assert response['headers']['Access-Control-Allow-Origin'] == '*'
        assert response['body'] == ''
    
    def test_health_check_request(self):
        """Test health check request handling."""
        handler_instance = LambdaHandler()
        
        event = {
            'httpMethod': 'GET',
            'path': '/mcp'
        }
        
        response = handler_instance.handle_event(event, None)
        
        assert response['statusCode'] == 200
        assert 'Content-Type' in response['headers']
        assert response['headers']['Content-Type'] == 'application/json'
        
        body = json.loads(response['body'])
        assert body['status'] == 'ok'
        assert body['server'] == 'quilt-mcp-server'
    
    def test_mcp_request_processing(self):
        """Test MCP request processing."""
        handler_instance = LambdaHandler()
        
        # Mock the processor
        handler_instance.processor.process_request = MagicMock(return_value={
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"tools": []}
        })
        
        mcp_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {}
        }
        
        event = {
            'httpMethod': 'POST',
            'path': '/mcp',
            'body': json.dumps(mcp_request),
            'headers': {'Content-Type': 'application/json'}
        }
        
        response = handler_instance.handle_event(event, None)
        
        assert response['statusCode'] == 200
        assert 'Content-Type' in response['headers']
        
        response_body = json.loads(response['body'])
        assert response_body['jsonrpc'] == '2.0'
        assert response_body['id'] == 1
        assert 'result' in response_body
        
        # Verify processor was called
        handler_instance.processor.process_request.assert_called_once_with(mcp_request)
    
    def test_invalid_json_request(self):
        """Test handling invalid JSON in request."""
        handler_instance = LambdaHandler()
        
        event = {
            'httpMethod': 'POST',
            'path': '/mcp',
            'body': 'invalid json',
            'headers': {'Content-Type': 'application/json'}
        }
        
        response = handler_instance.handle_event(event, None)
        
        assert response['statusCode'] == 400
        
        response_body = json.loads(response['body'])
        assert 'error' in response_body
    
    def test_empty_request_body(self):
        """Test handling empty request body."""
        handler_instance = LambdaHandler()
        
        event = {
            'httpMethod': 'POST',
            'path': '/mcp',
            'body': '',
            'headers': {'Content-Type': 'application/json'}
        }
        
        response = handler_instance.handle_event(event, None)
        
        assert response['statusCode'] == 400
    
    def test_processor_exception_handling(self):
        """Test handling processor exceptions."""
        handler_instance = LambdaHandler()
        
        # Mock processor to raise exception
        handler_instance.processor.process_request = MagicMock(side_effect=Exception("Test error"))
        
        mcp_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {}
        }
        
        event = {
            'httpMethod': 'POST',
            'path': '/mcp',
            'body': json.dumps(mcp_request),
            'headers': {'Content-Type': 'application/json'}
        }
        
        response = handler_instance.handle_event(event, None)
        
        assert response['statusCode'] == 500
        
        response_body = json.loads(response['body'])
        assert 'error' in response_body


class TestServerHandlerFunction:
    """Test the server handler function."""
    
    def test_server_handler_delegates_to_lambda_handler(self):
        """Test that server.handler delegates to lambda_handler."""
        from src.quilt_mcp.server import handler as server_handler
        
        # Mock lambda_handler
        with patch('src.quilt_mcp.server.lambda_handler') as mock_lambda_handler:
            mock_lambda_handler.return_value = {'statusCode': 200, 'body': '{}'}
            
            event = {'httpMethod': 'GET'}
            context = MagicMock()
            
            response = server_handler(event, context)
            
            assert response['statusCode'] == 200
            mock_lambda_handler.assert_called_once_with(event, context)
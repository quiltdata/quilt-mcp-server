import json
from unittest.mock import Mock, patch

import pytest

from quilt_mcp.handlers.lambda_handler import handle_mcp_info_request, handle_mcp_request, handler


class TestLambdaHandler:
    """Test suite for Lambda handler."""

    def test_handler_options_request(self):
        """Test CORS preflight OPTIONS request."""
        event = {
            'httpMethod': 'OPTIONS',
            'path': '/mcp/',
            'headers': {},
            'queryStringParameters': None,
            'body': ''
        }

        result = handler(event, {})

        assert result['statusCode'] == 200
        assert 'Access-Control-Allow-Origin' in result['headers']
        assert result['headers']['Access-Control-Allow-Origin'] == '*'
        assert 'Access-Control-Allow-Methods' in result['headers']

    def test_handler_get_request(self):
        """Test GET request for server info."""
        event = {
            'httpMethod': 'GET',
            'path': '/mcp/',
            'headers': {},
            'queryStringParameters': {},
            'body': ''
        }

        result = handler(event, {})

        assert result['statusCode'] == 200
        assert result['headers']['Content-Type'] == 'application/json'

        body = json.loads(result['body'])
        assert body['name'] == 'quilt-mcp-server'
        assert body['version'] == '1.0.0'
        assert 'capabilities' in body

    def test_handler_post_request(self):
        """Test POST request with MCP method call."""
        request_data = {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'initialize',
            'params': {}
        }

        event = {
            'httpMethod': 'POST',
            'path': '/mcp/',
            'headers': {'Content-Type': 'application/json'},
            'queryStringParameters': None,
            'body': json.dumps(request_data)
        }

        result = handler(event, {})

        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['jsonrpc'] == '2.0'
        assert body['id'] == 1
        assert 'result' in body

    def test_handler_invalid_json(self):
        """Test POST request with invalid JSON."""
        event = {
            'httpMethod': 'POST',
            'path': '/mcp/',
            'headers': {'Content-Type': 'application/json'},
            'queryStringParameters': None,
            'body': 'invalid json'
        }

        # Should handle gracefully and still process the request
        result = handler(event, {})
        assert result['statusCode'] == 200

    def test_handler_exception(self):
        """Test handler with exception."""
        with patch('quilt.lambda_handler.handle_mcp_info_request', side_effect=Exception('Test error')):
            event = {
                'httpMethod': 'GET',
                'path': '/mcp/',
                'headers': {},
                'queryStringParameters': {},
                'body': ''
            }

            result = handler(event, {})

            assert result['statusCode'] == 500
            body = json.loads(result['body'])
            assert 'error' in body

    @pytest.mark.asyncio
    async def test_handle_mcp_request_initialize(self):
        """Test MCP initialize request."""
        request_data = {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'initialize',
            'params': {}
        }

        result = await handle_mcp_request(request_data)

        assert result['jsonrpc'] == '2.0'
        assert result['id'] == 1
        assert 'result' in result
        assert result['result']['protocolVersion'] == '2024-11-05'
        assert 'capabilities' in result['result']
        assert 'serverInfo' in result['result']

    @pytest.mark.asyncio
    async def test_handle_mcp_request_tools_list(self):
        """Test MCP tools/list request."""
        request_data = {
            'jsonrpc': '2.0',
            'id': 2,
            'method': 'tools/list',
            'params': {}
        }

        mock_tool = Mock()
        mock_tool.name = 'test_tool'
        mock_tool.description = 'Test tool'
        mock_tool.parameters = {'type': 'object'}

        with patch('quilt.lambda_handler.mcp._tool_manager._tools', {
            'test_tool': mock_tool
        }):
            result = await handle_mcp_request(request_data)

            assert result['jsonrpc'] == '2.0'
            assert result['id'] == 2
            assert 'result' in result
            assert 'tools' in result['result']
            assert len(result['result']['tools']) == 1

    @pytest.mark.asyncio
    async def test_handle_mcp_request_tools_call_success(self):
        """Test successful MCP tools/call request."""
        def mock_tool(**kwargs):
            return {'result': 'success', 'args': kwargs}

        request_data = {
            'jsonrpc': '2.0',
            'id': 3,
            'method': 'tools/call',
            'params': {
                'name': 'test_tool',
                'arguments': {'param1': 'value1'}
            }
        }

        with patch('quilt.lambda_handler.mcp._tool_manager._tools', {
            'test_tool': Mock()
        }), patch('quilt.lambda_handler.mcp.call_tool', return_value=[Mock(text=json.dumps({'result': 'success', 'args': {'param1': 'value1'}}))]):
            result = await handle_mcp_request(request_data)

            assert result['jsonrpc'] == '2.0'
            assert result['id'] == 3
            assert 'result' in result
            assert 'content' in result['result']

    @pytest.mark.asyncio
    async def test_handle_mcp_request_tools_call_not_found(self):
        """Test MCP tools/call request with non-existent tool."""
        request_data = {
            'jsonrpc': '2.0',
            'id': 4,
            'method': 'tools/call',
            'params': {
                'name': 'nonexistent_tool',
                'arguments': {}
            }
        }

        with patch('quilt.lambda_handler.mcp._tool_manager._tools', {}):
            result = await handle_mcp_request(request_data)

            assert result['jsonrpc'] == '2.0'
            assert result['id'] == 4
            assert 'error' in result
            assert result['error']['code'] == -32601

    @pytest.mark.asyncio
    async def test_handle_mcp_request_tools_call_error(self):
        """Test MCP tools/call request with tool execution error."""
        def failing_tool(**kwargs):
            raise Exception('Tool failed')

        request_data = {
            'jsonrpc': '2.0',
            'id': 5,
            'method': 'tools/call',
            'params': {
                'name': 'failing_tool',
                'arguments': {}
            }
        }

        with patch('quilt.lambda_handler.mcp._tool_manager._tools', {
            'failing_tool': Mock()
        }), patch('quilt.lambda_handler.mcp.call_tool', side_effect=Exception('Tool failed')):
            result = await handle_mcp_request(request_data)

            assert result['jsonrpc'] == '2.0'
            assert result['id'] == 5
            assert 'error' in result
            assert result['error']['code'] == -32603

    @pytest.mark.asyncio
    async def test_handle_mcp_request_unknown_method(self):
        """Test MCP request with unknown method."""
        request_data = {
            'jsonrpc': '2.0',
            'id': 6,
            'method': 'unknown/method',
            'params': {}
        }

        result = await handle_mcp_request(request_data)

        assert result['jsonrpc'] == '2.0'
        assert result['id'] == 6
        assert 'error' in result
        assert result['error']['code'] == -32601

    @pytest.mark.asyncio
    async def test_handle_mcp_info_request(self):
        """Test MCP info request."""
        result = await handle_mcp_info_request({})

        assert result['name'] == 'quilt-mcp-server'
        assert result['version'] == '1.0.0'
        assert 'description' in result
        assert 'capabilities' in result

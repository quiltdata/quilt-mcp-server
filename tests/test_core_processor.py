"""Test the core MCP processor."""

import pytest
from unittest.mock import patch, MagicMock

from src.quilt_mcp.core import MCPProcessor, MCPError, ValidationError, ToolNotFoundError


class TestMCPProcessor:
    """Test the MCPProcessor class."""
    
    def test_processor_initialization(self):
        """Test processor initializes correctly."""
        processor = MCPProcessor()
        assert processor is not None
        assert processor.tool_registry is not None
        assert not processor._initialized
    
    def test_initialize_registers_tools(self):
        """Test initialization registers tools."""
        processor = MCPProcessor()
        
        # Mock tool modules to avoid import issues in tests
        with patch('src.quilt_mcp.core.processor.auth') as mock_auth, \
             patch('src.quilt_mcp.core.processor.packages') as mock_packages, \
             patch('src.quilt_mcp.core.processor.buckets') as mock_buckets, \
             patch('src.quilt_mcp.core.processor.package_ops') as mock_package_ops:
            
            # Mock module registration
            processor.tool_registry.register_from_module = MagicMock(return_value=5)
            
            processor.initialize()
            
            assert processor._initialized
            assert processor.tool_registry.register_from_module.call_count == 4
    
    def test_process_initialize_request(self):
        """Test processing initialize request."""
        processor = MCPProcessor()
        
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize", 
            "params": {
                "protocolVersion": "2024-11-05",
                "clientInfo": {"name": "test-client", "version": "1.0.0"}
            }
        }
        
        response = processor.process_request(request)
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert "result" in response
        assert response["result"]["protocolVersion"] == "2024-11-05"
        assert "capabilities" in response["result"]
        assert "serverInfo" in response["result"]
    
    def test_process_tools_list_request(self):
        """Test processing tools/list request.""" 
        processor = MCPProcessor()
        
        # Mock the tool registry
        processor.tool_registry.list_tools = MagicMock(return_value=[
            {"name": "test_tool", "description": "A test tool", "inputSchema": {}}
        ])
        
        request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        
        response = processor.process_request(request)
        
        assert response["jsonrpc"] == "2.0" 
        assert response["id"] == 2
        assert "result" in response
        assert "tools" in response["result"]
        assert len(response["result"]["tools"]) == 1
        assert response["result"]["tools"][0]["name"] == "test_tool"
    
    def test_process_tools_call_request(self):
        """Test processing tools/call request."""
        processor = MCPProcessor()
        
        # Mock tool call
        processor.tool_registry.call_tool = MagicMock(return_value={"status": "success", "data": "test result"})
        
        request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "test_tool",
                "arguments": {"arg1": "value1"}
            }
        }
        
        response = processor.process_request(request)
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 3
        assert "result" in response
        assert "content" in response["result"]
        assert response["result"]["isError"] is False
        
        # Verify tool was called correctly
        processor.tool_registry.call_tool.assert_called_once_with("test_tool", {"arg1": "value1"})
    
    def test_validation_error_on_invalid_jsonrpc(self):
        """Test validation error for invalid JSON-RPC."""
        processor = MCPProcessor()
        
        request = {
            "jsonrpc": "1.0",  # Invalid version
            "id": 1,
            "method": "initialize"
        }
        
        response = processor.process_request(request)
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert "error" in response
        assert response["error"]["code"] == -32602  # Invalid params
    
    def test_validation_error_on_missing_method(self):
        """Test validation error for missing method."""
        processor = MCPProcessor()
        
        request = {
            "jsonrpc": "2.0",
            "id": 1
            # Missing method
        }
        
        response = processor.process_request(request)
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert "error" in response
        assert response["error"]["code"] == -32602  # Invalid params
    
    def test_unknown_method_error(self):
        """Test error for unknown method."""
        processor = MCPProcessor()
        
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "unknown/method"
        }
        
        response = processor.process_request(request)
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert "error" in response
        assert response["error"]["code"] == -32602  # Invalid params
    
    def test_notification_request(self):
        """Test processing notification (no ID)."""
        processor = MCPProcessor()
        
        request = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }
        
        response = processor.process_request(request)
        
        assert response["jsonrpc"] == "2.0"
        assert "id" not in response  # No ID for notifications
        assert response["result"] is None
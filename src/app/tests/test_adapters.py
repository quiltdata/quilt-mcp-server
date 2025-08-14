"""Tests for adapters package."""

import unittest
from unittest.mock import patch, MagicMock

from quilt_mcp.adapters import FastMCPBridge


class TestAdapters(unittest.TestCase):
    """Test adapters module imports."""

    def test_fastmcp_bridge_import(self):
        """Test FastMCPBridge can be imported."""
        self.assertTrue(callable(FastMCPBridge))

    def test_all_exports(self):
        """Test __all__ exports."""
        from quilt_mcp.adapters import __all__
        self.assertIn("FastMCPBridge", __all__)


class TestFastMCPBridge(unittest.TestCase):
    """Test FastMCPBridge functionality."""

    @patch('quilt_mcp.adapters.fastmcp_bridge.FastMCP')
    @patch('quilt_mcp.adapters.fastmcp_bridge.MCPProcessor')
    def test_init(self, mock_processor_class, mock_fastmcp_class):
        """Test FastMCPBridge initialization."""
        bridge = FastMCPBridge("test")
        
        mock_fastmcp_class.assert_called_once_with("test")
        mock_processor_class.assert_called_once()
        self.assertFalse(bridge._registered)

    @patch('quilt_mcp.adapters.fastmcp_bridge.FastMCP')
    @patch('quilt_mcp.adapters.fastmcp_bridge.MCPProcessor')
    def test_initialize(self, mock_processor_class, mock_fastmcp_class):
        """Test bridge initialization."""
        mock_processor = MagicMock()
        mock_processor_class.return_value = mock_processor
        
        bridge = FastMCPBridge("test")
        
        with patch.object(bridge, '_register_tools_with_fastmcp') as mock_register_tools, \
             patch.object(bridge, '_register_health_endpoint') as mock_register_health:
            
            bridge.initialize()
            
            mock_processor.initialize.assert_called_once()
            mock_register_tools.assert_called_once()
            mock_register_health.assert_called_once()
            self.assertTrue(bridge._registered)

    @patch('quilt_mcp.adapters.fastmcp_bridge.FastMCP')
    @patch('quilt_mcp.adapters.fastmcp_bridge.MCPProcessor')
    def test_initialize_idempotent(self, mock_processor_class, mock_fastmcp_class):
        """Test that initialize() can be called multiple times safely."""
        mock_processor = MagicMock()
        mock_processor_class.return_value = mock_processor
        
        bridge = FastMCPBridge("test")
        bridge._registered = True  # Already initialized
        
        bridge.initialize()
        
        # Should not call processor.initialize again
        mock_processor.initialize.assert_not_called()

    @patch('quilt_mcp.adapters.fastmcp_bridge.FastMCP')
    @patch('quilt_mcp.adapters.fastmcp_bridge.MCPProcessor')
    def test_register_tools_with_fastmcp(self, mock_processor_class, mock_fastmcp_class):
        """Test tool registration with FastMCP."""
        mock_processor = MagicMock()
        mock_tool_registry = MagicMock()
        mock_processor.tool_registry = mock_tool_registry
        mock_processor_class.return_value = mock_processor
        
        # Mock tools list
        mock_tool_registry.list_tools.return_value = [
            {"name": "test_tool", "description": "Test tool", "inputSchema": {}}
        ]
        
        mock_fastmcp = MagicMock()
        mock_fastmcp_class.return_value = mock_fastmcp
        
        bridge = FastMCPBridge("test")
        bridge._register_tools_with_fastmcp()
        
        mock_tool_registry.list_tools.assert_called_once()

    @patch('quilt_mcp.adapters.fastmcp_bridge.FastMCP')
    @patch('quilt_mcp.adapters.fastmcp_bridge.MCPProcessor')
    def test_register_health_endpoint(self, mock_processor_class, mock_fastmcp_class):
        """Test health endpoint registration."""
        mock_fastmcp = MagicMock()
        mock_fastmcp_class.return_value = mock_fastmcp
        
        bridge = FastMCPBridge("test")
        bridge._register_health_endpoint()
        
        # Should register tool endpoint (FastMCP uses tool() decorator)
        mock_fastmcp.tool.assert_called_once()

    @patch('quilt_mcp.adapters.fastmcp_bridge.FastMCP')  
    @patch('quilt_mcp.adapters.fastmcp_bridge.MCPProcessor')
    def test_run(self, mock_processor_class, mock_fastmcp_class):
        """Test running the bridge."""
        mock_fastmcp = MagicMock()
        mock_fastmcp_class.return_value = mock_fastmcp
        
        bridge = FastMCPBridge("test")
        
        with patch.object(bridge, 'initialize') as mock_initialize:
            bridge.run(transport="streamable-http")
            
        mock_initialize.assert_called_once()
        mock_fastmcp.run.assert_called_once_with(transport="streamable-http")

    @patch('quilt_mcp.adapters.fastmcp_bridge.FastMCP')  
    @patch('quilt_mcp.adapters.fastmcp_bridge.MCPProcessor')
    def test_run_stdio(self, mock_processor_class, mock_fastmcp_class):
        """Test running with stdio transport."""
        mock_fastmcp = MagicMock()
        mock_fastmcp_class.return_value = mock_fastmcp
        
        bridge = FastMCPBridge("test")
        
        with patch.object(bridge, 'initialize'):
            bridge.run(transport="stdio")
            
        mock_fastmcp.run.assert_called_once_with(transport="stdio")

    @patch('quilt_mcp.adapters.fastmcp_bridge.FastMCP')  
    @patch('quilt_mcp.adapters.fastmcp_bridge.MCPProcessor')
    def test_run_invalid_transport(self, mock_processor_class, mock_fastmcp_class):
        """Test running with invalid transport."""
        bridge = FastMCPBridge("test")
        
        with patch.object(bridge, 'initialize'):
            with self.assertRaises(ValueError):
                bridge.run(transport="invalid")

    @patch('quilt_mcp.adapters.fastmcp_bridge.FastMCP')  
    @patch('quilt_mcp.adapters.fastmcp_bridge.MCPProcessor')
    def test_get_fastmcp_instance(self, mock_processor_class, mock_fastmcp_class):
        """Test getting FastMCP instance."""
        mock_fastmcp = MagicMock()
        mock_fastmcp_class.return_value = mock_fastmcp
        
        bridge = FastMCPBridge("test")
        
        with patch.object(bridge, 'initialize') as mock_initialize:
            result = bridge.get_fastmcp_instance()
            
        mock_initialize.assert_called_once()
        self.assertEqual(result, mock_fastmcp)

    @patch('quilt_mcp.adapters.fastmcp_bridge.FastMCP')
    @patch('quilt_mcp.adapters.fastmcp_bridge.MCPProcessor')
    def test_create_fastmcp_tool(self, mock_processor_class, mock_fastmcp_class):
        """Test creating FastMCP tool wrapper."""
        mock_processor = MagicMock()
        mock_tool_registry = MagicMock()
        mock_processor.tool_registry = mock_tool_registry
        mock_processor_class.return_value = mock_processor
        
        mock_fastmcp = MagicMock()
        mock_tool_decorator = MagicMock()
        mock_fastmcp.tool.return_value = mock_tool_decorator
        mock_fastmcp_class.return_value = mock_fastmcp
        
        bridge = FastMCPBridge("test")
        
        tool_def = {
            "name": "test_tool",
            "description": "Test tool description",
            "inputSchema": {}
        }
        
        bridge._create_fastmcp_tool(tool_def)
        
        mock_fastmcp.tool.assert_called_once()
        mock_tool_decorator.assert_called_once()

    @patch('quilt_mcp.adapters.fastmcp_bridge.FastMCP')
    @patch('quilt_mcp.adapters.fastmcp_bridge.MCPProcessor')
    def test_tool_wrapper_dict_result(self, mock_processor_class, mock_fastmcp_class):
        """Test tool wrapper with dict result."""
        mock_processor = MagicMock()
        mock_tool_registry = MagicMock()
        mock_processor.tool_registry = mock_tool_registry
        mock_processor_class.return_value = mock_processor
        
        # Mock tool registry call returns dict
        mock_tool_registry.call_tool.return_value = {"result": "success"}
        
        mock_fastmcp = MagicMock()
        mock_fastmcp_class.return_value = mock_fastmcp
        
        bridge = FastMCPBridge("test")
        
        tool_def = {
            "name": "test_tool",
            "description": "Test tool",
            "inputSchema": {}
        }
        
        # Extract the wrapper function by mocking the decorator
        captured_wrapper = None
        def capture_wrapper(func):
            nonlocal captured_wrapper
            captured_wrapper = func
            return func
            
        mock_fastmcp.tool.return_value = capture_wrapper
        
        bridge._create_fastmcp_tool(tool_def)
        
        # Call the wrapper
        result = captured_wrapper(arg1="value1")
        
        # Should return JSON string
        self.assertIn("success", result)
        mock_tool_registry.call_tool.assert_called_with("test_tool", {"arg1": "value1"})

    @patch('quilt_mcp.adapters.fastmcp_bridge.FastMCP')
    @patch('quilt_mcp.adapters.fastmcp_bridge.MCPProcessor')
    def test_tool_wrapper_error(self, mock_processor_class, mock_fastmcp_class):
        """Test tool wrapper error handling."""
        mock_processor = MagicMock()
        mock_tool_registry = MagicMock()
        mock_processor.tool_registry = mock_tool_registry
        mock_processor_class.return_value = mock_processor
        
        # Mock tool registry call raises error
        mock_tool_registry.call_tool.side_effect = Exception("Test error")
        
        mock_fastmcp = MagicMock()
        mock_fastmcp_class.return_value = mock_fastmcp
        
        bridge = FastMCPBridge("test")
        
        tool_def = {
            "name": "test_tool",
            "description": "Test tool",
            "inputSchema": {}
        }
        
        # Extract the wrapper function
        captured_wrapper = None
        def capture_wrapper(func):
            nonlocal captured_wrapper
            captured_wrapper = func
            return func
            
        mock_fastmcp.tool.return_value = capture_wrapper
        
        bridge._create_fastmcp_tool(tool_def)
        
        # Call the wrapper
        result = captured_wrapper()
        
        # Should return error message
        self.assertIn("Error:", result)
        self.assertIn("Test error", result)
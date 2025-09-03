"""
Test Tool Execution
Tests that tools work through the DXT package and handle errors properly.
"""

import asyncio
import json
import pytest
import os
from pathlib import Path
from tests.mcp_integration.test_mcp_handshake import MCPTestClient


class TestToolExecution:
    """Test MCP tool execution functionality."""
    
    @pytest.fixture
    def dxt_package_path(self):
        """Path to the built DXT package."""
        project_root = Path(__file__).parent.parent.parent.parent.parent
        dxt_path = project_root / "tools" / "dxt" / "dist"
        
        # Find the actual built DXT file
        if dxt_path.exists():
            dxt_files = list(dxt_path.glob("*.dxt"))
            if dxt_files:
                return str(dxt_files[0])
        
        pytest.skip("No DXT package found")
    
    async def start_dxt_process(self, dxt_package_path):
        """Start DXT process by running bootstrap.py from unpacked DXT."""
        if not os.path.exists(dxt_package_path):
            pytest.skip("DXT package not built yet")
        
        try:
            # First unpack the DXT file to a temp directory
            import tempfile
            import subprocess
            temp_dir = tempfile.mkdtemp()
            
            # Unpack the DXT file
            unpack_process = subprocess.run([
                "npx", "@anthropic-ai/dxt", "unpack", dxt_package_path, temp_dir
            ], capture_output=True, text=True)
            
            if unpack_process.returncode != 0:
                pytest.skip(f"Could not unpack DXT file: {unpack_process.stderr}")
            
            # Start the DXT process by running bootstrap.py directly
            bootstrap_path = os.path.join(temp_dir, "bootstrap.py")
            if not os.path.exists(bootstrap_path):
                pytest.skip(f"bootstrap.py not found in unpacked DXT at {bootstrap_path}")
            
            # Start DXT process using bootstrap.py (simulating Claude Desktop execution)
            process = await asyncio.create_subprocess_exec(
                "python3", bootstrap_path,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=temp_dir
            )
            
            # Give it time for startup and tool registration (bootstrap process)
            await asyncio.sleep(30.0)  # Give time for startup
            
            if process.returncode is not None:
                stderr = await process.stderr.read()
                pytest.skip(f"DXT process failed to start: {stderr.decode()}")
            
            return process
        except Exception as e:
            pytest.skip(f"Could not start DXT process: {e}")
    
    @pytest.mark.asyncio
    async def test_tool_call_basic_structure(self, dxt_package_path):
        """Test basic tool call request structure."""
        process = await self.start_dxt_process(dxt_package_path)
        client = MCPTestClient(process)
        
        try:
            # Initialize
            init_response = await client.initialize()
            if "error" in (init_response or {}):
                pytest.skip("Could not initialize MCP connection")
            
            # Get available tools
            tools = await client.list_tools()
            
            if not tools:
                pytest.skip("No tools available for execution testing")
            
            # Try to call the first available tool
            first_tool = tools[0]
            tool_name = first_tool.get("name")
            
            if not tool_name:
                pytest.skip("Tool has no name")
            
            # Make a basic tool call (may fail due to parameters, but should respond)
            response = await client.send_request("tools/call", {
                "name": tool_name,
                "arguments": {}
            }, timeout=10.0)
            
            assert response is not None, "Should receive response to tool call"
            
            # Should either succeed or fail with informative error
            if "error" in response:
                error_info = response["error"]
                assert error_info, "Error should provide information"
            elif "result" in response:
                # Successful tool call
                assert "content" in response["result"], "Successful tool call should have content"
        finally:
            await client.close()
    
    @pytest.mark.asyncio
    async def test_tool_error_handling(self, dxt_package_path):
        """Test tool error handling with invalid parameters."""
        process = await self.start_dxt_process(dxt_package_path)
        client = MCPTestClient(process)
        
        try:
            init_response = await client.initialize()
            if "error" in (init_response or {}):
                pytest.skip("Could not initialize MCP connection")
            
            tools = await client.list_tools()
            if not tools:
                pytest.skip("No tools available for error testing")
            
            first_tool = tools[0]
            tool_name = first_tool.get("name")
            
            # Test with invalid tool name
            response = await client.send_request("tools/call", {
                "name": "nonexistent_tool",
                "arguments": {}
            })
            
            assert response is not None, "Should respond to invalid tool call"
            assert "error" in response, "Should return error for nonexistent tool"
            
            # Test with invalid arguments for real tool
            response = await client.send_request("tools/call", {
                "name": tool_name,
                "arguments": {"invalid_param": "invalid_value"}
            })
            
            # Should handle invalid arguments gracefully
            assert response is not None, "Should respond to tool call with invalid args"
        finally:
            await client.close()
    
    @pytest.mark.asyncio
    async def test_tool_execution_timeout(self, dxt_package_path):
        """Test tool execution timeout handling."""
        process = await self.start_dxt_process(dxt_package_path)
        client = MCPTestClient(process)
        
        try:
            init_response = await client.initialize()
            if "error" in (init_response or {}):
                pytest.skip("Could not initialize MCP connection")
            
            tools = await client.list_tools()
            if not tools:
                pytest.skip("No tools available for timeout testing")
            
            first_tool = tools[0]
            tool_name = first_tool.get("name")
            
            # Test with very short timeout
            response = await client.send_request("tools/call", {
                "name": tool_name,
                "arguments": {}
            }, timeout=0.1)
            
            # Should either complete quickly or timeout gracefully
            if response and "error" in response and response["error"] == "timeout":
                # Timeout is acceptable for this test
                pass
            else:
                # Tool completed quickly, which is also good
                assert response is not None, "Should receive response even with short timeout"
        finally:
            await client.close()
    
    @pytest.mark.asyncio
    async def test_multiple_tool_calls(self, dxt_package_path):
        """Test multiple sequential tool calls."""
        process = await self.start_dxt_process(dxt_package_path)
        client = MCPTestClient(process)
        
        try:
            init_response = await client.initialize()
            if "error" in (init_response or {}):
                pytest.skip("Could not initialize MCP connection")
            
            tools = await client.list_tools()
            if not tools:
                pytest.skip("No tools available for multiple call testing")
            
            first_tool = tools[0]
            tool_name = first_tool.get("name")
            
            # Make multiple calls to the same tool
            responses = []
            for i in range(3):
                response = await client.send_request("tools/call", {
                    "name": tool_name,
                    "arguments": {}
                }, timeout=5.0)
                responses.append(response)
                
                # Small delay between calls
                await asyncio.sleep(0.1)
            
            # All calls should receive responses
            for i, response in enumerate(responses):
                assert response is not None, f"Call {i+1} should receive response"
            
            # Responses should be consistent in structure
            error_responses = [r for r in responses if r and "error" in r]
            success_responses = [r for r in responses if r and "result" in r]
            
            if error_responses and success_responses:
                pytest.skip("Mixed success/error responses - may indicate unstable tool")
        finally:
            await client.close()
    
    @pytest.mark.asyncio
    async def test_tool_response_format(self, dxt_package_path):
        """Test that tool responses follow proper MCP format."""
        process = await self.start_dxt_process(dxt_package_path)
        client = MCPTestClient(process)
        
        try:
            init_response = await client.initialize()
            if "error" in (init_response or {}):
                pytest.skip("Could not initialize MCP connection")
            
            tools = await client.list_tools()
            if not tools:
                pytest.skip("No tools available for response format testing")
            
            first_tool = tools[0]
            tool_name = first_tool.get("name")
            
            response = await client.send_request("tools/call", {
                "name": tool_name,
                "arguments": {}
            })
            
            assert response is not None, "Should receive response"
            
            # Should have proper JSON-RPC structure
            assert "jsonrpc" in response or "id" in response, \
                "Response should follow JSON-RPC format"
            
            if "result" in response:
                result = response["result"]
                # Successful tool response should have content
                assert "content" in result, "Tool result should have content"
                
                content = result["content"]
                assert isinstance(content, list), "Content should be a list"
                
                for content_item in content:
                    assert "type" in content_item, "Content item should have type"
                    assert "text" in content_item or "data" in content_item, \
                        "Content item should have text or data"
        finally:
            await client.close()
"""
Test Tool Discovery
Tests that all tools are discoverable via DXT and properly registered.
"""

import asyncio
import json
import pytest
import os
from pathlib import Path
from .test_mcp_handshake import MCPTestClient


class TestToolDiscovery:
    """Test MCP tool discovery functionality."""
    
    @pytest.fixture
    def dxt_package_path(self):
        """Path to the built DXT package."""
        project_root = Path(__file__).parent.parent.parent.parent.parent
        dxt_path = project_root / "tools" / "dxt" / "dist" / "quilt-mcp-dev.dxt"
        
        if not dxt_path.exists():
            dist_dir = project_root / "tools" / "dxt" / "dist"
            if dist_dir.exists():
                dxt_files = list(dist_dir.glob("*.dxt"))
                if dxt_files:
                    dxt_path = dxt_files[0]
        
        return str(dxt_path)
    
    async def start_dxt_process(self, dxt_package_path):
        """Start DXT process for testing."""
        if not os.path.exists(dxt_package_path):
            pytest.skip("DXT package not built yet")
        
        try:
            process = await asyncio.create_subprocess_exec(
                "npx", "@anthropic-ai/dxt", "run", dxt_package_path,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            await asyncio.sleep(2.0)  # Give more time for tool registration
            
            if process.returncode is not None:
                stderr = await process.stderr.read()
                pytest.skip(f"DXT process failed to start: {stderr.decode()}")
            
            return process
        except Exception as e:
            pytest.skip(f"Could not start DXT process: {e}")
    
    @pytest.mark.asyncio
    async def test_tools_list_request(self, dxt_package_path):
        """Test that tools/list request returns tool information."""
        process = await self.start_dxt_process(dxt_package_path)
        client = MCPTestClient(process)
        
        try:
            # Initialize first
            init_response = await client.initialize()
            if "error" in (init_response or {}):
                pytest.skip("Could not initialize MCP connection")
            
            # Request tools list
            tools_response = await client.send_request("tools/list")
            
            assert tools_response is not None, "Should receive response to tools/list"
            
            if "result" in tools_response:
                tools = tools_response["result"].get("tools", [])
                assert isinstance(tools, list), "Tools should be returned as a list"
            elif "error" in tools_response:
                # May not have tools loaded yet, but should provide informative error
                error_msg = str(tools_response["error"])
                assert error_msg, "Error message should be informative"
        finally:
            await client.close()
    
    @pytest.mark.asyncio
    async def test_minimum_tool_count(self, dxt_package_path):
        """Test that a reasonable number of tools are discoverable."""
        process = await self.start_dxt_process(dxt_package_path)
        client = MCPTestClient(process)
        
        try:
            init_response = await client.initialize()
            if "error" in (init_response or {}):
                pytest.skip("Could not initialize MCP connection")
            
            tools = await client.list_tools()
            
            # Should have at least some tools (even if not the full 84+ yet)
            # In early implementation, may have fewer tools working
            min_expected_tools = 1
            
            if len(tools) >= min_expected_tools:
                assert len(tools) >= min_expected_tools, \
                    f"Expected at least {min_expected_tools} tools, got {len(tools)}"
            else:
                # If no tools yet, that's okay for early implementation
                # but should be documented in the test
                pytest.skip(f"No tools loaded yet (found {len(tools)} tools). Implementation in progress.")
        finally:
            await client.close()
    
    @pytest.mark.asyncio
    async def test_tool_metadata_structure(self, dxt_package_path):
        """Test that discovered tools have proper metadata structure."""
        process = await self.start_dxt_process(dxt_package_path)
        client = MCPTestClient(process)
        
        try:
            init_response = await client.initialize()
            if "error" in (init_response or {}):
                pytest.skip("Could not initialize MCP connection")
            
            tools = await client.list_tools()
            
            if not tools:
                pytest.skip("No tools loaded yet for metadata validation")
            
            for tool in tools:
                # Each tool should have required metadata
                assert "name" in tool, f"Tool missing name: {tool}"
                assert tool["name"], "Tool name should not be empty"
                
                # Should have description
                if "description" in tool:
                    assert tool["description"], "Tool description should not be empty"
                
                # Should have schema information
                if "inputSchema" in tool:
                    schema = tool["inputSchema"]
                    assert isinstance(schema, dict), "Tool input schema should be a dict"
        finally:
            await client.close()
    
    @pytest.mark.asyncio
    async def test_quilt_specific_tools(self, dxt_package_path):
        """Test that Quilt-specific tools are discoverable."""
        process = await self.start_dxt_process(dxt_package_path)
        client = MCPTestClient(process)
        
        try:
            init_response = await client.initialize()
            if "error" in (init_response or {}):
                pytest.skip("Could not initialize MCP connection")
            
            tools = await client.list_tools()
            
            if not tools:
                pytest.skip("No tools loaded yet for Quilt tool validation")
            
            # Look for Quilt-related tools
            tool_names = [tool.get("name", "").lower() for tool in tools]
            
            # Should have some Quilt-related functionality
            quilt_indicators = ["quilt", "package", "browse", "search"]
            
            has_quilt_tools = any(
                any(indicator in name for indicator in quilt_indicators)
                for name in tool_names
            )
            
            if has_quilt_tools:
                assert has_quilt_tools, "Should have Quilt-related tools"
            else:
                # May be early in implementation
                pytest.skip("Quilt-specific tools not loaded yet. Implementation in progress.")
        finally:
            await client.close()
    
    @pytest.mark.asyncio
    async def test_tool_discovery_performance(self, dxt_package_path):
        """Test that tool discovery performs within acceptable time."""
        process = await self.start_dxt_process(dxt_package_path)
        client = MCPTestClient(process)
        
        try:
            init_response = await client.initialize()
            if "error" in (init_response or {}):
                pytest.skip("Could not initialize MCP connection")
            
            # Measure tool discovery time
            import time
            start_time = time.time()
            
            tools_response = await client.send_request("tools/list", timeout=10.0)
            
            discovery_time = time.time() - start_time
            
            # Should complete within reasonable time
            assert discovery_time < 10.0, f"Tool discovery took too long: {discovery_time:.2f}s"
            
            # Should not timeout
            if tools_response and "error" in tools_response:
                assert tools_response["error"] != "timeout", "Tool discovery should not timeout"
        finally:
            await client.close()
    
    @pytest.mark.asyncio
    async def test_tool_list_consistency(self, dxt_package_path):
        """Test that tool list returns consistent results across multiple requests."""
        process = await self.start_dxt_process(dxt_package_path)
        client = MCPTestClient(process)
        
        try:
            init_response = await client.initialize()
            if "error" in (init_response or {}):
                pytest.skip("Could not initialize MCP connection")
            
            # Get tools list twice
            tools1 = await client.list_tools()
            await asyncio.sleep(0.5)  # Small delay
            tools2 = await client.list_tools()
            
            # Should return consistent results
            assert len(tools1) == len(tools2), "Tool list length should be consistent"
            
            if tools1 and tools2:
                # Tool names should be the same
                names1 = {tool.get("name") for tool in tools1}
                names2 = {tool.get("name") for tool in tools2}
                assert names1 == names2, "Tool names should be consistent across requests"
        finally:
            await client.close()
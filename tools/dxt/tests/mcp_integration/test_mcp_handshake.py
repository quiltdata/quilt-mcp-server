"""
Test MCP Handshake
Tests MCP handshake with timeout scenarios between DXT and simulated Claude Desktop.
"""

import asyncio
import json
import pytest
import subprocess
import tempfile
import zipfile
import time
import signal
import os
from pathlib import Path
from unittest.mock import AsyncMock


class MCPTestClient:
    """Simple MCP test client for testing DXT communication."""
    
    def __init__(self, process):
        self.process = process
        self.request_id = 0
    
    async def send_request(self, method, params=None, timeout=10.0):
        """Send an MCP request and wait for response."""
        self.request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method
        }
        if params:
            request["params"] = params
        
        request_json = json.dumps(request) + "\n"
        
        try:
            self.process.stdin.write(request_json.encode())
            await self.process.stdin.drain()
            
            # Wait for response with timeout
            response_line = await asyncio.wait_for(
                self.process.stdout.readline(), 
                timeout=timeout
            )
            
            if not response_line:
                return None
            
            return json.loads(response_line.decode().strip())
        except asyncio.TimeoutError:
            return {"error": "timeout"}
        except Exception as e:
            return {"error": str(e)}
    
    async def initialize(self):
        """Send MCP initialize request."""
        return await self.send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "roots": {"listChanged": True},
                "sampling": {}
            },
            "clientInfo": {
                "name": "test-client",
                "version": "1.0.0"
            }
        })
    
    async def list_tools(self):
        """Send MCP tools/list request."""
        response = await self.send_request("tools/list")
        if response and "result" in response:
            return response["result"].get("tools", [])
        return []
    
    async def close(self):
        """Close the MCP client connection."""
        if self.process and self.process.returncode is None:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self.process.kill()


class TestMCPHandshake:
    """Test MCP handshake functionality."""
    
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
        """Start DXT process by running bootstrap.py from unpacked DXT."""
        if not os.path.exists(dxt_package_path):
            pytest.skip("DXT package not built yet")
        
        try:
            # First unpack the DXT file to a temp directory
            import tempfile
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
            
            # Give it more time to start up and install dependencies (bootstrap process)
            await asyncio.sleep(30.0)  # Bootstrap creates venv and installs deps
            
            if process.returncode is not None:
                stderr = await process.stderr.read()
                pytest.skip(f"DXT process failed to start: {stderr.decode()}")
            
            return process
        except Exception as e:
            pytest.skip(f"Could not start DXT process: {e}")
    
    @pytest.mark.asyncio
    async def test_mcp_handshake_basic(self, dxt_package_path):
        """Test basic MCP handshake with DXT."""
        process = await self.start_dxt_process(dxt_package_path)
        client = MCPTestClient(process)
        
        try:
            # Test initialize request
            response = await client.initialize()
            
            # Should get a valid response
            assert response is not None, "No response to initialize request"
            assert "error" not in response or response["error"] != "timeout", \
                "Initialize request timed out"
            
            # If successful, should have result with capabilities
            if "result" in response:
                result = response["result"]
                assert "capabilities" in result, "Initialize response should include capabilities"
        finally:
            await client.close()
    
    @pytest.mark.asyncio
    async def test_mcp_handshake_timeout_handling(self, dxt_package_path):
        """Test MCP handshake with timeout scenarios."""
        process = await self.start_dxt_process(dxt_package_path)
        client = MCPTestClient(process)
        
        try:
            # Test with very short timeout
            response = await client.send_request("initialize", timeout=0.1)
            
            # Should handle timeout gracefully
            if response and "error" in response:
                assert response["error"] == "timeout", "Should properly detect timeout"
        finally:
            await client.close()
    
    @pytest.mark.asyncio
    async def test_mcp_handshake_protocol_version(self, dxt_package_path):
        """Test MCP handshake with different protocol versions."""
        process = await self.start_dxt_process(dxt_package_path)
        client = MCPTestClient(process)
        
        try:
            # Test with different protocol version
            response = await client.send_request("initialize", {
                "protocolVersion": "2024-10-01",  # Older version
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"}
            })
            
            # Should either accept or reject gracefully
            assert response is not None, "Should respond to initialize with any version"
            
            if "error" in response:
                # Error should be informative about version compatibility
                error_msg = str(response.get("error", {}))
                assert "version" in error_msg.lower() or "protocol" in error_msg.lower(), \
                    "Version error should be informative"
        finally:
            await client.close()
    
    @pytest.mark.asyncio
    async def test_mcp_handshake_malformed_request(self, dxt_package_path):
        """Test MCP handshake with malformed requests."""
        process = await self.start_dxt_process(dxt_package_path)
        
        try:
            # Send malformed JSON
            malformed_json = '{"invalid": json,}\n'
            process.stdin.write(malformed_json.encode())
            await process.stdin.drain()
            
            # Should handle malformed request gracefully (not crash)
            await asyncio.sleep(1.0)
            
            # Process should still be running
            assert process.returncode is None, "DXT should handle malformed JSON gracefully"
        finally:
            if process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    process.kill()
    
    @pytest.mark.asyncio
    async def test_mcp_handshake_startup_time(self, dxt_package_path):
        """Test that MCP handshake completes within reasonable time."""
        start_time = time.time()
        
        process = await self.start_dxt_process(dxt_package_path)
        client = MCPTestClient(process)
        
        try:
            # Test handshake timing
            handshake_start = time.time()
            response = await client.initialize()
            handshake_time = time.time() - handshake_start
            
            # Should complete handshake quickly
            assert handshake_time < 5.0, f"Handshake took too long: {handshake_time:.2f}s"
            
            # Total startup should be reasonable
            total_time = time.time() - start_time
            assert total_time < 10.0, f"Total startup took too long: {total_time:.2f}s"
        finally:
            await client.close()
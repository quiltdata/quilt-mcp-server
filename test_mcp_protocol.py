#!/usr/bin/env python3
"""Test MCP protocol with correct SSE connection."""

import json
import time
from datetime import datetime


def test_mcp_initialize():
    """Test MCP initialization through SSE."""
    base_url = "https://demo.quiltdata.com"
    
    print(f"Testing MCP Protocol - {datetime.now()}")
    print("=" * 60)
    
    # Step 1: Connect to SSE endpoint to get session ID
    print("Step 1: Connect to SSE endpoint to establish session")
    import subprocess
    
    try:
        # Start SSE connection and capture session ID from headers
        result = subprocess.run([
            "curl", "-v", "-H", "Accept: text/event-stream",
            f"{base_url}/sse/"
        ], capture_output=True, text=True, timeout=10)
        
        print(f"Curl exit code: {result.returncode}")
        print(f"Headers: {result.stderr}")
        
        # Extract session ID from headers
        session_id = None
        for line in result.stderr.split('\n'):
            if 'mcp-session-id:' in line.lower():
                session_id = line.split(':')[-1].strip()
                break
        
        print(f"Session ID: {session_id}")
        
    except Exception as e:
        print(f"Error connecting to SSE: {e}")
        return
    
    print("\n" + "=" * 60)
    
    # Step 2: Test MCP initialize with session ID
    if session_id:
        print("Step 2: Test MCP initialize with session ID")
        
        initialize_data = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0"}
            }
        }
        
        try:
            result = subprocess.run([
                "curl", "-s", "-X", "POST",
                "-H", "Content-Type: application/json",
                "-H", f"mcp-session-id: {session_id}",
                "-d", json.dumps(initialize_data),
                f"{base_url}/sse/"
            ], capture_output=True, text=True, timeout=10)
            
            print(f"Status: {result.returncode}")
            print(f"Response: {result.stdout}")
            
        except Exception as e:
            print(f"Error with MCP initialize: {e}")
    
    print("\n" + "=" * 60)
    
    # Step 3: Test authentication status
    print("Step 3: Test authentication status")
    
    auth_data = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "auth_status",
        "params": {}
    }
    
    try:
        result = subprocess.run([
            "curl", "-s", "-X", "POST",
            "-H", "Content-Type: application/json",
            "-H", f"mcp-session-id: {session_id}" if session_id else "",
            "-d", json.dumps(auth_data),
            f"{base_url}/sse/"
        ], capture_output=True, text=True, timeout=10)
        
        print(f"Status: {result.returncode}")
        print(f"Response: {result.stdout}")
        
    except Exception as e:
        print(f"Error with auth status: {e}")


if __name__ == "__main__":
    test_mcp_initialize()

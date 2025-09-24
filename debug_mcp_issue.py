#!/usr/bin/env python3
"""
Debug script to understand the MCP initialization timing issue.
"""

import json
import time
import subprocess
import sys

def test_mcp_flow():
    """Test the MCP flow step by step to understand the issue."""
    
    print("🔍 Debugging MCP Authentication Issue")
    print("=" * 50)
    
    # Step 1: Initialize
    print("\n1. Testing initialization...")
    init_cmd = [
        "curl", "-s", "-X", "POST",
        "-H", "Content-Type: application/json",
        "-H", "Accept: application/json, text/event-stream", 
        "-H", "MCP-Protocol-Version: 2025-06-18",
        "-d", '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}',
        "https://demo.quiltdata.com/mcp/"
    ]
    
    try:
        result = subprocess.run(init_cmd, capture_output=True, text=True, timeout=30)
        print(f"Status: {result.returncode}")
        print(f"Response: {result.stdout}")
        
        if result.returncode != 0:
            print(f"Error: {result.stderr}")
            return False
            
        # Check if we got a proper response
        if "result" in result.stdout:
            print("✅ Initialize successful")
        else:
            print("❌ Initialize failed")
            print(f"Full response: {result.stdout}")
            return False
            
    except Exception as e:
        print(f"❌ Initialize request failed: {e}")
        return False
    
    # Step 2: Extract session ID (simulate what a client would do)
    print("\n2. Extracting session ID...")
    session_cmd = [
        "curl", "-s", "-I", "-X", "POST",
        "-H", "Content-Type: application/json",
        "-H", "Accept: application/json, text/event-stream",
        "-H", "MCP-Protocol-Version: 2025-06-18", 
        "-d", '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}',
        "https://demo.quiltdata.com/mcp/"
    ]
    
    try:
        result = subprocess.run(session_cmd, capture_output=True, text=True, timeout=30)
        session_id = None
        
        for line in result.stdout.split('\n'):
            if line.lower().startswith('mcp-session-id:'):
                session_id = line.split(':', 1)[1].strip()
                break
                
        if session_id:
            print(f"✅ Session ID: {session_id}")
        else:
            print("❌ Failed to extract session ID")
            print(f"Headers: {result.stdout}")
            return False
            
    except Exception as e:
        print(f"❌ Session extraction failed: {e}")
        return False
    
    # Step 3: Wait different amounts of time and test tools/list
    wait_times = [0, 1, 2, 3, 5]
    
    for wait_time in wait_times:
        print(f"\n3.{wait_times.index(wait_time) + 1}. Testing tools/list after {wait_time}s wait...")
        
        if wait_time > 0:
            print(f"⏳ Waiting {wait_time} seconds...")
            time.sleep(wait_time)
        
        tools_cmd = [
            "curl", "-s", "-X", "POST",
            "-H", "Content-Type: application/json",
            "-H", "Accept: application/json, text/event-stream",
            "-H", f"mcp-session-id: {session_id}",
            "-d", '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}',
            "https://demo.quiltdata.com/mcp/"
        ]
        
        try:
            result = subprocess.run(tools_cmd, capture_output=True, text=True, timeout=30)
            print(f"Status: {result.returncode}")
            print(f"Response: {result.stdout}")
            
            if "result" in result.stdout:
                print(f"✅ Tools list successful after {wait_time}s wait")
                return True
            elif "error" in result.stdout:
                error_data = json.loads(result.stdout.split('\n')[1].replace('data: ', ''))
                print(f"❌ Tools list failed after {wait_time}s: {error_data.get('error', {}).get('message', 'Unknown error')}")
            else:
                print(f"❌ Unexpected response after {wait_time}s: {result.stdout}")
                
        except Exception as e:
            print(f"❌ Tools list request failed after {wait_time}s: {e}")
    
    return False

if __name__ == "__main__":
    success = test_mcp_flow()
    sys.exit(0 if success else 1)

#!/usr/bin/env python3
"""
Test script to replicate and fix MCP authentication issues.
This script tests the complete MCP authentication flow.
"""

import json
import time
import requests
import sys
from typing import Dict, Any, Optional

class MCPTester:
    def __init__(self, base_url: str = "https://demo.quiltdata.com/mcp/"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session_id: Optional[str] = None
        self.initialized = False
        
    def make_request(self, method: str, params: Dict[str, Any] = None, 
                    request_id: int = 1) -> Dict[str, Any]:
        """Make an MCP request and return the response."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": "2025-06-18"
        }
        
        if self.session_id:
            headers["mcp-session-id"] = self.session_id
            
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method
        }
        
        if params:
            payload["params"] = params
            
        print(f"Making request: {method}")
        print(f"Headers: {headers}")
        print(f"Payload: {json.dumps(payload, indent=2)}")
        
        try:
            response = self.session.post(self.base_url, headers=headers, json=payload, timeout=30)
            print(f"Response status: {response.status_code}")
            print(f"Response headers: {dict(response.headers)}")
            
            # Handle SSE response
            if response.headers.get('content-type', '').startswith('text/event-stream'):
                # Parse SSE response
                lines = response.text.strip().split('\n')
                for line in lines:
                    if line.startswith('data: '):
                        data = line[6:]  # Remove 'data: ' prefix
                        try:
                            return json.loads(data)
                        except json.JSONDecodeError:
                            print(f"Failed to parse JSON: {data}")
                            return {"error": f"Invalid JSON: {data}"}
            else:
                # Regular JSON response
                return response.json()
                
        except Exception as e:
            print(f"Request failed: {e}")
            return {"error": str(e)}
    
    def initialize(self) -> bool:
        """Initialize the MCP connection."""
        print("\n=== INITIALIZING MCP CONNECTION ===")
        
        response = self.make_request("initialize", {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0"}
        })
        
        print(f"Initialize response: {json.dumps(response, indent=2)}")
        
        if "error" in response:
            print(f"Initialize failed: {response['error']}")
            return False
            
        if "result" in response:
            self.initialized = True
            print("✅ MCP initialization successful")
            return True
            
        print("❌ Unexpected initialize response")
        return False
    
    def list_tools(self) -> bool:
        """List available tools."""
        print("\n=== LISTING TOOLS ===")
        
        response = self.make_request("tools/list", {}, 2)
        print(f"Tools list response: {json.dumps(response, indent=2)}")
        
        if "error" in response:
            print(f"❌ Tools list failed: {response['error']}")
            return False
            
        if "result" in response:
            tools = response["result"].get("tools", [])
            print(f"✅ Found {len(tools)} tools:")
            for tool in tools:
                print(f"  - {tool.get('name', 'unknown')}")
            return True
            
        print("❌ Unexpected tools list response")
        return False
    
    def test_auth_status(self) -> bool:
        """Test the auth_status tool."""
        print("\n=== TESTING AUTH STATUS ===")
        
        response = self.make_request("tools/call", {
            "name": "auth_status",
            "arguments": {"random_string": "test"}
        }, 3)
        
        print(f"Auth status response: {json.dumps(response, indent=2)}")
        
        if "error" in response:
            print(f"❌ Auth status failed: {response['error']}")
            return False
            
        if "result" in response:
            auth_result = response["result"]
            print(f"✅ Auth status successful:")
            print(f"  Status: {auth_result.get('status', 'unknown')}")
            print(f"  Method: {auth_result.get('auth_method', 'unknown')}")
            print(f"  Catalog: {auth_result.get('catalog_name', 'unknown')}")
            return True
            
        print("❌ Unexpected auth status response")
        return False
    
    def run_full_test(self) -> bool:
        """Run the complete authentication test."""
        print("🧪 Starting MCP Authentication Test")
        print(f"Target URL: {self.base_url}")
        
        # Step 1: Initialize
        if not self.initialize():
            return False
            
        # Step 2: Wait a moment for initialization to complete
        print("\n⏳ Waiting for initialization to complete...")
        time.sleep(2)
        
        # Step 3: List tools
        if not self.list_tools():
            return False
            
        # Step 4: Test authentication
        if not self.test_auth_status():
            return False
            
        print("\n🎉 All tests passed!")
        return True

def main():
    """Main test function."""
    tester = MCPTester()
    
    try:
        success = tester.run_full_test()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n❌ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

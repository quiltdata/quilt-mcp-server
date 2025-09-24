#!/usr/bin/env python3
"""Simple SSE connection test using requests."""

import requests
import json
from datetime import datetime


def test_sse_connection():
    """Test SSE connection to MCP server."""
    base_url = "https://demo.quiltdata.com"
    
    print(f"Testing SSE Connection - {datetime.now()}")
    print("=" * 50)
    
    # Test 1: GET request to SSE endpoint
    print("Test 1: GET request to /sse/ endpoint")
    try:
        response = requests.get(
            f"{base_url}/sse/",
            headers={"Accept": "text/event-stream"},
            stream=True,
            timeout=5
        )
        print(f"Status: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        
        # Read first few lines
        count = 0
        for line in response.iter_lines():
            if line and count < 3:
                print(f"SSE Data: {line.decode()}")
                count += 1
            elif count >= 3:
                break
                
    except Exception as e:
        print(f"Error: {e}")
    
    print("\n" + "=" * 50)
    
    # Test 2: POST request to SSE endpoint (should fail)
    print("Test 2: POST request to /sse/ endpoint (should fail)")
    try:
        response = requests.post(
            f"{base_url}/sse/",
            headers={"Accept": "text/event-stream"},
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
            timeout=5
        )
        print(f"Status: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        print(f"Response: {response.text}")
                        
    except Exception as e:
        print(f"Error: {e}")
    
    print("\n" + "=" * 50)
    
    # Test 3: GET request to health endpoint
    print("Test 3: GET request to /mcp/healthz endpoint")
    try:
        response = requests.get(
            f"{base_url}/mcp/healthz",
            headers={"Accept": "text/event-stream"},
            timeout=5
        )
        print(f"Status: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        print(f"Response: {response.text}")
                        
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    test_sse_connection()

#!/usr/bin/env python3
"""Test MCP server endpoints to diagnose frontend integration issues."""

import requests
import json
import sys
import os

def test_endpoint(url, headers=None):
    """Test an MCP endpoint and show the response."""
    try:
        response = requests.get(url, headers=headers or {})
        print(f"\n{'='*80}")
        print(f"URL: {url}")
        print(f"Status: {response.status_code}")
        print(f"{'='*80}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(json.dumps(data, indent=2))
            except:
                print(response.text[:500])
        else:
            print(f"Error: {response.text[:500]}")
        return response
    except Exception as e:
        print(f"ERROR: {e}")
        return None

def main():
    # Get MCP server URL from environment or use default
    base_url = os.getenv("MCP_SERVER_URL", "https://demo.quiltdata.com/mcp")
    
    # Test 1: Health check
    print("\n" + "="*80)
    print("TEST 1: Health Check")
    print("="*80)
    test_endpoint(f"{base_url}/healthz")
    
    # Test 2: List available resources (requires auth)
    print("\n" + "="*80)
    print("TEST 2: List Available Resources")
    print("="*80)
    print("NOTE: This requires JWT authentication")
    
    # Get token from environment if available
    token = os.getenv("QUILT_ACCESS_TOKEN") or os.getenv("JWT_TOKEN")
    if token:
        headers = {"Authorization": f"Bearer {token}"}
        test_endpoint(f"{base_url}/tools/list_available_resources", headers)
    else:
        print("SKIP: No JWT token available (set QUILT_ACCESS_TOKEN or JWT_TOKEN)")
    
    # Test 3: Stack info
    print("\n" + "="*80)
    print("TEST 3: Stack Info")
    print("="*80)
    if token:
        test_endpoint(f"{base_url}/tools/stack_info", headers)
    else:
        print("SKIP: No JWT token available")

if __name__ == "__main__":
    main()

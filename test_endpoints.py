#!/usr/bin/env python3
"""
Script to test MCP server endpoints and diagnose issues.
"""

import requests
import json
import sys
from datetime import datetime


def test_endpoint(url, method="GET", data=None, headers=None, description=""):
    """Test an endpoint and return detailed results."""
    print(f"\n{'='*60}")
    print(f"Testing: {description}")
    print(f"URL: {url}")
    print(f"Method: {method}")
    
    try:
        if method == "GET":
            response = requests.get(url, headers=headers, timeout=10)
        elif method == "POST":
            response = requests.post(url, json=data, headers=headers, timeout=10)
        elif method == "OPTIONS":
            response = requests.options(url, headers=headers, timeout=10)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers:")
        for key, value in response.headers.items():
            print(f"  {key}: {value}")
        
        print(f"Response Body (first 500 chars):")
        body = response.text
        if len(body) > 500:
            print(body[:500] + "...")
        else:
            print(body)
            
        return {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "body": body,
            "success": response.status_code < 400
        }
        
    except requests.exceptions.RequestException as e:
        print(f"ERROR: {e}")
        return {
            "status_code": None,
            "headers": {},
            "body": str(e),
            "success": False,
            "error": str(e)
        }


def test_cors_preflight(url):
    """Test CORS preflight request."""
    headers = {
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type"
    }
    return test_endpoint(url, method="OPTIONS", headers=headers, description="CORS Preflight")


def test_mcp_initialize(url):
    """Test MCP initialize method."""
    data = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "endpoint-test",
                "version": "1.0"
            }
        }
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"
    }
    return test_endpoint(url, method="POST", data=data, headers=headers, description="MCP Initialize")


def main():
    """Main test function."""
    print(f"MCP Endpoint Test Script - {datetime.now()}")
    
    base_url = "https://demo.quiltdata.com"
    
    # Test endpoints
    tests = [
        {
            "url": f"{base_url}/mcp/",
            "method": "POST",
            "data": {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"}
                }
            },
            "headers": {
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream"
            },
            "description": "MCP Endpoint - Initialize"
        },
        {
            "url": f"{base_url}/sse/",
            "method": "GET",
            "headers": {"Accept": "text/event-stream"},
            "description": "SSE Endpoint - GET"
        },
        {
            "url": f"{base_url}/sse/",
            "method": "POST",
            "data": {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"}
                }
            },
            "headers": {"Content-Type": "application/json"},
            "description": "SSE Endpoint - POST"
        },
        {
            "url": f"{base_url}/mcp/",
            "method": "OPTIONS",
            "headers": {
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type"
            },
            "description": "MCP CORS Preflight"
        },
        {
            "url": f"{base_url}/sse/",
            "method": "OPTIONS",
            "headers": {
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "accept"
            },
            "description": "SSE CORS Preflight"
        }
    ]
    
    results = []
    
    for test in tests:
        result = test_endpoint(
            test["url"],
            method=test["method"],
            data=test.get("data"),
            headers=test.get("headers"),
            description=test["description"]
        )
        results.append({
            "test": test["description"],
            "result": result
        })
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    
    for result in results:
        status = "✅ PASS" if result["result"]["success"] else "❌ FAIL"
        status_code = result["result"]["status_code"] or "ERROR"
        print(f"{status} {result['test']} - Status: {status_code}")
    
    # Check for specific issues
    print(f"\n{'='*60}")
    print("DIAGNOSTIC ANALYSIS")
    print(f"{'='*60}")
    
    mcp_result = next((r for r in results if "MCP Endpoint" in r["test"]), None)
    sse_result = next((r for r in results if "SSE Endpoint - GET" in r["test"]), None)
    
    if mcp_result and not mcp_result["result"]["success"]:
        if mcp_result["result"]["status_code"] == 502:
            print("❌ MCP endpoint returning 502 Bad Gateway - Target group is unhealthy")
        elif mcp_result["result"]["status_code"] == 404:
            print("❌ MCP endpoint returning 404 - ALB routing issue")
        elif mcp_result["result"]["status_code"] == 405:
            print("❌ MCP endpoint returning 405 - Method not allowed")
    
    if sse_result and not sse_result["result"]["success"]:
        if sse_result["result"]["status_code"] == 502:
            print("❌ SSE endpoint returning 502 Bad Gateway - Target group is unhealthy")
        elif sse_result["result"]["status_code"] == 404:
            print("❌ SSE endpoint returning 404 - ALB routing issue")
        elif sse_result["result"]["status_code"] == 405:
            print("❌ SSE endpoint returning 405 - Method not allowed")
    
    # Check CORS headers
    cors_result = next((r for r in results if "CORS Preflight" in r["test"]), None)
    if cors_result and cors_result["result"]["success"]:
        headers = cors_result["result"]["headers"]
        if "access-control-expose-headers" in headers:
            if "mcp-session-id" in headers["access-control-expose-headers"]:
                print("✅ CORS headers properly configured with mcp-session-id")
            else:
                print("⚠️  CORS headers missing mcp-session-id")
        else:
            print("⚠️  CORS expose headers not present")


if __name__ == "__main__":
    main()


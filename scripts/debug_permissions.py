#!/usr/bin/env python3
"""
Debug script to test permissions tool token flow.

This script helps diagnose the 401 UNAUTHORIZED issue by testing
each step of the token flow manually.
"""

import os
import sys
import json
import requests
from typing import Optional

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from quilt_mcp.tools.permissions import permissions
from quilt_mcp.runtime import request_context
from quilt_mcp.clients.catalog import execute_catalog_query, _graphql_url


def test_token_with_curl(token: str) -> bool:
    """Test token directly with curl/requests."""
    print(f"\n🔍 Testing token with direct HTTP request...")
    print(f"Token: {token[:20]}...")
    
    url = "https://demo-registry.quiltdata.com/graphql"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "Debug-Script/1.0"
    }
    payload = {
        "query": "query { me { email isAdmin } }"
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:200]}...")
        
        if response.status_code == 200:
            data = response.json()
            if "errors" in data:
                print(f"❌ GraphQL errors: {data['errors']}")
                return False
            else:
                print(f"✅ Token works! User: {data.get('data', {}).get('me', {}).get('email')}")
                return True
        else:
            print(f"❌ HTTP error: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return False


def test_catalog_client(token: str) -> bool:
    """Test the catalog client directly."""
    print(f"\n🔍 Testing catalog client...")
    print(f"Token: {token[:20]}...")
    
    try:
        result = execute_catalog_query(
            graphql_url="https://demo-registry.quiltdata.com/graphql",
            query="query { me { email isAdmin } }",
            auth_token=token
        )
        
        if result.get("me"):
            print(f"✅ Catalog client works! User: {result['me'].get('email')}")
            return True
        else:
            print(f"❌ No user data returned: {result}")
            return False
            
    except Exception as e:
        print(f"❌ Catalog client failed: {e}")
        return False


def test_permissions_tool(token: str) -> bool:
    """Test the full permissions tool."""
    print(f"\n🔍 Testing permissions tool...")
    print(f"Token: {token[:20]}...")
    
    try:
        with request_context(token, {"source": "debug_script"}):
            result = permissions(action="discover")
        
        if result.get("success"):
            print(f"✅ Permissions tool works!")
            print(f"User: {result.get('user_identity', {}).get('email')}")
            print(f"Buckets: {result.get('total_buckets_checked')}")
            return True
        else:
            print(f"❌ Permissions tool failed: {result.get('error')}")
            return False
            
    except Exception as e:
        print(f"❌ Permissions tool exception: {e}")
        return False


def main():
    """Main debugging function."""
    print("🔧 Permissions Tool Debug Script")
    print("=" * 50)
    
    # Get token from environment
    token = os.getenv("QUILT_TEST_TOKEN")
    if not token:
        print("❌ QUILT_TEST_TOKEN environment variable not set")
        print("Set it with: export QUILT_TEST_TOKEN='your-jwt-token'")
        return 1
    
    # Set catalog URL
    os.environ["QUILT_CATALOG_URL"] = "https://demo.quiltdata.com"
    
    print(f"Token: {token[:20]}...")
    print(f"Catalog URL: {os.getenv('QUILT_CATALOG_URL')}")
    
    # Test each step
    steps = [
        ("Direct HTTP", lambda: test_token_with_curl(token)),
        ("Catalog Client", lambda: test_catalog_client(token)),
        ("Permissions Tool", lambda: test_permissions_tool(token)),
    ]
    
    results = []
    for name, test_func in steps:
        print(f"\n{'='*20} {name} {'='*20}")
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"❌ {name} failed with exception: {e}")
            results.append((name, False))
    
    # Summary
    print(f"\n{'='*50}")
    print("📊 SUMMARY")
    print(f"{'='*50}")
    
    all_passed = True
    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{name:20} {status}")
        if not success:
            all_passed = False
    
    if all_passed:
        print(f"\n🎉 All tests passed! The token should work in production.")
        return 0
    else:
        print(f"\n⚠️  Some tests failed. Check the output above for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

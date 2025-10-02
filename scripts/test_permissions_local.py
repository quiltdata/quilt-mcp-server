#!/usr/bin/env python3
"""
Local test script for the permissions toolset.

This script comprehensively tests all permissions actions:
- discover: Get user identity and accessible buckets
- access_check: Check access to specific buckets
- recommendations_get: Get permission recommendations

Run with:
    PYTHONPATH=src QUILT_CATALOG_URL=https://demo.quiltdata.com python scripts/test_permissions_local.py
"""

import json
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from quilt_mcp.tools.permissions import permissions
from quilt_mcp.runtime import request_context


def test_discovery_mode():
    """Test discovery mode (action=None) returns module info."""
    print("\n" + "=" * 80)
    print("TEST 1: Discovery Mode (action=None)")
    print("=" * 80)
    
    result = permissions()
    
    assert result.get("module") == "permissions", "Module name incorrect"
    assert "discover" in result.get("actions", []), "Missing 'discover' action"
    assert "access_check" in result.get("actions", []), "Missing 'access_check' action"
    assert "recommendations_get" in result.get("actions", []), "Missing 'recommendations_get' action"
    
    print("✅ Discovery mode works - 3 actions available")
    return True


def test_permissions_discovery(token):
    """Test full permissions discovery."""
    print("\n" + "=" * 80)
    print("TEST 2: Permissions Discovery (action='discover')")
    print("=" * 80)
    
    with request_context(token, {"source": "test"}):
        result = permissions(action="discover")
        
        assert result.get("success"), f"Discovery failed: {result.get('error')}"
        assert result.get("user_identity"), "No user identity returned"
        assert result.get("user_identity", {}).get("email"), "No email in user identity"
        assert "bucket_permissions" in result, "No bucket_permissions in result"
        assert "categorized_buckets" in result, "No categorized_buckets in result"
        
        user = result["user_identity"]
        buckets = result["bucket_permissions"]
        
        print(f"✅ User: {user.get('email')}")
        print(f"✅ Admin: {user.get('is_admin')}")
        print(f"✅ Roles: {', '.join(user.get('roles', []))}")
        print(f"✅ Total buckets: {len(buckets)}")
        print(f"✅ Accessible: {len(result['categorized_buckets'].get('accessible', []))}")
        
        return True


def test_filtered_discovery(token):
    """Test discovery with specific bucket filters."""
    print("\n" + "=" * 80)
    print("TEST 3: Filtered Discovery (check_buckets parameter)")
    print("=" * 80)
    
    with request_context(token, {"source": "test"}):
        test_buckets = ["quilt-example-bucket", "nonexistent-test-bucket"]
        result = permissions(
            action="discover",
            params={"check_buckets": test_buckets}
        )
        
        assert result.get("success"), f"Filtered discovery failed: {result.get('error')}"
        assert result.get("total_buckets_checked") == 2, "Should check exactly 2 buckets"
        
        buckets = {b["name"]: b for b in result["bucket_permissions"]}
        assert "quilt-example-bucket" in buckets, "Real bucket not found"
        assert "nonexistent-test-bucket" in buckets, "Nonexistent bucket not included"
        
        assert buckets["quilt-example-bucket"].get("accessible"), "Real bucket should be accessible"
        assert not buckets["nonexistent-test-bucket"].get("accessible"), "Nonexistent bucket should not be accessible"
        
        print(f"✅ Checked {len(test_buckets)} buckets")
        print(f"✅ quilt-example-bucket: accessible={buckets['quilt-example-bucket']['accessible']}")
        print(f"✅ nonexistent-test-bucket: accessible={buckets['nonexistent-test-bucket']['accessible']}")
        
        return True


def test_bucket_access_check(token):
    """Test individual bucket access checks."""
    print("\n" + "=" * 80)
    print("TEST 4: Bucket Access Check (action='access_check')")
    print("=" * 80)
    
    test_cases = [
        ("quilt-sandbox-bucket", True),
        ("nonexistent-bucket-xyz", False),
        ("quilt-example-bucket", True),
    ]
    
    with request_context(token, {"source": "test"}):
        for bucket_name, should_be_accessible in test_cases:
            result = permissions(
                action="access_check",
                params={"bucket_name": bucket_name}
            )
            
            assert result.get("success"), f"Access check failed for {bucket_name}"
            assert result.get("bucket_name") == bucket_name, "Bucket name mismatch"
            assert result.get("accessible") == should_be_accessible, \
                f"{bucket_name} accessibility mismatch: expected {should_be_accessible}, got {result.get('accessible')}"
            
            access = "✅" if result["accessible"] else "❌"
            print(f"{access} {bucket_name}: {result.get('permission_level')}")
    
    return True


def test_recommendations(token):
    """Test permission recommendations."""
    print("\n" + "=" * 80)
    print("TEST 5: Permission Recommendations (action='recommendations_get')")
    print("=" * 80)
    
    with request_context(token, {"source": "test"}):
        result = permissions(action="recommendations_get")
        
        assert result.get("success"), f"Recommendations failed: {result.get('error')}"
        assert "recommendations" in result, "No recommendations in result"
        
        recs = result["recommendations"]
        print(f"✅ Generated {len(recs)} recommendations")
        
        for rec in recs:
            print(f"  [{rec['priority'].upper()}] {rec['message']}")
        
        return True


def test_error_handling():
    """Test error handling for missing token."""
    print("\n" + "=" * 80)
    print("TEST 6: Error Handling (no token)")
    print("=" * 80)
    
    with request_context(None, {"source": "test"}):
        result = permissions(action="discover")
        
        assert not result.get("success"), "Should fail without token"
        assert "token required" in result.get("error", "").lower(), "Wrong error message"
        
        print(f"✅ Proper error for missing token: {result['error']}")
    
    return True


def test_invalid_action():
    """Test error handling for invalid action."""
    print("\n" + "=" * 80)
    print("TEST 7: Error Handling (invalid action)")
    print("=" * 80)
    
    token = os.getenv("TEST_TOKEN", "fake.token")
    with request_context(token, {"source": "test"}):
        result = permissions(action="invalid_action")
        
        assert not result.get("success"), "Should fail with invalid action"
        assert "unknown" in result.get("error", "").lower(), "Wrong error message"
        
        print(f"✅ Proper error for invalid action: {result['error']}")
    
    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("PERMISSIONS TOOLSET COMPREHENSIVE TEST SUITE")
    print("=" * 80)
    
    # Get token from environment
    token = os.getenv("TEST_TOKEN")
    if not token:
        print("\n❌ ERROR: TEST_TOKEN environment variable not set")
        print("Set it with: export TEST_TOKEN='your-jwt-token'")
        return 1
    
    catalog_url = os.getenv("QUILT_CATALOG_URL")
    if not catalog_url:
        print("\n❌ ERROR: QUILT_CATALOG_URL environment variable not set")
        print("Set it with: export QUILT_CATALOG_URL='https://demo.quiltdata.com'")
        return 1
    
    print(f"\nCatalog URL: {catalog_url}")
    print(f"Token: {token[:20]}...")
    
    tests = [
        ("Discovery Mode", test_discovery_mode, False),  # No token needed
        ("Permissions Discovery", test_permissions_discovery, True),
        ("Filtered Discovery", test_filtered_discovery, True),
        ("Bucket Access Check", test_bucket_access_check, True),
        ("Recommendations", test_recommendations, True),
        ("Error Handling", test_error_handling, False),  # No token needed
        ("Invalid Action", test_invalid_action, False),  # Uses fake token
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func, needs_token in tests:
        try:
            if needs_token:
                success = test_func(token)
            else:
                success = test_func()
            
            if success:
                passed += 1
        except AssertionError as e:
            print(f"\n❌ TEST FAILED: {test_name}")
            print(f"   Error: {e}")
            failed += 1
        except Exception as e:
            print(f"\n❌ TEST ERROR: {test_name}")
            print(f"   Exception: {e}")
            failed += 1
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"✅ Passed: {passed}/{len(tests)}")
    if failed > 0:
        print(f"❌ Failed: {failed}/{len(tests)}")
        return 1
    else:
        print("\n🎉 ALL TESTS PASSED!")
        return 0


if __name__ == "__main__":
    sys.exit(main())


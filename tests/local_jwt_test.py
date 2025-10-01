"""Local end-to-end JWT authentication test.

This test validates the complete JWT authentication flow locally
before deploying to production.
"""

import os
import sys
import jwt as pyjwt
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from quilt_mcp.services.bearer_auth_service import BearerAuthService, JwtAuthError
from quilt_mcp.services.jwt_decoder import safe_decompress_jwt
from quilt_mcp.services.session_auth import SessionAuthManager


def create_test_jwt(secret: str, buckets: list[str], permissions: list[str]) -> str:
    """Create a test JWT token."""
    payload = {
        "iss": "quilt-frontend",
        "aud": "quilt-mcp-server",
        "sub": "test-user-123",
        "iat": int(datetime.now().timestamp()),
        "exp": int((datetime.now() + timedelta(hours=24)).timestamp()),
        "jti": "test-token-id",
        "s": "w",
        "p": permissions,
        "r": ["ReadWriteQuiltV2-sales-prod"],
        "b": buckets,
        "buckets": buckets,
        "permissions": permissions,
        "roles": ["ReadWriteQuiltV2-sales-prod"],
        "scope": "w",
        "level": "write",
        "l": "write",
        "username": "testuser",
    }

    token = pyjwt.encode(payload, secret, algorithm="HS256", headers={"kid": "frontend-enhanced"})
    return token


def test_jwt_validation():
    """Test JWT validation with known secret."""
    print("\n" + "=" * 80)
    print("TEST 1: JWT Validation")
    print("=" * 80)

    secret = "quilt-sales-prod-mcp-jwt-secret-2025-enhanced-tokens-v2"
    buckets = ["quilt-sandbox-bucket", "cellpainting-gallery"]
    permissions = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]

    # Create test token
    token = create_test_jwt(secret, buckets, permissions)
    print(f"Created test token: {len(token)} chars")

    # Set environment variable
    os.environ["MCP_ENHANCED_JWT_SECRET"] = secret

    # Validate with BearerAuthService
    service = BearerAuthService()

    try:
        result = service.authenticate_header(f"Bearer {token}")
        print("✅ JWT validated successfully!")
        print(f"   User: {result.username}")
        print(f"   Buckets: {len(result.buckets)}")
        print(f"   Permissions: {len(result.permissions)}")
        print(f"   Roles: {result.roles}")
        return True
    except JwtAuthError as e:
        print(f"❌ JWT validation failed: {e.code} - {e.detail}")
        return False


def test_token_decompression():
    """Test JWT token decompression."""
    print("\n" + "=" * 80)
    print("TEST 2: JWT Decompression")
    print("=" * 80)

    # Create payload with compressed buckets
    payload = {
        "s": "w",
        "p": ["g", "p", "l"],  # Abbreviated permissions
        "r": ["TestRole"],
        "b": {  # Compressed buckets
            "_type": "groups",
            "_data": {"quilt": ["sandbox-bucket", "demos"], "cell": ["cellpainting-gallery"]},
        },
        "l": "write",
    }

    result = safe_decompress_jwt(payload)

    print(f"Decompressed permissions: {result['permissions']}")
    print(f"Decompressed buckets: {result['buckets']}")
    print(f"Scope: {result['scope']}")
    print(f"Level: {result['level']}")

    # Verify decompression
    assert "s3:GetObject" in result['permissions'], "Permission 'g' should decompress to s3:GetObject"
    assert "quilt-sandbox-bucket" in result['buckets'], "Bucket should be decompressed"

    print("✅ Decompression successful!")
    return True


def test_session_caching():
    """Test session-based authentication caching."""
    print("\n" + "=" * 80)
    print("TEST 3: Session Caching")
    print("=" * 80)

    secret = "quilt-sales-prod-mcp-jwt-secret-2025-enhanced-tokens-v2"
    os.environ["MCP_ENHANCED_JWT_SECRET"] = secret

    buckets = ["quilt-sandbox-bucket"]
    permissions = ["s3:GetObject", "s3:ListBucket"]
    token = create_test_jwt(secret, buckets, permissions)

    manager = SessionAuthManager()

    # First authentication (should cache)
    session_auth, error = manager.authenticate_session("test-session", f"Bearer {token}")

    if error:
        print(f"❌ Session authentication failed: {error}")
        return False

    print("✅ Session authenticated and cached")
    print(f"   Session ID: {session_auth.session_id}")
    print(f"   User: {session_auth.jwt_result.username}")

    # Second request (should use cache)
    cached_session = manager.get_session("test-session")

    if not cached_session:
        print("❌ Session not found in cache!")
        return False

    print("✅ Session retrieved from cache")

    # Verify stats
    stats = manager.get_stats()
    print(f"   Total sessions: {stats['total_sessions']}")

    assert stats['total_sessions'] == 1, "Should have 1 cached session"

    print("✅ Session caching successful!")
    return True


def test_frontend_token_with_backend_secret():
    """Test the actual frontend token with backend secret."""
    print("\n" + "=" * 80)
    print("TEST 4: Frontend Token Validation")
    print("=" * 80)

    # This is the actual token from frontend
    frontend_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6ImZyb250ZW5kLWVuaGFuY2VkIn0.eyJpZCI6Ijg3OTVmMGNjLThkZWItNDBkZC05MTMyLTEzMzU3Yzk4Mzk4NCIsInV1aWQiOiIwYjdiYjYxZi1jYTg3LTQ1YmEtYTllYS0wNjkzMzg2NDFiODIiLCJleHAiOjE3NjU5ODcwNzYsImlzcyI6InF1aWx0LWZyb250ZW5kIiwiYXVkIjoicXVpbHQtbWNwLXNlcnZlciIsInN1YiI6Ijg3OTVmMGNjLThkZWItNDBkZC05MTMyLTEzMzU3Yzk4Mzk4NCIsImlhdCI6MTc1OTIzNTMzNCwianRpIjoibWc2amFueXlzb3ZwIiwicyI6InciLCJwIjpbImF0aGVuYTpCYXRjaEdldFF1ZXJ5RXhlY3V0aW9uIiwiYXRoZW5hOkdldFF1ZXJ5RXhlY3V0aW9uIiwiYXRoZW5hOkdldFF1ZXJ5UmVzdWx0cyIsImF0aGVuYTpMaXN0UXVlcnlFeGVjdXRpb25zIiwiYXRoZW5hOkxpc3RXb3JrR3JvdXBzIiwiYXRoZW5hOlN0YXJ0UXVlcnlFeGVjdXRpb24iLCJhdGhlbmE6U3RvcFF1ZXJ5RXhlY3V0aW9uIiwiZ2x1ZTpHZXREYXRhYmFzZSIsImdsdWU6R2V0RGF0YWJhc2VzIiwiZ2x1ZTpHZXRUYWJsZSIsImdsdWU6R2V0VGFibGVzIiwiaWFtOkdldFBvbGljeSIsImlhbTpHZXRQb2xpY3lWZXJzaW9uIiwiaWFtOkxpc3RBdHRhY2hlZFVzZXJQb2xpY2llcyIsImlhbTpMaXN0VXNlclBvbGljaWVzIiwiYW11IiwiZCIsInMzOkdldEJ1Y2tldExvY2F0aW9uIiwiZyIsImd2IiwibGEiLCJsIiwicCIsInBhIl0sInIiOlsiUmVhZFdyaXRlUXVpbHRWMi1zYWxlcy1wcm9kIl0sImIiOnsiX3R5cGUiOiJncm91cHMiLCJfZGF0YSI6eyJjZWxscGFpbnRpbmciOlsiZ2FsbGVyeSJdLCJjZWxseGdlbmUiOlsiOTEzNTI0OTQ2MjI2LXVzLWVhc3QtMSIsImNlbnN1cy1wdWJsaWMtdXMtd2VzdC0yIl0sImRhdGEiOlsiZHJvcC1vZmYtYnVja2V0Il0sImV4YW1wbGUiOlsicGhhcm1hLWRhdGEiXSwiZmwiOlsiMTU4LXJhdyIsIjE1OS1yYXciLCIxNjAtcmF3IiwiZGF0YS1jb21tb25zIl0sImdhbnltZWRlIjpbInNhbmRib3gtYnVja2V0Il0sImdkYyI6WyJjY2xlLTItb3BlbiJdLCJuZiI6WyJjb3JlLWdhbGxlcnkiXSwib21pY3MiOlsicXVpbHQtb21pY3NxdWlsdGNrYWlucHV0ODUwNzg3NzE3MTk3dXNlYXN0MTMtNThlcGpseXQ1bWNwIiwicXVpbHQtb21pY3NxdWlsdGNrYW91dHB1dDg1MDc4NzcxNzE5N3VzZWFzdDEtZ3B1eDJqdWp1Y204Il0sInBtYyI6WyJvYS1vcGVuZGF0YSJdLCJxdWlsdCI6WyJiYWtlIiwiYmVuY2hsaW5nIiwiY2NsZS1waXBlbGluZS1ydW5zIiwiY3JvIiwiZGVtb3MiLCJleGFtcGxlLWJ1Y2tldCIsIm9wZW4tY2NsZS12aXJnaW5pYSIsInNhbGVzLXJhdyIsInNhbGVzLXN0YWdpbmciLCJzYW5kYm94LWJ1Y2tldCIsInpzLXNhbmRib3giXSwic2FsZXMiOlsicHJvZC1jYW5hcnlidWNrZXRhbGxvd2VkLWVpaG8zbnM5d2hjbSIsInByb2QtY2FuYXJ5YnVja2V0cmVzdHJpY3RlZC1kZWt3YnZ0eWE0NWYiLCJwcm9kLXN0YXR1c3JlcG9ydHNidWNrZXQtdGZienVtNzBkZnU3Il0sInNyYSI6WyJwdWItcnVuLW9kcCJdLCJ1ZHAiOlsic3BlYyJdLCJ6cyI6WyJkaXNjb3Zlcnktb21pY3MiXX19LCJidWNrZXRzIjpbImNlbGxwYWludGluZy1nYWxsZXJ5IiwiY2VsbHhnZW5lLTkxMzUyNDk0NjIyNi11cy1lYXN0LTEiLCJjZWxseGdlbmUtY2Vuc3VzLXB1YmxpYy11cy13ZXN0LTIiLCJkYXRhLWRyb3Atb2ZmLWJ1Y2tldCIsImV4YW1wbGUtcGhhcm1hLWRhdGEiLCJmbC0xNTgtcmF3IiwiZmwtMTU5LXJhdyIsImZsLTE2MC1yYXciLCJmbC1kYXRhLWNvbW1vbnMiLCJnYW55bWVkZS1zYW5kYm94LWJ1Y2tldCIsImdkYy1jY2xlLTItb3BlbiIsIm5mLWNvcmUtZ2FsbGVyeSIsIm9taWNzLXF1aWx0LW9taWNzcXVpbHRja2FpbnB1dDg1MDc4NzcxNzE5N3VzZWFzdDEzLTU4ZXBqbHl0NW1jcCIsIm9taWNzLXF1aWx0LW9taWNzcXVpbHRja2FvdXRwdXQ4NTA3ODc3MTcxOTd1c2Vhc3QxLWdwdXgyanRqdWNtOCIsInBtYy1vYS1vcGVuZGF0YSIsInF1aWx0LWJha2UiLCJxdWlsdC1iZW5jaGxpbmciLCJxdWlsdC1jY2xlLXBpcGVsaW5lLXJ1bnMiLCJxdWlsdC1jcm8iLCJxdWlsdC1kZW1vcyIsInF1aWx0LWV4YW1wbGUtYnVja2V0IiwicXVpbHQtb3Blbi1jY2xlLXZpcmdpbmlhIiwicXVpbHQtc2FsZXMtcmF3IiwicXVpbHQtc2FsZXMtc3RhZ2luZyIsInF1aWx0LXNhbmRib3gtYnVja2V0IiwicXVpbHQtenMtc2FuZGJveCIsInNhbGVzLXByb2QtY2FuYXJ5YnVja2V0YWxsb3dlZC1laWhvM25zOXdoY20iLCJzYWxlcy1wcm9kLWNhbmFyeWJ1Y2tldHJlc3RyaWN0ZWQtZGVrd2J2dHlhNDVmIiwic2FsZXMtcHJvZC1zdGF0dXNyZXBvcnRzYnVja2V0LXRmYnp1bTcwZGZ1NyIsInNyYS1wdWItcnVuLW9kcCIsInVkcC1zcGVjIiwienMtZGlzY292ZXJ5LW9taWNzIl0sInBlcm1pc3Npb25zIjpbImF0aGVuYTpCYXRjaEdldFF1ZXJ5RXhlY3V0aW9uIiwiYXRoZW5hOkdldFF1ZXJ5RXhlY3V0aW9uIiwiYXRoZW5hOkdldFF1ZXJ5UmVzdWx0cyIsImF0aGVuYTpMaXN0UXVlcnlFeGVjdXRpb25zIiwiYXRoZW5hOkxpc3RXb3JrR3JvdXBzIiwiYXRoZW5hOlN0YXJ0UXVlcnlFeGVjdXRpb24iLCJhdGhlbmE6U3RvcFF1ZXJ5RXhlY3V0aW9uIiwiZ2x1ZTpHZXREYXRhYmFzZSIsImdsdWU6R2V0RGF0YWJhc2VzIiwiZ2x1ZTpHZXRUYWJsZSIsImdsdWU6R2V0VGFibGVzIiwiaWFtOkdldFBvbGljeSIsImlhbTpHZXRQb2xpY3lWZXJzaW9uIiwiaWFtOkxpc3RBdHRhY2hlZFVzZXJQb2xpY2llcyIsImlhbTpMaXN0VXNlclBvbGljaWVzIiwiczM6QWJvcnRNdWx0aXBhcnRVcGxvYWQiLCJzMzpEZWxldGVPYmplY3QiLCJzMzpHZXRCdWNrZXRMb2NhdGlvbiIsInMzOkdldE9iamVjdCIsInMzOkdldE9iamVjdFZlcnNpb24iLCJzMzpMaXN0QWxsTXlCdWNrZXRzIiwiczM6TGlzdEJ1Y2tldCIsInMzOlB1dE9iamVjdCIsInMzOlB1dE9iamVjdEFjbCJdLCJyb2xlcyI6WyJSZWFkV3JpdGVRdWlsdFYyLXNhbGVzLXByb2QiXSwic2NvcGUiOiJ3IiwibGV2ZWwiOiJ3cml0ZSIsImwiOiJ3cml0ZSJ9.mppD7BR6jX7xIXaLR3oh_WR_2l6A_sC5abbzuSQo_Ac"

    # Try with the secret we think is correct
    secret = "quilt-sales-prod-mcp-jwt-secret-2025-enhanced-tokens-v2"

    print("Testing frontend token with backend secret...")
    print(f"Token length: {len(frontend_token)}")
    print(f"Secret length: {len(secret)}")

    try:
        payload = pyjwt.decode(frontend_token, secret, algorithms=["HS256"], options={"verify_aud": False})
        print("✅ Frontend token validates with backend secret!")
        print(f"   User: {payload.get('sub')}")
        print(f"   Buckets: {len(payload.get('buckets', []))}")
        return True
    except pyjwt.InvalidSignatureError:
        print("❌ Signature verification FAILED")
        print("   This means frontend is using a DIFFERENT secret!")

        # Try to brute force find the right secret
        print("\n🔍 Trying possible secret variations...")

        variations = [
            secret,
            secret.strip(),
            secret + "\n",
            secret + "\r\n",
            "development-enhanced-jwt-secret",
            # Add more variations
        ]

        for var_secret in variations:
            try:
                pyjwt.decode(frontend_token, var_secret, algorithms=["HS256"], options={"verify_aud": False})
                print(f"\n✅ FOUND IT! Secret is: {repr(var_secret)}")
                print(f"   Length: {len(var_secret)}")
                return True
            except pyjwt.PyJWTError:
                continue

        print("\n🚨 None of the variations worked!")
        print("   Frontend must be using a completely different secret")
        return False


def main():
    """Run all local JWT tests."""
    print("\n" + "=" * 80)
    print("LOCAL JWT AUTHENTICATION TEST SUITE")
    print("=" * 80)

    results = []

    # Run tests
    results.append(("JWT Validation", test_jwt_validation()))
    results.append(("Token Decompression", test_token_decompression()))
    results.append(("Session Caching", test_session_caching()))
    results.append(("Frontend Token", test_frontend_token_with_backend_secret()))

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {name}")

    all_passed = all(result[1] for result in results)

    if all_passed:
        print("\n🎉 ALL TESTS PASSED - Ready to deploy!")
        return 0
    else:
        print("\n🚨 SOME TESTS FAILED - Do NOT deploy yet!")
        failed = [name for name, passed in results if not passed]
        print(f"Failed tests: {', '.join(failed)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

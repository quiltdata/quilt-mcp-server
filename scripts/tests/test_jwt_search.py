#!/usr/bin/env python3
"""
Simple integration test for JWT authentication scaffolding.
Generates a Platform-style JWT and validates decoding/auth flow.
"""

import sys
from pathlib import Path

# Add src and tests to path
repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(repo_root / "src"))
sys.path.insert(0, str(repo_root / "tests"))

from jwt_helpers import generate_test_jwt
from quilt_mcp.services.jwt_auth_service import JWTAuthService
from quilt_mcp.runtime_context import set_runtime_auth, RuntimeAuthState


def main():
    print("=" * 80)
    print("JWT Authentication Smoke Test")
    print("=" * 80)

    jwt_token = generate_test_jwt(
        secret="test-secret-key-for-stateless-testing-only",
        expiry_seconds=3600,
        user_id="user-123",
        user_uuid="uuid-123",
    )

    print(f"  JWT created: {jwt_token[:50]}...")

    from jwt import decode

    decoded = decode(
        jwt_token,
        "test-secret-key-for-stateless-testing-only",
        algorithms=["HS256"],
        options={"verify_aud": False},
    )
    print(f"  id: {decoded.get('id')}")
    print(f"  uuid: {decoded.get('uuid')}")
    print(f"  exp: {decoded.get('exp')}")

    set_runtime_auth(
        RuntimeAuthState(
            scheme="bearer",
            access_token=jwt_token,
            claims=decoded,
        )
    )

    auth_service = JWTAuthService()
    print(f"  is_valid: {auth_service.is_valid()}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

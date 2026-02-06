#!/usr/bin/env python3
"""
Simple integration test for JWT authentication scaffolding.
Generates a Platform-style JWT and validates decoding/auth flow.
"""

import sys
from pathlib import Path

# Add src to path
repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(repo_root / "src"))

import jwt as pyjwt
import time
import uuid

from quilt_mcp.services.jwt_auth_service import JWTAuthService
from quilt_mcp.runtime_context import set_runtime_auth, RuntimeAuthState


def generate_test_jwt(secret: str = "test-secret", expires_in: int = 3600) -> tuple:
    """Generate a test JWT token and claims.

    Returns:
        Tuple of (token, claims)
    """
    claims = {
        "id": "test-user-jwt-search",
        "uuid": str(uuid.uuid4()),
        "exp": int(time.time()) + expires_in,
    }
    token = pyjwt.encode(claims, secret, algorithm="HS256")
    return token, claims


def main():
    print("=" * 80)
    print("JWT Authentication Smoke Test")
    print("=" * 80)

    jwt_token, decoded = generate_test_jwt()

    print(f"  JWT created: {jwt_token[:50]}...")
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

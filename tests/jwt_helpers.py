#!/usr/bin/env python3
"""
JWT token generation helper for testing MCP servers with JWT authentication.

This utility generates HS256 JWT tokens for testing purposes only.
Do not use in production - tokens should come from proper auth systems.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional

try:
    import jwt
except ImportError:
    print("❌ PyJWT library required. Install with: pip install PyJWT", file=sys.stderr)
    sys.exit(1)


def generate_test_jwt(
    secret: str,
    expiry_seconds: int = 3600,
    issuer: Optional[str] = None,
    audience: Optional[str] = None,
    user_id: Optional[str] = None,
    user_uuid: Optional[str] = None,
    tenant_id: Optional[str] = None,
) -> str:
    """Generate a test JWT token for MCP authentication.

    Args:
        secret: Secret key for HS256 signing
        expiry_seconds: Token expiry time in seconds (default: 1 hour)
        issuer: Token issuer claim (optional)
        audience: Token audience claim (optional)
        user_id: User ID claim (defaults to "test-user-id")
        user_uuid: User UUID claim (defaults to "test-user-uuid")
        tenant_id: Optional tenant identifier for multitenant deployments

    Returns:
        JWT token string
    """
    now = datetime.now(timezone.utc)
    payload: Dict[str, Any] = {
        "id": user_id or "test-user-id",
        "uuid": user_uuid or "test-user-uuid",
        "exp": int((now + timedelta(seconds=expiry_seconds)).timestamp()),
    }

    if issuer:
        payload["iss"] = issuer
    if audience:
        payload["aud"] = audience
    if tenant_id:
        payload["tenant_id"] = tenant_id

    token = jwt.encode(payload, secret, algorithm="HS256")
    return token


def decode_jwt_for_inspection(token: str, secret: str) -> Dict[str, Any]:
    """Decode JWT token for inspection (testing only)."""
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"], options={"verify_aud": False})
        return payload
    except jwt.InvalidTokenError as e:
        raise ValueError(f"Invalid JWT token: {e}")


def main():
    """Command-line interface for JWT token generation."""
    parser = argparse.ArgumentParser(
        description="Generate test JWT tokens for MCP authentication",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate token with default user claims
  python jwt_helpers.py generate --secret test-secret

  # Generate token with custom ID/UUID and expiry
  python jwt_helpers.py generate --secret test-secret --id user-123 --uuid 3caa49a9-3752-486e-b979-51a369d6df69 --expiry 7200

  # Inspect existing token
  python jwt_helpers.py inspect --token eyJhbGciOi... --secret test-secret
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    gen_parser = subparsers.add_parser("generate", help="Generate a new JWT token")
    gen_parser.add_argument("--secret", required=True, help="Secret key for HS256 signing")
    gen_parser.add_argument("--expiry", type=int, default=3600, help="Token expiry in seconds (default: 3600)")
    gen_parser.add_argument("--issuer", default=None, help="Token issuer (optional)")
    gen_parser.add_argument("--audience", default=None, help="Token audience (optional)")
    gen_parser.add_argument("--id", dest="user_id", default=None, help="User ID claim (id)")
    gen_parser.add_argument("--uuid", dest="user_uuid", default=None, help="User UUID claim (uuid)")
    gen_parser.add_argument("--tenant-id", help="Tenant identifier for multitenant deployments")

    inspect_parser = subparsers.add_parser("inspect", help="Inspect JWT token")
    inspect_parser.add_argument("--token", required=True, help="JWT token to inspect")
    inspect_parser.add_argument("--secret", required=True, help="Secret key for verification")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "generate":
            token = generate_test_jwt(
                secret=args.secret,
                expiry_seconds=args.expiry,
                issuer=args.issuer,
                audience=args.audience,
                user_id=args.user_id,
                user_uuid=args.user_uuid,
                tenant_id=args.tenant_id,
            )
            print(token)
        elif args.command == "inspect":
            payload = decode_jwt_for_inspection(args.token, args.secret)
            print("JWT Token Payload:")
            print(json.dumps(payload, indent=2))

            if "exp" in payload:
                exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
                now = datetime.now(timezone.utc)
                if exp_time > now:
                    remaining = exp_time - now
                    print(f"\nToken expires in: {remaining}")
                else:
                    print(f"\n⚠️  Token expired {now - exp_time} ago")
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

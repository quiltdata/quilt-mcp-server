#!/usr/bin/env python3
"""
JWT token generation helper for testing MCP servers with JWT authentication.

This utility generates HS256 JWT tokens for testing purposes only.
Do not use in production - tokens should come from proper auth systems.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Any, Optional

try:
    import jwt
except ImportError:
    print("❌ PyJWT library required. Install with: pip install PyJWT", file=sys.stderr)
    sys.exit(1)

try:
    import quilt3
except ImportError:
    print("❌ quilt3 library required. Install with: pip install quilt3", file=sys.stderr)
    sys.exit(1)


def extract_catalog_token_from_session() -> Optional[str]:
    """Extract catalog bearer token from active quilt3 session.

    Returns:
        Catalog bearer token string, or None if no session exists
    """
    try:
        # Use quilt3 API to load auth data
        import quilt3.session as session

        auth_data = session._load_auth()

        if not auth_data:
            return None

        # Get registry URL for current catalog
        registry_url = get_current_registry_url()
        if not registry_url:
            # Fall back to any available session
            registry_url = next(iter(auth_data.keys()), None)

        if not registry_url or registry_url not in auth_data:
            return None

        # Extract bearer token (prefer access_token - it's the JWT the catalog expects)
        session_data = auth_data[registry_url]
        return session_data.get("access_token") or session_data.get("refresh_token")

    except Exception:
        return None


def get_current_catalog_url() -> Optional[str]:
    """Get current catalog URL from quilt3 configuration.

    Returns:
        Catalog URL string, or None if not configured
    """
    try:
        # Try to get from quilt3 config
        config = quilt3.config()
        if config:
            # Try different possible keys
            return config.get('navigator_url') or config.get('catalog_url') or os.getenv("QUILT_CATALOG_URL")

        # Fallback to environment variable
        return os.getenv("QUILT_CATALOG_URL")

    except Exception:
        return os.getenv("QUILT_CATALOG_URL")


def get_current_registry_url() -> Optional[str]:
    """Get current registry URL from quilt3 configuration.

    Returns:
        Registry URL string, or None if not configured
    """
    try:
        # Try to get from quilt3 config
        config = quilt3.config()
        if config:
            # Try different possible keys
            registry = config.get('registryUrl') or config.get('registry_url')
            if registry:
                return registry

        # Derive from catalog URL
        catalog_url = get_current_catalog_url()
        if catalog_url:
            # Convert catalog URL to registry URL
            # e.g., https://nightly.quilttest.com -> https://nightly-registry.quilttest.com
            if "nightly.quilttest.com" in catalog_url:
                return catalog_url.replace("nightly.quilttest.com", "nightly-registry.quilttest.com")
            elif "quiltdata.com" in catalog_url:
                return catalog_url.replace("quiltdata.com", "registry.quiltdata.com")

        return None

    except Exception:
        return None


def get_quilt3_user_id() -> Optional[str]:
    """Get user ID from active quilt3 session.

    Returns:
        User ID string, or None if no session exists
    """
    try:
        # Use quilt3 API to load auth data
        import quilt3.session as session

        auth_data = session._load_auth()

        if not auth_data:
            return "quilt-user"

        # Get registry URL for current catalog
        registry_url = get_current_registry_url()
        if not registry_url:
            # Fall back to any available session
            registry_url = next(iter(auth_data.keys()), None)

        if not registry_url or registry_url not in auth_data:
            return "quilt-user"

        session_data = auth_data[registry_url]

        # Try to decode the access token to get user ID
        access_token = session_data.get("access_token")
        if access_token:
            try:
                # JWT tokens have 3 parts: header.payload.signature
                payload_part = access_token.split('.')[1]
                # Add padding if needed
                payload_part += '=' * (4 - len(payload_part) % 4)
                import base64

                payload = json.loads(base64.b64decode(payload_part))
                return payload.get("id") or payload.get("uuid") or "quilt-user"
            except Exception:
                pass

        return "quilt-user"

    except Exception:
        return "quilt-user"


def validate_quilt3_session_exists() -> bool:
    """Validate that an active quilt3 session exists.

    Returns:
        True if session exists and is valid, False otherwise
    """
    catalog_token = extract_catalog_token_from_session()
    catalog_url = get_current_catalog_url()

    if not catalog_token:
        print("❌ No quilt3 session found. Run 'quilt3 login' first.", file=sys.stderr)
        return False

    if not catalog_url:
        print(
            "❌ No catalog URL configured. Run 'quilt3.config(\"https://your-catalog-url\")' first.", file=sys.stderr
        )
        return False

    return True


def generate_test_jwt(
    role_arn: str,
    secret: str,
    expiry_seconds: int = 3600,
    issuer: str = "mcp-test",
    audience: str = "mcp-server",
    external_id: Optional[str] = None,
    session_tags: Optional[Dict[str, str]] = None,
    catalog_token: Optional[str] = None,
    catalog_url: Optional[str] = None,
    registry_url: Optional[str] = None,
    auto_extract: bool = False,
) -> str:
    """Generate a test JWT token for MCP authentication.

    Args:
        role_arn: AWS IAM role ARN to assume
        secret: Secret key for HS256 signing
        expiry_seconds: Token expiry time in seconds (default: 1 hour)
        issuer: Token issuer claim
        audience: Token audience claim
        external_id: Optional external ID for role assumption
        session_tags: Optional session tags for AWS role
        catalog_token: Optional catalog bearer token (if not provided, will auto-extract)
        catalog_url: Optional catalog URL (if not provided, will auto-extract)
        registry_url: Optional registry URL (if not provided, will auto-extract)
        auto_extract: If True, automatically extract catalog auth from quilt3 session

    Returns:
        JWT token string
    """
    now = datetime.now(timezone.utc)

    # Auto-extract catalog authentication if requested or if not provided
    if auto_extract or (not catalog_token and not catalog_url):
        if not catalog_token:
            catalog_token = extract_catalog_token_from_session()
        if not catalog_url:
            catalog_url = get_current_catalog_url()
        if not registry_url:
            registry_url = get_current_registry_url()

    # Standard JWT claims
    payload = {
        "iss": issuer,
        "aud": audience,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expiry_seconds)).timestamp()),
        "sub": get_quilt3_user_id() or "test-user",
    }

    # MCP-specific claims for AWS role assumption
    payload["role_arn"] = role_arn

    if external_id:
        payload["external_id"] = external_id

    if session_tags:
        payload["session_tags"] = session_tags

    # Add catalog authentication claims
    if catalog_token:
        payload["catalog_token"] = catalog_token
    if catalog_url:
        payload["catalog_url"] = catalog_url
    if registry_url:
        payload["registry_url"] = registry_url

    # Generate token
    token = jwt.encode(payload, secret, algorithm="HS256")

    return token


def decode_jwt_for_inspection(token: str, secret: str) -> Dict[str, Any]:
    """Decode JWT token for inspection (testing only).

    Args:
        token: JWT token string
        secret: Secret key for verification

    Returns:
        Decoded payload dictionary
    """
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
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
  # Generate token with auto-extracted catalog auth
  python jwt_helpers.py generate --role-arn arn:aws:iam::123456789:role/TestRole --secret test-secret --auto-extract

  # Generate token with custom expiry
  python jwt_helpers.py generate --role-arn arn:aws:iam::123456789:role/TestRole --secret test-secret --expiry 7200 --auto-extract

  # Inspect existing token
  python jwt_helpers.py inspect --token eyJhbGciOi... --secret test-secret
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Generate command
    gen_parser = subparsers.add_parser("generate", help="Generate a new JWT token")
    gen_parser.add_argument("--role-arn", required=True, help="AWS IAM role ARN to assume")
    gen_parser.add_argument("--secret", required=True, help="Secret key for HS256 signing")
    gen_parser.add_argument("--expiry", type=int, default=3600, help="Token expiry in seconds (default: 3600)")
    gen_parser.add_argument("--external-id", help="External ID for role assumption")
    gen_parser.add_argument("--session-tags", help="Session tags as JSON string")
    gen_parser.add_argument("--issuer", default="mcp-test", help="Token issuer (default: mcp-test)")
    gen_parser.add_argument("--audience", default="mcp-server", help="Token audience (default: mcp-server)")
    gen_parser.add_argument(
        "--auto-extract", action="store_true", help="Auto-extract catalog authentication from quilt3 session"
    )
    gen_parser.add_argument("--catalog-token", help="Catalog bearer token (overrides auto-extract)")
    gen_parser.add_argument("--catalog-url", help="Catalog URL (overrides auto-extract)")
    gen_parser.add_argument("--registry-url", help="Registry URL (overrides auto-extract)")

    # Inspect command
    inspect_parser = subparsers.add_parser("inspect", help="Inspect JWT token")
    inspect_parser.add_argument("--token", required=True, help="JWT token to inspect")
    inspect_parser.add_argument("--secret", required=True, help="Secret key for verification")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "generate":
            # Validate quilt3 session if auto-extract is requested
            if args.auto_extract and not validate_quilt3_session_exists():
                sys.exit(1)

            # Parse session tags if provided
            session_tags = None
            if args.session_tags:
                try:
                    session_tags = json.loads(args.session_tags)
                except json.JSONDecodeError:
                    print("❌ Invalid JSON for session tags", file=sys.stderr)
                    sys.exit(1)

            # Generate token
            token = generate_test_jwt(
                role_arn=args.role_arn,
                secret=args.secret,
                expiry_seconds=args.expiry,
                issuer=args.issuer,
                audience=args.audience,
                external_id=args.external_id,
                session_tags=session_tags,
                catalog_token=args.catalog_token,
                catalog_url=args.catalog_url,
                registry_url=args.registry_url,
                auto_extract=args.auto_extract,
            )

            print(token)

        elif args.command == "inspect":
            # Decode and display token
            payload = decode_jwt_for_inspection(args.token, args.secret)

            print("JWT Token Payload:")
            print(json.dumps(payload, indent=2))

            # Show expiry in human-readable format
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

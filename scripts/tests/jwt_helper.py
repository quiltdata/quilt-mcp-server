#!/usr/bin/env python3
"""
JWT token generation helper for testing MCP servers with JWT authentication.

This utility generates HS256 JWT tokens for testing purposes only.
Do not use in production - tokens should come from proper auth systems.
"""

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
    role_arn: str,
    secret: str,
    expiry_seconds: int = 3600,
    issuer: str = "mcp-test",
    audience: str = "mcp-server",
    external_id: Optional[str] = None,
    session_tags: Optional[Dict[str, str]] = None
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
        
    Returns:
        JWT token string
    """
    now = datetime.now(timezone.utc)
    
    # Standard JWT claims
    payload = {
        "iss": issuer,
        "aud": audience,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expiry_seconds)).timestamp()),
        "sub": "test-user"
    }
    
    # MCP-specific claims for AWS role assumption
    payload["role_arn"] = role_arn
    
    if external_id:
        payload["external_id"] = external_id
        
    if session_tags:
        payload["session_tags"] = session_tags
    
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
  # Generate token for testing
  python jwt_helper.py generate --role-arn arn:aws:iam::123456789:role/TestRole --secret test-secret

  # Generate token with custom expiry
  python jwt_helper.py generate --role-arn arn:aws:iam::123456789:role/TestRole --secret test-secret --expiry 7200

  # Inspect existing token
  python jwt_helper.py inspect --token eyJhbGciOi... --secret test-secret
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Generate command
    gen_parser = subparsers.add_parser("generate", help="Generate a new JWT token")
    gen_parser.add_argument("--role-arn", required=True, 
                           help="AWS IAM role ARN to assume")
    gen_parser.add_argument("--secret", required=True,
                           help="Secret key for HS256 signing")
    gen_parser.add_argument("--expiry", type=int, default=3600,
                           help="Token expiry in seconds (default: 3600)")
    gen_parser.add_argument("--external-id", 
                           help="External ID for role assumption")
    gen_parser.add_argument("--session-tags", 
                           help="Session tags as JSON string")
    gen_parser.add_argument("--issuer", default="mcp-test",
                           help="Token issuer (default: mcp-test)")
    gen_parser.add_argument("--audience", default="mcp-server", 
                           help="Token audience (default: mcp-server)")
    
    # Inspect command
    inspect_parser = subparsers.add_parser("inspect", help="Inspect JWT token")
    inspect_parser.add_argument("--token", required=True,
                               help="JWT token to inspect")
    inspect_parser.add_argument("--secret", required=True,
                               help="Secret key for verification")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    try:
        if args.command == "generate":
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
                session_tags=session_tags
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
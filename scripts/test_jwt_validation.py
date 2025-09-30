#!/usr/bin/env python3
"""Test JWT token validation locally to diagnose signature issues."""

import os
import sys
import jwt
import json
from datetime import datetime

def decode_jwt_without_verification(token):
    """Decode JWT without verifying signature to see the payload."""
    try:
        # Decode header
        header = jwt.get_unverified_header(token)
        print("\n" + "="*80)
        print("JWT HEADER (Unverified)")
        print("="*80)
        print(json.dumps(header, indent=2))
        
        # Decode payload
        payload = jwt.decode(token, options={"verify_signature": False})
        print("\n" + "="*80)
        print("JWT PAYLOAD (Unverified)")
        print("="*80)
        print(json.dumps(payload, indent=2, default=str))
        
        # Check expiration
        if 'exp' in payload:
            exp_time = datetime.fromtimestamp(payload['exp'])
            now = datetime.now()
            print(f"\nExpiration: {exp_time}")
            print(f"Current Time: {now}")
            print(f"Expired: {now > exp_time}")
        
        return header, payload
    except Exception as e:
        print(f"ERROR decoding JWT: {e}")
        return None, None

def validate_jwt_with_secret(token, secret):
    """Validate JWT with the given secret."""
    try:
        print("\n" + "="*80)
        print("JWT VALIDATION WITH SECRET")
        print("="*80)
        print(f"Secret (first 8 chars): {secret[:8]}...")
        print(f"Secret (last 8 chars): ...{secret[-8:]}")
        print(f"Secret length: {len(secret)}")
        
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options={"verify_aud": False}
        )
        
        print("\n✅ JWT VALIDATION SUCCESSFUL")
        print(f"Payload keys: {list(payload.keys())}")
        print(f"Buckets: {len(payload.get('buckets', payload.get('b', [])))}")
        print(f"Permissions: {len(payload.get('permissions', payload.get('p', [])))}")
        print(f"Roles: {payload.get('roles', payload.get('r', []))}")
        
        return True
    except jwt.ExpiredSignatureError:
        print("\n❌ JWT VALIDATION FAILED: Token expired")
        return False
    except jwt.InvalidSignatureError as e:
        print(f"\n❌ JWT VALIDATION FAILED: Invalid signature - {e}")
        print("\n🔍 DIAGNOSIS:")
        print("  The secret used to sign the token does NOT match the secret being used to validate it.")
        print("  Frontend secret and backend secret MUST be identical.")
        return False
    except jwt.InvalidTokenError as e:
        print(f"\n❌ JWT VALIDATION FAILED: {e}")
        return False

def main():
    if len(sys.argv) < 2:
        print("Usage: python test_jwt_validation.py <jwt-token> [secret]")
        print("\nTo get the JWT token:")
        print("  1. Open browser console on demo.quiltdata.com")
        print("  2. Run: await window.__dynamicAuthManager.getCurrentToken()")
        print("  3. Copy the token")
        print("\nSecret will be read from MCP_ENHANCED_JWT_SECRET env var if not provided")
        sys.exit(1)
    
    token = sys.argv[1]
    secret = sys.argv[2] if len(sys.argv) > 2 else os.getenv("MCP_ENHANCED_JWT_SECRET", "")
    
    if not secret:
        print("❌ No secret provided. Set MCP_ENHANCED_JWT_SECRET or pass as second argument")
        sys.exit(1)
    
    print("="*80)
    print("JWT TOKEN VALIDATION TEST")
    print("="*80)
    print(f"Token length: {len(token)} chars")
    
    # Decode without verification
    header, payload = decode_jwt_without_verification(token)
    
    # Validate with secret
    if secret:
        validate_jwt_with_secret(token, secret)
    
    print("\n" + "="*80)
    print("EXPECTED SECRET (from ECS task definition):")
    print("="*80)
    print("quilt-sales-prod-mcp-jwt-secret-2025-enhanced-tokens-v2")
    print("\n" + "="*80)

if __name__ == "__main__":
    main()

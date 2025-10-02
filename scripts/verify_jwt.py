#!/usr/bin/env python3
"""
Diagnostic script to verify JWT tokens.

Usage:
    python scripts/verify_jwt.py <jwt_token>
    
This will decode the JWT header and payload without verification to see what's inside.
"""

import sys
import base64
import json


def decode_jwt_unverified(token):
    """Decode JWT without verification to inspect its contents."""
    try:
        # Split the JWT into its three parts
        parts = token.split('.')
        if len(parts) != 3:
            print(f"❌ Invalid JWT format: expected 3 parts, got {len(parts)}")
            return None, None
        
        header_b64, payload_b64, signature_b64 = parts
        
        # Decode header
        try:
            # Add padding if needed
            header_padded = header_b64 + '=' * (4 - len(header_b64) % 4)
            header_bytes = base64.urlsafe_b64decode(header_padded)
            header = json.loads(header_bytes)
            print("✅ JWT Header:")
            print(json.dumps(header, indent=2))
        except Exception as e:
            print(f"❌ Failed to decode header: {e}")
            return None, None
        
        # Decode payload
        try:
            # Add padding if needed
            payload_padded = payload_b64 + '=' * (4 - len(payload_b64) % 4)
            payload_bytes = base64.urlsafe_b64decode(payload_padded)
            payload = json.loads(payload_bytes)
            print("\n✅ JWT Payload:")
            print(json.dumps(payload, indent=2))
        except Exception as e:
            print(f"❌ Failed to decode payload: {e}")
            return header, None
        
        print(f"\n📊 Token Info:")
        print(f"  - Header length: {len(header_b64)} chars")
        print(f"  - Payload length: {len(payload_b64)} chars")
        print(f"  - Signature length: {len(signature_b64)} chars")
        print(f"  - Total token length: {len(token)} chars")
        
        return header, payload
    
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return None, None


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/verify_jwt.py <jwt_token>")
        print("\nExample:")
        print("  python scripts/verify_jwt.py eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...")
        sys.exit(1)
    
    token = sys.argv[1].strip()
    
    print("🔍 Analyzing JWT token...")
    print("=" * 80)
    
    header, payload = decode_jwt_unverified(token)
    
    if header and payload:
        print("\n" + "=" * 80)
        print("✅ JWT token structure is valid!")
        print("\n💡 Next steps:")
        print("  1. Verify the 'kid' in the header matches MCP_ENHANCED_JWT_KID")
        print("  2. Verify the token was signed with the secret in MCP_ENHANCED_JWT_SECRET")
        print("  3. Check that 'exp' (expiration) hasn't passed")
        if 'aws_credentials' in payload or 'awsCredentials' in payload:
            print("  4. ✅ AWS credentials found in payload")
        else:
            print("  4. ⚠️  No AWS credentials found in payload")
    else:
        print("\n" + "=" * 80)
        print("❌ JWT token has issues - see errors above")


if __name__ == "__main__":
    main()


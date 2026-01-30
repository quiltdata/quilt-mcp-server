#!/usr/bin/env python3
"""
Decode the catalog bearer token to understand its structure.
"""

import base64
import json
import sys

def decode_jwt_without_verification(token):
    """Decode JWT without signature verification to inspect payload."""
    try:
        # Split the token
        parts = token.split('.')
        if len(parts) != 3:
            return None, "Invalid JWT format"
        
        header, payload, signature = parts
        
        # Decode header
        header_data = json.loads(base64.urlsafe_b64decode(header + '=='))
        
        # Decode payload
        payload_data = json.loads(base64.urlsafe_b64decode(payload + '=='))
        
        return {
            'header': header_data,
            'payload': payload_data,
            'signature': signature
        }, None
        
    except Exception as e:
        return None, str(e)

def main():
    # The catalog bearer token from the session analysis
    catalog_token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpZCI6IjgxYTM1MjgyLTAxNDktNGViMy1iYjhlLTYyNzM3OWRiNmExYyIsInV1aWQiOiIzYjVkYTYzNS1hZmEzLTRjM2QtOGM2Zi0zOTQ3M2M0YmY4YjkiLCJleHAiOjE3Nzc0MzI2Mzh9.GeZ7gBesVKVODm52BFy4gYboqU9ytX9hPnK9SPrabQw"
    
    print("🔍 Decoding Catalog Bearer Token")
    print("=" * 60)
    
    decoded, error = decode_jwt_without_verification(catalog_token)
    
    if error:
        print(f"❌ Error decoding token: {error}")
        return
    
    print("📋 Token Header:")
    print(json.dumps(decoded['header'], indent=2))
    
    print("\n📋 Token Payload:")
    print(json.dumps(decoded['payload'], indent=2))
    
    print(f"\n🔐 Signature: {decoded['signature'][:20]}...")
    
    # Analyze the payload
    payload = decoded['payload']
    
    print("\n🔍 Analysis:")
    print(f"  Token type: Quilt catalog authentication token")
    print(f"  User ID: {payload.get('id', 'N/A')}")
    print(f"  UUID: {payload.get('uuid', 'N/A')}")
    print(f"  Expires: {payload.get('exp', 'N/A')}")
    
    # Convert expiry to human readable
    if 'exp' in payload:
        import datetime
        exp_time = datetime.datetime.fromtimestamp(payload['exp'])
        print(f"  Expires at: {exp_time}")
        
        now = datetime.datetime.now()
        if exp_time > now:
            remaining = exp_time - now
            print(f"  Time remaining: {remaining}")
        else:
            print(f"  ⚠️  Token expired!")
    
    print("\n💡 Key Insights:")
    print("1. This is a Quilt-specific authentication token")
    print("2. It contains user identity information for the catalog")
    print("3. It's separate from AWS credentials")
    print("4. Our test JWTs are missing this catalog authentication")
    
    print("\n🔧 Solution Options:")
    print("1. Include catalog bearer token in our MCP JWT")
    print("2. Use AWS credentials to obtain catalog token programmatically")
    print("3. Implement catalog authentication flow in JWT auth service")

if __name__ == "__main__":
    main()
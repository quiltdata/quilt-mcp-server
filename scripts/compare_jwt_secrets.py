#!/usr/bin/env python3
"""Compare JWT secrets byte-by-byte to find differences."""

import sys

def compare_secrets(secret1, secret2, label1="Secret 1", label2="Secret 2"):
    """Compare two secrets byte-by-byte."""
    print("="*80)
    print("JWT SECRET COMPARISON")
    print("="*80)
    
    print(f"\n{label1}:")
    print(f"  Value: {secret1}")
    print(f"  Length: {len(secret1)}")
    print(f"  First 10: {secret1[:10]}")
    print(f"  Last 10: {secret1[-10:]}")
    print(f"  Bytes: {secret1.encode('utf-8').hex()[:40]}...")
    
    print(f"\n{label2}:")
    print(f"  Value: {secret2}")
    print(f"  Length: {len(secret2)}")
    print(f"  First 10: {secret2[:10]}")
    print(f"  Last 10: {secret2[-10:]}")
    print(f"  Bytes: {secret2.encode('utf-8').hex()[:40]}...")
    
    print("\n" + "="*80)
    print("COMPARISON")
    print("="*80)
    
    if secret1 == secret2:
        print("✅ Secrets are IDENTICAL")
        return True
    else:
        print("❌ Secrets are DIFFERENT")
        print(f"\nLength: {len(secret1)} vs {len(secret2)}")
        
        # Find first difference
        min_len = min(len(secret1), len(secret2))
        for i in range(min_len):
            if secret1[i] != secret2[i]:
                print(f"\nFirst difference at position {i}:")
                print(f"  {label1}[{i}]: '{secret1[i]}' (ASCII {ord(secret1[i])})")
                print(f"  {label2}[{i}]: '{secret2[i]}' (ASCII {ord(secret2[i])})")
                
                # Show context
                start = max(0, i-5)
                end = min(min_len, i+6)
                print(f"\n  Context {label1}: ...{secret1[start:end]}...")
                print(f"  Context {label2}: ...{secret2[start:end]}...")
                break
        
        if len(secret1) != len(secret2):
            print(f"\nExtra characters in longer secret:")
            if len(secret1) > len(secret2):
                print(f"  {label1} has: '{secret1[len(secret2):]}'")
            else:
                print(f"  {label2} has: '{secret2[len(secret1):]}'")
        
        return False

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python compare_jwt_secrets.py <secret1> <secret2>")
        print("\nExample:")
        print("  python compare_jwt_secrets.py 'backend-secret' 'frontend-secret'")
        sys.exit(1)
    
    secret1 = sys.argv[1]
    secret2 = sys.argv[2]
    
    label1 = sys.argv[3] if len(sys.argv) > 3 else "Backend Secret"
    label2 = sys.argv[4] if len(sys.argv) > 4 else "Frontend Secret"
    
    compare_secrets(secret1, secret2, label1, label2)

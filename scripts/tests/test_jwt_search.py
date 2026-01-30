#!/usr/bin/env python3
"""
Simple integration test for JWT authentication with search_catalog.
Tests the complete flow: extract session -> create JWT -> call search.
"""

import json
import sys
from pathlib import Path

# Add src and scripts to path
repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(repo_root / "src"))
sys.path.insert(0, str(repo_root / "scripts" / "tests"))

# Import JWT helper functions
from jwt_helper import (
    extract_catalog_token_from_session,
    get_current_catalog_url,
    get_current_registry_url,
    generate_test_jwt,
)

# Import MCP service
from quilt_mcp.services.jwt_auth_service import JWTAuthService


def main():
    print("=" * 80)
    print("JWT Authentication + Search Integration Test")
    print("=" * 80)

    # Step 1: Extract session info
    print("\n[Step 1] Extracting quilt3 session info...")
    catalog_token = extract_catalog_token_from_session()
    catalog_url = get_current_catalog_url()
    registry_url = get_current_registry_url()

    print(f"  Catalog URL: {catalog_url}")
    print(f"  Registry URL: {registry_url}")
    print(f"  Token type: {type(catalog_token).__name__}")
    print(f"  Token length: {len(catalog_token) if catalog_token else 0}")
    print(f"  Token prefix: {catalog_token[:20] if catalog_token else 'None'}...")

    if not catalog_token:
        print("❌ No catalog token found!")
        return 1

    if not catalog_url:
        print("❌ No catalog URL found!")
        return 1

    # Step 2: Create JWT with embedded catalog credentials
    print("\n[Step 2] Creating JWT token with catalog credentials...")
    jwt_token = generate_test_jwt(
        role_arn="arn:aws:iam::712023778557:role/QuiltMCPTestRole",
        secret="test-secret-key-for-stateless-testing-only",
        expiry_seconds=3600,
        catalog_token=catalog_token,
        catalog_url=catalog_url,
        registry_url=registry_url,
        auto_extract=False,  # We already extracted above
    )

    print(f"  JWT created: {jwt_token[:50]}...")

    # Step 3: Decode and verify JWT contents
    print("\n[Step 3] Verifying JWT contents...")
    import jwt as pyjwt
    decoded = pyjwt.decode(
        jwt_token,
        "test-secret-key-for-stateless-testing-only",
        algorithms=["HS256"],
        audience="mcp-server",
        options={"verify_aud": True}
    )
    print(f"  Subject: {decoded.get('sub')}")
    print(f"  Role ARN: {decoded.get('role_arn')}")
    print(f"  Catalog URL: {decoded.get('catalog_url')}")
    print(f"  Registry URL: {decoded.get('registry_url')}")
    print(f"  Has catalog_token: {'catalog_token' in decoded}")
    print(f"  Catalog token in JWT: {decoded.get('catalog_token', 'MISSING')[:20]}...")

    # Step 4: Set up runtime context with JWT
    print("\n[Step 4] Setting up runtime context with JWT...")
    from quilt_mcp.runtime_context import set_runtime_auth, RuntimeAuthState

    set_runtime_auth(RuntimeAuthState(
        scheme="bearer",
        access_token=jwt_token,
        claims=decoded,
    ))
    print(f"  Runtime auth configured with JWT claims")

    # Initialize auth service
    auth_service = JWTAuthService()
    print(f"  JWT auth service initialized")

    # Step 5: Test search with JWT catalog credentials
    print("\n[Step 5] Testing search_catalog with JWT catalog credentials...")

    # Get catalog credentials from JWT claims
    jwt_catalog_url = decoded.get("catalog_url")
    jwt_catalog_token = decoded.get("catalog_token")

    print(f"  Using catalog_url from JWT: {jwt_catalog_url}")
    print(f"  Using catalog_token from JWT: {jwt_catalog_token[:20] if jwt_catalog_token else 'None'}...")

    # Import search tool
    from quilt_mcp.tools.search import search_catalog

    try:
        # Call search_catalog directly (it uses runtime context)
        results = search_catalog(
            query="README.md",
            limit=10,
            scope="global",
            bucket="",
        )
        print(f"  ✅ Search succeeded!")

        # Results is a dict
        if isinstance(results, dict) and 'results' in results:
            result_count = len(results['results'])
            print(f"  Results count: {result_count}")
            print(f"  Query time: {results.get('query_time_ms', 0):.1f}ms")
            print(f"  Backend used: {results.get('backend_used', 'unknown')}")

            if result_count > 0:
                first_result = results['results'][0]
                print(f"  First result: {first_result.get('s3_uri', 'N/A')}")
                print(f"  Score: {first_result.get('score', 0):.2f}")
            else:
                print("  ⚠️  No results found - this might indicate auth issues!")
                return 1
        else:
            print(f"  ⚠️ Unexpected result type: {type(results)}")
            return 1

    except Exception as e:
        print(f"  ❌ Search failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    print("\n" + "=" * 80)
    print("✅ All steps completed successfully!")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    sys.exit(main())

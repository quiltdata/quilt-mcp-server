#!/usr/bin/env python3
"""
Validate the authentication design flaw hypothesis.

This script checks if the MCP server has proper catalog authentication
and confirms whether the search failures are due to missing catalog session.
"""

import os
import sys
sys.path.insert(0, 'src')

def check_authentication_status():
    """Check the current authentication status of the MCP server."""
    print("🔍 Checking MCP Server Authentication Status")
    print("=" * 60)
    
    try:
        from quilt_mcp.services.quilt_service import QuiltService
        
        qs = QuiltService()
        
        # Check session support
        has_session = qs.has_session_support()
        print(f"📡 Has session support: {has_session}")
        
        # Check authentication status
        is_authenticated = qs.is_authenticated()
        print(f"🔐 Is authenticated: {is_authenticated}")
        
        # Check logged in URL
        logged_in_url = qs.get_logged_in_url()
        print(f"🌐 Logged in URL: {logged_in_url}")
        
        # Check registry URL
        registry_url = qs.get_registry_url()
        print(f"📋 Registry URL: {registry_url}")
        
        # Get catalog info
        catalog_info = qs.get_catalog_info()
        print(f"📊 Catalog info: {catalog_info}")
        
        print("\n" + "=" * 60)
        
        # Analyze results
        if not has_session:
            print("❌ PROBLEM: No quilt3 session support available")
            print("   This means quilt3.session.get_session() will fail")
            print("   Search operations require authenticated session")
            
        if not is_authenticated:
            print("❌ PROBLEM: Not authenticated with any Quilt catalog")
            print("   This means no catalog login was performed")
            print("   Search operations require catalog authentication")
            
        if not registry_url:
            print("❌ PROBLEM: No registry URL available")
            print("   This means no catalog is configured")
            print("   Search operations need a target catalog")
            
        if has_session and is_authenticated and registry_url:
            print("✅ GOOD: Proper catalog authentication detected")
            print("   Search should work with this configuration")
        else:
            print("\n🚨 AUTHENTICATION DESIGN FLAW CONFIRMED:")
            print("   - MCP server lacks proper catalog authentication")
            print("   - Search operations will fail due to missing session")
            print("   - This explains the 0 results in search_catalog tests")
            print("   - Need to implement JWT authentication or catalog login")
            
    except Exception as e:
        print(f"❌ ERROR checking authentication: {e}")
        print("   This might indicate missing dependencies or configuration")

def check_search_backend_status():
    """Check the search backend status."""
    print("\n🔍 Checking Search Backend Status")
    print("=" * 60)
    
    try:
        from quilt_mcp.search.backends.elasticsearch import Quilt3ElasticsearchBackend
        
        backend = Quilt3ElasticsearchBackend()
        
        # Check if backend is initialized
        print(f"🔧 Backend type: {backend.backend_type}")
        print(f"📊 Backend status: {backend.status}")
        
        # Try to check session
        backend._check_session()
        print(f"📡 Session available: {backend._session_available}")
        
        if hasattr(backend, '_auth_error'):
            print(f"🚨 Auth error: {backend._auth_error}")
            
        # Try health check
        import asyncio
        health = asyncio.run(backend.health_check())
        print(f"💚 Health check: {health}")
        
    except Exception as e:
        print(f"❌ ERROR checking search backend: {e}")

def check_environment_variables():
    """Check relevant environment variables."""
    print("\n🔍 Checking Environment Variables")
    print("=" * 60)
    
    relevant_vars = [
        'MCP_REQUIRE_JWT',
        'MCP_JWT_SECRET',
        'AWS_ACCESS_KEY_ID',
        'AWS_SECRET_ACCESS_KEY',
        'AWS_PROFILE',
        'QUILT_TEST_ROLE_ARN',
    ]
    
    for var in relevant_vars:
        value = os.environ.get(var)
        if value:
            if 'SECRET' in var or 'KEY' in var:
                print(f"🔑 {var}: [REDACTED]")
            else:
                print(f"📝 {var}: {value}")
        else:
            print(f"❌ {var}: (not set)")

def main():
    """Main validation function."""
    print("🔍 MCP Server Authentication Validation")
    print("Testing the hypothesis that search failures are due to authentication design flaw")
    print("=" * 80)
    
    check_environment_variables()
    check_authentication_status()
    check_search_backend_status()
    
    print("\n" + "=" * 80)
    print("📋 SUMMARY:")
    print("If authentication design flaw is confirmed:")
    print("1. Implement JWT authentication per spec/a10-multitenant/04-finish-jwt.md")
    print("2. Or provide proper catalog credentials for testing")
    print("3. Ensure stateless operation with catalog authentication")
    print("4. Re-run stateless MCP tests to validate fix")

if __name__ == "__main__":
    main()
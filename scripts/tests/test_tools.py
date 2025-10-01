#!/usr/bin/env python3
"""
Syntactic smoke test for Quilt MCP server tools.

This is a purely syntactic test that verifies function signatures and basic
return types without requiring AWS credentials or network access.
"""

import asyncio
from quilt_mcp.tools import catalog as auth_tools
from quilt_mcp.tools.packages import package_browse
from quilt_mcp.tools.search import catalog_search


async def test_quilt_tools():
    """Basic smoke test against tool function signatures (no network/AWS required)."""
    print("Testing Quilt MCP Server Tools...")
    print("=" * 50)

    # Test catalog_status tool
    print("\n1. Testing catalog_status:")
    result = auth_tools.catalog_status()
    assert isinstance(result, dict)

    # Test catalog_search (replaces packages_list)
    print("\n2. Testing catalog_search (dry):")
    try:
        response = catalog_search(query="*", scope="catalog", limit=10)
        assert isinstance(response, dict)
    except Exception as e:
        if "AccessDenied" in str(e) or "S3NoValidClientError" in str(e):
            print(f"Skipped catalog_search due to access denied: {e}")
            response = {"results": [], "error": "Access denied"}
        else:
            raise

    # Test package_browse error handling on nonexistent package
    print("\n3. Testing package_browse (nonexistent):")
    pkg_info = package_browse("nonexistent/placeholder")
    assert isinstance(pkg_info, dict)

    print("\n" + "=" * 50)
    print("Testing complete!")


if __name__ == "__main__":
    asyncio.run(test_quilt_tools())

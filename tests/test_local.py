#!/usr/bin/env python3
"""
Test script for the Quilt MCP server
"""

import asyncio
import pytest
from quilt_mcp.tools import auth as auth_tools
from quilt_mcp.tools.packages import packages_list, package_browse

@pytest.mark.asyncio
async def test_quilt_tools():
    """Basic smoke test against local tool functions (no network)."""
    print("Testing Quilt MCP Server Tools...")
    print("=" * 50)
    
    # Test auth_status tool
    print("\n1. Testing auth_status:")
    result = auth_tools.auth_status()
    assert isinstance(result, dict)
    
    # Test packages_list signature (dry call with default registry)
    print("\n2. Testing packages_list (dry):")
    response = packages_list()
    assert isinstance(response, dict)
    
    # Test package_browse error handling on nonexistent package
    print("\n3. Testing package_browse (nonexistent):")
    pkg_info = package_browse("nonexistent/placeholder")
    assert isinstance(pkg_info, dict)
    
    print("\n" + "=" * 50)
    print("Testing complete!")

if __name__ == "__main__":
    asyncio.run(test_quilt_tools())



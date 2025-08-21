#!/usr/bin/env python3
"""
Test script for the Quilt MCP server
"""

import asyncio
from quilt.quilt import mcp

async def test_quilt_tools():
    """Test the Quilt MCP tools"""
    print("Testing Quilt MCP Server Tools...")
    print("=" * 50)
    
    # Test check_quilt_auth
    print("\n1. Testing check_quilt_auth:")
    try:
        auth_result = mcp.check_quilt_auth()
        print(f"Auth status: {auth_result}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test list_packages
    print("\n2. Testing list_packages:")
    try:
        packages = mcp.list_packages(registry="s3://quilt-example", prefix="akarve")
        print(f"Found {len(packages)} packages")
        for pkg in packages[:3]:  # Show first 3
            print(f"  - {pkg.get('name', 'Unknown')}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test browse_package
    print("\n3. Testing browse_package:")
    try:
        pkg_info = mcp.browse_package("akarve/tmp", registry="s3://quilt-example")
        if "error" not in pkg_info:
            print(f"Package: {pkg_info.get('name')}")
            print(f"Files: {len(pkg_info.get('files', []))}")
            for file_info in pkg_info.get('files', [])[:3]:
                print(f"  - {file_info.get('path')} ({file_info.get('size', 'Unknown size')} bytes)")
        else:
            print(f"Error: {pkg_info.get('error')}")
    except Exception as e:
        print(f"Error: {e}")
    
    print("\n" + "=" * 50)
    print("Testing complete!")

if __name__ == "__main__":
    asyncio.run(test_quilt_tools())



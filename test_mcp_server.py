#!/usr/bin/env python3
"""
Test script for the Quilt MCP server functions
"""

import sys
import os

# Add the quilt directory to the path and import directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'quilt'))

# Import the functions directly from the quilt.py file
import quilt

def test_quilt_tools():
    """Test the Quilt MCP tools directly"""
    print("Testing Quilt MCP Server Tools...")
    print("=" * 50)
    
    # Test check_quilt_auth
    print("\n1. Testing check_quilt_auth:")
    try:
        auth_result = quilt.check_quilt_auth()
        print(f"Auth status: {auth_result}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test list_packages
    print("\n2. Testing list_packages:")
    try:
        packages = quilt.list_packages(registry="s3://quilt-example", prefix="akarve")
        print(f"Found {len(packages)} packages")
        for pkg in packages[:3]:  # Show first 3
            print(f"  - {pkg.get('name', 'Unknown')}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test browse_package
    print("\n3. Testing browse_package:")
    try:
        pkg_info = quilt.browse_package("akarve/tmp", registry="s3://quilt-example")
        if "error" not in pkg_info:
            print(f"Package: {pkg_info.get('name')}")
            print(f"Files: {len(pkg_info.get('files', []))}")
            for file_info in pkg_info.get('files', [])[:3]:
                print(f"  - {file_info.get('path')} ({file_info.get('size', 'Unknown size')} bytes)")
        else:
            print(f"Error: {pkg_info.get('error')}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test search_package_contents
    print("\n4. Testing search_package_contents:")
    try:
        search_results = quilt.search_package_contents("akarve/tmp", "README", registry="s3://quilt-example")
        print(f"Found {len(search_results)} search results")
        for result in search_results[:2]:
            print(f"  - {result.get('type')}: {result.get('path')}")
    except Exception as e:
        print(f"Error: {e}")
    
    print("\n" + "=" * 50)
    print("Testing complete!")

if __name__ == "__main__":
    test_quilt_tools()

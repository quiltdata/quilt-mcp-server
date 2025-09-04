#!/usr/bin/env python3
"""
Test DXT package imports to diagnose module resolution issues.

This script validates that the DXT build contains all necessary modules
and that they can be imported correctly using the same path setup as dxt_main.py.
"""

import sys
import os
from pathlib import Path
import traceback

def test_dxt_imports(dxt_build_path: Path) -> bool:
    """
    Test DXT package imports by replicating dxt_main.py path setup.
    
    Args:
        dxt_build_path: Path to the DXT build directory
        
    Returns:
        True if all imports succeed, False otherwise
    """
    
    print(f"🔍 Testing DXT imports from: {dxt_build_path}")
    
    # Verify build directory exists
    if not dxt_build_path.exists():
        print(f"❌ DXT build directory not found: {dxt_build_path}")
        return False
    
    # Check for expected structure
    lib_dir = dxt_build_path / "lib"
    if not lib_dir.exists():
        print(f"❌ Dependencies directory not found: {lib_dir}")
        return False
    
    print(f"✅ Build directory structure found")
    print(f"   - Build path: {dxt_build_path}")
    print(f"   - Lib path: {lib_dir}")
    
    # Store original sys.path
    original_path = sys.path.copy()
    
    try:
        # Replicate dxt_main.py path setup (lines 8-10)
        sys.path.insert(0, str(lib_dir))
        sys.path.insert(0, str(dxt_build_path))
        
        print(f"🔧 Modified Python path:")
        print(f"   [0] {sys.path[0]}")
        print(f"   [1] {sys.path[1]}")
        
        # Test critical import from dxt_main.py:12
        print(f"🧪 Testing critical import: 'from quilt_mcp.utils import run_server'")
        
        try:
            from quilt_mcp.utils import run_server
            print("✅ Primary import successful: quilt_mcp.utils.run_server")
        except ImportError as e:
            print(f"❌ Primary import failed: {e}")
            print(f"   This is the exact error from Issue #89")
            
            # Diagnostic information
            print(f"\n🔍 Diagnostic information:")
            
            # Check if quilt_mcp directory exists
            quilt_mcp_dir = dxt_build_path / "quilt_mcp"
            if quilt_mcp_dir.exists():
                print(f"✅ quilt_mcp directory found: {quilt_mcp_dir}")
                utils_file = quilt_mcp_dir / "utils.py"
                if utils_file.exists():
                    print(f"✅ utils.py file found: {utils_file}")
                else:
                    print(f"❌ utils.py file not found in: {quilt_mcp_dir}")
                    print(f"   Contents: {list(quilt_mcp_dir.iterdir())}")
            else:
                print(f"❌ quilt_mcp directory not found in: {dxt_build_path}")
                print(f"   Build contents: {list(dxt_build_path.iterdir())}")
            
            # Check bundled dependencies
            print(f"\n📦 Bundled dependencies in {lib_dir}:")
            if lib_dir.exists():
                for item in lib_dir.iterdir():
                    if item.is_dir():
                        print(f"   📁 {item.name}")
                    else:
                        print(f"   📄 {item.name}")
            
            return False
        
        # Test additional critical imports
        test_imports = [
            ("fastmcp", "Basic FastMCP functionality"),
            ("mcp", "Core MCP protocol support"),
            ("quilt3", "Quilt data access"),
            ("boto3", "AWS integration"),
        ]
        
        print(f"\n🧪 Testing additional dependencies:")
        all_passed = True
        
        for module_name, description in test_imports:
            try:
                __import__(module_name)
                print(f"✅ {module_name}: {description}")
            except ImportError as e:
                print(f"❌ {module_name}: {e}")
                all_passed = False
        
        if all_passed:
            print(f"\n🎉 All DXT imports successful!")
            print(f"   The DXT package should work correctly.")
            return True
        else:
            print(f"\n⚠️  Some dependency imports failed.")
            print(f"   This may cause runtime issues.")
            return False
            
    except Exception as e:
        print(f"❌ Unexpected error during import testing: {e}")
        traceback.print_exc()
        return False
    
    finally:
        # Restore original sys.path
        sys.path = original_path

def main():
    """Main entry point for the import test."""
    
    # Determine DXT build path
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    dxt_build_path = repo_root / "tools" / "dxt" / "build"
    
    print("🚀 DXT Import Test")
    print("=" * 50)
    
    success = test_dxt_imports(dxt_build_path)
    
    print("=" * 50)
    if success:
        print("✅ DXT import test PASSED")
        sys.exit(0)
    else:
        print("❌ DXT import test FAILED")
        print("\nThis indicates the issue from GitHub Issue #89:")
        print("The DXT package is missing required modules or has path issues.")
        sys.exit(1)

if __name__ == "__main__":
    main()
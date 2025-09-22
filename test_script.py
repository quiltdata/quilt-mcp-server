#!/usr/bin/env python3
"""Quick test script to run legacy function tests."""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_imports():
    """Test that we can import the legacy functions."""
    try:
        from quilt_mcp.tools.packages import packages_search
        from quilt_mcp.tools.buckets import bucket_objects_search, bucket_objects_search_graphql
        from quilt_mcp.constants import DEFAULT_REGISTRY

        print("✅ All legacy functions imported successfully")
        print(f"DEFAULT_REGISTRY: '{DEFAULT_REGISTRY}'")

        # Test packages_search with mocked catalog_search
        from unittest.mock import patch

        with patch('quilt_mcp.tools.packages.catalog_search') as mock_catalog_search:
            mock_catalog_search.return_value = {"results": [], "count": 0}
            result = packages_search("test")
            print("✅ packages_search test passed")

        return True

    except Exception as e:
        print(f"❌ Import/test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)
#!/usr/bin/env python3
"""
Debug the search_catalog failures by testing search directly.

This script attempts to reproduce the search failures and understand
why search_catalog is returning 0 results.
"""

import os
import sys
import asyncio
sys.path.insert(0, 'src')

async def test_search_directly():
    """Test search functionality directly."""
    print("🔍 Testing Search Functionality Directly")
    print("=" * 60)
    
    try:
        from quilt_mcp.search.tools.unified_search import UnifiedSearchEngine
        
        engine = UnifiedSearchEngine()
        
        # Test the same queries that are failing
        test_queries = [
            {"query": "README.md", "scope": "global", "bucket": ""},
            {"query": "README.md", "scope": "file", "bucket": ""},
            {"query": "raw/test", "scope": "package", "bucket": ""},
        ]
        
        for i, test in enumerate(test_queries, 1):
            print(f"\n🧪 Test {i}: {test}")
            print("-" * 40)
            
            try:
                result = await engine.search(
                    query=test["query"],
                    scope=test["scope"],
                    bucket=test["bucket"],
                    limit=10
                )
                
                print(f"✅ Success: {result.get('success', False)}")
                print(f"📊 Total results: {result.get('total_results', 0)}")
                print(f"🔧 Backend used: {result.get('backend_used', 'None')}")
                print(f"⏱️  Query time: {result.get('query_time_ms', 0):.2f}ms")
                
                if result.get('error'):
                    print(f"❌ Error: {result['error']}")
                
                if result.get('backend_status'):
                    print(f"🔧 Backend status: {result['backend_status']}")
                
                if result.get('backend_info'):
                    print(f"ℹ️  Backend info: {result['backend_info']}")
                
                # Show first few results if any
                results = result.get('results', [])
                if results:
                    print(f"📋 First result: {results[0]}")
                else:
                    print("📋 No results returned")
                    
            except Exception as e:
                print(f"❌ Exception: {e}")
                import traceback
                traceback.print_exc()
                
    except Exception as e:
        print(f"❌ ERROR setting up search engine: {e}")
        import traceback
        traceback.print_exc()

async def test_elasticsearch_backend():
    """Test Elasticsearch backend directly."""
    print("\n🔍 Testing Elasticsearch Backend Directly")
    print("=" * 60)
    
    try:
        from quilt_mcp.search.backends.elasticsearch import Quilt3ElasticsearchBackend
        
        backend = Quilt3ElasticsearchBackend()
        
        print(f"🔧 Backend status: {backend.status}")
        print(f"📡 Session available: {backend._session_available}")
        
        # Try to get available buckets
        try:
            buckets = backend._get_available_buckets()
            print(f"🪣 Available buckets: {buckets}")
        except Exception as e:
            print(f"❌ Error getting buckets: {e}")
        
        # Try a simple search
        try:
            result = await backend.search(
                query="README.md",
                scope="file",
                bucket="",
                limit=10
            )
            print(f"🔍 Search result status: {result.status}")
            print(f"📊 Search result count: {len(result.results)}")
            if result.error_message:
                print(f"❌ Search error: {result.error_message}")
        except Exception as e:
            print(f"❌ Search exception: {e}")
            import traceback
            traceback.print_exc()
            
    except Exception as e:
        print(f"❌ ERROR testing backend: {e}")
        import traceback
        traceback.print_exc()

def test_search_tool():
    """Test the search_catalog tool directly."""
    print("\n🔍 Testing search_catalog Tool Directly")
    print("=" * 60)
    
    try:
        from quilt_mcp.tools.search import search_catalog
        
        # Test the same queries that are failing
        test_queries = [
            {"query": "README.md", "scope": "global", "bucket": ""},
            {"query": "README.md", "scope": "file", "bucket": ""},
            {"query": "raw/test", "scope": "package", "bucket": ""},
        ]
        
        for i, test in enumerate(test_queries, 1):
            print(f"\n🧪 Tool Test {i}: {test}")
            print("-" * 40)
            
            try:
                result = search_catalog(
                    query=test["query"],
                    scope=test["scope"],
                    bucket=test["bucket"],
                    limit=10
                )
                
                print(f"✅ Success: {result.get('success', False)}")
                print(f"📊 Total results: {result.get('total_results', 0)}")
                
                if result.get('error'):
                    print(f"❌ Error: {result['error']}")
                    
                # Show result structure
                print(f"🔧 Result keys: {list(result.keys())}")
                
            except Exception as e:
                print(f"❌ Exception: {e}")
                import traceback
                traceback.print_exc()
                
    except Exception as e:
        print(f"❌ ERROR testing search tool: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """Main debug function."""
    print("🔍 Search Catalog Debug Analysis")
    print("Investigating why search_catalog returns 0 results")
    print("=" * 80)
    
    await test_search_directly()
    await test_elasticsearch_backend()
    test_search_tool()
    
    print("\n" + "=" * 80)
    print("📋 DEBUG SUMMARY:")
    print("This analysis should reveal:")
    print("1. Whether search backend is properly initialized")
    print("2. Whether buckets are available for searching")
    print("3. Whether search queries are being executed correctly")
    print("4. What specific errors are occurring in the search pipeline")

if __name__ == "__main__":
    asyncio.run(main())
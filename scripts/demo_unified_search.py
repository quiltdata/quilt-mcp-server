#!/usr/bin/env python3
"""Demo script for unified search functionality.

This script demonstrates the capabilities of the new unified search architecture.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add app to Python path
sys.path.insert(0, str(Path(__file__).parent / "app"))

from quilt_mcp.search.tools.unified_search import unified_search


async def demo_unified_search():
    """Demonstrate unified search capabilities."""
    print("🔍 Unified Search Architecture Demo")
    print("=" * 50)
    
    # Demo queries showcasing different capabilities
    demo_queries = [
        {
            "query": "CSV files in genomics packages",
            "description": "Natural language file search with domain context",
            "scope": "global"
        },
        {
            "query": "packages created last month", 
            "description": "Package discovery with temporal filters",
            "scope": "catalog"
        },
        {
            "query": "files larger than 100MB",
            "description": "Analytical search with size filters", 
            "scope": "global"
        },
        {
            "query": "README files",
            "description": "Simple file search",
            "scope": "global"
        },
        {
            "query": "csv",
            "description": "Bucket-specific search (S3 fallback)",
            "scope": "bucket",
            "target": "quilt-example"
        }
    ]
    
    for i, demo in enumerate(demo_queries, 1):
        print(f"\n📋 Demo {i}: {demo['description']}")
        print(f"Query: \"{demo['query']}\"")
        print(f"Scope: {demo['scope']}")
        if demo.get('target'):
            print(f"Target: {demo['target']}")
        
        try:
            result = await unified_search(
                query=demo['query'],
                scope=demo['scope'],
                target=demo.get('target', ''),
                limit=5,
                explain_query=True
            )
            
            # Show results summary
            print(f"✅ Success: {result['success']}")
            print(f"📊 Results: {len(result.get('results', []))}")
            print(f"⏱️  Query Time: {result.get('query_time_ms', 0):.1f}ms")
            print(f"🔧 Backends Used: {', '.join(result.get('backends_used', []))}")
            
            # Show query analysis
            analysis = result.get('analysis', {})
            if analysis:
                print(f"🎯 Query Type: {analysis.get('query_type', 'unknown')}")
                print(f"📈 Confidence: {analysis.get('confidence', 0):.2f}")
                if analysis.get('keywords'):
                    print(f"🔤 Keywords: {', '.join(analysis['keywords'])}")
                if analysis.get('file_extensions'):
                    print(f"📁 Extensions: {', '.join(analysis['file_extensions'])}")
            
            # Show backend performance
            backend_status = result.get('backend_status', {})
            if backend_status:
                print("🔧 Backend Performance:")
                for backend, status in backend_status.items():
                    status_emoji = "✅" if status['status'] == 'available' else "❌"
                    print(f"   {status_emoji} {backend}: {status['status']} "
                          f"({status.get('result_count', 0)} results, "
                          f"{status.get('query_time_ms', 0):.1f}ms)")
                    if status.get('error'):
                        print(f"      Error: {status['error']}")
            
            # Show sample results
            if result.get('results'):
                print("📄 Sample Results:")
                for j, res in enumerate(result['results'][:3]):
                    print(f"   {j+1}. {res.get('title', 'Unknown')} ({res.get('type', 'unknown')})")
                    if res.get('package_name'):
                        print(f"      Package: {res['package_name']}")
                    if res.get('s3_uri'):
                        print(f"      URI: {res['s3_uri']}")
                    print(f"      Score: {res.get('score', 0):.2f}")
            
            # Show explanation if available
            explanation = result.get('explanation')
            if explanation:
                print("💡 Query Explanation:")
                query_analysis = explanation.get('query_analysis', {})
                print(f"   Detected Intent: {query_analysis.get('detected_type', 'unknown')}")
                print(f"   Confidence: {query_analysis.get('confidence', 0):.2f}")
                
                backend_selection = explanation.get('backend_selection', {})
                print(f"   Backend Selection: {', '.join(backend_selection.get('selected', []))}")
                print(f"   Reasoning: {backend_selection.get('reasoning', 'Not provided')}")
        
        except Exception as e:
            print(f"❌ Demo {i} failed: {e}")
            import traceback
            traceback.print_exc()
        
        print("-" * 50)
    
    print("\n🎉 Demo completed!")
    print("\nKey Features Demonstrated:")
    print("✅ Natural language query processing")
    print("✅ Automatic query type detection")
    print("✅ Intelligent backend selection")
    print("✅ Parallel backend execution")
    print("✅ Result aggregation and ranking") 
    print("✅ Error handling and fallbacks")
    print("✅ Performance monitoring")
    print("✅ Query explanations")


if __name__ == "__main__":
    asyncio.run(demo_unified_search())



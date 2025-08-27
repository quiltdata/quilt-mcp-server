#!/usr/bin/env python3
"""
Interactive MCP Server Testing Suite

This script provides comprehensive testing of the MCP server including:
- Functionality validation
- Error handling
- Performance measurement
- Unified search architecture validation
"""

import asyncio
import json
import time
import sys
import os
from typing import Dict, Any, List
import traceback

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from quilt_mcp.utils import create_mcp_server, register_tools
from mcp.types import CallToolRequest, ListToolsRequest


class MCPServerTester:
    """Interactive MCP Server Tester"""
    
    def __init__(self):
        self.server = None
        self.setup_server()
        
    def setup_server(self):
        """Set up the MCP server with all tools"""
        print("🚀 Setting up MCP server...")
        try:
            self.server = create_mcp_server()
            tool_count = register_tools(self.server, verbose=False)
            print(f"✅ MCP server ready with {tool_count} tools")
        except Exception as e:
            print(f"❌ Server setup failed: {e}")
            raise
    
    async def list_tools(self) -> Dict[str, Any]:
        """List all available tools"""
        try:
            request = ListToolsRequest(
                method="tools/list",
                params={}
            )
            response = await self.server.list_tools(request)
            return {
                "success": True,
                "tools": [{"name": tool.name, "description": tool.description} for tool in response.tools],
                "count": len(response.tools)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a specific tool and measure performance"""
        start_time = time.time()
        try:
            request = CallToolRequest(
                method="tools/call",
                params={
                    "name": tool_name,
                    "arguments": arguments
                }
            )
            response = await self.server.call_tool(request)
            end_time = time.time()
            
            return {
                "success": True,
                "tool_name": tool_name,
                "arguments": arguments,
                "response": response.content,
                "execution_time_ms": round((end_time - start_time) * 1000, 2),
                "is_error": response.isError if hasattr(response, 'isError') else False
            }
        except Exception as e:
            end_time = time.time()
            return {
                "success": False,
                "tool_name": tool_name,
                "arguments": arguments,
                "error": str(e),
                "execution_time_ms": round((end_time - start_time) * 1000, 2)
            }
    
    async def test_basic_functionality(self) -> Dict[str, Any]:
        """Test basic MCP functionality"""
        print("\n📋 Testing basic MCP functionality...")
        
        results = {
            "list_tools": await self.list_tools(),
            "tool_calls": []
        }
        
        # Test basic tools
        basic_tests = [
            ("mcp_quilt_auth_status", {"random_string": "test"}),
            ("mcp_quilt_filesystem_status", {"random_string": "test"}),
            ("mcp_quilt_catalog_info", {"random_string": "test"}),
        ]
        
        for tool_name, args in basic_tests:
            print(f"   Testing {tool_name}...")
            result = await self.call_tool(tool_name, args)
            results["tool_calls"].append(result)
            
            if result["success"]:
                print(f"   ✅ {tool_name}: {result['execution_time_ms']}ms")
            else:
                print(f"   ❌ {tool_name}: {result['error']}")
        
        return results
    
    async def test_search_functionality(self) -> Dict[str, Any]:
        """Test search functionality including unified search"""
        print("\n🔍 Testing search functionality...")
        
        results = {"search_tests": []}
        
        # Test different search functions
        search_tests = [
            ("mcp_quilt_packages_search", {"query": "data", "limit": 3}),
            ("mcp_quilt_bucket_objects_search", {"bucket": "s3://quilt-sandbox-bucket", "query": "data", "limit": 3}),
        ]
        
        # Add unified search if available
        tools_response = await self.list_tools()
        if tools_response["success"]:
            tool_names = [tool["name"] for tool in tools_response["tools"]]
            if "unified_search" in tool_names:
                search_tests.append(("unified_search", {
                    "query": "CSV files", 
                    "scope": "catalog", 
                    "limit": 3,
                    "explain_query": True
                }))
        
        for tool_name, args in search_tests:
            print(f"   Testing {tool_name}...")
            result = await self.call_tool(tool_name, args)
            results["search_tests"].append(result)
            
            if result["success"]:
                print(f"   ✅ {tool_name}: {result['execution_time_ms']}ms")
                # Check for results
                if result.get("response"):
                    response_content = result["response"]
                    if isinstance(response_content, list) and len(response_content) > 0:
                        content = response_content[0].text if hasattr(response_content[0], 'text') else str(response_content[0])
                        try:
                            parsed = json.loads(content)
                            if "results" in parsed:
                                print(f"      Found {len(parsed['results'])} results")
                        except:
                            pass
            else:
                print(f"   ❌ {tool_name}: {result['error']}")
        
        return results
    
    async def test_error_handling(self) -> Dict[str, Any]:
        """Test error handling with invalid inputs"""
        print("\n⚠️  Testing error handling...")
        
        results = {"error_tests": []}
        
        # Test with invalid inputs
        error_tests = [
            ("mcp_quilt_packages_search", {"query": "", "limit": -1}),  # Invalid limit
            ("mcp_quilt_bucket_objects_search", {"bucket": "invalid-bucket", "query": "test"}),  # Invalid bucket
            ("nonexistent_tool", {"any": "args"}),  # Nonexistent tool
        ]
        
        for tool_name, args in error_tests:
            print(f"   Testing error case: {tool_name}...")
            result = await self.call_tool(tool_name, args)
            results["error_tests"].append(result)
            
            if not result["success"]:
                print(f"   ✅ Error handled correctly: {result['execution_time_ms']}ms")
            else:
                print(f"   ⚠️  Expected error but got success: {result['execution_time_ms']}ms")
        
        return results
    
    async def test_performance(self) -> Dict[str, Any]:
        """Test performance with multiple concurrent calls"""
        print("\n⚡ Testing performance...")
        
        # Test concurrent calls
        concurrent_tasks = []
        test_tool = "mcp_quilt_auth_status"
        test_args = {"random_string": "perf_test"}
        
        print(f"   Running 5 concurrent calls to {test_tool}...")
        start_time = time.time()
        
        for i in range(5):
            task = self.call_tool(test_tool, {**test_args, "call_id": i})
            concurrent_tasks.append(task)
        
        results = await asyncio.gather(*concurrent_tasks)
        end_time = time.time()
        
        total_time = round((end_time - start_time) * 1000, 2)
        successful_calls = sum(1 for r in results if r["success"])
        avg_time = round(sum(r["execution_time_ms"] for r in results) / len(results), 2)
        
        print(f"   ✅ Concurrent test: {successful_calls}/5 successful")
        print(f"   ✅ Total time: {total_time}ms, Average per call: {avg_time}ms")
        
        return {
            "concurrent_test": {
                "total_calls": 5,
                "successful_calls": successful_calls,
                "total_time_ms": total_time,
                "average_time_ms": avg_time,
                "results": results
            }
        }
    
    async def run_comprehensive_test(self) -> Dict[str, Any]:
        """Run all tests and return comprehensive results"""
        print("🧪 Starting comprehensive MCP server testing...")
        
        test_results = {
            "timestamp": time.time(),
            "server_info": {
                "server_type": type(self.server).__name__,
                "tools_registered": len((await self.list_tools()).get("tools", []))
            }
        }
        
        # Run all test suites
        test_results["basic_functionality"] = await self.test_basic_functionality()
        test_results["search_functionality"] = await self.test_search_functionality()
        test_results["error_handling"] = await self.test_error_handling()
        test_results["performance"] = await self.test_performance()
        
        return test_results


async def main():
    """Main test runner"""
    print("=" * 60)
    print("🔬 MCP SERVER INTERACTIVE TESTING SUITE")
    print("=" * 60)
    
    try:
        tester = MCPServerTester()
        results = await tester.run_comprehensive_test()
        
        print("\n" + "=" * 60)
        print("📊 TEST RESULTS SUMMARY")
        print("=" * 60)
        
        # Basic functionality summary
        basic = results["basic_functionality"]
        tools_count = basic["list_tools"].get("count", 0)
        successful_basic = sum(1 for call in basic["tool_calls"] if call["success"])
        total_basic = len(basic["tool_calls"])
        
        print(f"📋 Basic Functionality: {successful_basic}/{total_basic} tests passed")
        print(f"   Tools available: {tools_count}")
        
        # Search functionality summary
        search = results["search_functionality"]
        successful_search = sum(1 for test in search["search_tests"] if test["success"])
        total_search = len(search["search_tests"])
        
        print(f"🔍 Search Functionality: {successful_search}/{total_search} tests passed")
        
        # Error handling summary
        error = results["error_handling"]
        handled_errors = sum(1 for test in error["error_tests"] if not test["success"])
        total_errors = len(error["error_tests"])
        
        print(f"⚠️  Error Handling: {handled_errors}/{total_errors} errors properly handled")
        
        # Performance summary
        perf = results["performance"]["concurrent_test"]
        print(f"⚡ Performance: {perf['successful_calls']}/5 concurrent calls successful")
        print(f"   Average response time: {perf['average_time_ms']}ms")
        
        # Overall assessment
        total_tests = total_basic + total_search + total_errors + 1  # +1 for performance
        passed_tests = successful_basic + successful_search + handled_errors + (1 if perf['successful_calls'] >= 4 else 0)
        
        print(f"\n🎯 Overall: {passed_tests}/{total_tests} test categories passed")
        
        if passed_tests == total_tests:
            print("✅ ALL TESTS PASSED - MCP server is working correctly!")
        elif passed_tests >= total_tests * 0.8:
            print("⚠️  MOSTLY WORKING - Some issues detected but server is functional")
        else:
            print("❌ ISSUES DETECTED - Server needs attention")
        
        # Save detailed results
        with open("mcp_test_results.json", "w") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\n📄 Detailed results saved to: mcp_test_results.json")
        
    except Exception as e:
        print(f"\n❌ Testing failed: {e}")
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

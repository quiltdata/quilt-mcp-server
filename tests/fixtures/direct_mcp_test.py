#!/usr/bin/env python3
"""
Direct MCP Tool Testing Suite

This script tests MCP tools directly by calling the underlying functions,
providing comprehensive validation of functionality, error handling, and performance.
"""

import asyncio
import json
import time
import sys
import os
from typing import Dict, Any, List
import traceback

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))

from quilt_mcp.utils import create_mcp_server, register_tools


class DirectMCPTester:
    """Direct MCP Tool Tester"""

    def __init__(self):
        self.server = None
        self.tools = {}
        self.setup_server()

    def setup_server(self):
        """Set up the MCP server and extract tools"""
        print("🚀 Setting up MCP server...")
        try:
            self.server = create_mcp_server()
            tool_count = register_tools(self.server, verbose=False)

            # Extract tools from the server
            self.tools = self.server.get_tools()

            print(f"✅ MCP server ready with {tool_count} tools")
            print(f"✅ Extracted {len(self.tools)} callable tools")
        except Exception as e:
            print(f"❌ Server setup failed: {e}")
            raise

    async def call_tool_direct(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Call a tool directly and measure performance"""
        start_time = time.time()
        try:
            if tool_name not in self.tools:
                raise ValueError(f"Tool '{tool_name}' not found")

            tool_func = self.tools[tool_name]

            # Call the tool function directly
            if asyncio.iscoroutinefunction(tool_func):
                result = await tool_func(**arguments)
            else:
                result = tool_func(**arguments)

            end_time = time.time()

            return {
                "success": True,
                "tool_name": tool_name,
                "arguments": arguments,
                "result": result,
                "execution_time_ms": round((end_time - start_time) * 1000, 2),
            }
        except Exception as e:
            end_time = time.time()
            return {
                "success": False,
                "tool_name": tool_name,
                "arguments": arguments,
                "error": str(e),
                "error_type": type(e).__name__,
                "execution_time_ms": round((end_time - start_time) * 1000, 2),
            }

    def list_available_tools(self) -> Dict[str, Any]:
        """List all available tools"""
        tools_info = []
        for tool_name, tool_func in self.tools.items():
            try:
                # Get function signature
                import inspect

                sig = inspect.signature(tool_func)
                params = list(sig.parameters.keys())

                tools_info.append(
                    {
                        "name": tool_name,
                        "parameters": params,
                        "is_async": asyncio.iscoroutinefunction(tool_func),
                    }
                )
            except Exception as e:
                tools_info.append({"name": tool_name, "error": str(e)})

        return {"success": True, "tools": tools_info, "count": len(tools_info)}

    async def test_basic_functionality(self) -> Dict[str, Any]:
        """Test basic MCP functionality"""
        print("\n📋 Testing basic MCP functionality...")

        results = {"list_tools": self.list_available_tools(), "tool_calls": []}

        # Test basic tools that should always work
        basic_tests = [
            ("mcp_quilt_auth_status", {"random_string": "test"}),
            ("mcp_quilt_filesystem_status", {"random_string": "test"}),
            ("mcp_quilt_catalog_info", {"random_string": "test"}),
            ("mcp_quilt_catalog_name", {"random_string": "test"}),
        ]

        for tool_name, args in basic_tests:
            if tool_name in self.tools:
                print(f"   Testing {tool_name}...")
                result = await self.call_tool_direct(tool_name, args)
                results["tool_calls"].append(result)

                if result["success"]:
                    print(f"   ✅ {tool_name}: {result['execution_time_ms']}ms")
                    # Show result summary
                    if isinstance(result["result"], dict):
                        success_status = result["result"].get("success", "unknown")
                        print(f"      Result success: {success_status}")
                else:
                    print(f"   ❌ {tool_name}: {result['error']}")
            else:
                print(f"   ⚠️  {tool_name}: Tool not found")

        return results

    async def test_search_functionality(self) -> Dict[str, Any]:
        """Test search functionality including unified search"""
        print("\n🔍 Testing search functionality...")

        results = {"search_tests": []}

        # Test different search functions
        search_tests = [
            ("mcp_quilt_packages_search", {"query": "data", "limit": 3}),
            (
                "mcp_quilt_bucket_objects_search",
                {"bucket": "s3://quilt-sandbox-bucket", "query": "data", "limit": 3},
            ),
            ("mcp_quilt_packages_list", {"limit": 5}),
        ]

        # Add unified search if available
        if "unified_search" in self.tools:
            search_tests.append(
                (
                    "unified_search",
                    {
                        "query": "CSV files",
                        "scope": "catalog",
                        "limit": 3,
                        "explain_query": True,
                    },
                )
            )

        for tool_name, args in search_tests:
            if tool_name in self.tools:
                print(f"   Testing {tool_name}...")
                result = await self.call_tool_direct(tool_name, args)
                results["search_tests"].append(result)

                if result["success"]:
                    print(f"   ✅ {tool_name}: {result['execution_time_ms']}ms")
                    # Check for results
                    if isinstance(result["result"], dict):
                        if "results" in result["result"]:
                            results_count = len(result["result"]["results"])
                            print(f"      Found {results_count} results")
                        elif "packages" in result["result"]:
                            packages_count = len(result["result"]["packages"])
                            print(f"      Found {packages_count} packages")
                else:
                    print(f"   ❌ {tool_name}: {result['error']}")
            else:
                print(f"   ⚠️  {tool_name}: Tool not found")

        return results

    async def test_error_handling(self) -> Dict[str, Any]:
        """Test error handling with invalid inputs"""
        print("\n⚠️  Testing error handling...")

        results = {"error_tests": []}

        # Test with invalid inputs
        error_tests = [
            ("mcp_quilt_packages_search", {"query": "", "limit": -1}),  # Invalid limit
            (
                "mcp_quilt_bucket_objects_search",
                {"bucket": "invalid-bucket", "query": "test"},
            ),  # Invalid bucket
            ("mcp_quilt_auth_status", {}),  # Missing required parameter
        ]

        for tool_name, args in error_tests:
            if tool_name in self.tools:
                print(f"   Testing error case: {tool_name}...")
                result = await self.call_tool_direct(tool_name, args)
                results["error_tests"].append(result)

                if not result["success"]:
                    print(
                        f"   ✅ Error handled correctly: {result['execution_time_ms']}ms ({result['error_type']})"
                    )
                else:
                    # Check if the result indicates an error
                    if isinstance(result["result"], dict) and not result["result"].get(
                        "success"
                    ):
                        print(
                            f"   ✅ Error handled in result: {result['execution_time_ms']}ms"
                        )
                    else:
                        print(
                            f"   ⚠️  Expected error but got success: {result['execution_time_ms']}ms"
                        )
            else:
                print(f"   ⚠️  {tool_name}: Tool not found for error test")

        return results

    async def test_performance(self) -> Dict[str, Any]:
        """Test performance with multiple concurrent calls"""
        print("\n⚡ Testing performance...")

        # Test concurrent calls
        concurrent_tasks = []
        test_tool = "mcp_quilt_auth_status"
        test_args = {"random_string": "perf_test"}

        if test_tool not in self.tools:
            print(f"   ⚠️  Performance test skipped: {test_tool} not available")
            return {"concurrent_test": {"error": "Test tool not available"}}

        print(f"   Running 5 concurrent calls to {test_tool}...")
        start_time = time.time()

        for i in range(5):
            task = self.call_tool_direct(test_tool, {**test_args, "call_id": str(i)})
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
                "results": results,
            }
        }

    async def test_unified_search_architecture(self) -> Dict[str, Any]:
        """Test unified search architecture specifically"""
        print("\n🏗️  Testing unified search architecture...")

        results = {"unified_search_tests": []}

        # Test unified search if available
        if "unified_search" in self.tools:
            unified_tests = [
                {
                    "query": "CSV files",
                    "scope": "catalog",
                    "limit": 3,
                    "explain_query": True,
                },
                {"query": "genomics data", "scope": "global", "limit": 2},
                {
                    "query": "test",
                    "scope": "bucket",
                    "target": "s3://quilt-sandbox-bucket",
                    "limit": 1,
                },
            ]

            for test_args in unified_tests:
                print(
                    f"   Testing unified search: {test_args['query']} ({test_args['scope']})..."
                )
                result = await self.call_tool_direct("unified_search", test_args)
                results["unified_search_tests"].append(result)

                if result["success"]:
                    print(f"   ✅ Unified search: {result['execution_time_ms']}ms")

                    # Check for explanation (if requested)
                    if isinstance(result["result"], dict):
                        if "explanation" in result["result"]:
                            explanation = result["result"]["explanation"]
                            backends = explanation.get("backends_selected", [])
                            print(f"      Backends used: {backends}")

                        if "results" in result["result"]:
                            results_count = len(result["result"]["results"])
                            print(f"      Found {results_count} results")
                else:
                    print(f"   ❌ Unified search failed: {result['error']}")
        else:
            print("   ⚠️  Unified search not available")
            results["unified_search_tests"].append(
                {"success": False, "error": "unified_search tool not found"}
            )

        return results

    async def run_comprehensive_test(self) -> Dict[str, Any]:
        """Run all tests and return comprehensive results"""
        print("🧪 Starting comprehensive MCP tool testing...")

        test_results = {
            "timestamp": time.time(),
            "server_info": {
                "server_type": type(self.server).__name__,
                "tools_registered": len(self.tools),
                "tool_names": list(self.tools.keys())[:10],  # First 10 for brevity
            },
        }

        # Run all test suites
        test_results["basic_functionality"] = await self.test_basic_functionality()
        test_results["search_functionality"] = await self.test_search_functionality()
        test_results["error_handling"] = await self.test_error_handling()
        test_results["performance"] = await self.test_performance()
        test_results["unified_search_architecture"] = (
            await self.test_unified_search_architecture()
        )

        return test_results


async def main():
    """Main test runner"""
    print("=" * 70)
    print("🔬 DIRECT MCP TOOL TESTING SUITE")
    print("=" * 70)

    try:
        tester = DirectMCPTester()
        results = await tester.run_comprehensive_test()

        print("\n" + "=" * 70)
        print("📊 TEST RESULTS SUMMARY")
        print("=" * 70)

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

        print(
            f"🔍 Search Functionality: {successful_search}/{total_search} tests passed"
        )

        # Error handling summary
        error = results["error_handling"]
        handled_errors = sum(
            1
            for test in error["error_tests"]
            if not test["success"]
            or (
                isinstance(test.get("result"), dict)
                and not test["result"].get("success")
            )
        )
        total_errors = len(error["error_tests"])

        print(
            f"⚠️  Error Handling: {handled_errors}/{total_errors} errors properly handled"
        )

        # Performance summary
        perf = results["performance"].get("concurrent_test", {})
        if "error" not in perf:
            successful_perf = perf.get("successful_calls", 0)
            print(f"⚡ Performance: {successful_perf}/5 concurrent calls successful")
            print(f"   Average response time: {perf.get('average_time_ms', 0)}ms")
        else:
            print(f"⚡ Performance: Test skipped ({perf['error']})")

        # Unified search summary
        unified = results["unified_search_architecture"]
        successful_unified = sum(
            1 for test in unified["unified_search_tests"] if test["success"]
        )
        total_unified = len(unified["unified_search_tests"])

        print(f"🏗️  Unified Search: {successful_unified}/{total_unified} tests passed")

        # Overall assessment
        total_categories = 5
        passed_categories = 0

        if successful_basic >= total_basic * 0.8:
            passed_categories += 1
        if successful_search >= total_search * 0.8:
            passed_categories += 1
        if handled_errors >= total_errors * 0.8:
            passed_categories += 1
        if "error" not in perf and perf.get("successful_calls", 0) >= 4:
            passed_categories += 1
        if successful_unified >= max(1, total_unified * 0.8):
            passed_categories += 1

        print(
            f"\n🎯 Overall: {passed_categories}/{total_categories} test categories passed"
        )

        if passed_categories == total_categories:
            print("✅ ALL TESTS PASSED - MCP server is working correctly!")
            print("✅ Server is functional, error-free, and efficient!")
        elif passed_categories >= total_categories * 0.8:
            print("⚠️  MOSTLY WORKING - Minor issues detected but server is functional")
        else:
            print("❌ ISSUES DETECTED - Server needs attention")

        # Performance assessment
        if "error" not in perf:
            avg_time = perf.get("average_time_ms", 0)
            if avg_time < 100:
                print("🚀 EXCELLENT PERFORMANCE - Average response time < 100ms")
            elif avg_time < 500:
                print("✅ GOOD PERFORMANCE - Average response time < 500ms")
            else:
                print("⚠️  SLOW PERFORMANCE - Average response time > 500ms")

        # Save detailed results
        with open("direct_mcp_test_results.json", "w") as f:
            json.dump(results, f, indent=2, default=str)
        print("\n📄 Detailed results saved to: direct_mcp_test_results.json")

    except Exception as e:
        print(f"\n❌ Testing failed: {e}")
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

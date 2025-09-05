#!/usr/bin/env python3
"""
Mock LLM-MCP Integration Testing Suite

This script simulates an LLM client interacting with MCP tools to test
functionality, error handling, and performance without the MCP protocol overhead.
"""

import asyncio
import json
import time
import sys
import os
from typing import Dict, Any, List, Callable
import traceback
from dataclasses import dataclass

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from quilt_mcp.utils import create_mcp_server, register_tools


@dataclass
class MockToolCall:
    """Represents a tool call from an LLM"""

    name: str
    arguments: Dict[str, Any]
    call_id: str = "mock_call"


@dataclass
class MockToolResult:
    """Represents the result of a tool call"""

    success: bool
    content: Any
    execution_time_ms: float
    error: str = None


class MockLLMClient:
    """Mock LLM client that simulates Claude/GPT calling MCP tools"""

    def __init__(self):
        self.server = None
        self.tools: Dict[str, Callable] = {}
        # Setup will be called async from the tester

    async def setup_mcp_connection(self):
        """Simulate connecting to MCP server and getting tools"""
        print("🔌 Establishing mock MCP connection...")
        try:
            self.server = create_mcp_server()
            tool_count = register_tools(self.server, verbose=False)

            # Extract callable tools
            self.tools = await self.server.get_tools()

            print(f"✅ Connected to MCP server with {tool_count} tools")
            print(f"✅ Available for LLM routing: {len(self.tools)} callable tools")

        except Exception as e:
            print(f"❌ MCP connection failed: {e}")
            raise

    async def call_tool(self, tool_call: MockToolCall) -> MockToolResult:
        """Simulate LLM calling an MCP tool"""
        start_time = time.time()

        try:
            if tool_call.name not in self.tools:
                raise ValueError(f"Tool '{tool_call.name}' not available to LLM")

            tool_obj = self.tools[tool_call.name]

            # Simulate LLM routing the call to the MCP tool
            # FunctionTool objects have a 'run' method
            if hasattr(tool_obj, 'run'):
                result = await tool_obj.run(**tool_call.arguments)
            elif callable(tool_obj):
                if asyncio.iscoroutinefunction(tool_obj):
                    result = await tool_obj(**tool_call.arguments)
                else:
                    result = tool_obj(**tool_call.arguments)
            else:
                raise ValueError(f"Tool '{tool_call.name}' is not callable")

            end_time = time.time()

            return MockToolResult(
                success=True, content=result, execution_time_ms=round((end_time - start_time) * 1000, 2)
            )

        except Exception as e:
            end_time = time.time()
            return MockToolResult(
                success=False, content=None, execution_time_ms=round((end_time - start_time) * 1000, 2), error=str(e)
            )

    def get_available_tools(self) -> List[str]:
        """Get list of tools available to the LLM"""
        return list(self.tools.keys())

    async def simulate_llm_conversation(self, user_query: str) -> Dict[str, Any]:
        """Simulate an LLM processing a user query and calling appropriate tools"""
        print(f"\n🤖 LLM processing query: '{user_query}'")

        # Simulate LLM deciding which tools to call based on the query
        tool_calls = self._analyze_query_and_select_tools(user_query)

        results = []
        for tool_call in tool_calls:
            print(f"   🔧 LLM calling tool: {tool_call.name}")
            result = await self.call_tool(tool_call)
            results.append({"tool_call": tool_call, "result": result})

            if result.success:
                print(f"   ✅ Tool succeeded: {result.execution_time_ms}ms")
            else:
                print(f"   ❌ Tool failed: {result.error}")

        return {"user_query": user_query, "tool_calls": results, "total_tools_called": len(results)}

    def _analyze_query_and_select_tools(self, query: str) -> List[MockToolCall]:
        """Simulate LLM analyzing query and selecting appropriate tools"""
        query_lower = query.lower()
        tool_calls = []

        # Simulate different LLM decision patterns
        if "auth" in query_lower or "status" in query_lower:
            tool_calls.append(MockToolCall("auth_status", {}))  # No parameters needed

        if "search" in query_lower or "find" in query_lower:
            if "csv" in query_lower:
                tool_calls.append(MockToolCall("packages_search", {"query": "csv", "limit": 5}))
            elif "data" in query_lower:
                tool_calls.append(MockToolCall("packages_search", {"query": "data", "limit": 3}))

            # Try unified search if available
            if "unified_search" in self.tools:
                tool_calls.append(
                    MockToolCall(
                        "unified_search", {"query": query, "scope": "catalog", "limit": 3, "explain_query": True}
                    )
                )

        if "list" in query_lower or "packages" in query_lower:
            tool_calls.append(MockToolCall("packages_list", {"limit": 5}))

        if "bucket" in query_lower:
            tool_calls.append(
                MockToolCall(
                    "bucket_objects_search", {"bucket": "s3://quilt-sandbox-bucket", "query": "data", "limit": 3}
                )
            )

        # Default fallback
        if not tool_calls:
            tool_calls.append(MockToolCall("catalog_info", {}))  # No parameters needed

        return tool_calls


class MockLLMMCPTester:
    """Comprehensive tester for LLM-MCP integration"""

    def __init__(self):
        self.llm_client = MockLLMClient()

    async def initialize(self):
        """Initialize the LLM client connection"""
        await self.llm_client.setup_mcp_connection()

    async def test_basic_functionality(self) -> Dict[str, Any]:
        """Test basic functionality through LLM routing"""
        print("\n📋 Testing basic functionality via LLM routing...")

        # Simulate various user queries that would trigger basic tools
        test_queries = ["What's my authentication status?", "Check system status", "Get catalog information"]

        results = []
        for query in test_queries:
            result = await self.llm_client.simulate_llm_conversation(query)
            results.append(result)

        return {"basic_tests": results}

    async def test_search_functionality(self) -> Dict[str, Any]:
        """Test search functionality through LLM routing"""
        print("\n🔍 Testing search functionality via LLM routing...")

        # Simulate search-related queries
        search_queries = [
            "Find CSV files in the catalog",
            "Search for data packages",
            "List available packages",
            "Search bucket for data files",
        ]

        results = []
        for query in search_queries:
            result = await self.llm_client.simulate_llm_conversation(query)
            results.append(result)

        return {"search_tests": results}

    async def test_unified_search_architecture(self) -> Dict[str, Any]:
        """Test unified search architecture through LLM"""
        print("\n🏗️  Testing unified search architecture via LLM...")

        # Test unified search specifically
        unified_queries = [
            "Find genomics data using unified search",
            "Search for CSV files with advanced capabilities",
            "Use intelligent search to find research datasets",
        ]

        results = []
        for query in unified_queries:
            result = await self.llm_client.simulate_llm_conversation(query)
            results.append(result)

        return {"unified_search_tests": results}

    async def test_error_handling(self) -> Dict[str, Any]:
        """Test error handling through LLM routing"""
        print("\n⚠️  Testing error handling via LLM routing...")

        # Test error cases by calling tools with invalid parameters
        error_tests = [
            MockToolCall("packages_search", {"query": "", "limit": -1}),
            MockToolCall("nonexistent_tool", {"any": "args"}),
            MockToolCall("bucket_objects_search", {"bucket": "invalid-bucket"}),
            MockToolCall("auth_status", {}),  # Missing required param
        ]

        results = []
        for tool_call in error_tests:
            print(f"   Testing error case: {tool_call.name}")
            result = await self.llm_client.call_tool(tool_call)
            results.append({"tool_call": tool_call, "result": result})

            if not result.success:
                print(f"   ✅ Error handled: {result.execution_time_ms}ms")
            elif result.success and isinstance(result.content, dict) and not result.content.get("success"):
                print(f"   ✅ Error in result: {result.execution_time_ms}ms")
            else:
                print(f"   ⚠️  Unexpected success: {result.execution_time_ms}ms")

        return {"error_tests": results}

    async def test_performance(self) -> Dict[str, Any]:
        """Test performance with concurrent LLM requests"""
        print("\n⚡ Testing performance via concurrent LLM calls...")

        # Simulate multiple LLM instances making concurrent requests
        concurrent_queries = [
            "Check auth status",
            "Search for data",
            "List packages",
            "Get catalog info",
            "Find CSV files",
        ]

        print("   Simulating 5 concurrent LLM conversations...")
        start_time = time.time()

        tasks = [self.llm_client.simulate_llm_conversation(query) for query in concurrent_queries]

        results = await asyncio.gather(*tasks)
        end_time = time.time()

        total_time = round((end_time - start_time) * 1000, 2)

        # Analyze results
        total_tool_calls = sum(r["total_tools_called"] for r in results)
        successful_conversations = sum(1 for r in results if any(tc["result"].success for tc in r["tool_calls"]))

        # Calculate average tool response time
        all_tool_times = []
        for conversation in results:
            for tool_call in conversation["tool_calls"]:
                all_tool_times.append(tool_call["result"].execution_time_ms)

        avg_tool_time = round(sum(all_tool_times) / len(all_tool_times), 2) if all_tool_times else 0

        print(f"   ✅ Concurrent test: {successful_conversations}/5 conversations successful")
        print(f"   ✅ Total time: {total_time}ms, Total tool calls: {total_tool_calls}")
        print(f"   ✅ Average tool response time: {avg_tool_time}ms")

        return {
            "concurrent_test": {
                "total_conversations": 5,
                "successful_conversations": successful_conversations,
                "total_time_ms": total_time,
                "total_tool_calls": total_tool_calls,
                "average_tool_time_ms": avg_tool_time,
                "results": results,
            }
        }

    async def test_tool_availability(self) -> Dict[str, Any]:
        """Test tool availability and registration"""
        print("\n📚 Testing tool availability for LLM...")

        available_tools = self.llm_client.get_available_tools()

        # Check for key tools
        key_tools = ["auth_status", "packages_search", "packages_list", "bucket_objects_search", "unified_search"]

        found_tools = [tool for tool in key_tools if tool in available_tools]
        missing_tools = [tool for tool in key_tools if tool not in available_tools]

        print(f"   ✅ Total tools available: {len(available_tools)}")
        print(f"   ✅ Key tools found: {len(found_tools)}/{len(key_tools)}")

        if missing_tools:
            print(f"   ⚠️  Missing key tools: {missing_tools}")

        return {
            "total_tools": len(available_tools),
            "key_tools_found": found_tools,
            "missing_tools": missing_tools,
            "all_tools": available_tools[:20],  # First 20 for brevity
        }

    async def run_comprehensive_test(self) -> Dict[str, Any]:
        """Run comprehensive LLM-MCP integration test"""
        print("🧪 Starting comprehensive Mock LLM-MCP integration testing...")

        test_results = {
            "timestamp": time.time(),
            "test_type": "Mock LLM-MCP Integration",
            "llm_client_info": {"tools_available": len(self.llm_client.get_available_tools())},
        }

        # Run all test suites
        test_results["tool_availability"] = await self.test_tool_availability()
        test_results["basic_functionality"] = await self.test_basic_functionality()
        test_results["search_functionality"] = await self.test_search_functionality()
        test_results["unified_search_architecture"] = await self.test_unified_search_architecture()
        test_results["error_handling"] = await self.test_error_handling()
        test_results["performance"] = await self.test_performance()

        return test_results


async def main():
    """Main test runner"""
    print("=" * 70)
    print("🔬 MOCK LLM-MCP INTEGRATION TESTING SUITE")
    print("=" * 70)

    try:
        tester = MockLLMMCPTester()
        await tester.initialize()
        results = await tester.run_comprehensive_test()

        print("\n" + "=" * 70)
        print("📊 MOCK LLM-MCP INTEGRATION TEST RESULTS")
        print("=" * 70)

        # Tool availability summary
        tools = results["tool_availability"]
        print("📚 Tool Availability:")
        print(f"   Total tools: {tools['total_tools']}")
        print(
            f"   Key tools: {len(tools['key_tools_found'])}/{len(tools['key_tools_found']) + len(tools['missing_tools'])}"
        )

        # Functionality tests summary
        basic = results["basic_functionality"]["basic_tests"]
        successful_basic = sum(1 for test in basic if any(tc["result"].success for tc in test["tool_calls"]))

        search = results["search_functionality"]["search_tests"]
        successful_search = sum(1 for test in search if any(tc["result"].success for tc in test["tool_calls"]))

        unified = results["unified_search_architecture"]["unified_search_tests"]
        successful_unified = sum(1 for test in unified if any(tc["result"].success for tc in test["tool_calls"]))

        print("\n🤖 LLM Routing Tests:")
        print(f"   Basic functionality: {successful_basic}/{len(basic)} conversations successful")
        print(f"   Search functionality: {successful_search}/{len(search)} conversations successful")
        print(f"   Unified search: {successful_unified}/{len(unified)} conversations successful")

        # Error handling summary
        error_tests = results["error_handling"]["error_tests"]
        handled_errors = sum(
            1
            for test in error_tests
            if not test["result"].success
            or (
                test["result"].success
                and isinstance(test["result"].content, dict)
                and not test["result"].content.get("success")
            )
        )

        print(f"   Error handling: {handled_errors}/{len(error_tests)} errors properly handled")

        # Performance summary
        perf = results["performance"]["concurrent_test"]
        print("\n⚡ Performance Results:")
        print(f"   Concurrent conversations: {perf['successful_conversations']}/5 successful")
        print(f"   Total tool calls: {perf['total_tool_calls']}")
        print(f"   Average tool response: {perf['average_tool_time_ms']}ms")

        # Overall assessment
        tool_availability_ok = len(tools['key_tools_found']) >= 4
        functionality_ok = (successful_basic + successful_search + successful_unified) >= 6
        error_handling_ok = handled_errors >= len(error_tests) * 0.8
        performance_ok = perf['successful_conversations'] >= 4 and perf['average_tool_time_ms'] < 1000

        categories_passed = sum([tool_availability_ok, functionality_ok, error_handling_ok, performance_ok])

        print(f"\n🎯 Overall Assessment: {categories_passed}/4 categories passed")

        if categories_passed == 4:
            print("✅ EXCELLENT - MCP server works perfectly with LLM routing!")
            print("✅ Tool availability: ✓")
            print("✅ LLM routing: ✓")
            print("✅ Error handling: ✓")
            print("✅ Performance: ✓")
        elif categories_passed >= 3:
            print("⚠️  GOOD - MCP server is functional with minor issues")
        else:
            print("❌ ISSUES DETECTED - MCP server needs attention")

        # Efficiency assessment
        avg_time = perf['average_tool_time_ms']
        if avg_time < 50:
            print("🚀 HIGHLY EFFICIENT - Sub-50ms average tool response")
        elif avg_time < 200:
            print("✅ EFFICIENT - Good tool response times")
        else:
            print("⚠️  SLOW - Tool response times could be improved")

        # Save detailed results
        with open("mock_llm_mcp_test_results.json", "w") as f:
            json.dump(results, f, indent=2, default=str)
        print("\n📄 Detailed results saved to: mock_llm_mcp_test_results.json")

        return 0 if categories_passed >= 3 else 1

    except Exception as e:
        print(f"\n❌ Testing failed: {e}")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

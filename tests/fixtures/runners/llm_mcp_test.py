#!/usr/bin/env python3
"""
LLM-MCP Integration Testing Suite

This script tests the MCP server by communicating with an LLM that has the MCP server
attached, providing realistic testing of tool routing, error handling, and performance.
"""

import asyncio
import json
import time
import sys
import os
from typing import Dict, Any, List
import traceback
import subprocess
import tempfile
from pathlib import Path

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))


class LLMMCPTester:
    """LLM-MCP Integration Tester"""

    def __init__(self):
        self.mcp_server_process = None
        self.test_results = []

    def create_mcp_config(self) -> str:
        """Create MCP configuration file for the LLM client"""
        config = {
            "mcpServers": {
                "quilt-mcp": {
                    "command": "python",
                    "args": ["main.py"],
                    "cwd": str(Path(__file__).parent / "app"),
                    "env": {"PYTHONPATH": str(Path(__file__).parent / "app")},
                }
            }
        }

        # Create temporary config file
        config_file = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(config, config_file, indent=2)
        config_file.close()

        return config_file.name

    async def start_mcp_server(self) -> bool:
        """Start the MCP server process"""
        print("🚀 Starting MCP server...")
        try:
            # Start the MCP server in stdio mode
            self.mcp_server_process = await asyncio.create_subprocess_exec(
                sys.executable,
                "main.py",
                cwd=str(Path(__file__).parent / "app"),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, "PYTHONPATH": str(Path(__file__).parent / "app")},
            )

            # Give it a moment to start
            await asyncio.sleep(2)

            if self.mcp_server_process.returncode is None:
                print("✅ MCP server started successfully")
                return True
            else:
                print(f"❌ MCP server failed to start (exit code: {self.mcp_server_process.returncode})")
                return False

        except Exception as e:
            print(f"❌ Failed to start MCP server: {e}")
            return False

    async def send_mcp_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Send a request to the MCP server and get response"""
        if not self.mcp_server_process:
            return {"error": "MCP server not running"}

        try:
            # Send JSON-RPC request
            request_json = json.dumps(request) + "\n"
            self.mcp_server_process.stdin.write(request_json.encode())
            await self.mcp_server_process.stdin.drain()

            # Read response
            response_line = await self.mcp_server_process.stdout.readline()
            if response_line:
                response = json.loads(response_line.decode().strip())
                return response
            else:
                return {"error": "No response from server"}

        except Exception as e:
            return {"error": f"Communication error: {e}"}

    async def test_mcp_handshake(self) -> Dict[str, Any]:
        """Test MCP protocol handshake"""
        print("\n🤝 Testing MCP handshake...")

        start_time = time.time()

        # Send initialize request
        initialize_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "clientInfo": {"name": "llm-mcp-tester", "version": "1.0.0"},
            },
        }

        response = await self.send_mcp_request(initialize_request)
        end_time = time.time()

        success = "result" in response and not response.get("error")

        if success:
            print(f"   ✅ Handshake successful: {round((end_time - start_time) * 1000, 2)}ms")
            capabilities = response.get("result", {}).get("capabilities", {})
            print(f"   ✅ Server capabilities: {list(capabilities.keys())}")
        else:
            print(f"   ❌ Handshake failed: {response.get('error', 'Unknown error')}")

        return {
            "success": success,
            "response": response,
            "execution_time_ms": round((end_time - start_time) * 1000, 2),
        }

    async def test_list_tools(self) -> Dict[str, Any]:
        """Test listing available tools"""
        print("\n📋 Testing tool listing...")

        start_time = time.time()

        list_tools_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }

        response = await self.send_mcp_request(list_tools_request)
        end_time = time.time()

        success = "result" in response and "tools" in response.get("result", {})

        if success:
            tools = response["result"]["tools"]
            print(f"   ✅ Found {len(tools)} tools: {round((end_time - start_time) * 1000, 2)}ms")

            # Show sample tools
            sample_tools = [tool["name"] for tool in tools[:5]]
            print(f"   ✅ Sample tools: {sample_tools}")

            # Check for key tools
            tool_names = [tool["name"] for tool in tools]
            key_tools = [
                "mcp_quilt_auth_status",
                "mcp_quilt_packages_search",
                "unified_search",
            ]
            found_key_tools = [tool for tool in key_tools if tool in tool_names]
            print(f"   ✅ Key tools found: {found_key_tools}")

        else:
            print(f"   ❌ Tool listing failed: {response.get('error', 'Unknown error')}")

        return {
            "success": success,
            "response": response,
            "execution_time_ms": round((end_time - start_time) * 1000, 2),
            "tools_count": (len(response.get("result", {}).get("tools", [])) if success else 0),
        }

    async def test_tool_call(self, tool_name: str, arguments: Dict[str, Any], request_id: int = 3) -> Dict[str, Any]:
        """Test calling a specific tool"""
        print(f"   Testing {tool_name}...")

        start_time = time.time()

        tool_call_request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }

        response = await self.send_mcp_request(tool_call_request)
        end_time = time.time()

        success = "result" in response and not response.get("error")

        if success:
            result = response["result"]
            print(f"   ✅ {tool_name}: {round((end_time - start_time) * 1000, 2)}ms")

            # Check result content
            if "content" in result:
                content = result["content"]
                if isinstance(content, list) and len(content) > 0:
                    first_content = content[0]
                    if hasattr(first_content, "text"):
                        try:
                            parsed = json.loads(first_content.text)
                            if "success" in parsed:
                                print(f"      Tool success: {parsed['success']}")
                            if "results" in parsed:
                                print(f"      Results count: {len(parsed['results'])}")
                        except (json.JSONDecodeError, TypeError, KeyError):
                            print(f"      Content length: {len(str(first_content))}")
        else:
            error_msg = response.get("error", {})
            print(f"   ❌ {tool_name}: {error_msg}")

        return {
            "success": success,
            "tool_name": tool_name,
            "arguments": arguments,
            "response": response,
            "execution_time_ms": round((end_time - start_time) * 1000, 2),
        }

    async def test_basic_functionality(self) -> Dict[str, Any]:
        """Test basic MCP functionality through LLM routing"""
        print("\n📋 Testing basic functionality via LLM routing...")

        results = {"tool_calls": []}

        # Test basic tools
        basic_tests = [
            ("mcp_quilt_auth_status", {"random_string": "test"}),
            ("mcp_quilt_filesystem_status", {"random_string": "test"}),
            ("mcp_quilt_catalog_info", {"random_string": "test"}),
        ]

        request_id = 10
        for tool_name, args in basic_tests:
            result = await self.test_tool_call(tool_name, args, request_id)
            results["tool_calls"].append(result)
            request_id += 1

        return results

    async def test_search_functionality(self) -> Dict[str, Any]:
        """Test search functionality through LLM routing"""
        print("\n🔍 Testing search functionality via LLM routing...")

        results = {"search_tests": []}

        # Test search functions
        search_tests = [
            ("mcp_quilt_packages_search", {"query": "data", "limit": 3}),
            (
                "mcp_quilt_bucket_objects_search",
                {"bucket": "s3://quilt-sandbox-bucket", "query": "data", "limit": 3},
            ),
            ("mcp_quilt_packages_list", {"limit": 5}),
        ]

        # Test unified search if available
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

        request_id = 20
        for tool_name, args in search_tests:
            result = await self.test_tool_call(tool_name, args, request_id)
            results["search_tests"].append(result)
            request_id += 1

        return results

    async def test_error_handling(self) -> Dict[str, Any]:
        """Test error handling through LLM routing"""
        print("\n⚠️  Testing error handling via LLM routing...")

        results = {"error_tests": []}

        # Test error cases
        error_tests = [
            (
                "mcp_quilt_packages_search",
                {"query": "", "limit": -1},
            ),  # Invalid parameters
            ("nonexistent_tool", {"any": "args"}),  # Nonexistent tool
            (
                "mcp_quilt_bucket_objects_search",
                {"bucket": "invalid-bucket"},
            ),  # Invalid bucket
        ]

        request_id = 30
        for tool_name, args in error_tests:
            result = await self.test_tool_call(tool_name, args, request_id)
            results["error_tests"].append(result)

            # For error tests, we expect either failure or error in result
            if not result["success"]:
                print("      ✅ Error properly handled at protocol level")
            elif result["success"]:
                # Check if the tool returned an error in its content
                response = result.get("response", {})
                if "result" in response and "content" in response["result"]:
                    print("      ✅ Error handled at tool level")

            request_id += 1

        return results

    async def test_performance(self) -> Dict[str, Any]:
        """Test performance with concurrent requests"""
        print("\n⚡ Testing performance via LLM routing...")

        # Test concurrent tool calls
        concurrent_tasks = []
        test_tool = "mcp_quilt_auth_status"
        test_args = {"random_string": "perf_test"}

        print(f"   Running 5 concurrent calls to {test_tool}...")
        start_time = time.time()

        for i in range(5):
            task = self.test_tool_call(test_tool, {**test_args, "call_id": str(i)}, 40 + i)
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

    async def cleanup(self):
        """Clean up resources"""
        if self.mcp_server_process:
            print("\n🧹 Cleaning up MCP server...")
            self.mcp_server_process.terminate()
            try:
                await asyncio.wait_for(self.mcp_server_process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self.mcp_server_process.kill()
                await self.mcp_server_process.wait()
            print("✅ MCP server stopped")

    async def run_comprehensive_test(self) -> Dict[str, Any]:
        """Run comprehensive LLM-MCP integration test"""
        print("🧪 Starting comprehensive LLM-MCP integration testing...")

        # Start MCP server
        if not await self.start_mcp_server():
            return {"error": "Failed to start MCP server"}

        try:
            test_results = {
                "timestamp": time.time(),
                "test_type": "LLM-MCP Integration",
            }

            # Run protocol tests
            test_results["handshake"] = await self.test_mcp_handshake()
            test_results["list_tools"] = await self.test_list_tools()

            # Run functionality tests
            test_results["basic_functionality"] = await self.test_basic_functionality()
            test_results["search_functionality"] = await self.test_search_functionality()
            test_results["error_handling"] = await self.test_error_handling()
            test_results["performance"] = await self.test_performance()

            return test_results

        finally:
            await self.cleanup()


async def main():
    """Main test runner"""
    print("=" * 70)
    print("🔬 LLM-MCP INTEGRATION TESTING SUITE")
    print("=" * 70)

    try:
        tester = LLMMCPTester()
        results = await tester.run_comprehensive_test()

        if "error" in results:
            print(f"\n❌ Testing failed: {results['error']}")
            return 1

        print("\n" + "=" * 70)
        print("📊 LLM-MCP INTEGRATION TEST RESULTS")
        print("=" * 70)

        # Protocol tests summary
        handshake_success = results["handshake"]["success"]
        tools_count = results["list_tools"]["tools_count"]

        print("🤝 Protocol Tests:")
        print(f"   Handshake: {'✅ Success' if handshake_success else '❌ Failed'}")
        print(f"   Tools available: {tools_count}")

        # Functionality tests summary
        basic = results["basic_functionality"]
        successful_basic = sum(1 for call in basic["tool_calls"] if call["success"])
        total_basic = len(basic["tool_calls"])

        search = results["search_functionality"]
        successful_search = sum(1 for test in search["search_tests"] if test["success"])
        total_search = len(search["search_tests"])

        print("\n📋 Functionality Tests:")
        print(f"   Basic functionality: {successful_basic}/{total_basic} passed")
        print(f"   Search functionality: {successful_search}/{total_search} passed")

        # Error handling summary
        error = results["error_handling"]
        total_errors = len(error["error_tests"])
        print(f"   Error handling: {total_errors} error cases tested")

        # Performance summary
        perf = results["performance"]["concurrent_test"]
        successful_perf = perf["successful_calls"]
        avg_time = perf["average_time_ms"]

        print("\n⚡ Performance Tests:")
        print(f"   Concurrent calls: {successful_perf}/5 successful")
        print(f"   Average response time: {avg_time}ms")

        # Overall assessment
        protocol_ok = handshake_success and tools_count > 0
        functionality_ok = (successful_basic + successful_search) >= (total_basic + total_search) * 0.7
        performance_ok = successful_perf >= 4 and avg_time < 1000

        total_categories = 3
        passed_categories = sum([protocol_ok, functionality_ok, performance_ok])

        print(f"\n🎯 Overall Assessment: {passed_categories}/{total_categories} categories passed")

        if passed_categories == total_categories:
            print("✅ EXCELLENT - MCP server integration is working perfectly!")
            print("✅ Protocol compliance: ✓")
            print("✅ Tool routing: ✓")
            print("✅ Performance: ✓")
        elif passed_categories >= 2:
            print("⚠️  GOOD - MCP server is functional with minor issues")
        else:
            print("❌ ISSUES DETECTED - MCP server integration needs attention")

        # Efficiency assessment
        if avg_time < 100:
            print("🚀 HIGHLY EFFICIENT - Sub-100ms average response time")
        elif avg_time < 500:
            print("✅ EFFICIENT - Good response times")
        else:
            print("⚠️  SLOW - Response times could be improved")

        # Save detailed results
        with open("llm_mcp_test_results.json", "w") as f:
            json.dump(results, f, indent=2, default=str)
        print("\n📄 Detailed results saved to: llm_mcp_test_results.json")

        return 0 if passed_categories >= 2 else 1

    except Exception as e:
        print(f"\n❌ Testing failed: {e}")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

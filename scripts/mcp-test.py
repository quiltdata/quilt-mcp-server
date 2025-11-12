#!/usr/bin/env python3
"""
Modern MCP endpoint testing tool.

Replaces the legacy bash script with a cleaner Python implementation
using requests library for HTTP handling and proper JSON schema validation.
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import yaml
from jsonschema import validate


class MCPTester:
    """MCP endpoint testing client with JSON-RPC support."""
    
    def __init__(self, endpoint: str, verbose: bool = False):
        self.endpoint = endpoint
        self.verbose = verbose
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json, text/event-stream'
        })
        self.request_id = 1
        
    def _log(self, message: str, level: str = "INFO") -> None:
        """Log message with timestamp."""
        if level == "DEBUG" and not self.verbose:
            return
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        prefix = "🔍" if level == "DEBUG" else "ℹ️" if level == "INFO" else "❌"
        print(f"[{timestamp}] {prefix} {message}")
        
    def _make_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make JSON-RPC request to MCP endpoint."""
        request_data = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method
        }
        if params:
            request_data["params"] = params

        self.request_id += 1

        self._log(f"Making request: {method}", "DEBUG")
        if self.verbose and params:
            self._log(f"Params: {json.dumps(params, indent=2)}", "DEBUG")

        try:
            response = self.session.post(
                self.endpoint,
                json=request_data,
                timeout=10
            )
            response.raise_for_status()

            # Handle SSE (Server-Sent Events) response format
            content_type = response.headers.get('content-type', '')
            if 'text/event-stream' in content_type:
                # Parse SSE format: "event: message\ndata: {...}"
                text = response.text.strip()
                lines = text.split('\n')
                json_data = None

                for line in lines:
                    if line.startswith('data: '):
                        json_data = line[6:]  # Remove "data: " prefix
                        break

                if json_data:
                    result = json.loads(json_data)
                else:
                    raise Exception("No data field found in SSE response")
            else:
                # Regular JSON response
                result = response.json()

            self._log(f"Response: {json.dumps(result, indent=2)}", "DEBUG")

            if "error" in result:
                raise Exception(f"JSON-RPC error: {result['error']}")

            return result.get("result", {})

        except requests.exceptions.RequestException as e:
            raise Exception(f"HTTP request failed: {e}")
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid JSON response: {e}")
    
    def initialize(self) -> Dict[str, Any]:
        """Initialize MCP session."""
        self._log("Initializing MCP session...")
        
        params = {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "mcp-test",
                "version": "1.0.0"
            }
        }
        
        result = self._make_request("initialize", params)
        self._log("✅ Session initialized successfully")
        return result
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools from MCP server."""
        self._log("Querying available tools...")
        
        result = self._make_request("tools/list")
        tools = result.get("tools", [])
        
        self._log(f"✅ Found {len(tools)} tools")
        return tools
    
    def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Call a specific tool."""
        self._log(f"Calling tool: {name}")

        params: Dict[str, Any] = {"name": name}
        if arguments:
            params["arguments"] = arguments

        result = self._make_request("tools/call", params)
        self._log(f"✅ Tool {name} executed successfully")
        return result

    def list_resources(self) -> List[Dict[str, Any]]:
        """List available resources from MCP server."""
        self._log("Querying available resources...")

        result = self._make_request("resources/list")
        resources = result.get("resources", [])

        self._log(f"✅ Found {len(resources)} resources")
        return resources

    def read_resource(self, uri: str) -> Dict[str, Any]:
        """Read a specific resource."""
        self._log(f"Reading resource: {uri}")

        params = {"uri": uri}
        result = self._make_request("resources/read", params)

        self._log(f"✅ Resource {uri} read successfully")
        return result


def load_test_config(config_path: Path) -> Dict[str, Any]:
    """Load test configuration from YAML file."""
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"❌ Test config not found: {config_path}")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"❌ Invalid YAML config: {e}")
        sys.exit(1)


def run_tools_test(tester: MCPTester, config: Dict[str, Any], specific_tool: Optional[str] = None) -> tuple[bool, Dict[str, Any]]:
    """Run comprehensive tools test.

    Returns:
        Tuple of (success: bool, results: Dict with detailed test information)
    """
    test_tools = config.get("test_tools", {})

    if specific_tool:
        if specific_tool not in test_tools:
            print(f"❌ Tool '{specific_tool}' not found in test config")
            return False, {}
        test_tools = {specific_tool: test_tools[specific_tool]}

    success_count = 0
    total_count = len(test_tools)

    # Track tools by effect type
    all_side_effects = set()  # Tools with side effects (not 'none')
    tested_side_effects = set()

    # Track detailed results
    failed_tests = []
    passed_tests = []

    # First pass: identify all tools with side effects in config
    for tool_name, tool_config in config.get("test_tools", {}).items():
        effect = tool_config.get("effect", "none")
        if effect != "none":
            all_side_effects.add(tool_name)

    print(f"\n🧪 Running tools test ({total_count} tools)...")

    for tool_name, test_config in test_tools.items():
        try:
            print(f"\n--- Testing tool: {tool_name} ---")

            # Get test arguments
            test_args = test_config.get("arguments", {})

            # Get actual tool name (for variants, use "tool" field)
            actual_tool_name = test_config.get("tool", tool_name)

            # Call the tool
            result = tester.call_tool(actual_tool_name, test_args)

            # Validate response if schema provided
            if "response_schema" in test_config:
                validate(result, test_config["response_schema"])
                tester._log("✅ Response schema validation passed")

            success_count += 1
            print(f"✅ {tool_name}: PASSED")

            passed_tests.append({
                "name": tool_name,
                "actual_tool": actual_tool_name,
                "arguments": test_args,
                "result": result
            })

            # Track if tool with side effects was tested
            effect = test_config.get("effect", "none")
            if effect != "none":
                tested_side_effects.add(tool_name)

        except Exception as e:
            print(f"❌ {tool_name}: FAILED - {e}")

            failed_tests.append({
                "name": tool_name,
                "actual_tool": test_config.get("tool", tool_name),
                "arguments": test_config.get("arguments", {}),
                "error": str(e),
                "error_type": type(e).__name__
            })

    print(f"\n📊 Test Results: {success_count}/{total_count} tools passed")

    # Report untested tools with side effects
    untested_side_effects = all_side_effects - tested_side_effects
    if untested_side_effects:
        print(f"\n⚠️  Tools with side effects NOT tested ({len(untested_side_effects)}):")
        for tool in sorted(untested_side_effects):
            # Get effect type for each untested tool
            effect = config.get("test_tools", {}).get(tool, {}).get("effect", "unknown")
            print(f"  • {tool} (effect: {effect})")
    elif all_side_effects:
        print(f"\n✅ All {len(all_side_effects)} tools with side effects were tested")

    results = {
        "total": total_count,
        "passed": success_count,
        "failed": len(failed_tests),
        "passed_tests": passed_tests,
        "failed_tests": failed_tests,
        "untested_side_effects": sorted(untested_side_effects)
    }

    return success_count == total_count, results


def run_resources_test(
    tester: MCPTester,
    config: Dict[str, Any],
    specific_resource: Optional[str] = None
) -> tuple[bool, Dict[str, Any]]:
    """Run comprehensive resources test.

    Returns:
        Tuple of (success: bool, results: Dict with detailed test information)
    """
    test_resources = config.get("test_resources", {})

    if specific_resource:
        if specific_resource not in test_resources:
            print(f"❌ Resource '{specific_resource}' not found in test config")
            return False, {}
        test_resources = {specific_resource: test_resources[specific_resource]}

    if not test_resources:
        print("⚠️  No resources configured for testing")
        return True, {"total": 0, "passed": 0, "failed": 0, "skipped": 0}

    success_count = 0
    fail_count = 0
    skip_count = 0
    total_count = len(test_resources)

    # Track detailed results
    passed_tests = []
    failed_tests = []
    skipped_tests = []

    print(f"\n🗂️  Running resources test ({total_count} resources)...")

    # First, list available resources and templates
    try:
        result = tester.list_resources()

        # FastMCP returns both 'resources' (static) and 'resourceTemplates' (templated)
        available_resources = result.get("resources", [])
        available_templates = result.get("resourceTemplates", [])

        # Combine URIs from both lists
        available_uris = {r["uri"] for r in available_resources}
        available_template_patterns = {t["uriTemplate"] for t in available_templates}

        print(f"📋 Server provides {len(available_resources)} static resources, {len(available_templates)} templates")
    except Exception as e:
        print(f"❌ Failed to list resources: {e}")
        return False

    # Test each resource
    for uri_pattern, test_config in test_resources.items():
        try:
            print(f"\n--- Testing resource: {uri_pattern} ---")

            # Substitute URI variables if needed
            uri = uri_pattern
            uri_vars = test_config.get("uri_variables", {})
            skip_resource = False

            for var_name, var_value in uri_vars.items():
                if var_value.startswith("CONFIGURE_"):
                    skip_count += 1
                    print(f"  ⏭️  Skipped (needs configuration: {var_name})")
                    skip_resource = True
                    skipped_tests.append({
                        "uri": uri_pattern,
                        "reason": f"Needs configuration: {var_name}",
                        "config_needed": var_name
                    })
                    break
                uri = uri.replace(f"{{{var_name}}}", var_value)

            if skip_resource:
                continue

            # Check if resource exists (check both static resources and templates)
            is_templated = '{' in uri_pattern
            if is_templated:
                # For templates, check if the pattern is in resourceTemplates
                if uri_pattern not in available_template_patterns:
                    fail_count += 1
                    error_msg = "Template not found in server resourceTemplates"
                    print(f"  ❌ {error_msg}")
                    failed_tests.append({
                        "uri": uri_pattern,
                        "resolved_uri": uri,
                        "error": error_msg,
                        "uri_variables": uri_vars
                    })
                    continue
            else:
                # For static resources, check if URI is in resources list
                if uri not in available_uris:
                    fail_count += 1
                    error_msg = "Resource not found in server resources"
                    print(f"  ❌ {error_msg}")
                    failed_tests.append({
                        "uri": uri_pattern,
                        "resolved_uri": uri,
                        "error": error_msg,
                        "uri_variables": uri_vars
                    })
                    continue

            # Read the resource
            result = tester.read_resource(uri)

            # Validate resource content
            contents = result.get("contents", [])
            if not contents:
                fail_count += 1
                error_msg = "Empty contents"
                print(f"  ❌ {error_msg}")
                failed_tests.append({
                    "uri": uri_pattern,
                    "resolved_uri": uri,
                    "error": error_msg,
                    "result": result
                })
                continue

            content = contents[0]

            # Validate MIME type
            expected_mime = test_config.get("expected_mime_type", "text/plain")
            actual_mime = content.get("mimeType", "text/plain")

            mime_mismatch = None
            if expected_mime != actual_mime:
                mime_mismatch = f"expected {expected_mime}, got {actual_mime}"
                print(f"  ⚠️  MIME type mismatch ({mime_mismatch})")

            # Validate content based on type
            validation = test_config.get("content_validation", {})
            content_type = validation.get("type", "text")
            validation_error = None

            if content_type == "text":
                text = content.get("text", "")
                min_len = validation.get("min_length", 0)
                max_len = validation.get("max_length", float('inf'))

                if len(text) < min_len:
                    fail_count += 1
                    validation_error = f"Content too short ({len(text)} < {min_len})"
                    print(f"  ❌ {validation_error}")
                    failed_tests.append({
                        "uri": uri_pattern,
                        "resolved_uri": uri,
                        "error": validation_error,
                        "content_length": len(text),
                        "expected_min": min_len
                    })
                    continue

                if len(text) > max_len:
                    fail_count += 1
                    validation_error = f"Content too long ({len(text)} > {max_len})"
                    print(f"  ❌ {validation_error}")
                    failed_tests.append({
                        "uri": uri_pattern,
                        "resolved_uri": uri,
                        "error": validation_error,
                        "content_length": len(text),
                        "expected_max": max_len
                    })
                    continue

            elif content_type == "json":
                # Parse and validate JSON content
                text = content.get("text", "")
                try:
                    json_data = json.loads(text)

                    # Validate against schema if provided
                    if "schema" in validation and validation["schema"]:
                        validate(json_data, validation["schema"])
                        tester._log("✅ Schema validation passed")

                except json.JSONDecodeError as e:
                    fail_count += 1
                    validation_error = f"Invalid JSON content: {e}"
                    print(f"  ❌ {validation_error}")
                    failed_tests.append({
                        "uri": uri_pattern,
                        "resolved_uri": uri,
                        "error": validation_error,
                        "content_preview": text[:200] if len(text) > 200 else text
                    })
                    continue
                except Exception as e:
                    fail_count += 1
                    validation_error = f"Schema validation failed: {e}"
                    print(f"  ❌ {validation_error}")
                    failed_tests.append({
                        "uri": uri_pattern,
                        "resolved_uri": uri,
                        "error": validation_error,
                        "parsed_content": json_data if 'json_data' in locals() else None
                    })
                    continue

            elif content_type == "blob":
                blob = content.get("blob", "")
                if not blob:
                    fail_count += 1
                    validation_error = "Empty blob content"
                    print(f"  ❌ {validation_error}")
                    failed_tests.append({
                        "uri": uri_pattern,
                        "resolved_uri": uri,
                        "error": validation_error
                    })
                    continue

            success_count += 1
            print(f"✅ {uri}: PASSED")
            passed_tests.append({
                "uri": uri_pattern,
                "resolved_uri": uri,
                "mime_type": actual_mime,
                "mime_mismatch": mime_mismatch,
                "content_type": content_type,
                "uri_variables": uri_vars if uri_vars else None
            })

        except Exception as e:
            fail_count += 1
            print(f"❌ {uri_pattern}: FAILED - {e}")
            failed_tests.append({
                "uri": uri_pattern,
                "resolved_uri": uri if 'uri' in locals() else uri_pattern,
                "error": str(e),
                "error_type": type(e).__name__
            })

    print(f"\n📊 Resource Test Results: {success_count} passed, {fail_count} failed, {skip_count} skipped (out of {total_count} total)")

    results = {
        "total": total_count,
        "passed": success_count,
        "failed": fail_count,
        "skipped": skip_count,
        "passed_tests": passed_tests,
        "failed_tests": failed_tests,
        "skipped_tests": skipped_tests
    }

    return fail_count == 0, results


def print_detailed_summary(tools_results: Optional[Dict[str, Any]] = None,
                          resources_results: Optional[Dict[str, Any]] = None) -> None:
    """Print detailed test summary with failures and skips."""

    print("\n" + "=" * 80)
    print("📊 OVERALL TEST SUMMARY")
    print("=" * 80)

    # Tools summary
    if tools_results:
        print("\n🔧 Tools Tests:")
        print(f"   Total: {tools_results['total']}")
        print(f"   ✅ Passed: {tools_results['passed']}")
        print(f"   ❌ Failed: {tools_results['failed']}")

        if tools_results['failed_tests']:
            print(f"\n   Failed Tools ({len(tools_results['failed_tests'])}):")
            for test in tools_results['failed_tests']:
                print(f"\n   • {test['name']}")
                print(f"     Tool: {test['actual_tool']}")
                if test['arguments']:
                    print(f"     Input: {json.dumps(test['arguments'], indent=6)}")
                print(f"     Error: {test['error']}")
                print(f"     Error Type: {test['error_type']}")

        if tools_results.get('untested_side_effects'):
            print(f"\n   ⚠️  Untested Tools with Side Effects ({len(tools_results['untested_side_effects'])}):")
            for tool in tools_results['untested_side_effects']:
                print(f"     • {tool}")

    # Resources summary
    if resources_results:
        print(f"\n🗂️  Resources Tests:")
        print(f"   Total: {resources_results['total']}")
        print(f"   ✅ Passed: {resources_results['passed']}")
        print(f"   ❌ Failed: {resources_results['failed']}")
        print(f"   ⏭️  Skipped: {resources_results['skipped']}")

        if resources_results['failed_tests']:
            print(f"\n   Failed Resources ({len(resources_results['failed_tests'])}):")
            for test in resources_results['failed_tests']:
                print(f"\n   • {test['uri']}")
                if test.get('resolved_uri') != test['uri']:
                    print(f"     Resolved URI: {test['resolved_uri']}")
                if test.get('uri_variables'):
                    print(f"     Variables: {json.dumps(test['uri_variables'], indent=6)}")
                print(f"     Error: {test['error']}")
                if 'error_type' in test:
                    print(f"     Error Type: {test['error_type']}")
                # Show additional context if available
                for key in ['content_length', 'expected_min', 'expected_max', 'content_preview']:
                    if key in test:
                        print(f"     {key.replace('_', ' ').title()}: {test[key]}")

        if resources_results['skipped_tests']:
            print(f"\n   Skipped Resources ({len(resources_results['skipped_tests'])}):")
            for test in resources_results['skipped_tests']:
                print(f"\n   • {test['uri']}")
                print(f"     Reason: {test['reason']}")
                if test.get('config_needed'):
                    print(f"     Configuration Needed: {test['config_needed']}")

    # Overall status
    print("\n" + "=" * 80)
    tools_ok = not tools_results or tools_results['failed'] == 0
    resources_ok = not resources_results or resources_results['failed'] == 0

    if tools_results and resources_results:
        tools_status = "✅ PASSED" if tools_ok else "❌ FAILED"
        resources_status = "✅ PASSED" if resources_ok else "❌ FAILED"
        overall_status = "✅ ALL TESTS PASSED" if (tools_ok and resources_ok) else "❌ SOME TESTS FAILED"

        print(f"   Tools: {tools_status}")
        print(f"   Resources: {resources_status}")
        print(f"   Overall: {overall_status}")
    elif tools_results:
        overall_status = "✅ ALL TESTS PASSED" if tools_ok else "❌ TESTS FAILED"
        print(f"   Tools: {overall_status}")
    elif resources_results:
        overall_status = "✅ ALL TESTS PASSED" if resources_ok else "❌ TESTS FAILED"
        print(f"   Resources: {overall_status}")

    print("=" * 80)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Modern MCP endpoint testing tool",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("endpoint", help="MCP endpoint URL to test")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("-t", "--tools-test", action="store_true",
                       help="Run tools test with test configurations")
    parser.add_argument("-T", "--test-tool", metavar="TOOL_NAME",
                       help="Test specific tool by name")
    parser.add_argument("--list-tools", action="store_true",
                       help="List available tools from MCP server")
    parser.add_argument("--list-resources", action="store_true",
                       help="List available resources from MCP server")
    parser.add_argument("-r", "--resources-test", action="store_true",
                       help="Run resources test with test configurations")
    parser.add_argument("-R", "--test-resource", metavar="RESOURCE_URI",
                       help="Test specific resource by URI")
    parser.add_argument("--config", type=Path,
                       default=Path(__file__).parent / "tests" / "mcp-test.yaml",
                       help="Path to test configuration file (auto-generated by mcp-list.py)")
    
    args = parser.parse_args()
    
    # Create tester instance
    tester = MCPTester(args.endpoint, args.verbose)
    
    try:
        # Initialize session
        tester.initialize()

        if args.list_tools:
            # List available tools
            tools = tester.list_tools()
            print(f"\n📋 Available Tools ({len(tools)}):")
            for tool in tools:
                print(f"  • {tool.get('name', 'Unknown')}: {tool.get('description', 'No description')}")
            return

        if args.list_resources:
            # List available resources
            resources = tester.list_resources()
            print(f"\n🗂️  Available Resources ({len(resources)}):")
            for resource in resources:
                print(f"  • {resource.get('uri', 'Unknown')}: {resource.get('name', 'No name')}")
                if 'description' in resource:
                    print(f"    {resource['description']}")
            return

        if args.tools_test or args.test_tool:
            # Load test configuration
            config = load_test_config(args.config)

            # Run tools test
            success, results = run_tools_test(tester, config, args.test_tool)

            # Print detailed summary
            print_detailed_summary(tools_results=results)

            sys.exit(0 if success else 1)

        if args.resources_test or args.test_resource:
            # Load test configuration
            config = load_test_config(args.config)

            # Run resources test
            success, results = run_resources_test(tester, config, args.test_resource)

            # Print detailed summary
            print_detailed_summary(resources_results=results)

            sys.exit(0 if success else 1)

        # Default: basic connectivity test
        tools = tester.list_tools()
        resources = tester.list_resources()
        print(f"✅ Successfully connected to MCP endpoint")
        print(f"📋 Server has {len(tools)} available tools")
        print(f"🗂️  Server has {len(resources)} available resources")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
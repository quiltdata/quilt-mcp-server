#!/usr/bin/env python3
"""
Modern MCP endpoint testing tool with unified transport support.

Supports both HTTP and stdio transports for flexible testing scenarios:
- HTTP: For testing deployed endpoints and manual testing
- stdio: For integration testing with local/Docker servers via pipes

This tool is the single source of truth for MCP test execution logic.
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import requests
import yaml
from jsonschema import validate


class TestResults:
    """Tracks test results with consistent structure for all outcomes.

    Ensures that result dictionaries ALWAYS contain all required keys,
    fixing the bug where incomplete dictionaries cause print_detailed_summary() to fail.
    """

    def __init__(self):
        """Initialize counters and lists to empty state."""
        self.total = 0
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.passed_tests = []
        self.failed_tests = []
        self.skipped_tests = []

    def record_pass(self, test_info: dict) -> None:
        """Record a successful test.

        Args:
            test_info: Dict with test details (input, output, metadata)
        """
        self.total += 1
        self.passed += 1
        self.passed_tests.append(test_info)

    def record_failure(self, test_info: dict) -> None:
        """Record a failed test.

        Args:
            test_info: Dict with test details (input, partial output, error)
        """
        self.total += 1
        self.failed += 1
        self.failed_tests.append(test_info)

    def record_skip(self, test_info: dict) -> None:
        """Record a skipped test.

        Args:
            test_info: Dict with test details (what was skipped, reason)
        """
        self.total += 1
        self.skipped += 1
        self.skipped_tests.append(test_info)

    def is_success(self) -> bool:
        """Check if all tests passed (no failures).

        Returns:
            True if no failures, False otherwise
        """
        return self.failed == 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert results to dictionary with ALL required keys.

        This method guarantees that the returned dictionary always has
        the complete structure expected by print_detailed_summary().

        Returns:
            Dict with keys: total, passed, failed, skipped,
                           passed_tests, failed_tests, skipped_tests
        """
        return {
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "passed_tests": self.passed_tests,
            "failed_tests": self.failed_tests,
            "skipped_tests": self.skipped_tests
        }


class MCPTester:
    """MCP endpoint testing client supporting both stdio and HTTP transports."""

    def __init__(
        self,
        endpoint: Optional[str] = None,
        process: Optional[subprocess.Popen] = None,
        stdin_fd: Optional[int] = None,
        stdout_fd: Optional[int] = None,
        verbose: bool = False,
        transport: str = "http"
    ):
        """Initialize MCP tester with specified transport.

        Args:
            endpoint: HTTP endpoint URL (required for HTTP transport)
            process: Running subprocess with stdio pipes (for stdio transport)
            stdin_fd: File descriptor for stdin (alternative to process)
            stdout_fd: File descriptor for stdout (alternative to process)
            verbose: Enable verbose output
            transport: "http" or "stdio"
        """
        self.transport = transport
        self.verbose = verbose
        self.request_id = 1

        if transport == "http":
            if not endpoint:
                raise ValueError("endpoint required for HTTP transport")
            self.endpoint = endpoint
            self.session = requests.Session()
            self.session.headers.update({
                'Content-Type': 'application/json',
                'Accept': 'application/json, text/event-stream'
            })
            self.process = None
            self.stdin_file = None
            self.stdout_file = None

        elif transport == "stdio":
            if process:
                # Use provided process
                self.process = process
                self.stdin_file = process.stdin
                self.stdout_file = process.stdout
            elif stdin_fd is not None and stdout_fd is not None:
                # Use file descriptors (for subprocess invocation)
                import os
                self.process = None
                # Open file objects from file descriptors
                self.stdin_file = os.fdopen(stdin_fd, 'w', buffering=1)
                self.stdout_file = os.fdopen(stdout_fd, 'r', buffering=1)
            else:
                raise ValueError("process or (stdin_fd and stdout_fd) required for stdio transport")
            self.endpoint = None
            self.session = None

        else:
            raise ValueError(f"Unsupported transport: {transport}")

    def _log(self, message: str, level: str = "INFO") -> None:
        """Log message with timestamp."""
        if level == "DEBUG" and not self.verbose:
            return
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        prefix = "🔍" if level == "DEBUG" else "ℹ️" if level == "INFO" else "❌"
        print(f"[{timestamp}] {prefix} {message}")

    def _make_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make JSON-RPC request using configured transport."""
        if self.transport == "http":
            return self._make_http_request(method, params)
        else:
            return self._make_stdio_request(method, params)

    def _make_http_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make JSON-RPC request via HTTP transport."""
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

    def _make_stdio_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make JSON-RPC request via stdio transport."""
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
            # Write request to stdin
            request_json = json.dumps(request_data) + "\n"
            self.stdin_file.write(request_json)
            self.stdin_file.flush()

            # Read response from stdout
            response_line = self.stdout_file.readline()
            if not response_line:
                raise Exception("No response from server (EOF)")

            result = json.loads(response_line)

            self._log(f"Response: {json.dumps(result, indent=2)}", "DEBUG")

            if "error" in result:
                raise Exception(f"JSON-RPC error: {result['error']}")

            return result.get("result", {})

        except json.JSONDecodeError as e:
            raise Exception(f"Invalid JSON response: {e}")
        except Exception as e:
            # Re-raise with more context
            raise Exception(f"stdio request failed: {e}")

    def _send_notification(self, method: str, params: Optional[Dict[str, Any]] = None) -> None:
        """Send JSON-RPC notification (no response expected).

        Notifications are one-way messages with no "id" field.
        Used for events like notifications/initialized.
        """
        if self.transport != "stdio":
            # HTTP transport doesn't use notifications
            return

        notification = {
            "jsonrpc": "2.0",
            "method": method
        }
        if params:
            notification["params"] = params

        self._log(f"Sending notification: {method}", "DEBUG")
        if self.verbose and params:
            self._log(f"Params: {json.dumps(params, indent=2)}", "DEBUG")

        # Write notification to stdin
        notification_json = json.dumps(notification) + "\n"
        self.stdin_file.write(notification_json)
        self.stdin_file.flush()

        # Brief pause for server processing
        time.sleep(0.1)

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

        # stdio transport requires notifications/initialized after initialize
        if self.transport == "stdio":
            self._log("Sending notifications/initialized...", "DEBUG")
            self._send_notification("notifications/initialized")

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
        return result  # Return full result to preserve resourceTemplates

    def read_resource(self, uri: str) -> Dict[str, Any]:
        """Read a specific resource."""
        self._log(f"Reading resource: {uri}")

        params = {"uri": uri}
        result = self._make_request("resources/read", params)

        self._log(f"✅ Resource {uri} read successfully")
        return result


    @staticmethod
    def run_test_suite(
        endpoint: str = None,
        stdin_fd: int = None,
        stdout_fd: int = None,
        transport: str = "http",
        verbose: bool = False,
        config: dict = None,
        run_tools: bool = False,
        run_resources: bool = False,
        specific_tool: str = None,
        specific_resource: str = None,
        process: Optional[subprocess.Popen] = None
    ) -> tuple[Optional[Dict], Optional[Dict]]:
        """Run test suite with tools and/or resources tests.

        Args:
            endpoint: HTTP endpoint URL (for HTTP transport)
            stdin_fd: File descriptor for stdin (for stdio transport)
            stdout_fd: File descriptor for stdout (for stdio transport)
            transport: "http" or "stdio"
            verbose: Enable verbose output
            config: Test configuration dictionary
            run_tools: Run tools tests
            run_resources: Run resources tests
            specific_tool: Test specific tool only
            specific_resource: Test specific resource only
            process: Running subprocess with stdio pipes (alternative to stdin_fd/stdout_fd)

        Returns:
            Tuple of (tools_results_dict, resources_results_dict)
            Either may be None if that test type wasn't run
        """
        tools_results = None
        resources_results = None

        if run_tools:
            # Create ToolsTester instance
            if transport == "http":
                tester = ToolsTester(endpoint=endpoint, verbose=verbose, transport=transport, config=config)
            elif process:
                tester = ToolsTester(process=process, verbose=verbose, transport=transport, config=config)
            else:
                tester = ToolsTester(stdin_fd=stdin_fd, stdout_fd=stdout_fd, verbose=verbose, transport=transport, config=config)

            # Initialize and run tests
            tester.initialize()
            tester.run_all_tests(specific_tool=specific_tool)
            tools_results = tester.to_dict()

        if run_resources:
            # Create ResourcesTester instance
            if transport == "http":
                tester = ResourcesTester(endpoint=endpoint, verbose=verbose, transport=transport, config=config)
            elif process:
                tester = ResourcesTester(process=process, verbose=verbose, transport=transport, config=config)
            else:
                tester = ResourcesTester(stdin_fd=stdin_fd, stdout_fd=stdout_fd, verbose=verbose, transport=transport, config=config)

            # Initialize and run tests
            tester.initialize()
            tester.run_all_tests(specific_resource=specific_resource)
            resources_results = tester.to_dict()

        return tools_results, resources_results


class ToolsTester(MCPTester):
    """Tool testing subclass with integrated result tracking."""

    def __init__(self, config: Dict[str, Any] = None, **kwargs):
        """Initialize ToolsTester with test configuration.

        Args:
            config: Test configuration dictionary
            **kwargs: Passed to MCPTester parent
        """
        super().__init__(**kwargs)
        self.config = config or {}
        self.results = TestResults()

        # Track tools with side effects
        self.all_side_effects = set()
        self.tested_side_effects = set()

        # Identify all tools with side effects in config
        for tool_name, tool_config in self.config.get("test_tools", {}).items():
            effect = tool_config.get("effect", "none")
            if effect != "none":
                self.all_side_effects.add(tool_name)

    def run_test(self, tool_name: str, test_config: Dict[str, Any]) -> None:
        """Run a single tool test and record the result.

        Args:
            tool_name: Name of the tool in config
            test_config: Test configuration for this tool
        """
        try:
            print(f"\n--- Testing tool: {tool_name} ---")

            # Get test arguments
            test_args = test_config.get("arguments", {})

            # Get actual tool name (for variants, use "tool" field)
            actual_tool_name = test_config.get("tool", tool_name)

            # Call the tool
            result = self.call_tool(actual_tool_name, test_args)

            # Validate response if schema provided
            if "response_schema" in test_config:
                validate(result, test_config["response_schema"])
                self._log("✅ Response schema validation passed")

            print(f"✅ {tool_name}: PASSED")

            # Record success
            self.results.record_pass({
                "name": tool_name,
                "actual_tool": actual_tool_name,
                "arguments": test_args,
                "result": result
            })

            # Track if tool with side effects was tested
            effect = test_config.get("effect", "none")
            if effect != "none":
                self.tested_side_effects.add(tool_name)

        except Exception as e:
            print(f"❌ {tool_name}: FAILED - {e}")

            # Record failure
            self.results.record_failure({
                "name": tool_name,
                "actual_tool": test_config.get("tool", tool_name),
                "arguments": test_config.get("arguments", {}),
                "error": str(e),
                "error_type": type(e).__name__
            })

    def run_all_tests(self, specific_tool: str = None) -> None:
        """Run all configured tool tests.

        Args:
            specific_tool: If provided, run only this tool's test
        """
        test_tools = self.config.get("test_tools", {})

        if specific_tool:
            if specific_tool not in test_tools:
                print(f"❌ Tool '{specific_tool}' not found in test config")
                # Record as failure
                self.results.record_failure({
                    "name": specific_tool,
                    "actual_tool": specific_tool,
                    "arguments": {},
                    "error": "Tool not found in test config",
                    "error_type": "ConfigurationError"
                })
                return
            test_tools = {specific_tool: test_tools[specific_tool]}

        total_count = len(test_tools)
        print(f"\n🧪 Running tools test ({total_count} tools)...")

        for tool_name, test_config in test_tools.items():
            self.run_test(tool_name, test_config)

        # Report results
        print(f"\n📊 Test Results: {self.results.passed}/{self.results.total} tools passed")

        # Report untested tools with side effects
        untested_side_effects = self.all_side_effects - self.tested_side_effects
        if untested_side_effects:
            print(f"\n⚠️  Tools with side effects NOT tested ({len(untested_side_effects)}):")
            for tool in sorted(untested_side_effects):
                effect = self.config.get("test_tools", {}).get(tool, {}).get("effect", "unknown")
                print(f"  • {tool} (effect: {effect})")
        elif self.all_side_effects:
            print(f"\n✅ All {len(self.all_side_effects)} tools with side effects were tested")

    def to_dict(self) -> Dict[str, Any]:
        """Convert test results to dictionary.

        Returns:
            Dictionary with all standard keys plus untested_side_effects
        """
        result = self.results.to_dict()
        untested_side_effects = self.all_side_effects - self.tested_side_effects
        result["untested_side_effects"] = sorted(untested_side_effects)
        return result


class ResourcesTester(MCPTester):
    """Resource testing subclass with integrated result tracking."""

    def __init__(self, config: Dict[str, Any] = None, **kwargs):
        """Initialize ResourcesTester with test configuration.

        Args:
            config: Test configuration dictionary
            **kwargs: Passed to MCPTester parent
        """
        super().__init__(**kwargs)
        self.config = config or {}
        self.results = TestResults()

        # Track available resources
        self.available_uris = set()
        self.available_templates = set()

    def _initialize_resources(self) -> bool:
        """Query server for available resources.

        Returns:
            True if successful, False on error
        """
        try:
            result = self.list_resources()

            # FastMCP returns both 'resources' (static) and 'resourceTemplates' (templated)
            available_resources = result.get("resources", [])
            available_templates = result.get("resourceTemplates", [])

            # Store URIs
            self.available_uris = {r["uri"] for r in available_resources}
            self.available_templates = {t["uriTemplate"] for t in available_templates}

            print(f"📋 Server provides {len(available_resources)} static resources, {len(available_templates)} templates")
            return True

        except Exception as e:
            print(f"❌ Failed to list resources: {e}")
            return False

    def _validate_content(self, content: dict, validation: dict) -> Optional[str]:
        """Validate resource content based on validation config.

        Args:
            content: Content dict from resource response
            validation: Validation configuration

        Returns:
            Error message if validation failed, None if passed
        """
        content_type = validation.get("type", "text")

        if content_type == "text":
            text = content.get("text", "")
            min_len = validation.get("min_length", 0)
            max_len = validation.get("max_length", float('inf'))

            if len(text) < min_len:
                return f"Content too short ({len(text)} < {min_len})"
            if len(text) > max_len:
                return f"Content too long ({len(text)} > {max_len})"

        elif content_type == "json":
            text = content.get("text", "")
            try:
                json_data = json.loads(text)

                # Validate against schema if provided
                if "schema" in validation and validation["schema"]:
                    validate(json_data, validation["schema"])
                    self._log("✅ Schema validation passed")

            except json.JSONDecodeError as e:
                return f"Invalid JSON content: {e}"
            except Exception as e:
                return f"Schema validation failed: {e}"

        elif content_type == "blob":
            blob = content.get("blob", "")
            if not blob:
                return "Empty blob content"

        return None  # Validation passed

    def run_test(self, uri_pattern: str, test_config: Dict[str, Any]) -> None:
        """Run a single resource test and record the result.

        Args:
            uri_pattern: URI pattern from config (may contain variables)
            test_config: Test configuration for this resource
        """
        try:
            print(f"\n--- Testing resource: {uri_pattern} ---")

            # Substitute URI variables if needed
            uri = uri_pattern
            uri_vars = test_config.get("uri_variables", {})

            for var_name, var_value in uri_vars.items():
                if var_value.startswith("CONFIGURE_"):
                    # Skip resource that needs configuration
                    print(f"  ⏭️  Skipped (needs configuration: {var_name})")
                    self.results.record_skip({
                        "uri": uri_pattern,
                        "reason": f"Needs configuration: {var_name}",
                        "config_needed": var_name
                    })
                    return
                uri = uri.replace(f"{{{var_name}}}", var_value)

            # Check if resource exists
            is_templated = '{' in uri_pattern
            if is_templated:
                if uri_pattern not in self.available_templates:
                    print(f"  ❌ Template not found in server resourceTemplates")
                    self.results.record_failure({
                        "uri": uri_pattern,
                        "resolved_uri": uri,
                        "error": "Template not found in server resourceTemplates",
                        "uri_variables": uri_vars
                    })
                    return
            else:
                if uri not in self.available_uris:
                    print(f"  ❌ Resource not found in server resources")
                    self.results.record_failure({
                        "uri": uri_pattern,
                        "resolved_uri": uri,
                        "error": "Resource not found in server resources",
                        "uri_variables": uri_vars
                    })
                    return

            # Read the resource
            result = self.read_resource(uri)

            # Validate resource content
            contents = result.get("contents", [])
            if not contents:
                print(f"  ❌ Empty contents")
                self.results.record_failure({
                    "uri": uri_pattern,
                    "resolved_uri": uri,
                    "error": "Empty contents",
                    "result": result
                })
                return

            content = contents[0]

            # Validate MIME type
            expected_mime = test_config.get("expected_mime_type", "text/plain")
            actual_mime = content.get("mimeType", "text/plain")

            mime_mismatch = None
            if expected_mime != actual_mime:
                mime_mismatch = f"expected {expected_mime}, got {actual_mime}"
                print(f"  ⚠️  MIME type mismatch ({mime_mismatch})")

            # Validate content
            validation = test_config.get("content_validation", {})
            validation_error = self._validate_content(content, validation)

            if validation_error:
                print(f"  ❌ {validation_error}")
                self.results.record_failure({
                    "uri": uri_pattern,
                    "resolved_uri": uri,
                    "error": validation_error,
                    "content_length": len(content.get("text", "")),
                    "expected_min": validation.get("min_length"),
                    "expected_max": validation.get("max_length")
                })
                return

            # Success!
            print(f"✅ {uri}: PASSED")
            self.results.record_pass({
                "uri": uri_pattern,
                "resolved_uri": uri,
                "mime_type": actual_mime,
                "mime_mismatch": mime_mismatch,
                "content_type": validation.get("type", "text"),
                "uri_variables": uri_vars if uri_vars else None
            })

        except Exception as e:
            print(f"❌ {uri_pattern}: FAILED - {e}")
            self.results.record_failure({
                "uri": uri_pattern,
                "resolved_uri": uri if 'uri' in locals() else uri_pattern,
                "error": str(e),
                "error_type": type(e).__name__
            })

    def run_all_tests(self, specific_resource: str = None) -> None:
        """Run all configured resource tests.

        Args:
            specific_resource: If provided, run only this resource's test
        """
        test_resources = self.config.get("test_resources", {})

        if specific_resource:
            if specific_resource not in test_resources:
                print(f"❌ Resource '{specific_resource}' not found in test config")
                self.results.record_failure({
                    "uri": specific_resource,
                    "resolved_uri": specific_resource,
                    "error": "Resource not found in test config",
                    "error_type": "ConfigurationError"
                })
                return
            test_resources = {specific_resource: test_resources[specific_resource]}

        if not test_resources:
            print("⚠️  No resources configured for testing")
            return

        total_count = len(test_resources)
        print(f"\n🗂️  Running resources test ({total_count} resources)...")

        # Initialize: list available resources
        if not self._initialize_resources():
            # Failed to list resources - record failure for all tests
            for uri_pattern in test_resources.keys():
                self.results.record_failure({
                    "uri": uri_pattern,
                    "resolved_uri": uri_pattern,
                    "error": "Failed to list resources from server",
                    "error_type": "InitializationError"
                })
            return

        # Test each resource
        for uri_pattern, test_config in test_resources.items():
            self.run_test(uri_pattern, test_config)

        # Report results
        print(f"\n📊 Resource Test Results: {self.results.passed} passed, {self.results.failed} failed, {self.results.skipped} skipped (out of {self.results.total} total)")

    def to_dict(self) -> Dict[str, Any]:
        """Convert test results to dictionary.

        Returns:
            Dictionary with all standard keys
        """
        return self.results.to_dict()




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
        description="Modern MCP endpoint testing tool with unified transport support",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Transport modes:
  HTTP (default):
    mcp-test.py http://localhost:8000/mcp --tools-test

  stdio (for integration testing):
    mcp-test.py --stdio --stdin-fd 3 --stdout-fd 4 --tools-test

Examples:
  # Test HTTP endpoint with all tests
  mcp-test.py http://localhost:8000/mcp --tools-test --resources-test

  # Test specific tool via HTTP
  mcp-test.py http://localhost:8000/mcp --test-tool bucket_objects_list

  # List available tools
  mcp-test.py http://localhost:8000/mcp --list-tools

  # stdio mode (typically called by test orchestrator)
  mcp-test.py --stdio --stdin-fd 3 --stdout-fd 4 --tools-test
        """
    )

    # Endpoint argument (optional for stdio mode)
    parser.add_argument(
        "endpoint",
        nargs="?",
        help="MCP endpoint URL (required for HTTP transport, ignored for stdio)"
    )

    # Transport selection
    transport_group = parser.add_mutually_exclusive_group()
    transport_group.add_argument(
        "--http",
        action="store_true",
        help="Use HTTP transport (default)"
    )
    transport_group.add_argument(
        "--stdio",
        action="store_true",
        help="Use stdio transport (for integration testing)"
    )

    # stdio-specific options
    parser.add_argument(
        "--stdin-fd",
        type=int,
        help="File descriptor for stdin (required for stdio transport)"
    )
    parser.add_argument(
        "--stdout-fd",
        type=int,
        help="File descriptor for stdout (required for stdio transport)"
    )

    # Test options
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

    # Determine transport mode
    if args.stdio:
        transport = "stdio"
        if args.stdin_fd is None or args.stdout_fd is None:
            print("❌ --stdin-fd and --stdout-fd required for stdio transport")
            sys.exit(1)
    else:
        transport = "http"
        if not args.endpoint:
            print("❌ endpoint URL required for HTTP transport")
            parser.print_help()
            sys.exit(1)

    # Create tester instance
    try:
        if transport == "http":
            tester = MCPTester(
                endpoint=args.endpoint,
                verbose=args.verbose,
                transport="http"
            )
        else:  # stdio
            tester = MCPTester(
                stdin_fd=args.stdin_fd,
                stdout_fd=args.stdout_fd,
                verbose=args.verbose,
                transport="stdio"
            )
    except Exception as e:
        print(f"❌ Failed to create tester: {e}")
        sys.exit(1)

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
            result = tester.list_resources()
            resources = result.get("resources", [])
            templates = result.get("resourceTemplates", [])
            print(f"\n🗂️  Available Resources ({len(resources)} static, {len(templates)} templates):")
            for resource in resources:
                print(f"  • {resource.get('uri', 'Unknown')}: {resource.get('name', 'No name')}")
                if 'description' in resource:
                    print(f"    {resource['description']}")
            if templates:
                print(f"\n  Resource Templates:")
                for template in templates:
                    print(f"  • {template.get('uriTemplate', 'Unknown')}: {template.get('name', 'No name')}")
            return

        tools_results = None
        resources_results = None

        # Determine which tests to run
        run_tools = args.tools_test or args.test_tool
        run_resources = args.resources_test or args.test_resource

        if run_tools or run_resources:
            # Load test configuration
            config = load_test_config(args.config)

            # Determine transport and connection parameters
            if transport == "http":
                tools_results, resources_results = MCPTester.run_test_suite(
                    endpoint=args.endpoint,
                    transport="http",
                    verbose=args.verbose,
                    config=config,
                    run_tools=run_tools,
                    run_resources=run_resources,
                    specific_tool=args.test_tool if args.test_tool else None,
                    specific_resource=args.test_resource if args.test_resource else None
                )
            else:  # stdio
                tools_results, resources_results = MCPTester.run_test_suite(
                    stdin_fd=args.stdin_fd,
                    stdout_fd=args.stdout_fd,
                    transport="stdio",
                    verbose=args.verbose,
                    config=config,
                    run_tools=run_tools,
                    run_resources=run_resources,
                    specific_tool=args.test_tool if args.test_tool else None,
                    specific_resource=args.test_resource if args.test_resource else None
                )

        # Print detailed summary if we ran any tests
        if tools_results or resources_results:
            print_detailed_summary(tools_results=tools_results, resources_results=resources_results)

            # Determine overall success
            tools_ok = not tools_results or tools_results['failed'] == 0
            resources_ok = not resources_results or resources_results['failed'] == 0
            overall_success = tools_ok and resources_ok

            sys.exit(0 if overall_success else 1)

        # Default: basic connectivity test
        if not (args.list_tools or args.list_resources or args.tools_test or args.test_tool or args.resources_test or args.test_resource):
            tools = tester.list_tools()
            result = tester.list_resources()
            resources = result.get("resources", [])
            templates = result.get("resourceTemplates", [])
            print(f"✅ Successfully connected to MCP endpoint")
            print(f"📋 Server has {len(tools)} available tools")
            print(f"🗂️  Server has {len(resources)} static resources and {len(templates)} templates")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

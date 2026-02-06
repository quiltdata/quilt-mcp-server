#!/usr/bin/env python3
"""
Modern MCP endpoint testing tool with unified transport support.

Supports both HTTP and stdio transports for flexible testing scenarios:
- HTTP: For testing deployed endpoints and manual testing
- stdio: For integration testing with local/Docker servers via pipes

This tool is the single source of truth for MCP test execution logic.
"""

import argparse
import enum
import json
import os
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import requests
import yaml
from jsonschema import validate

# JWT generation for testing
import jwt as pyjwt
import uuid as uuid_module


def generate_test_jwt(secret: str = "test-secret", expires_in: int = 3600) -> str:
    """Generate a test JWT token for testing.

    Args:
        secret: HS256 shared secret for signing
        expires_in: Expiration time in seconds from now

    Returns:
        Signed JWT token string
    """
    payload = {
        "id": "test-user-mcp-test",
        "uuid": str(uuid_module.uuid4()),
        "exp": int(time.time()) + expires_in,
    }
    return pyjwt.encode(payload, secret, algorithm="HS256")


class ResourceFailureType(enum.Enum):
    """Classify resource test failures for better reporting."""
    TEMPLATE_NOT_REGISTERED = "template_not_registered"
    URI_NOT_FOUND = "uri_not_found"
    CONTENT_VALIDATION = "content_validation"
    SERVER_ERROR = "server_error"
    CONFIG_ERROR = "config_error"


def classify_resource_failure(test_info: dict) -> ResourceFailureType:
    """Classify resource failure for intelligent reporting.

    Args:
        test_info: Test failure information dict

    Returns:
        ResourceFailureType classification
    """
    error = test_info.get('error', '')

    if 'Template not found in server resourceTemplates' in error:
        return ResourceFailureType.TEMPLATE_NOT_REGISTERED
    elif 'Resource not found in server resources' in error:
        return ResourceFailureType.URI_NOT_FOUND
    elif 'validation failed' in error.lower():
        return ResourceFailureType.CONTENT_VALIDATION
    elif 'error_type' in test_info and test_info['error_type'] == 'ConfigurationError':
        return ResourceFailureType.CONFIG_ERROR
    else:
        return ResourceFailureType.SERVER_ERROR


def analyze_failure_patterns(failed_tests: List[Dict]) -> Dict[str, Any]:
    """Analyze failure patterns to provide actionable insights.

    Args:
        failed_tests: List of failed test info dictionaries

    Returns:
        Dict with pattern analysis:
        - dominant_pattern: Most common ResourceFailureType
        - pattern_count: Count of dominant pattern
        - total_failures: Total number of failures
        - recommendations: List of actionable recommendations
        - severity: 'critical' | 'warning' | 'info'
    """
    if not failed_tests:
        return {'severity': 'info', 'recommendations': []}

    # Classify all failures
    classifications = [classify_resource_failure(t) for t in failed_tests]

    # Find dominant pattern
    pattern_counts = Counter(classifications)
    dominant = pattern_counts.most_common(1)[0]

    # Generate recommendations based on pattern
    recommendations = []
    severity = 'warning'

    if dominant[0] == ResourceFailureType.TEMPLATE_NOT_REGISTERED:
        if dominant[1] == len(failed_tests):
            # ALL failures are template registration
            severity = 'warning'  # Not critical - static resources work
            recommendations = [
                "✅ Static resources all work - core MCP protocol OK",
                "🔍 Check server logs for template registration messages",
                "🔧 Review feature flags in config (SSO_ENABLED, ADMIN_API_ENABLED, etc.)",
                "📖 Consult docs for template activation requirements"
            ]
        else:
            severity = 'warning'
            recommendations = [
                "Some templates not registered - may need configuration",
                "Compare working vs failing templates for patterns"
            ]
    elif dominant[0] == ResourceFailureType.SERVER_ERROR:
        severity = 'critical'
        recommendations = [
            "❌ Server errors detected - check server logs",
            "🐛 May indicate bugs in resource handlers",
            "🔧 Verify server is properly configured"
        ]

    return {
        'dominant_pattern': dominant[0],
        'pattern_count': dominant[1],
        'total_failures': len(failed_tests),
        'recommendations': recommendations,
        'severity': severity
    }


def format_results_line(passed: int, failed: int, skipped: int = 0) -> str:
    """Format results line with conditional display of counts.

    Only shows counts when they're non-zero to avoid cluttered output.

    Args:
        passed: Number of passed tests
        failed: Number of failed tests
        skipped: Number of skipped tests

    Returns:
        Formatted results string

    Examples:
        >>> format_results_line(17, 0, 0)
        'Results: ✅ 17 passed'
        >>> format_results_line(12, 5, 0)
        'Results: ✅ 12 passed, ❌ 5 failed'
        >>> format_results_line(10, 0, 2)
        'Results: ✅ 10 passed, ⏭️ 2 skipped'
    """
    parts = [f"✅ {passed} passed"]

    if failed > 0:
        parts.append(f"❌ {failed} failed")

    if skipped > 0:
        parts.append(f"⏭️ {skipped} skipped")

    return "   " + ", ".join(parts)


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


class SearchValidator:
    """Validates search results against expected outcomes."""

    def __init__(self, validation_config: Dict[str, Any], env_vars: Dict[str, str]):
        """Initialize validator with config and environment.

        Args:
            validation_config: Validation rules from YAML
            env_vars: Environment variables for substitution
        """
        self.config = validation_config
        self.env_vars = env_vars

    def validate(self, result: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate search result.

        Returns:
            (is_valid, error_message)
            - is_valid: True if validation passed
            - error_message: None if valid, error string if invalid
        """
        validation_type = self.config.get("type")

        if validation_type == "search":
            return self._validate_search(result)
        else:
            # Unknown validation type - skip
            return True, None

    def _validate_search(self, result: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate search-specific results."""

        # Extract results array from response
        # MCP tools return {"content": [...]} format
        content = result.get("content", [])
        if not content:
            return False, "Empty response content"

        # Parse the actual results (usually JSON string in content[0]["text"])
        try:
            if isinstance(content[0], dict) and "text" in content[0]:
                search_results = json.loads(content[0]["text"])
            else:
                search_results = content[0]

            results_list = search_results.get("results", [])
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            return False, f"Failed to parse search results: {e}"

        # Check minimum results
        min_results = self.config.get("min_results", 0)
        if len(results_list) < min_results:
            return False, f"Expected at least {min_results} results, got {len(results_list)}"

        # Check must_contain rules
        must_contain = self.config.get("must_contain", [])
        for rule in must_contain:
            is_found, error = self._check_must_contain(results_list, rule)
            if not is_found:
                return False, error

        # Check result shape if specified
        result_shape = self.config.get("result_shape")
        if result_shape:
            shape_valid, shape_error = self._validate_result_shape(results_list, result_shape)
            if not shape_valid:
                return False, shape_error

        # All checks passed
        return True, None

    def _check_must_contain(
        self,
        results: List[Dict],
        rule: Dict[str, str]
    ) -> tuple[bool, Optional[str]]:
        """Check if results contain expected value.

        Args:
            results: List of result dictionaries
            rule: must_contain rule with value, field, match_type

        Returns:
            (is_found, error_message)
        """
        expected_value = rule["value"]
        field_name = rule["field"]
        match_type = rule.get("match_type", "substring")
        description = rule.get("description", f"Expected to find '{expected_value}'")

        # Search through results
        found = False
        for result in results:
            actual_value = result.get(field_name, "")

            if match_type == "exact":
                if actual_value == expected_value:
                    found = True
                    break
            elif match_type == "substring":
                if expected_value in str(actual_value):
                    found = True
                    break
            elif match_type == "regex":
                import re
                if re.search(expected_value, str(actual_value)):
                    found = True
                    break

        if not found:
            # Generate helpful error message
            error = f"{description}\n"
            error += f"  Expected: '{expected_value}' in field '{field_name}'\n"
            error += f"  Match type: {match_type}\n"
            error += f"  Searched {len(results)} results\n"

            # Show sample of what we found instead
            if results and len(results) > 0:
                sample = results[:3]
                sample_values = [r.get(field_name, "<missing>") for r in sample]
                error += f"  Sample values: {sample_values}"

            return False, error

        return True, None

    def _validate_result_shape(
        self,
        results: List[Dict],
        shape: Dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """Validate that results have expected shape.

        Args:
            results: List of result dictionaries
            shape: Expected shape with required_fields, optional_fields, etc.

        Returns:
            (is_valid, error_message)
        """
        if not results:
            return True, None  # Empty results are OK if we got this far

        required_fields = shape.get("required_fields", [])

        # Check first result (representative sample)
        first_result = results[0]
        missing_fields = [f for f in required_fields if f not in first_result]

        if missing_fields:
            return False, f"Results missing required fields: {missing_fields}"

        return True, None


def validate_test_coverage(server_tools: List[Dict[str, Any]], config_tools: Dict[str, Any]) -> None:
    """Validate that all server tools are covered by test config.

    This prevents tools from going untested when new capabilities are added.
    Raises descriptive error with remediation steps if coverage gaps exist.

    Args:
        server_tools: List of tool dicts from server (with 'name' field)
        config_tools: Dict of test configurations keyed by tool name (may include variants)

    Raises:
        ValueError: If any server tools are not covered by test config
    """
    # Extract tool names from server
    server_tool_names = {tool['name'] for tool in server_tools}

    # Extract base tool names from config (handles variants like "search_catalog.file.no_bucket")
    # Variants use format: "tool_name.variant" and have a "tool" field with actual tool name
    config_tool_names = set()
    for config_key, config_value in config_tools.items():
        if isinstance(config_value, dict) and 'tool' in config_value:
            # This is a variant - use the "tool" field
            config_tool_names.add(config_value['tool'])
        else:
            # Regular tool - use the key itself
            config_tool_names.add(config_key)

    # Find uncovered tools
    uncovered = server_tool_names - config_tool_names

    if uncovered:
        raise ValueError(
            f"\n{'='*80}\n"
            f"❌ ERROR: {len(uncovered)} tool(s) on server are NOT covered by test config!\n"
            f"{'='*80}\n\n"
            f"Uncovered tools:\n" +
            "\n".join(f"  • {tool}" for tool in sorted(uncovered)) +
            f"\n\n"
            f"📋 Coverage Summary:\n"
            f"   Server has: {len(server_tool_names)} tools\n"
            f"   Config has: {len(config_tool_names)} tool configs (including variants)\n"
            f"   Missing:    {len(uncovered)} tools\n\n"
            f"🔧 Action Required:\n"
            f"   1. Run: uv run scripts/mcp-test-setup.py\n"
            f"   2. This regenerates scripts/tests/mcp-test.yaml with ALL server tools\n"
            f"   3. Re-run this test\n\n"
            f"💡 Why This Matters:\n"
            f"   • New tools were added to server but not to test config\n"
            f"   • Running mcp-test-setup.py ensures test coverage stays synchronized\n"
            f"   • This prevents capabilities from going untested\n"
            f"   • Config drift detection is critical for CI/CD reliability\n"
            f"{'='*80}\n"
        )


class MCPTester:
    """MCP endpoint testing client supporting both stdio and HTTP transports."""

    def __init__(
        self,
        endpoint: Optional[str] = None,
        process: Optional[subprocess.Popen] = None,
        stdin_fd: Optional[int] = None,
        stdout_fd: Optional[int] = None,
        verbose: bool = False,
        transport: str = "http",
        jwt_token: Optional[str] = None
    ):
        """Initialize MCP tester with specified transport.

        Args:
            endpoint: HTTP endpoint URL (required for HTTP transport)
            process: Running subprocess with stdio pipes (for stdio transport)
            stdin_fd: File descriptor for stdin (alternative to process)
            stdout_fd: File descriptor for stdout (alternative to process)
            verbose: Enable verbose output
            transport: "http" or "stdio"
            jwt_token: JWT token for authentication (HTTP transport only)
        """
        self.transport = transport
        self.verbose = verbose
        self.request_id = 1
        self.jwt_token = jwt_token  # Store for error handling

        if transport == "http":
            if not endpoint:
                raise ValueError("endpoint required for HTTP transport")
            self.endpoint = endpoint
            self.session = requests.Session()
            self.session.headers.update({
                'Content-Type': 'application/json',
                'Accept': 'application/json, text/event-stream'
            })

            # Add JWT authentication if token provided
            if jwt_token:
                self._log("JWT authentication enabled", "DEBUG")
                self.session.headers.update({
                    'Authorization': f'Bearer {jwt_token}'
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

    def _mask_token(self, token: Optional[str]) -> str:
        """Mask JWT token for safe display (show first and last 4 chars)."""
        if not token:
            return "(none)"
        if len(token) <= 12:
            return "***"
        return f"{token[:4]}...{token[-4:]}"

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

            # Special handling for auth errors
            if response.status_code == 401:
                if self.jwt_token:
                    raise Exception(
                        "Authentication failed: JWT token rejected (invalid or expired)\n"
                        f"Token preview: {self._mask_token(self.jwt_token)}\n"
                        "Troubleshooting:\n"
                        "  - Verify token signature matches server JWT_SECRET\n"
                        "  - Check token expiration (exp claim)\n"
                        "  - Ensure token includes required claims (id, uuid, exp)"
                    )
                else:
                    raise Exception(
                        "Authentication required: Server requires JWT token\n"
                        "Solution: Pass --jwt-token TOKEN or set MCP_JWT_TOKEN env var"
                    )

            if response.status_code == 403:
                raise Exception(
                    "Authorization failed: Insufficient permissions\n"
                    f"Token preview: {self._mask_token(self.jwt_token)}\n"
                    "Troubleshooting:\n"
                    "  - Verify JWT is valid for the Platform deployment\n"
                    "  - Check that the user has access to the requested package/bucket"
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
        process: Optional[subprocess.Popen] = None,
        selection_stats: Optional[Dict[str, Any]] = None,
        jwt_token: Optional[str] = None
    ) -> bool:
        """Run test suite with tools and/or resources tests, print summary, return success.

        This method is the single entry point for running tests. It:
        1. Executes the requested tests (tools and/or resources)
        2. Prints detailed summary with failure information
        3. Returns boolean success status

        This design ensures the detailed summary is ALWAYS printed - it's impossible
        to forget since it's built into the test runner itself.

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
            selection_stats: Stats from filter_tests_by_idempotence() (optional)
            jwt_token: JWT token for authentication (HTTP transport only)

        Returns:
            True if all tests passed (no failures), False otherwise
        """
        # FIXME: Refactor to reuse MCP session instead of creating separate sessions
        # for tools and resources tests. Current implementation initializes twice which
        # is redundant. Should create one base tester, initialize once, then share the
        # session state between ToolsTester and ResourcesTester instances.
        tools_results = None
        resources_results = None

        if run_tools:
            # Create ToolsTester instance
            if transport == "http":
                tester = ToolsTester(endpoint=endpoint, verbose=verbose, transport=transport, config=config, jwt_token=jwt_token)
            elif process:
                tester = ToolsTester(process=process, verbose=verbose, transport=transport, config=config)
            else:
                tester = ToolsTester(stdin_fd=stdin_fd, stdout_fd=stdout_fd, verbose=verbose, transport=transport, config=config)

            # Initialize session
            tester.initialize()

            # CRITICAL: Validate that config covers all server tools (prevents drift)
            # This check ensures mcp-test-setup.py was run after any tool additions
            if not specific_tool:  # Skip validation when testing specific tool
                server_tools = tester.list_tools()
                config_tools = config.get('test_tools', {}) if config else {}
                validate_test_coverage(server_tools, config_tools)

            # Run tests
            tester.run_all_tests(specific_tool=specific_tool)
            tools_results = tester.to_dict()

        if run_resources:
            # Create ResourcesTester instance
            if transport == "http":
                tester = ResourcesTester(endpoint=endpoint, verbose=verbose, transport=transport, config=config, jwt_token=jwt_token)
            elif process:
                tester = ResourcesTester(process=process, verbose=verbose, transport=transport, config=config)
            else:
                tester = ResourcesTester(stdin_fd=stdin_fd, stdout_fd=stdout_fd, verbose=verbose, transport=transport, config=config)

            # Initialize and run tests
            tester.initialize()
            tester.run_all_tests(specific_resource=specific_resource)
            resources_results = tester.to_dict()

        # ALWAYS print detailed summary when tests run
        print_detailed_summary(
            tools_results=tools_results,
            resources_results=resources_results,
            selection_stats=selection_stats,
            verbose=verbose
        )

        # Calculate and return success status
        tools_ok = not tools_results or tools_results['failed'] == 0
        resources_ok = not resources_results or resources_results['failed'] == 0
        return tools_ok and resources_ok


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

        # NEW: Store environment variables for validation
        self.env_vars = config.get("environment", {})

        # Track tools with side effects
        self.all_side_effects = set()
        self.tested_side_effects = set()

        # Identify all tools with side effects in config
        for tool_name, tool_config in self.config.get("test_tools", {}).items():
            effect = tool_config.get("effect", "none")
            if effect != "none":
                self.all_side_effects.add(tool_name)

    def _summarize_result(self, result: Dict[str, Any]) -> str:
        """Generate human-readable summary of result for error reporting."""
        try:
            content = result.get("content", [])
            if content and isinstance(content[0], dict) and "text" in content[0]:
                data = json.loads(content[0]["text"])
                results = data.get("results", [])
                return f"{len(results)} results returned"
            return "Unknown result format"
        except:
            return "Could not parse result"

    def _is_error_response(self, result: Dict[str, Any]) -> bool:
        """Check if the MCP response indicates an error.

        MCP tools can return errors in two forms:
        1. JSON error responses with an "error" field (runtime errors from tool execution)
        2. Plain text validation errors (parameter validation failures from MCP server)

        This method checks if the response represents either error condition.

        Args:
            result: The MCP tool response

        Returns:
            True if the response indicates an error, False otherwise

        Examples:
            JSON error: {"error": "AWS access is not available in JWT mode", ...}
            Validation error: "1 validation error for call[tool_name]\ns3_uri\n  String should match..."
        """
        try:
            content = result.get("content", [])
            if content and isinstance(content[0], dict) and "text" in content[0]:
                text_content = content[0]["text"]

                # Check for validation errors (plain text containing "validation error")
                if "validation error" in text_content.lower():
                    return True

                # Try to parse as JSON and check for error field
                try:
                    data = json.loads(text_content)
                    # Error responses have an "error" field with a string value
                    return "error" in data and isinstance(data["error"], str)
                except json.JSONDecodeError:
                    # If it's not JSON and not a validation error, assume success
                    return False

            return False
        except Exception:
            return False

    def _extract_error_message(self, result: Dict[str, Any]) -> str:
        """Extract the error message from an error response.

        Args:
            result: The MCP tool response with an error

        Returns:
            The error message string
        """
        try:
            content = result.get("content", [])
            if content and isinstance(content[0], dict) and "text" in content[0]:
                text_content = content[0]["text"]

                # Check for validation errors (plain text)
                if "validation error" in text_content.lower():
                    # Return the FULL validation error with all details
                    # Pydantic validation errors have multiple lines with field names,
                    # error types, and messages - we need ALL of this information
                    return text_content.strip()

                # Try to parse as JSON
                try:
                    data = json.loads(text_content)
                    return data.get("error", "Unknown error")
                except json.JSONDecodeError:
                    # Return the raw text if it's not JSON
                    return text_content[:200] if len(text_content) > 200 else text_content

            return "Could not parse error message"
        except Exception:
            return "Could not parse error message"

    def run_test(self, tool_name: str, test_config: Dict[str, Any]) -> None:
        """Run a single tool test with smart validation.

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

            # Check for error responses
            # MCP tools return typed responses with error variants that have an "error" field
            # If the response contains an error, the test should fail
            if self._is_error_response(result):
                error_msg = self._extract_error_message(result)
                print(f"❌ {tool_name}: FAILED - Tool returned error response")
                print(f"   Error: {error_msg}")

                self.results.record_failure({
                    "name": tool_name,
                    "actual_tool": actual_tool_name,
                    "arguments": test_args,
                    "error": f"Tool returned error response: {error_msg}",
                    "error_type": "ErrorResponse",
                    "result_summary": self._summarize_result(result)
                })
                return

            # Schema validation (existing)
            if "response_schema" in test_config:
                validate(result, test_config["response_schema"])
                self._log("✅ Response schema validation passed")

            # NEW: Smart validation for search tools
            if "validation" in test_config:
                validator = SearchValidator(
                    test_config["validation"],
                    self.env_vars
                )
                is_valid, error_msg = validator.validate(result)

                if not is_valid:
                    # Validation failed - record detailed error
                    print(f"❌ {tool_name}: VALIDATION FAILED")
                    print(f"   {error_msg}")

                    self.results.record_failure({
                        "name": tool_name,
                        "actual_tool": actual_tool_name,
                        "arguments": test_args,
                        "error": f"Smart validation failed: {error_msg}",
                        "error_type": "ValidationError",
                        "result_summary": self._summarize_result(result)
                    })
                    return
                else:
                    self._log(f"✅ Smart validation passed: {test_config['validation'].get('description', 'OK')}")

            print(f"✅ {tool_name}: PASSED")

            # Record success
            self.results.record_pass({
                "name": tool_name,
                "actual_tool": actual_tool_name,
                "arguments": test_args,
                "result": result,
                "validation": "passed" if "validation" in test_config else "schema_only"
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
        print("\n" + "=" * 80)

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

            # Check if resource is available from server
            # Skip resources that aren't registered (e.g., local_dev-only resources in multiuser mode)
            if uri_pattern not in self.available_uris:
                # Check if it's a template match
                is_template_match = any(
                    uri_pattern.replace("{", "").replace("}", "") in template
                    for template in self.available_templates
                )
                if not is_template_match:
                    print(f"  ⏭️  Skipped (not available from server)")
                    self.results.record_skip({
                        "uri": uri_pattern,
                        "reason": "Resource not available from server (may be mode-restricted)"
                    })
                    return

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
                    print(f"  ❌ Template '{uri_pattern}' not found in server resourceTemplates")
                    print(f"     This may indicate the resource template is disabled in the current mode")
                    self.results.record_failure({
                        "uri": uri_pattern,
                        "resolved_uri": uri,
                        "error": f"Template '{uri_pattern}' not found in server resourceTemplates (may be mode-restricted)",
                        "uri_variables": uri_vars,
                        "available_templates_count": len(self.available_templates)
                    })
                    return
            else:
                if uri not in self.available_uris:
                    print(f"  ❌ Resource '{uri}' not found in server resources")
                    print(f"     This may indicate the resource is disabled in the current mode")
                    self.results.record_failure({
                        "uri": uri_pattern,
                        "resolved_uri": uri,
                        "error": f"Resource '{uri}' not found in server resources (may be mode-restricted)",
                        "uri_variables": uri_vars,
                        "available_count": len(self.available_uris)
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
            config = yaml.safe_load(f)

        # Validate required environment variables
        env_vars = config.get("environment", {})
        quilt_test_bucket = env_vars.get("QUILT_TEST_BUCKET")

        if not quilt_test_bucket:
            print("❌ QUILT_TEST_BUCKET must be set in test configuration")
            print("   Edit scripts/tests/mcp-test.yaml and set environment.QUILT_TEST_BUCKET")
            sys.exit(1)

        # Ensure QUILT_TEST_BUCKET is also set in OS environment
        if not os.environ.get("QUILT_TEST_BUCKET"):
            os.environ["QUILT_TEST_BUCKET"] = quilt_test_bucket
            print(f"ℹ️  Set QUILT_TEST_BUCKET={quilt_test_bucket} from config")

        return config
    except FileNotFoundError:
        print(f"❌ Test config not found: {config_path}")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"❌ Invalid YAML config: {e}")
        sys.exit(1)


def filter_tests_by_idempotence(config: Dict[str, Any], idempotent_only: bool) -> tuple[Dict[str, Any], dict]:
    """Filter test tools based on effect classification.

    Args:
        config: Test configuration dictionary
        idempotent_only: If True, only include tools with effect='none' (read-only)

    Returns:
        Tuple of (filtered_config, stats_dict) where:
        - filtered_config: Config with filtered test_tools
        - stats_dict: Statistics about filtering including:
            - total_tools: total number of tools in config
            - total_resources: total number of resources in config
            - selected_tools: number of tools selected
            - effect_counts: dict of effect type -> count of selected tools
    """
    test_tools = config.get('test_tools', {})
    test_resources = config.get('test_resources', {})
    filtered_tools = {}
    effect_counts = {}

    for tool_name, tool_config in test_tools.items():
        effect = tool_config.get('effect', 'none')

        # Count by effect type
        effect_counts[effect] = effect_counts.get(effect, 0) + 1

        # Filter: idempotent_only means only 'none' effect
        if idempotent_only and effect == 'none':
            filtered_tools[tool_name] = tool_config
        elif not idempotent_only:
            filtered_tools[tool_name] = tool_config

    # Create filtered config
    filtered_config = config.copy()
    filtered_config['test_tools'] = filtered_tools

    stats = {
        'total_tools': len(test_tools),
        'total_resources': len(test_resources),
        'selected_tools': len(filtered_tools),
        'effect_counts': effect_counts
    }

    return filtered_config, stats


def print_detailed_summary(
    tools_results: Optional[Dict[str, Any]] = None,
    resources_results: Optional[Dict[str, Any]] = None,
    selection_stats: Optional[Dict[str, Any]] = None,
    server_info: Optional[Dict[str, Any]] = None,
    verbose: bool = False
) -> None:
    """Print intelligent test summary with context and pattern analysis.

    Args:
        tools_results: Tool test results from ToolsTester.to_dict()
        resources_results: Resource test results from ResourcesTester.to_dict()
        selection_stats: Stats from filter_tests_by_idempotence() including:
            - total_tools: total number of tools in config
            - total_resources: total number of resources in config
            - selected_tools: number of tools selected for testing
            - effect_counts: dict of effect type -> count
        server_info: Server capabilities from initialize() (optional)
        verbose: Include detailed configuration and analysis (optional)
    """
    print("\n" + "=" * 80)
    print("📊 TEST SUITE SUMMARY")
    print("=" * 80)

    # Tools summary
    if tools_results:
        total_tools = selection_stats.get('total_tools', tools_results['total']) if selection_stats else tools_results['total']
        selected_tools = tools_results['total']
        skipped_tools = total_tools - selected_tools

        # Header with selection context
        if skipped_tools > 0:
            print(f"\n🔧 TOOLS (Tested {selected_tools}/{total_tools} tested, {skipped_tools} skipped)")
            # Show reason for skipping
            if selection_stats:
                effect_counts = selection_stats.get('effect_counts', {})
                non_none_effects = {k: v for k, v in effect_counts.items() if k != 'none'}
                if non_none_effects:
                    skipped_summary = ", ".join(f"{effect}: {count}" for effect, count in sorted(non_none_effects.items()))
                    print(f"   Selection: Idempotent only (SKIPPED: {skipped_summary})")
        else:
            print(f"\n🔧 TOOLS ({selected_tools}/{total_tools} tested)")

        # Results line with conditional display
        print(format_results_line(tools_results['passed'], tools_results['failed']))

        # Show failures if any
        if tools_results['failed'] > 0 and tools_results['failed_tests']:
            print(f"\n   ❌ Failed Tools ({len(tools_results['failed_tests'])}):")
            for test in tools_results['failed_tests']:
                print(f"\n      • {test['name']}")
                print(f"        Tool: {test['actual_tool']}")
                if test['arguments']:
                    print(f"        Input: {json.dumps(test['arguments'], indent=9)}")

                # Format error message with proper indentation for multi-line errors
                error_msg = test['error']
                if '\n' in error_msg:
                    # Multi-line error (e.g., validation errors) - indent each line
                    lines = error_msg.split('\n')
                    print(f"        Error: {lines[0]}")
                    for line in lines[1:]:
                        print(f"               {line}")
                else:
                    # Single-line error
                    print(f"        Error: {error_msg}")

                print(f"        Error Type: {test['error_type']}")

        if tools_results.get('untested_side_effects'):
            print(f"\n   ⚠️  Untested Tools with Side Effects ({len(tools_results['untested_side_effects'])}):")
            for tool in tools_results['untested_side_effects']:
                print(f"      • {tool}")

    # Resources summary
    if resources_results:
        total_resources = selection_stats.get('total_resources', resources_results['total']) if selection_stats else resources_results['total']

        # Header - resources always test all configured
        print(f"\n🗂️  RESOURCES ({total_resources}/{total_resources} tested)")

        # Count static vs template resources based on failure patterns
        static_count = 0
        template_count = 0
        for test in resources_results.get('passed_tests', []):
            if test.get('uri_variables'):
                template_count += 1
            else:
                static_count += 1
        for test in resources_results.get('failed_tests', []):
            if test.get('uri_variables') or '{' in test.get('uri', ''):
                template_count += 1
            else:
                static_count += 1

        if static_count > 0 or template_count > 0:
            print(f"   Type Breakdown: {static_count} static URIs, {template_count} templates")

        # Results line with conditional display
        print(format_results_line(
            resources_results['passed'],
            resources_results['failed'],
            resources_results.get('skipped', 0)
        ))

        # Analyze failure patterns if there are failures
        if resources_results['failed'] > 0 and resources_results['failed_tests']:
            analysis = analyze_failure_patterns(resources_results['failed_tests'])

            # Show concise failure summary based on pattern
            if analysis['dominant_pattern'] == ResourceFailureType.TEMPLATE_NOT_REGISTERED:
                if analysis['pattern_count'] == analysis['total_failures']:
                    # All failures are template registration
                    print(f"\n   ⚠️  All {analysis['total_failures']} failures: Template registration issues")
                    print(f"      Templates not registered by server:")
                    for test in resources_results['failed_tests']:
                        print(f"      - {test['uri']}")

                    print(f"\n   📋 Likely Causes:")
                    print(f"      • Features require activation (env vars, feature flags)")
                    print(f"      • Dynamic registration based on runtime config")
                    print(f"      • Expected behavior for optional features")

                    print(f"\n   📊 Impact Assessment:")
                    if static_count > 0:
                        print(f"      ✅ Core MCP protocol working (all static resources pass)")
                    if tools_results and tools_results['failed'] == 0:
                        print(f"      ✅ All idempotent tools working")
                    print(f"      ⚠️  Some advanced features unavailable")
                else:
                    # Mixed failure types
                    print(f"\n   ❌ Failed Resources ({len(resources_results['failed_tests'])}):")
                    for test in resources_results['failed_tests']:
                        print(f"\n      • {test['uri']}")
                        if test.get('resolved_uri') != test['uri']:
                            print(f"        Resolved URI: {test['resolved_uri']}")
                        if test.get('uri_variables'):
                            print(f"        Variables: {json.dumps(test['uri_variables'], indent=9)}")
                        print(f"        Error: {test['error']}")
                        if 'error_type' in test:
                            print(f"        Error Type: {test['error_type']}")
            else:
                # Non-template failures - show detailed list
                print(f"\n   ❌ Failed Resources ({len(resources_results['failed_tests'])}):")
                for test in resources_results['failed_tests']:
                    print(f"\n      • {test['uri']}")
                    if test.get('resolved_uri') != test['uri']:
                        print(f"        Resolved URI: {test['resolved_uri']}")
                    if test.get('uri_variables'):
                        print(f"        Variables: {json.dumps(test['uri_variables'], indent=9)}")
                    print(f"        Error: {test['error']}")
                    if 'error_type' in test:
                        print(f"        Error Type: {test['error_type']}")

        if resources_results.get('skipped', 0) > 0 and resources_results['skipped_tests']:
            print(f"\n   Skipped Resources ({len(resources_results['skipped_tests'])}):")
            for test in resources_results['skipped_tests']:
                print(f"\n      • {test['uri']}")
                print(f"        Reason: {test['reason']}")
                if test.get('config_needed'):
                    print(f"        Configuration Needed: {test['config_needed']}")

    # Overall status with intelligent assessment
    print("\n" + "=" * 80)
    tools_ok = not tools_results or tools_results['failed'] == 0
    resources_ok = not resources_results or resources_results['failed'] == 0

    # Analyze severity for nuanced status
    severity = 'info'
    if resources_results and resources_results['failed'] > 0:
        analysis = analyze_failure_patterns(resources_results.get('failed_tests', []))
        severity = analysis.get('severity', 'warning')

    # Determine overall status
    if tools_ok and resources_ok:
        overall_status = "✅ ALL TESTS PASSED"
        detail_lines = []
        if tools_results:
            detail_lines.append(f"- {tools_results['passed']} idempotent tools verified")
        if resources_results:
            detail_lines.append(f"- {resources_results['passed']} resources verified")
        detail_lines.append("- No failures detected")
    elif not tools_ok:
        overall_status = "❌ CRITICAL FAILURE"
        detail_lines = [
            f"- {tools_results['failed']}/{tools_results['total']} core tools failing",
            "- Immediate action required"
        ]
    elif severity == 'warning':
        overall_status = "⚠️  PARTIAL PASS"
        detail_lines = []
        if tools_results:
            detail_lines.append(f"- Core functionality verified ({tools_results['passed']}/{tools_results['total']} tools)")
        if resources_results:
            passed_static = sum(1 for t in resources_results.get('passed_tests', []) if not t.get('uri_variables'))
            if passed_static > 0:
                detail_lines.append(f"- {passed_static} static resources verified")
            detail_lines.append(f"- {resources_results['failed']} optional templates not registered (may be expected)")
        detail_lines.append("- No critical failures detected")
    else:
        overall_status = "❌ FAILURE"
        detail_lines = [
            f"- {resources_results['failed']} resource tests failed",
            "- Review failures and address issues"
        ]

    print(f"   Overall Status: {overall_status}")
    for line in detail_lines:
        print(f"   {line}")
    print("=" * 80)

    # Show next steps if applicable
    if severity == 'warning' and resources_results and resources_results['failed'] > 0:
        analysis = analyze_failure_patterns(resources_results.get('failed_tests', []))
        if analysis.get('recommendations'):
            print(f"\n💡 Next Steps:")
            for rec in analysis['recommendations']:
                print(f"   • {rec}")
            if selection_stats and selection_stats.get('total_tools', 0) > selection_stats.get('selected_tools', 0):
                print(f"   • Run with --all to test write operations")
            if not verbose:
                print(f"   • Run with --verbose for detailed analysis")
            print()


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

JWT Authentication:
  # Use bundled sample catalog JWT token
  mcp-test.py http://localhost:8000/mcp --jwt --tools-test

  # Using environment variable
  export MCP_JWT_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  mcp-test.py http://localhost:8000/mcp --tools-test

  # Using command-line argument
  mcp-test.py http://localhost:8000/mcp --jwt-token "eyJhbGciOi..." --tools-test

  # Or provide your own catalog JWT token via env/CLI

For detailed JWT testing documentation, see: docs/JWT_TESTING.md
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

    # JWT Authentication (mutually exclusive options)
    jwt_group = parser.add_mutually_exclusive_group()
    jwt_group.add_argument("--jwt-token", type=str,
                       help="JWT token for authentication (HTTP transport only). "
                            "Alternatively, set MCP_JWT_TOKEN environment variable. "
                            "⚠️  Prefer env var for production use to avoid token exposure in logs.")
    jwt_group.add_argument("--jwt", action="store_true",
                       help="Use bundled sample catalog JWT token (HTTP transport only).")
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
                       help="Path to test configuration file (auto-generated by mcp-test-setup.py)")
    parser.add_argument("--idempotent-only", action="store_true",
                       help="Run only idempotent (read-only) tools with effect='none' (matches test-mcp behavior)")

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

    # Resolve JWT token
    jwt_token = None

    if args.jwt:
        # Use sample catalog JWT for testing
        if transport != "http":
            print("❌ --jwt only supported for HTTP transport")
            sys.exit(1)

        print("🔐 Generating test JWT token...")

        try:
            jwt_token = generate_test_jwt(secret="test-secret")
            if args.verbose:
                masked = f"{jwt_token[:8]}...{jwt_token[-8:]}" if len(jwt_token) > 16 else "***"
                print(f"   Token preview: {masked}")
        except Exception as e:
            print(f"❌ Failed to load sample JWT token: {e}")
            sys.exit(1)
    else:
        # Use provided token (command line takes precedence over env var)
        jwt_token = args.jwt_token or os.environ.get('MCP_JWT_TOKEN')

        if jwt_token and transport != "http":
            print("⚠️  Warning: --jwt-token ignored for stdio transport")
            jwt_token = None

        if jwt_token and args.jwt_token:
            # Token passed on command line - warn about security
            print("⚠️  Security Warning: JWT token passed on command line")
            print("    Prefer using MCP_JWT_TOKEN environment variable")
            print("    Command-line arguments may be visible in process lists\n")

    # Create tester instance
    try:
        if transport == "http":
            tester = MCPTester(
                endpoint=args.endpoint,
                verbose=args.verbose,
                transport="http",
                jwt_token=jwt_token
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

        # Determine which tests to run
        run_tools = args.tools_test or args.test_tool
        run_resources = args.resources_test or args.test_resource

        if run_tools or run_resources:
            # Load test configuration
            config = load_test_config(args.config)

            # Apply idempotence filtering if requested
            selection_stats = None
            if args.idempotent_only:
                print("🔓 Filtering to idempotent-only tests (read-only, effect='none')...")
                config, selection_stats = filter_tests_by_idempotence(config, idempotent_only=True)
                print(f"📋 Selected {selection_stats['selected_tools']}/{selection_stats['total_tools']} tools for testing")
                filtered_out = selection_stats['total_tools'] - selection_stats['selected_tools']
                if filtered_out > 0:
                    non_none_effects = {k: v for k, v in selection_stats['effect_counts'].items() if k != 'none'}
                    skipped_summary = ", ".join(f"{effect}: {count}" for effect, count in sorted(non_none_effects.items()))
                    print(f"   Skipped {filtered_out} non-idempotent tools ({skipped_summary})")

            # Run test suite (prints summary internally and returns boolean success)
            if transport == "http":
                success = MCPTester.run_test_suite(
                    endpoint=args.endpoint,
                    transport="http",
                    verbose=args.verbose,
                    config=config,
                    run_tools=run_tools,
                    run_resources=run_resources,
                    specific_tool=args.test_tool if args.test_tool else None,
                    specific_resource=args.test_resource if args.test_resource else None,
                    jwt_token=jwt_token,
                    selection_stats=selection_stats
                )
            else:  # stdio
                success = MCPTester.run_test_suite(
                    stdin_fd=args.stdin_fd,
                    stdout_fd=args.stdout_fd,
                    transport="stdio",
                    verbose=args.verbose,
                    config=config,
                    run_tools=run_tools,
                    run_resources=run_resources,
                    specific_tool=args.test_tool if args.test_tool else None,
                    specific_resource=args.test_resource if args.test_resource else None,
                    selection_stats=selection_stats
                )

            sys.exit(0 if success else 1)

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

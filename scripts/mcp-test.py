#!/usr/bin/env python3
"""
Modern MCP endpoint testing tool with unified transport support.

Supports both HTTP and local transports for flexible testing scenarios:
- spawn-local (default): Spawn local MCP server for testing
- HTTP: For testing deployed endpoints and manual testing

This tool is the single source of truth for MCP test execution logic.
"""

import argparse
import enum
import json
import os
import re
import subprocess
import sys
import time
import uuid as uuid_module
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import requests
import yaml
from jsonschema import validate

# JWT generation for testing
import jwt as pyjwt

# Import testing framework modules
from quilt_mcp.testing import (
    MCPTester,
    TestResults,
    SearchValidator,
    ResourceFailureType,
    ToolLoopExecutor,
    substitute_templates,
    validate_test_coverage,
    validate_loop_coverage,
    classify_resource_failure,
    analyze_failure_patterns,
    load_test_config,
    filter_tests_by_idempotence,
    parse_selector,
    validate_selector_names,
    filter_by_selector,
    format_results_line,
    print_detailed_summary,
)

# Script paths for local server spawning
SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent


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


class LocalMCPServer:
    """Manages local MCP server process lifecycle for testing."""

    def __init__(self, python_path: Optional[str] = None):
        """Initialize local server configuration.

        Args:
            python_path: Path to Python executable (default: uv's Python)
        """
        self.python_path = python_path or sys.executable
        self.process: Optional[subprocess.Popen] = None
        self.server_id = f"local-{uuid_module.uuid4().hex[:8]}"

    def start(self) -> bool:
        """Start MCP server as local subprocess with stdio transport.

        Returns:
            True if server started successfully, False otherwise
        """
        print(f"🚀 Starting local MCP server...")
        print(f"   Python: {self.python_path}")
        print(f"   Server ID: {self.server_id}")

        try:
            # Build environment with necessary variables
            env = os.environ.copy()
            env["FASTMCP_TRANSPORT"] = "stdio"

            # Optional: inherit AWS credentials from environment
            # (already present in env if user is configured)

            # Start server process using uv
            cmd = ["uv", "run", "python", "src/main.py", "--skip-banner"]

            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered
                cwd=REPO_ROOT,  # Run from repo root
                env=env,
            )

            # Brief wait for startup
            time.sleep(0.5)  # Much faster than Docker's 2s

            # Check if process is still running
            if self.process.poll() is not None:
                stderr = self.process.stderr.read() if self.process.stderr else ""
                print(f"❌ Server exited immediately")
                print(f"   stderr: {stderr}")
                return False

            print(f"✅ Server started (PID: {self.process.pid})")
            return True

        except Exception as e:
            print(f"❌ Failed to start server: {e}")
            return False

    def stop(self):
        """Stop local server process."""
        if not self.process:
            return

        print(f"\n🛑 Stopping server {self.server_id}...")
        try:
            # Send SIGTERM for graceful shutdown
            self.process.terminate()
            try:
                # Wait for graceful shutdown (shorter timeout than Docker)
                self.process.wait(timeout=3)
                print("✅ Server stopped gracefully")
            except subprocess.TimeoutExpired:
                print("⚠️  Timeout, force killing...")
                self.process.kill()
                self.process.wait()
                print("✅ Server force-stopped")
        except Exception as e:
            print(f"⚠️  Error during cleanup: {e}")
            if self.process:
                try:
                    self.process.kill()
                except:
                    pass

    def get_process(self) -> Optional[subprocess.Popen]:
        """Get the running server process for direct communication.

        Returns:
            Server process if running, None otherwise
        """
        return self.process


# ============================================================================
# Imported from quilt_mcp.testing module
# ============================================================================
# The following components are now imported from quilt_mcp.testing:
# - ResourceFailureType, classify_resource_failure, analyze_failure_patterns
# - format_results_line, print_detailed_summary
# - TestResults
# - SearchValidator
# - validate_test_coverage
# - substitute_templates, ToolLoopExecutor
# - validate_loop_coverage
# - load_test_config, filter_tests_by_idempotence
# - parse_selector, validate_selector_names, filter_by_selector
#
# Only script-specific code remains below:
# - LocalMCPServer (local server process management)
# - ToolsTester, ResourcesTester (test execution with MCPTester base)
# - main() (CLI and orchestration)
# ============================================================================


def run_test_suite(
    endpoint: str = None,
    transport: str = "http",
    verbose: bool = False,
    config: dict = None,
    *,
    run_tools: bool,
    run_resources: bool,
    run_loops: bool,
    specific_tool: str = None,
    specific_resource: str = None,
    specific_loop: str = None,
    process: Optional[subprocess.Popen] = None,
    selection_stats: Optional[Dict[str, Any]] = None,
    jwt_token: Optional[str] = None,
) -> bool:
    """Run test suite with tools, resources, and/or loops tests, print summary, return success.

    This method is the single entry point for running tests. It:
    1. Executes the requested tests (tools, resources, and/or loops)
    2. Prints detailed summary with failure information
    3. Returns boolean success status

    This design ensures the detailed summary is ALWAYS printed - it's impossible
    to forget since it's built into the test runner itself.

    Args:
        endpoint: HTTP endpoint URL (for HTTP transport)
        transport: "http" or "stdio"
        verbose: Enable verbose output
        config: Test configuration dictionary
        run_tools: Run tools tests
        run_resources: Run resources tests
        run_loops: Run tool loops tests
        specific_tool: Test specific tool only
        specific_resource: Test specific resource only
        specific_loop: Test specific loop only
        process: Running subprocess with stdio pipes (for spawn-local transport)
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
    loops_results = None

    if run_tools:
        # Create ToolsTester instance
        if transport == "http":
            tester = ToolsTester(
                endpoint=endpoint, verbose=verbose, transport=transport, config=config, jwt_token=jwt_token
            )
        else:  # spawn-local with process
            tester = ToolsTester(process=process, verbose=verbose, transport=transport, config=config)

        # Initialize session
        tester.initialize()

        # CRITICAL: Validate that config covers all server tools (prevents drift)
        # This check ensures mcp-test-setup.py was run after any tool additions
        # IMPORTANT: Skip validation when running with --idempotent-only filter
        # because the filtered config won't have write-effect tools
        if (
            not specific_tool and selection_stats is None
        ):  # Skip validation when testing specific tool or using filters
            server_tools = tester.list_tools()
            config_tools = config.get('test_tools', {}) if config else {}
            validate_test_coverage(server_tools, config_tools)

        # Run tests
        tester.run_all_tests(specific_tool=specific_tool)
        tools_results = tester.to_dict()

    if run_resources:
        # Create ResourcesTester instance
        if transport == "http":
            tester = ResourcesTester(
                endpoint=endpoint, verbose=verbose, transport=transport, config=config, jwt_token=jwt_token
            )
        else:  # spawn-local with process
            tester = ResourcesTester(process=process, verbose=verbose, transport=transport, config=config)

        # Initialize and run tests
        tester.initialize()
        tester.run_all_tests(specific_resource=specific_resource)
        resources_results = tester.to_dict()

    if run_loops:
        # Create MCPTester instance for loops
        if transport == "http":
            tester = MCPTester(endpoint=endpoint, verbose=verbose, transport="http", jwt_token=jwt_token)
        else:  # spawn-local with process
            tester = MCPTester(process=process, verbose=verbose, transport="stdio")

        # Initialize session
        tester.initialize()

        # Create loop executor
        env_vars = config.get("environment", {}) if config else {}
        executor = ToolLoopExecutor(tester, env_vars, verbose=verbose)

        # Run loops
        tool_loops = config.get('tool_loops', {}) if config else {}
        if specific_loop:
            if specific_loop not in tool_loops:
                print(f"❌ Loop '{specific_loop}' not found in config")
                loops_results = {
                    "total": 0,
                    "passed": 0,
                    "failed": 1,
                    "skipped": 0,
                    "passed_tests": [],
                    "failed_tests": [{"loop": specific_loop, "error": "Loop not found in configuration"}],
                    "skipped_tests": [],
                }
            else:
                executor.execute_loop(specific_loop, tool_loops[specific_loop])
                loops_results = executor.results.to_dict()
        else:
            loops_results = executor.execute_all_loops(tool_loops)

    # ALWAYS print detailed summary when tests run
    print_detailed_summary(
        tools_results=tools_results,
        resources_results=resources_results,
        selection_stats=selection_stats,
        verbose=verbose,
        loops_results=loops_results,  # Pass loops results
        config=config,  # Pass config to analyze tools in loops vs truly skipped
    )

    # Calculate and return success status
    tools_ok = not tools_results or tools_results['failed'] == 0
    resources_ok = not resources_results or resources_results['failed'] == 0
    loops_ok = not loops_results or loops_results['failed'] == 0
    return tools_ok and resources_ok and loops_ok


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

                self.results.record_failure(
                    {
                        "name": tool_name,
                        "actual_tool": actual_tool_name,
                        "arguments": test_args,
                        "error": f"Tool returned error response: {error_msg}",
                        "error_type": "ErrorResponse",
                        "result_summary": self._summarize_result(result),
                    }
                )
                return

            # Schema validation (existing)
            if "response_schema" in test_config:
                validate(result, test_config["response_schema"])
                self._log("✅ Response schema validation passed")

            # NEW: Smart validation for search tools
            if "validation" in test_config:
                validator = SearchValidator(test_config["validation"], self.env_vars)
                is_valid, error_msg = validator.validate(result)

                if not is_valid:
                    # Validation failed - record detailed error
                    print(f"❌ {tool_name}: VALIDATION FAILED")
                    print(f"   {error_msg}")

                    self.results.record_failure(
                        {
                            "name": tool_name,
                            "actual_tool": actual_tool_name,
                            "arguments": test_args,
                            "error": f"Smart validation failed: {error_msg}",
                            "error_type": "ValidationError",
                            "result_summary": self._summarize_result(result),
                        }
                    )
                    return
                else:
                    self._log(f"✅ Smart validation passed: {test_config['validation'].get('description', 'OK')}")

            print(f"✅ {tool_name}: PASSED")

            # Record success
            self.results.record_pass(
                {
                    "name": tool_name,
                    "actual_tool": actual_tool_name,
                    "arguments": test_args,
                    "result": result,
                    "validation": "passed" if "validation" in test_config else "schema_only",
                }
            )

            # Track if tool with side effects was tested
            effect = test_config.get("effect", "none")
            if effect != "none":
                self.tested_side_effects.add(tool_name)

        except Exception as e:
            print(f"❌ {tool_name}: FAILED - {e}")

            # Record failure
            self.results.record_failure(
                {
                    "name": tool_name,
                    "actual_tool": test_config.get("tool", tool_name),
                    "arguments": test_config.get("arguments", {}),
                    "error": str(e),
                    "error_type": type(e).__name__,
                }
            )

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
                self.results.record_failure(
                    {
                        "name": specific_tool,
                        "actual_tool": specific_tool,
                        "arguments": {},
                        "error": "Tool not found in test config",
                        "error_type": "ConfigurationError",
                    }
                )
                return

            test_config = test_tools[specific_tool]
            # Warn if testing write-effect tool in isolation
            effect = test_config.get("effect", "none")
            if effect in ["create", "update", "remove"]:
                print(f"⚠️  Testing write-effect tool in isolation (may fail without prerequisites)")

            test_tools = {specific_tool: test_config}

        # Filter out write-effect tools (they're tested via loops)
        filtered_tools = {}
        skipped_write_effect = []

        for tool_name, test_config in test_tools.items():
            # Skip if specific tool was requested (already handled above)
            if specific_tool:
                filtered_tools[tool_name] = test_config
                continue

            effect = test_config.get("effect", "none")
            category = test_config.get("category", "unknown")

            # Skip write-effect tools (create/update/remove effects)
            if effect in ["create", "update", "remove"] or category == "write-effect":
                skipped_write_effect.append(tool_name)
                self.results.record_skip(
                    {
                        "name": tool_name,
                        "reason": f"Write-effect tool (effect={effect}) - tested via tool loops",
                        "effect": effect,
                        "category": category,
                    }
                )
                continue

            filtered_tools[tool_name] = test_config

        total_count = len(filtered_tools)
        skipped_count = len(skipped_write_effect)

        print(f"\n🧪 Running tools test ({total_count} tools)...")
        if skipped_count > 0:
            print(f"   ⊘ Skipping {skipped_count} write-effect tools (tested via loops)")

        for tool_name, test_config in filtered_tools.items():
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

            print(
                f"📋 Server provides {len(available_resources)} static resources, {len(available_templates)} templates"
            )
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
                    uri_pattern.replace("{", "").replace("}", "") in template for template in self.available_templates
                )
                if not is_template_match:
                    print(f"  ⏭️  Skipped (not available from server)")
                    self.results.record_skip(
                        {"uri": uri_pattern, "reason": "Resource not available from server (may be mode-restricted)"}
                    )
                    return

            # Substitute URI variables if needed
            uri = uri_pattern
            uri_vars = test_config.get("uri_variables", {})

            for var_name, var_value in uri_vars.items():
                if var_value.startswith("CONFIGURE_"):
                    # Skip resource that needs configuration
                    print(f"  ⏭️  Skipped (needs configuration: {var_name})")
                    self.results.record_skip(
                        {"uri": uri_pattern, "reason": f"Needs configuration: {var_name}", "config_needed": var_name}
                    )
                    return
                uri = uri.replace(f"{{{var_name}}}", var_value)

            # Check if resource exists
            is_templated = '{' in uri_pattern
            if is_templated:
                if uri_pattern not in self.available_templates:
                    print(f"  ❌ Template '{uri_pattern}' not found in server resourceTemplates")
                    print(f"     This may indicate the resource template is disabled in the current mode")
                    self.results.record_failure(
                        {
                            "uri": uri_pattern,
                            "resolved_uri": uri,
                            "error": f"Template '{uri_pattern}' not found in server resourceTemplates (may be mode-restricted)",
                            "uri_variables": uri_vars,
                            "available_templates_count": len(self.available_templates),
                        }
                    )
                    return
            else:
                if uri not in self.available_uris:
                    print(f"  ❌ Resource '{uri}' not found in server resources")
                    print(f"     This may indicate the resource is disabled in the current mode")
                    self.results.record_failure(
                        {
                            "uri": uri_pattern,
                            "resolved_uri": uri,
                            "error": f"Resource '{uri}' not found in server resources (may be mode-restricted)",
                            "uri_variables": uri_vars,
                            "available_count": len(self.available_uris),
                        }
                    )
                    return

            # Read the resource
            result = self.read_resource(uri)

            # Validate resource content
            contents = result.get("contents", [])
            if not contents:
                print(f"  ❌ Empty contents")
                self.results.record_failure(
                    {"uri": uri_pattern, "resolved_uri": uri, "error": "Empty contents", "result": result}
                )
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
                self.results.record_failure(
                    {
                        "uri": uri_pattern,
                        "resolved_uri": uri,
                        "error": validation_error,
                        "content_length": len(content.get("text", "")),
                        "expected_min": validation.get("min_length"),
                        "expected_max": validation.get("max_length"),
                    }
                )
                return

            # Success!
            print(f"✅ {uri}: PASSED")
            self.results.record_pass(
                {
                    "uri": uri_pattern,
                    "resolved_uri": uri,
                    "mime_type": actual_mime,
                    "mime_mismatch": mime_mismatch,
                    "content_type": validation.get("type", "text"),
                    "uri_variables": uri_vars if uri_vars else None,
                }
            )

        except Exception as e:
            print(f"❌ {uri_pattern}: FAILED - {e}")
            self.results.record_failure(
                {
                    "uri": uri_pattern,
                    "resolved_uri": uri if 'uri' in locals() else uri_pattern,
                    "error": str(e),
                    "error_type": type(e).__name__,
                }
            )

    def run_all_tests(self, specific_resource: str = None) -> None:
        """Run all configured resource tests.

        Args:
            specific_resource: If provided, run only this resource's test
        """
        test_resources = self.config.get("test_resources", {})

        if specific_resource:
            if specific_resource not in test_resources:
                print(f"❌ Resource '{specific_resource}' not found in test config")
                self.results.record_failure(
                    {
                        "uri": specific_resource,
                        "resolved_uri": specific_resource,
                        "error": "Resource not found in test config",
                        "error_type": "ConfigurationError",
                    }
                )
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
                self.results.record_failure(
                    {
                        "uri": uri_pattern,
                        "resolved_uri": uri_pattern,
                        "error": "Failed to list resources from server",
                        "error_type": "InitializationError",
                    }
                )
            return

        # Test each resource
        for uri_pattern, test_config in test_resources.items():
            self.run_test(uri_pattern, test_config)

        # Report results
        print(
            f"\n📊 Resource Test Results: {self.results.passed} passed, {self.results.failed} failed, {self.results.skipped} skipped (out of {self.results.total} total)"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert test results to dictionary.

        Returns:
            Dictionary with all standard keys
        """
        return self.results.to_dict()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Modern MCP endpoint testing tool with unified transport support",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Transport modes:
  Local (default - spawn local server for testing):
    mcp-test.py                           # Uses spawn-local by default
    mcp-test.py --python /usr/bin/python3.12

  HTTP (for testing deployed endpoints):
    mcp-test.py http://localhost:8000/mcp

Examples:
  # Test local server (default - no flags needed)
  mcp-test.py

  # Test with custom Python interpreter
  mcp-test.py --python /usr/bin/python3.12

  # Test against HTTP endpoint
  mcp-test.py http://localhost:8000/mcp

  # Run specific tools only
  mcp-test.py --tools bucket_list,bucket_search

  # Run idempotent operations only (tools only, no resources or loops)
  mcp-test.py --resources none --loops none

  # Run specific tools and resources, skip loops
  mcp-test.py -t package_browse,package_install \\
    -r quilt+s3://bucket#package=pkg -l none

  # List available tools
  mcp-test.py --list-tools

JWT Authentication (HTTP only):
  # Use bundled sample catalog JWT token
  mcp-test.py http://localhost:8000/mcp --jwt

  # Using environment variable
  export MCP_JWT_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  mcp-test.py http://localhost:8000/mcp

  # Using command-line argument
  mcp-test.py http://localhost:8000/mcp --jwt-token "eyJhbGciOi..."

For detailed JWT testing documentation, see: docs/JWT_TESTING.md
        """,
    )

    # Endpoint argument (optional - spawn-local is default)
    parser.add_argument(
        "endpoint", nargs="?", help="MCP endpoint URL (if provided, uses HTTP transport; otherwise uses spawn-local)"
    )

    # Transport selection
    transport_group = parser.add_mutually_exclusive_group()
    transport_group.add_argument("--http", action="store_true", help="Force HTTP transport (requires endpoint URL)")
    transport_group.add_argument(
        "--spawn-local", action="store_true", help="Explicitly use spawn-local mode (default if no endpoint provided)"
    )

    # Local server options
    parser.add_argument(
        "--python", type=str, help="Python executable path for spawn-local mode (default: uv's Python)"
    )

    # Test options
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    # JWT Authentication (mutually exclusive options)
    jwt_group = parser.add_mutually_exclusive_group()
    jwt_group.add_argument(
        "--jwt-token",
        type=str,
        help="JWT token for authentication (HTTP transport only). "
        "Alternatively, set MCP_JWT_TOKEN environment variable. "
        "⚠️  Prefer env var for production use to avoid token exposure in logs.",
    )
    jwt_group.add_argument(
        "--jwt", action="store_true", help="Use bundled sample catalog JWT token (HTTP transport only)."
    )
    parser.add_argument(
        "-t", "--tools", metavar="SELECTOR", help="Select tools to test: 'all' (default), 'none', or 'name1,name2,...'"
    )
    parser.add_argument(
        "-r",
        "--resources",
        metavar="SELECTOR",
        help="Select resources to test: 'all' (default), 'none', or 'uri1,uri2,...'",
    )
    parser.add_argument(
        "-l", "--loops", metavar="SELECTOR", help="Select loops to run: 'all' (default), 'none', or 'loop1,loop2,...'"
    )
    parser.add_argument("--list-tools", action="store_true", help="List available tools from MCP server")
    parser.add_argument("--list-resources", action="store_true", help="List available resources from MCP server")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).parent / "tests" / "mcp-test.yaml",
        help="Path to test configuration file (auto-generated by mcp-test-setup.py)",
    )
    parser.add_argument(
        "--validate-coverage",
        action="store_true",
        help="Validate that all tools have test coverage (standalone or in loops)",
    )

    args = parser.parse_args()

    # Determine transport mode
    local_server = None  # Track local server for cleanup

    # Default to spawn-local unless endpoint is provided or --http is specified
    if args.endpoint or args.http:
        transport = "http"
        if not args.endpoint:
            print("❌ endpoint URL required for HTTP transport")
            parser.print_help()
            sys.exit(1)
    else:
        transport = "spawn-local"
        # We'll spawn the server after loading config

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
            tester = MCPTester(endpoint=args.endpoint, verbose=args.verbose, transport="http", jwt_token=jwt_token)
        else:  # spawn-local (default)
            # Spawn local server
            local_server = LocalMCPServer(python_path=args.python)
            if not local_server.start():
                print("❌ Failed to start local MCP server")
                sys.exit(1)

            # Create tester with spawned process
            tester = MCPTester(process=local_server.get_process(), verbose=args.verbose, transport="stdio")
    except Exception as e:
        print(f"❌ Failed to create tester: {e}")
        if local_server:
            local_server.stop()
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
            if local_server:
                local_server.stop()
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
            if local_server:
                local_server.stop()
            return

        # Handle coverage validation
        if args.validate_coverage:
            config = load_test_config(args.config)
            server_tools = tester.list_tools()
            tool_loops = config.get('tool_loops', {})
            standalone_tools = config.get('test_tools', {})

            is_complete, uncovered = validate_loop_coverage(server_tools, tool_loops, standalone_tools)

            if local_server:
                local_server.stop()

            if is_complete:
                print(f"✅ Coverage validation PASSED: All {len(server_tools)} tools covered")
                sys.exit(0)
            else:
                print(f"❌ Coverage validation FAILED: {len(uncovered)} tools not covered")
                print(f"\nUncovered tools:")
                for tool in uncovered:
                    print(f"  • {tool}")
                print(f"\n💡 Add these tools to tool_loops or test_tools in mcp-test.yaml")
                sys.exit(1)

        # Parse selectors (default to 'all' for each category)
        try:
            tools_type, tools_names = parse_selector(args.tools, 'tools')
            resources_type, resources_names = parse_selector(args.resources, 'resources')
            loops_type, loops_names = parse_selector(args.loops, 'loops')
        except ValueError as e:
            print(f"❌ Invalid selector: {e}")
            sys.exit(1)

        # Determine if we should run tests (any selector specified OR no flags at all means run everything)
        any_selector_specified = args.tools or args.resources or args.loops
        should_run_tests = any_selector_specified or not (
            args.list_tools or args.list_resources or args.validate_coverage
        )

        if should_run_tests:
            # Load test configuration
            config = load_test_config(args.config)

            # Validate selector names
            try:
                validate_selector_names(tools_type, tools_names, config.get('test_tools', {}), 'tools')
                validate_selector_names(resources_type, resources_names, config.get('test_resources', {}), 'resources')
                validate_selector_names(loops_type, loops_names, config.get('tool_loops', {}), 'loops')
            except ValueError as e:
                print(f"❌ {e}")
                sys.exit(1)

            # Filter config based on selectors
            filtered_config = config.copy()
            filtered_config['test_tools'] = filter_by_selector(config.get('test_tools', {}), tools_type, tools_names)
            filtered_config['test_resources'] = filter_by_selector(
                config.get('test_resources', {}), resources_type, resources_names
            )
            filtered_config['tool_loops'] = filter_by_selector(config.get('tool_loops', {}), loops_type, loops_names)

            # Compute selection stats for reporting
            selection_stats = {
                'total_tools': len(config.get('test_tools', {})),
                'selected_tools': len(filtered_config['test_tools']),
                'total_resources': len(config.get('test_resources', {})),
                'selected_resources': len(filtered_config['test_resources']),
                'total_loops': len(config.get('tool_loops', {})),
                'selected_loops': len(filtered_config['tool_loops']),
            }

            # Determine which categories to run (based on filtered config)
            run_tools = len(filtered_config['test_tools']) > 0
            run_resources = len(filtered_config['test_resources']) > 0
            run_loops = len(filtered_config['tool_loops']) > 0

            # Print selection summary if filtering was applied
            if any_selector_specified:
                print("📋 Test Selection:")
                if args.tools:
                    print(
                        f"   Tools: {args.tools} → {selection_stats['selected_tools']}/{selection_stats['total_tools']} selected"
                    )
                if args.resources:
                    print(
                        f"   Resources: {args.resources} → {selection_stats['selected_resources']}/{selection_stats['total_resources']} selected"
                    )
                if args.loops:
                    print(
                        f"   Loops: {args.loops} → {selection_stats['selected_loops']}/{selection_stats['total_loops']} selected"
                    )
                print()

            # Run test suite (prints summary internally and returns boolean success)
            try:
                if transport == "http":
                    success = run_test_suite(
                        endpoint=args.endpoint,
                        transport="http",
                        verbose=args.verbose,
                        config=filtered_config,
                        run_tools=run_tools,
                        run_resources=run_resources,
                        run_loops=run_loops,
                        specific_tool=None,  # No longer used - use selector filtering instead
                        specific_resource=None,  # No longer used - use selector filtering instead
                        specific_loop=None,  # No longer used - use selector filtering instead
                        jwt_token=jwt_token,
                        selection_stats=selection_stats,
                    )
                else:  # spawn-local (default)
                    success = run_test_suite(
                        process=local_server.get_process(),
                        transport="stdio",
                        verbose=args.verbose,
                        config=filtered_config,
                        run_tools=run_tools,
                        run_resources=run_resources,
                        run_loops=run_loops,
                        specific_tool=None,  # No longer used - use selector filtering instead
                        specific_resource=None,  # No longer used - use selector filtering instead
                        specific_loop=None,  # No longer used - use selector filtering instead
                        selection_stats=selection_stats,
                    )
            finally:
                # Always cleanup local server if spawned
                if local_server:
                    local_server.stop()

            sys.exit(0 if success else 1)

    except Exception as e:
        print(f"❌ Test failed: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        # Cleanup on error
        if local_server:
            local_server.stop()
        sys.exit(1)


if __name__ == "__main__":
    main()

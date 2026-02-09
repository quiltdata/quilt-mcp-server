"""MCP client for testing - JSON-RPC transport layer.

This module provides the core MCP testing client that handles JSON-RPC
communication over HTTP and stdio transports.
"""

import json
import subprocess
import time
from typing import Any, Dict, List, Optional

import requests


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
        jwt_token: Optional[str] = None,
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
            self.session.headers.update(
                {'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream'}
            )

            # Add JWT authentication if token provided
            if jwt_token:
                self._log("JWT authentication enabled", "DEBUG")
                self.session.headers.update({'Authorization': f'Bearer {jwt_token}'})

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
        request_data = {"jsonrpc": "2.0", "id": self.request_id, "method": method}
        if params:
            request_data["params"] = params

        self.request_id += 1

        self._log(f"Making request: {method}", "DEBUG")
        if self.verbose and params:
            self._log(f"Params: {json.dumps(params, indent=2)}", "DEBUG")

        try:
            response = self.session.post(self.endpoint, json=request_data, timeout=10)

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
        request_data = {"jsonrpc": "2.0", "id": self.request_id, "method": method}
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

        notification = {"jsonrpc": "2.0", "method": method}
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
            "clientInfo": {"name": "mcp-test", "version": "1.0.0"},
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

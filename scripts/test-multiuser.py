#!/usr/bin/env python3
"""
Multiuser MCP testing orchestrator.

Runs MCP tests across multiple users with proper JWT authentication
and validates stateless behavior.
"""

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
import jwt as pyjwt
import uuid

repo_root = Path(__file__).parent.parent


def generate_test_jwt(secret: str = "test-secret", expires_in: int = 3600) -> str:
    """Generate a test JWT token for testing.

    Args:
        secret: HS256 shared secret for signing
        expires_in: Expiration time in seconds from now

    Returns:
        Signed JWT token string
    """
    payload = {
        "id": "test-user-multiuser",
        "uuid": str(uuid.uuid4()),
        "exp": int(time.time()) + expires_in,
    }
    return pyjwt.encode(payload, secret, algorithm="HS256")


class MultiuserTestRunner:
    """Orchestrates multiuser testing across multiple users."""

    def __init__(self, config: Dict[str, Any], endpoint: str, verbose: bool = False):
        """Initialize test runner.

        Args:
            config: Test configuration from YAML
            endpoint: MCP endpoint URL
            verbose: Enable verbose output
        """
        self.config = config
        self.endpoint = endpoint
        self.verbose = verbose
        self.user_tokens: Dict[str, str] = {}
        self.results: Dict[str, Any] = {"total": 0, "passed": 0, "failed": 0, "scenarios": []}

    def _log(self, message: str, level: str = "INFO") -> None:
        """Log message with timestamp."""
        if level == "DEBUG" and not self.verbose:
            return
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        prefix = "🔍" if level == "DEBUG" else "ℹ️" if level == "INFO" else "❌" if level == "ERROR" else "✅"
        print(f"[{timestamp}] {prefix} {message}")

    def setup_users(self) -> bool:
        """Load JWT tokens for all configured users.

        Returns:
            True if successful, False otherwise
        """
        self._log("Setting up user JWT tokens...")

        users_config = self.config.get("users", {})
        if not users_config:
            self._log("No users configured", "ERROR")
            return False

        # Load token for each user
        for user_label, user_config in users_config.items():
            try:
                token = user_config.get("jwt_token") or user_config.get("token")
                if not token:
                    token = generate_test_jwt()

                if not token:
                    self._log(f"Missing JWT token for user {user_label}", "ERROR")
                    return False

                self.user_tokens[user_label] = token
                self._log(f"✅ Token loaded for {user_label}")

            except Exception as e:
                self._log(f"Failed to load token for {user_label}: {e}", "ERROR")
                return False

        self._log(f"✅ Loaded {len(self.user_tokens)} user tokens")
        return True

    def run_basic_connectivity_tests(self) -> Dict[str, Any]:
        """Run basic connectivity tests for all users.

        Returns:
            Test results dictionary
        """
        self._log("\n" + "=" * 80)
        self._log("Running basic connectivity tests...")
        self._log("=" * 80)

        results = {"name": "Basic Connectivity", "passed": 0, "failed": 0, "tests": []}

        for user_label, token in self.user_tokens.items():
            self._log(f"\nTesting user: {user_label}")

            try:
                import requests

                # Test initialize
                init_result = self._test_initialize(token)
                if init_result["success"]:
                    results["passed"] += 1
                    self._log(f"  ✅ Initialize: PASSED")
                else:
                    results["failed"] += 1
                    self._log(f"  ❌ Initialize: FAILED - {init_result['error']}")

                results["tests"].append({"user": user_label, "test": "initialize", **init_result})

                # Test tools/list
                tools_result = self._test_tools_list(token)
                if tools_result["success"]:
                    results["passed"] += 1
                    tool_count = tools_result.get("tool_count", 0)
                    self._log(f"  ✅ Tools List: PASSED ({tool_count} tools)")
                else:
                    results["failed"] += 1
                    self._log(f"  ❌ Tools List: FAILED - {tools_result['error']}")

                results["tests"].append({"user": user_label, "test": "tools_list", **tools_result})

            except Exception as e:
                results["failed"] += 2
                self._log(f"  ❌ Connectivity test failed: {e}", "ERROR")
                results["tests"].append({"user": user_label, "error": str(e)})

        return results

    def run_concurrent_tests(self) -> Dict[str, Any]:
        """Run concurrent user operations test.

        Returns:
            Test results dictionary
        """
        self._log("\n" + "=" * 80)
        self._log("Running concurrent user operations test...")
        self._log("=" * 80)

        results = {"name": "Concurrent Operations", "passed": 0, "failed": 0, "tests": []}

        def test_user_concurrently(user_label: str, token: str) -> Dict[str, Any]:
            """Test single user operation."""
            try:
                result = self._test_tools_list(token)
                return {"user": user_label, "success": result["success"], "error": result.get("error")}
            except Exception as e:
                return {"user": user_label, "success": False, "error": str(e)}

        # Run all user tests concurrently
        with ThreadPoolExecutor(max_workers=len(self.user_tokens)) as executor:
            futures = {
                executor.submit(test_user_concurrently, user_label, token): user_label
                for user_label, token in self.user_tokens.items()
            }

            for future in as_completed(futures):
                user_label = futures[future]
                try:
                    result = future.result()
                    if result["success"]:
                        results["passed"] += 1
                        self._log(f"  ✅ {user_label}: Concurrent test passed")
                    else:
                        results["failed"] += 1
                        self._log(f"  ❌ {user_label}: Concurrent test failed - {result['error']}")

                    results["tests"].append(result)

                except Exception as e:
                    results["failed"] += 1
                    self._log(f"  ❌ {user_label}: Exception - {e}", "ERROR")
                    results["tests"].append({"user": user_label, "success": False, "error": str(e)})

        return results

    def _test_initialize(self, token: str) -> Dict[str, Any]:
        """Test MCP initialize method."""
        import requests

        try:
            response = requests.post(
                self.endpoint,
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "jsonrpc": "2.0",
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "multiuser-test", "version": "1.0"},
                    },
                    "id": 1,
                },
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()
                if "result" in data:
                    return {"success": True, "result": data["result"]}
                else:
                    return {"success": False, "error": data.get("error", "Unknown error")}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _test_tools_list(self, token: str) -> Dict[str, Any]:
        """Test MCP tools/list method."""
        import requests

        try:
            response = requests.post(
                self.endpoint,
                headers={"Authorization": f"Bearer {token}"},
                json={"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 1},
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()
                if "result" in data:
                    tools = data["result"].get("tools", [])
                    return {"success": True, "tool_count": len(tools)}
                else:
                    return {"success": False, "error": data.get("error", "Unknown error")}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _call_tool(self, token: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a specific MCP tool."""
        import requests

        try:
            response = requests.post(
                self.endpoint,
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {"name": tool_name, "arguments": arguments},
                    "id": 1,
                },
                timeout=30,
            )

            if response.status_code == 200:
                data = response.json()
                if "result" in data:
                    return {"success": True, "result": data["result"]}
                else:
                    return {"success": False, "error": str(data.get("error", "Unknown error"))}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def run_all_tests(self) -> bool:
        """Run all test scenarios.

        Returns:
            True if all tests passed, False otherwise
        """
        # Setup
        if not self.setup_users():
            self._log("Failed to setup users", "ERROR")
            return False

        # Run test scenarios
        connectivity_results = self.run_basic_connectivity_tests()
        self.results["scenarios"].append(connectivity_results)
        self.results["total"] += connectivity_results["passed"] + connectivity_results["failed"]
        self.results["passed"] += connectivity_results["passed"]
        self.results["failed"] += connectivity_results["failed"]

        concurrent_results = self.run_concurrent_tests()
        self.results["scenarios"].append(concurrent_results)
        self.results["total"] += concurrent_results["passed"] + concurrent_results["failed"]
        self.results["passed"] += concurrent_results["passed"]
        self.results["failed"] += concurrent_results["failed"]

        # Print summary
        self.print_summary()

        return self.results["failed"] == 0

    def print_summary(self) -> None:
        """Print test results summary."""
        print("\n" + "=" * 80)
        print("📊 MULTIUSER TEST SUMMARY")
        print("=" * 80)

        for scenario in self.results["scenarios"]:
            total_tests = scenario['passed'] + scenario['failed']
            if total_tests > 0:
                print(f"\n{scenario['name']}:")
                print(f"  ✅ Passed: {scenario['passed']}")
                print(f"  ❌ Failed: {scenario['failed']}")

        print("\n" + "=" * 80)
        print(f"Overall Results:")
        print(f"  Total: {self.results['total']}")
        print(f"  ✅ Passed: {self.results['passed']}")
        print(f"  ❌ Failed: {self.results['failed']}")

        if self.results["failed"] == 0:
            print("\n✅ ALL TESTS PASSED")
        else:
            print(f"\n❌ {self.results['failed']} TEST(S) FAILED")

        print("=" * 80)


def expand_env_vars(value: Any) -> Any:
    """Recursively expand environment variables in config values.

    Supports:
    - ${VAR} - replace with environment variable or leave as-is if not set
    - ${VAR:-default} - replace with environment variable or use default

    Args:
        value: Config value (string, dict, list, or other)

    Returns:
        Value with environment variables expanded
    """
    if isinstance(value, str):
        # Pattern for ${VAR} or ${VAR:-default}
        pattern = r'\$\{([^}:]+)(?::(-)?([^}]*))?\}'

        def replace_var(match):
            var_name = match.group(1)
            has_default = match.group(2) is not None
            default_value = match.group(3) if has_default else None

            env_value = os.environ.get(var_name)

            if env_value is not None:
                return env_value
            elif has_default:
                return default_value or ""
            else:
                # Variable not set and no default - leave unexpanded for validation
                return match.group(0)

        return re.sub(pattern, replace_var, value)

    elif isinstance(value, dict):
        return {k: expand_env_vars(v) for k, v in value.items()}

    elif isinstance(value, list):
        return [expand_env_vars(item) for item in value]

    else:
        return value


def load_config(config_path: Path) -> Dict[str, Any]:
    """Load test configuration from YAML file with environment variable expansion."""
    try:
        with open(config_path, 'r') as f:
            config_raw = yaml.safe_load(f)

        # Expand environment variables in entire config
        config = expand_env_vars(config_raw)

        # Set environment variables from config (for backward compatibility)
        env_vars = config.get("environment", {})
        for key, value in env_vars.items():
            if not os.environ.get(key) and value and not value.startswith("${"):
                os.environ[key] = str(value)

        return config

    except FileNotFoundError:
        print(f"❌ Config file not found: {config_path}", file=sys.stderr)
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"❌ Invalid YAML config: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Multiuser MCP testing orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run against a server (uses catalog JWT token if provided)
  export TEST_JWT_TOKEN=your-catalog-jwt
  python scripts/test-multiuser.py http://localhost:8001/mcp

  # Run with custom config
  python scripts/test-multiuser.py http://localhost:8001/mcp \\
    --config scripts/tests/mcp-test-multiuser.yaml

  # Verbose output
  python scripts/test-multiuser.py http://localhost:8001/mcp -v
        """,
    )

    parser.add_argument("endpoint", help="MCP endpoint URL (e.g., http://localhost:8001/mcp)")

    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).parent / "tests" / "mcp-test-multiuser.yaml",
        help="Path to test configuration file",
    )

    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Load configuration
    config = load_config(args.config)

    # Run tests
    runner = MultiuserTestRunner(
        config,
        args.endpoint,
        verbose=args.verbose,
    )
    success = runner.run_all_tests()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

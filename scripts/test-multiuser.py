#!/usr/bin/env python3
"""
Multiuser MCP testing orchestrator.

Runs MCP tests across multiple tenants with proper JWT authentication
and validates tenant isolation.
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

# Add tests directory to path for jwt_helpers
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / 'tests'))

try:
    from jwt_helpers import generate_test_jwt
except ImportError:
    print("❌ Could not import jwt_helpers. Make sure tests/jwt_helpers.py exists.", file=sys.stderr)
    sys.exit(1)


class MultiuserTestRunner:
    """Orchestrates multiuser testing across multiple tenants."""

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
        self.tenant_tokens: Dict[str, str] = {}
        self.results: Dict[str, Any] = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "scenarios": []
        }

    def _log(self, message: str, level: str = "INFO") -> None:
        """Log message with timestamp."""
        if level == "DEBUG" and not self.verbose:
            return
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        prefix = "🔍" if level == "DEBUG" else "ℹ️" if level == "INFO" else "❌" if level == "ERROR" else "✅"
        print(f"[{timestamp}] {prefix} {message}")

    def setup_tenants(self) -> bool:
        """Generate JWT tokens for all configured tenants.

        Returns:
            True if successful, False otherwise
        """
        self._log("Setting up tenant JWT tokens...")

        tenants_config = self.config.get("tenants", {})
        if not tenants_config:
            self._log("No tenants configured", "ERROR")
            return False

        # Generate token for each tenant
        for tenant_id, tenant_config in tenants_config.items():
            try:
                jwt_secret = tenant_config.get("jwt_secret")
                user_id = tenant_config.get("user_id")
                user_uuid = tenant_config.get("user_uuid")

                if not jwt_secret or not user_id or not user_uuid:
                    self._log(f"Missing jwt_secret, user_id, or user_uuid for tenant {tenant_id}", "ERROR")
                    return False

                self._log(f"Generating JWT for tenant: {tenant_id}", "DEBUG")

                token = generate_test_jwt(
                    secret=jwt_secret,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    user_uuid=user_uuid,
                    expiry_seconds=3600,
                )

                self.tenant_tokens[tenant_id] = token
                self._log(f"✅ Token generated for {tenant_id}")

            except Exception as e:
                self._log(f"Failed to generate token for {tenant_id}: {e}", "ERROR")
                return False

        self._log(f"✅ Generated {len(self.tenant_tokens)} tenant tokens")
        return True

    def run_basic_connectivity_tests(self) -> Dict[str, Any]:
        """Run basic connectivity tests for all tenants.

        Returns:
            Test results dictionary
        """
        self._log("\n" + "="*80)
        self._log("Running basic connectivity tests...")
        self._log("="*80)

        results = {
            "name": "Basic Connectivity",
            "passed": 0,
            "failed": 0,
            "tests": []
        }

        for tenant_id, token in self.tenant_tokens.items():
            self._log(f"\nTesting tenant: {tenant_id}")

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

                results["tests"].append({
                    "tenant": tenant_id,
                    "test": "initialize",
                    **init_result
                })

                # Test tools/list
                tools_result = self._test_tools_list(token)
                if tools_result["success"]:
                    results["passed"] += 1
                    tool_count = tools_result.get("tool_count", 0)
                    self._log(f"  ✅ Tools List: PASSED ({tool_count} tools)")
                else:
                    results["failed"] += 1
                    self._log(f"  ❌ Tools List: FAILED - {tools_result['error']}")

                results["tests"].append({
                    "tenant": tenant_id,
                    "test": "tools_list",
                    **tools_result
                })

            except Exception as e:
                results["failed"] += 2
                self._log(f"  ❌ Connectivity test failed: {e}", "ERROR")
                results["tests"].append({
                    "tenant": tenant_id,
                    "error": str(e)
                })

        return results

    def run_concurrent_tests(self) -> Dict[str, Any]:
        """Run concurrent tenant operations test.

        Returns:
            Test results dictionary
        """
        self._log("\n" + "="*80)
        self._log("Running concurrent tenant operations test...")
        self._log("="*80)

        results = {
            "name": "Concurrent Operations",
            "passed": 0,
            "failed": 0,
            "tests": []
        }

        def test_tenant_concurrently(tenant_id: str, token: str) -> Dict[str, Any]:
            """Test single tenant operation."""
            try:
                result = self._test_tools_list(token)
                return {
                    "tenant": tenant_id,
                    "success": result["success"],
                    "error": result.get("error")
                }
            except Exception as e:
                return {
                    "tenant": tenant_id,
                    "success": False,
                    "error": str(e)
                }

        # Run all tenant tests concurrently
        with ThreadPoolExecutor(max_workers=len(self.tenant_tokens)) as executor:
            futures = {
                executor.submit(test_tenant_concurrently, tenant_id, token): tenant_id
                for tenant_id, token in self.tenant_tokens.items()
            }

            for future in as_completed(futures):
                tenant_id = futures[future]
                try:
                    result = future.result()
                    if result["success"]:
                        results["passed"] += 1
                        self._log(f"  ✅ {tenant_id}: Concurrent test passed")
                    else:
                        results["failed"] += 1
                        self._log(f"  ❌ {tenant_id}: Concurrent test failed - {result['error']}")

                    results["tests"].append(result)

                except Exception as e:
                    results["failed"] += 1
                    self._log(f"  ❌ {tenant_id}: Exception - {e}", "ERROR")
                    results["tests"].append({
                        "tenant": tenant_id,
                        "success": False,
                        "error": str(e)
                    })

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
                        "clientInfo": {"name": "multiuser-test", "version": "1.0"}
                    },
                    "id": 1
                },
                timeout=10
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
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/list",
                    "params": {},
                    "id": 1
                },
                timeout=10
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
                    "params": {
                        "name": tool_name,
                        "arguments": arguments
                    },
                    "id": 1
                },
                timeout=30
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
        if not self.setup_tenants():
            self._log("Failed to setup tenants", "ERROR")
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
        print("\n" + "="*80)
        print("📊 MULTIUSER TEST SUMMARY")
        print("="*80)

        for scenario in self.results["scenarios"]:
            total_tests = scenario['passed'] + scenario['failed']
            if total_tests > 0:
                print(f"\n{scenario['name']}:")
                print(f"  ✅ Passed: {scenario['passed']}")
                print(f"  ❌ Failed: {scenario['failed']}")

        print("\n" + "="*80)
        print(f"Overall Results:")
        print(f"  Total: {self.results['total']}")
        print(f"  ✅ Passed: {self.results['passed']}")
        print(f"  ❌ Failed: {self.results['failed']}")

        if self.results["failed"] == 0:
            print("\n✅ ALL TESTS PASSED")
        else:
            print(f"\n❌ {self.results['failed']} TEST(S) FAILED")

        print("="*80)


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
  # Run against real server with real credentials (requires env vars)
  export TEST_TENANT_A_ID=user-a
  export TEST_TENANT_A_UUID=uuid-a
  export TEST_TENANT_B_ID=user-b
  export TEST_TENANT_B_UUID=uuid-b
  export TEST_JWT_SECRET=your-jwt-secret
  python scripts/test-multiuser.py http://localhost:8001/mcp

  # Run with custom config
  python scripts/test-multiuser.py http://localhost:8001/mcp \\
    --config scripts/tests/mcp-test-multiuser.yaml

  # Verbose output
  python scripts/test-multiuser.py http://localhost:8001/mcp -v
        """
    )

    parser.add_argument(
        "endpoint",
        help="MCP endpoint URL (e.g., http://localhost:8001/mcp)"
    )

    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).parent / "tests" / "mcp-test-multiuser.yaml",
        help="Path to test configuration file"
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output"
    )

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

#!/usr/bin/env python3
"""
Multitenant MCP testing orchestrator.

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
    from jwt_helpers import generate_test_jwt, validate_quilt3_session_exists
except ImportError:
    print("❌ Could not import jwt_helpers. Make sure tests/jwt_helpers.py exists.", file=sys.stderr)
    sys.exit(1)


class MultitenantTestRunner:
    """Orchestrates multitenant testing across multiple tenants."""

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

        # Validate quilt3 session exists
        if not validate_quilt3_session_exists():
            self._log("quilt3 session not configured. Run: quilt3 login", "ERROR")
            return False

        # Generate token for each tenant
        for tenant_id, tenant_config in tenants_config.items():
            try:
                role_arn = tenant_config.get("role_arn")
                jwt_secret = tenant_config.get("jwt_secret")

                if not role_arn or not jwt_secret:
                    self._log(f"Missing role_arn or jwt_secret for tenant {tenant_id}", "ERROR")
                    return False

                self._log(f"Generating JWT for tenant: {tenant_id}", "DEBUG")

                token = generate_test_jwt(
                    role_arn=role_arn,
                    secret=jwt_secret,
                    tenant_id=tenant_id,
                    auto_extract=True,
                    expiry_seconds=3600
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

    def run_isolation_tests(self) -> Dict[str, Any]:
        """Run tenant isolation tests.

        Returns:
            Test results dictionary
        """
        self._log("\n" + "="*80)
        self._log("Running tenant isolation tests...")
        self._log("="*80)

        results = {
            "name": "Tenant Isolation",
            "passed": 0,
            "failed": 0,
            "tests": []
        }

        tenant_ids = list(self.tenant_tokens.keys())
        if len(tenant_ids) < 2:
            self._log("Need at least 2 tenants for isolation tests", "ERROR")
            return results

        tenant_a = tenant_ids[0]
        tenant_b = tenant_ids[1]
        token_a = self.tenant_tokens[tenant_a]
        token_b = self.tenant_tokens[tenant_b]

        self._log(f"Testing isolation between {tenant_a} and {tenant_b}")

        # Test 1: Tenant A creates workflow, Tenant B cannot access
        try:
            workflow_id = f"isolated-test-{int(time.time())}"

            # Tenant A creates workflow
            self._log(f"\n  {tenant_a}: Creating workflow '{workflow_id}'", "DEBUG")
            create_result = self._call_tool(
                token_a,
                "workflow_create",
                {
                    "workflow_id": workflow_id,
                    "description": f"Created by {tenant_a}"
                }
            )

            if not create_result.get("success"):
                results["failed"] += 1
                self._log(f"  ❌ {tenant_a} failed to create workflow", "ERROR")
                results["tests"].append({
                    "test": "workflow_creation",
                    "tenant": tenant_a,
                    "success": False,
                    "error": create_result.get("error")
                })
                return results

            self._log(f"  ✅ {tenant_a}: Workflow created")

            # Tenant B tries to access (should fail)
            self._log(f"  {tenant_b}: Attempting to access workflow", "DEBUG")
            access_result = self._call_tool(
                token_b,
                "workflow_status",
                {"workflow_id": workflow_id}
            )

            # We expect this to fail (workflow not found for tenant B)
            if access_result.get("success"):
                # If it succeeded, tenant isolation is broken!
                results["failed"] += 1
                self._log(f"  ❌ SECURITY ISSUE: {tenant_b} accessed {tenant_a}'s workflow!", "ERROR")
                results["tests"].append({
                    "test": "workflow_isolation",
                    "success": False,
                    "error": "Tenant B accessed Tenant A's workflow - isolation broken!"
                })
            else:
                # Failed as expected - isolation works
                error = access_result.get("error", "")
                if "not found" in error.lower():
                    results["passed"] += 1
                    self._log(f"  ✅ Isolation verified: {tenant_b} cannot access workflow")
                    results["tests"].append({
                        "test": "workflow_isolation",
                        "success": True,
                        "message": "Tenant isolation working correctly"
                    })
                else:
                    # Failed but for wrong reason
                    results["failed"] += 1
                    self._log(f"  ⚠️  Failed but unexpected error: {error}")
                    results["tests"].append({
                        "test": "workflow_isolation",
                        "success": False,
                        "error": f"Unexpected error: {error}"
                    })

        except Exception as e:
            results["failed"] += 1
            self._log(f"  ❌ Isolation test error: {e}", "ERROR")
            results["tests"].append({
                "test": "workflow_isolation",
                "success": False,
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
                        "clientInfo": {"name": "multitenant-test", "version": "1.0"}
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

        isolation_results = self.run_isolation_tests()
        self.results["scenarios"].append(isolation_results)
        self.results["total"] += isolation_results["passed"] + isolation_results["failed"]
        self.results["passed"] += isolation_results["passed"]
        self.results["failed"] += isolation_results["failed"]

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
        print("📊 MULTITENANT TEST SUMMARY")
        print("="*80)

        for scenario in self.results["scenarios"]:
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


def load_config(config_path: Path) -> Dict[str, Any]:
    """Load test configuration from YAML file."""
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        # Set environment variables from config
        env_vars = config.get("environment", {})
        for key, value in env_vars.items():
            if not os.environ.get(key):
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
        description="Multitenant MCP testing orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with default config
  python scripts/test-multitenant.py http://localhost:8001/mcp

  # Run with custom config
  python scripts/test-multitenant.py http://localhost:8001/mcp \\
    --config scripts/tests/mcp-test-multitenant.yaml

  # Verbose output
  python scripts/test-multitenant.py http://localhost:8001/mcp -v
        """
    )

    parser.add_argument(
        "endpoint",
        help="MCP endpoint URL (e.g., http://localhost:8001/mcp)"
    )

    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).parent / "tests" / "mcp-test-multitenant.yaml",
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
    runner = MultitenantTestRunner(config, args.endpoint, verbose=args.verbose)
    success = runner.run_all_tests()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

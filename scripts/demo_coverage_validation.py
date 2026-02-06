#!/usr/bin/env python3
"""
Demonstration of test coverage validation in mcp-test.py.

This script shows how the validation prevents config drift when tools are added
to the server without updating the test configuration.

Run this to see:
1. ✅ Success case: All tools covered
2. ❌ Error case: New tool added, config not updated
"""

import sys
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent))

# Import dynamically (can't use regular import due to hyphen in filename)
import importlib.util
spec = importlib.util.spec_from_file_location(
    "mcp_test",
    Path(__file__).parent / "mcp-test.py"
)
assert spec and spec.loader
mcp_test = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mcp_test)

validate_test_coverage = mcp_test.validate_test_coverage


def demo_success_case():
    """Demonstrate successful validation when all tools are covered."""
    print("=" * 80)
    print("✅ DEMO 1: Success Case - All Tools Covered")
    print("=" * 80)
    print()

    # Simulated server tools
    server_tools = [
        {"name": "bucket_objects_list"},
        {"name": "package_browse"},
        {"name": "search_catalog"}
    ]

    # Config covering all tools
    config_tools = {
        "bucket_objects_list": {
            "effect": "none",
            "arguments": {"bucket": "test-bucket"}
        },
        "package_browse": {
            "effect": "none",
            "arguments": {"package_name": "test/package"}
        },
        "search_catalog": {
            "effect": "none",
            "arguments": {"query": "test"}
        }
    }

    print(f"Server has {len(server_tools)} tools:")
    for tool in server_tools:
        print(f"  • {tool['name']}")

    print(f"\nConfig covers {len(config_tools)} tools:")
    for name in config_tools.keys():
        print(f"  • {name}")

    print("\n🔍 Running validation...")
    try:
        validate_test_coverage(server_tools, config_tools)
        print("✅ PASSED: All tools covered by config!")
    except ValueError as e:
        print(f"❌ FAILED: {e}")

    print()


def demo_failure_case():
    """Demonstrate validation error when new tool is not in config."""
    print("=" * 80)
    print("❌ DEMO 2: Failure Case - New Tool Not Covered")
    print("=" * 80)
    print()

    # Simulated server tools (including new tool!)
    server_tools = [
        {"name": "bucket_objects_list"},
        {"name": "package_browse"},
        {"name": "search_catalog"},
        {"name": "new_visualization_tool"},  # NEW TOOL ADDED!
        {"name": "new_admin_tool"}          # ANOTHER NEW TOOL!
    ]

    # Old config (hasn't been regenerated)
    config_tools = {
        "bucket_objects_list": {
            "effect": "none",
            "arguments": {"bucket": "test-bucket"}
        },
        "package_browse": {
            "effect": "none",
            "arguments": {"package_name": "test/package"}
        },
        "search_catalog": {
            "effect": "none",
            "arguments": {"query": "test"}
        }
        # Missing: new_visualization_tool, new_admin_tool
    }

    print(f"Server has {len(server_tools)} tools:")
    for tool in server_tools:
        marker = "🆕" if "new" in tool["name"] else "  "
        print(f"  {marker} {tool['name']}")

    print(f"\nConfig covers only {len(config_tools)} tools:")
    for name in config_tools.keys():
        print(f"  • {name}")

    print("\n🔍 Running validation...")
    try:
        validate_test_coverage(server_tools, config_tools)
        print("✅ PASSED: All tools covered by config!")
    except ValueError as e:
        print("❌ VALIDATION ERROR CAUGHT:")
        print(str(e))

    print()


def demo_variant_case():
    """Demonstrate validation with tool variants (search_catalog.file.no_bucket)."""
    print("=" * 80)
    print("🔀 DEMO 3: Tool Variants - Multiple Configs for Same Tool")
    print("=" * 80)
    print()

    # Server only knows about base tools
    server_tools = [
        {"name": "search_catalog"},
        {"name": "bucket_objects_list"}
    ]

    # Config has multiple variants of search_catalog
    config_tools = {
        "search_catalog.file.no_bucket": {
            "tool": "search_catalog",  # Maps to actual tool
            "effect": "none",
            "arguments": {"query": "test", "scope": "file"}
        },
        "search_catalog.package.with_bucket": {
            "tool": "search_catalog",
            "effect": "none",
            "arguments": {"query": "test", "scope": "package", "bucket": "my-bucket"}
        },
        "search_catalog.global.no_bucket": {
            "tool": "search_catalog",
            "effect": "none",
            "arguments": {"query": "test", "scope": "global"}
        },
        "bucket_objects_list": {
            "effect": "none",
            "arguments": {"bucket": "test"}
        }
    }

    print(f"Server has {len(server_tools)} tools:")
    for tool in server_tools:
        print(f"  • {tool['name']}")

    print(f"\nConfig has {len(config_tools)} test cases (variants):")
    for name in config_tools.keys():
        if "." in name:
            print(f"  🔀 {name} (variant)")
        else:
            print(f"  • {name}")

    print("\n🔍 Running validation...")
    try:
        validate_test_coverage(server_tools, config_tools)
        print("✅ PASSED: Variants correctly map to base tools!")
    except ValueError as e:
        print(f"❌ FAILED: {e}")

    print()


def main():
    """Run all demonstration scenarios."""
    print("\n" + "=" * 80)
    print("📊 MCP Test Coverage Validation Demonstration")
    print("=" * 80)
    print()
    print("This demonstrates the validation that prevents test config drift")
    print("when new tools are added to the MCP server.")
    print()

    # Run demos
    demo_success_case()
    demo_variant_case()
    demo_failure_case()

    print("=" * 80)
    print("💡 Key Takeaway")
    print("=" * 80)
    print()
    print("When you add new tools to the MCP server:")
    print("  1. The validation will ERROR if test config is outdated")
    print("  2. Run: uv run scripts/mcp-list.py")
    print("  3. This regenerates scripts/tests/mcp-test.yaml with ALL tools")
    print("  4. Tests can now run with full coverage")
    print()
    print("This prevents tools from being deployed without test coverage! ✅")
    print()


if __name__ == "__main__":
    main()

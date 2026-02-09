#!/usr/bin/env python3
"""Generate canonical tool and resource listings from MCP server code.

This script inspects the actual MCP server implementation to generate
authoritative tool and resource listings, eliminating manual maintenance and drift.
Resources are distinguished from tools with a 'type' column in the CSV output.

Phase 2 Enhancement: Intelligent test discovery with validation
- Executes tools with test parameters to discover what actually works
- Records PASSED/FAILED/SKIPPED status for each tool
- Captures actual response values for test expectations
- Uses discovered data to inform later tool tests

Phase 3 Enhancement (A18): 100% tool coverage with intelligent inference
- Tool classification system (5 categories)
- Argument inference from signatures and environment
- Context parameter injection for permission tools
- Coverage validation and reporting
- Smart regeneration (only when sources change)

Phase 4 Enhancement (A18): Tool loops for write-operation testing
- Define tool loops that create → modify → verify → cleanup resources
- Generate tool_loops section in YAML with template placeholders
- Support template substitution ({uuid}, {env.VAR})
- Enable 100% coverage including write operations
"""

import asyncio
import csv
import inspect
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import yaml
from enum import Enum
from dotenv import dotenv_values
from quiltx import get_catalog_url
from quiltx.stack import find_matching_stack, stack_outputs

# Add custom YAML representer for Enum objects
# This allows enums to be serialized as their string values instead of Python objects
def enum_representer(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', data.value)

yaml.add_multi_representer(Enum, enum_representer)

# Add src to path for imports
script_dir = Path(__file__).parent
repo_root = script_dir.parent
src_dir = repo_root / "src"

# Only add to path if not already in PYTHONPATH
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from quilt_mcp.utils import create_configured_server
from quilt_mcp.context.request_context import RequestContext

# Import testing framework modules
from quilt_mcp.testing import (
    DiscoveryResult,
    DiscoveryOrchestrator,
    DiscoveredDataRegistry,
    classify_tool,
    infer_arguments,
    create_mock_context,
    get_user_athena_database,
    generate_tool_loops,
    get_test_roles,
    validate_tool_loops_coverage,
    validate_test_coverage,
    truncate_response,
    generate_csv_output,
    generate_json_output,
    generate_test_yaml,
    extract_tool_metadata,
    extract_resource_metadata,
)


# ============================================================================
# Script-Specific Code
# ============================================================================
# Most functionality has been moved to quilt_mcp.testing module.
# Only script-specific code remains: enum_representer and main()
# ============================================================================

async def main():
    """Generate all canonical tool and resource listings."""
    import argparse

    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Generate MCP test configuration with intelligent discovery and 100% coverage"
    )
    parser.add_argument(
        "--skip-discovery",
        action="store_true",
        help="Skip tool discovery phase (generate config without validation)"
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate coverage without regenerating YAML (exit 0 if 100%%, 1 otherwise)"
    )
    parser.add_argument(
        "--show-missing",
        action="store_true",
        help="List tools without test configurations and exit"
    )
    parser.add_argument(
        "--show-categories",
        action="store_true",
        help="Show tool classification (category + effect) and exit"
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick mode: validate only essential tools (not yet implemented)"
    )
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="Re-discover only tools with FAILED status (not yet implemented)"
    )
    parser.add_argument(
        "--discovery-timeout",
        type=float,
        default=15.0,
        help="Timeout in seconds for each tool discovery (default: 15.0)"
    )
    args = parser.parse_args()

    # Load environment configuration from .env
    repo_root = Path(__file__).parent.parent
    env_file = repo_root / ".env"
    env_vars = dotenv_values(env_file)

    if env_vars:
        print(f"📋 Loaded configuration from .env")
        print(f"   AWS_PROFILE: {env_vars.get('AWS_PROFILE', 'not set')}")
        print(f"   AWS_DEFAULT_REGION: {env_vars.get('AWS_DEFAULT_REGION', 'not set')}")
        print(f"   QUILT_TEST_BUCKET: {env_vars.get('QUILT_TEST_BUCKET', 'not set')}")
    else:
        print("⚠️  No .env file found - using default test configuration")

    if args.skip_discovery:
        print("⚠️  Discovery phase skipped (--skip-discovery flag)")

    print("\n🔍 Phase 1: Introspection - Extracting tools from MCP server...")

    # Create server instance to introspect tools
    server = create_configured_server(verbose=False)

    # Handle --show-categories mode
    if args.show_categories:
        print("\n📊 Tool Classification:")
        server_tools = await server.get_tools()
        by_category = {}
        for tool_name, handler in server_tools.items():
            effect, category = classify_tool(tool_name, handler)
            by_category.setdefault(category, []).append((tool_name, effect))

        for category in ['zero-arg', 'required-arg', 'optional-arg', 'write-effect', 'context-required']:
            if category in by_category:
                print(f"\n{category.upper().replace('-', ' ')} ({len(by_category[category])} tools):")
                for tool_name, effect in sorted(by_category[category]):
                    print(f"  • {tool_name} (effect={effect})")
        sys.exit(0)

    # Handle --show-missing mode
    if args.show_missing:
        scripts_tests_dir = Path(__file__).parent / "tests"
        yaml_path = scripts_tests_dir / "mcp-test.yaml"

        if not yaml_path.exists():
            print(f"❌ Test config not found: {yaml_path}")
            print("   Run without --show-missing to generate it")
            sys.exit(1)

        # Load existing YAML
        with open(yaml_path, 'r') as f:
            config = yaml.safe_load(f)

        # Get server tools
        server_tools = await server.get_tools()
        server_tool_names = set(server_tools.keys())

        # Get config tools (handle variants)
        config_tool_names = set()
        for config_key, config_value in config.get('test_tools', {}).items():
            if isinstance(config_value, dict) and 'tool' in config_value:
                config_tool_names.add(config_value['tool'])
            else:
                config_tool_names.add(config_key)

        # Find missing
        missing = server_tool_names - config_tool_names

        if missing:
            print(f"\n❌ {len(missing)} tool(s) NOT covered by test config:")
            for tool_name in sorted(missing):
                handler = server_tools[tool_name]
                effect, category = classify_tool(tool_name, handler)
                print(f"  • {tool_name} (category={category}, effect={effect})")
            print(f"\n📋 Coverage: {len(config_tool_names)}/{len(server_tool_names)} tools")
            print(f"   Run without --show-missing to regenerate with 100% coverage")
            sys.exit(1)
        else:
            print(f"✅ All {len(server_tool_names)} tools covered by test config")
            sys.exit(0)

    # Handle --validate-only mode
    if args.validate_only:
        scripts_tests_dir = Path(__file__).parent / "tests"
        yaml_path = scripts_tests_dir / "mcp-test.yaml"

        if not yaml_path.exists():
            print(f"❌ Test config not found: {yaml_path}")
            sys.exit(1)

        with open(yaml_path, 'r') as f:
            config = yaml.safe_load(f)

        server_tools = await server.get_tools()
        server_tool_names = set(server_tools.keys())

        config_tool_names = set()
        for config_key, config_value in config.get('test_tools', {}).items():
            if isinstance(config_value, dict) and 'tool' in config_value:
                config_tool_names.add(config_value['tool'])
            else:
                config_tool_names.add(config_key)

        missing = server_tool_names - config_tool_names

        if missing:
            print(f"❌ Coverage validation FAILED: {len(missing)} tools missing")
            sys.exit(1)
        else:
            print(f"✅ Coverage validation PASSED: {len(server_tool_names)} tools covered")
            sys.exit(0)

    tools = await extract_tool_metadata(server)

    print(f"📊 Found {len(tools)} tools across {len(set(tool['module'] for tool in tools))} modules")

    print("🔍 Extracting resources from MCP server...")
    # Get resources directly from FastMCP server
    resources = await extract_resource_metadata(server)

    print(f"📊 Found {len(resources)} resources across {len(set(resource['module'] for resource in resources))} modules")

    # Combine tools and resources
    all_items = tools + resources

    # Generate outputs
    output_dir = Path(__file__).parent.parent
    tests_fixtures_dir = output_dir / "tests" / "fixtures"
    scripts_tests_dir = Path(__file__).parent / "tests"

    print("\n📝 Generating CSV output...")
    generate_csv_output(all_items, str(tests_fixtures_dir / "mcp-list.csv"))

    print("📋 Generating JSON metadata...")
    generate_json_output(all_items, str(output_dir / "build" / "tools_metadata.json"))

    print("\n🧪 Phase 3: Generation - Creating test configuration YAML...")
    await generate_test_yaml(
        server,
        str(scripts_tests_dir / "mcp-test.yaml"),
        env_vars,
        skip_discovery=args.skip_discovery,
        discovery_timeout=args.discovery_timeout
    )

    print("\n✅ Canonical tool and resource listings generated!")
    print("📂 Files created:")
    print("   - tests/fixtures/mcp-list.csv")
    print("   - build/tools_metadata.json")
    print("   - scripts/tests/mcp-test.yaml (with discovery results and tool loops)")
    print(f"\n📈 Summary:")
    print(f"   - {len(tools)} tools")
    print(f"   - {len(resources)} resources")
    print(f"   - {len(all_items)} total items")

    if not args.skip_discovery:
        print(f"\n💡 Next steps:")
        print(f"   1. Review tool loops section in mcp-test.yaml")
        print(f"   2. Run all tests: uv run python scripts/mcp-test.py")
        print(f"   3. Test specific loop: uv run python scripts/mcp-test.py --loops admin_user_basic")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

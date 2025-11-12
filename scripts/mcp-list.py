#!/usr/bin/env python3
"""Generate canonical tool and resource listings from MCP server code.

This script inspects the actual MCP server implementation to generate
authoritative tool and resource listings, eliminating manual maintenance and drift.
Resources are distinguished from tools with a 'type' column in the CSV output.
"""

import csv
import inspect
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import yaml
from dotenv import dotenv_values

# Add src to path for imports
script_dir = Path(__file__).parent
repo_root = script_dir.parent
src_dir = repo_root / "src"

# Only add to path if not already in PYTHONPATH
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from quilt_mcp.utils import create_configured_server
from quilt_mcp.resources import create_default_registry

async def extract_tool_metadata(server) -> List[Dict[str, Any]]:
    """Extract comprehensive metadata from all registered tools."""
    tools = []

    server_tools = await server.get_tools()
    for tool_name, handler in server_tools.items():
        # Get function signature and docstring
        sig = inspect.signature(handler.fn)
        doc = inspect.getdoc(handler.fn) or "No description available"

        # Get module information
        module = inspect.getmodule(handler.fn)
        module_name = module.__name__ if module else "unknown"

        # Extract module short name (last component)
        short_module = module_name.split('.')[-1]

        # Check if function is async
        is_async = inspect.iscoroutinefunction(handler.fn)

        # Build full signature string
        signature_str = f"{tool_name}{sig}"

        tools.append({
            "type": "tool",
            "name": tool_name,
            "module": short_module,
            "signature": signature_str,
            "description": doc.split('\n')[0],  # First line only
            "is_async": is_async,
            "full_module_path": module_name,
            "handler_class": handler.__class__.__name__
        })

    # Sort by module then name for consistent ordering
    tools.sort(key=lambda x: (x["module"], x["name"]))
    return tools

async def extract_resource_metadata() -> List[Dict[str, Any]]:
    """Extract comprehensive metadata from all registered resources."""
    resources = []

    registry = create_default_registry()

    # Access the internal _resources list to iterate through registered resources
    for resource in registry._resources:
        # Get resource class information
        resource_class = resource.__class__
        module = inspect.getmodule(resource_class)
        module_name = module.__name__ if module else "unknown"

        # Extract module short name (last component)
        short_module = module_name.split('.')[-1]

        # Get class docstring
        doc = inspect.getdoc(resource_class) or "No description available"

        # Build signature string showing the URI pattern
        uri_pattern = resource.uri_pattern
        signature_str = f"{resource_class.__name__}(uri='{uri_pattern}')"

        # Check if _read_impl method exists and is async
        is_async = hasattr(resource, '_read_impl') and inspect.iscoroutinefunction(resource._read_impl)

        resources.append({
            "type": "resource",
            "name": uri_pattern,
            "module": short_module,
            "signature": signature_str,
            "description": doc.split('\n')[0],  # First line only
            "is_async": is_async,
            "full_module_path": module_name,
            "handler_class": resource_class.__name__
        })

    # Sort by URI pattern for consistent ordering
    resources.sort(key=lambda x: x["name"])
    return resources

def generate_csv_output(items: List[Dict[str, Any]], output_file: str):
    """Generate CSV output for tools and resources with type column."""
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            "type", "module", "function_name", "signature", "description",
            "is_async", "full_module_path"
        ])

        for item in items:
            writer.writerow([
                item["type"],
                item["module"],
                item["name"],
                item["signature"],
                item["description"],
                str(item["is_async"]),
                item["full_module_path"]
            ])

def generate_json_output(items: List[Dict[str, Any]], output_file: str):
    """Generate structured JSON output for tooling."""
    tools = [item for item in items if item["type"] == "tool"]
    resources = [item for item in items if item["type"] == "resource"]

    output = {
        "metadata": {
            "generated_by": "scripts/mcp-list.py",
            "tool_count": len(tools),
            "resource_count": len(resources),
            "total_count": len(items),
            "modules": list(set(item["module"] for item in items))
        },
        "tools": tools,
        "resources": resources
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)


async def generate_test_yaml(server, output_file: str, env_vars: Dict[str, str]):
    """Generate mcp-test.yaml configuration with all available tools.

    This creates test configurations for mcp-test.py to validate the MCP server.
    Each tool gets a basic test case that can be customized as needed.
    Environment configuration from .env is embedded for self-contained testing.
    """
    # Extract test-relevant configuration from environment
    test_config = {
        "_generated_by": "scripts/mcp-list.py - Auto-generated test configuration",
        "_note": "Edit test cases below to customize arguments and validation",
        "environment": {
            "AWS_PROFILE": env_vars.get("AWS_PROFILE", "default"),
            "AWS_DEFAULT_REGION": env_vars.get("AWS_DEFAULT_REGION", "us-east-1"),
            "QUILT_CATALOG_DOMAIN": env_vars.get("QUILT_CATALOG_DOMAIN", ""),
            "QUILT_DEFAULT_BUCKET": env_vars.get("QUILT_DEFAULT_BUCKET", ""),
            "QUILT_TEST_PACKAGE": env_vars.get("QUILT_TEST_PACKAGE", ""),
            "QUILT_TEST_ENTRY": env_vars.get("QUILT_TEST_ENTRY", ""),
        },
        "test_tools": {},
        "test_config": {
            "timeout": 30,
            "retry_attempts": 2,
            "fail_fast": False
        }
    }

    # Get all registered tools
    # Get all tools
    server_tools = await server.get_tools()

    # Load values from .env
    default_bucket = env_vars.get("QUILT_DEFAULT_BUCKET", "s3://quilt-example")
    catalog_domain = env_vars.get("QUILT_CATALOG_DOMAIN", "open.quiltdata.com")
    test_package = env_vars.get("QUILT_TEST_PACKAGE", "examples/wellplates")
    bucket_name = default_bucket.replace("s3://", "").split("/")[0]

    # Define test execution order and custom configurations
    # Phase 1: Setup, Phase 2: Discovery, Phase 3-N: Use discovered data
    tool_order = [
        # Phase 1: Setup
        "catalog_configure",
        # Phase 2: Discovery - list real objects first
        "bucket_objects_list",
        "search_catalog",
        "search_explain",
        "search_suggest",
        # Phase 3: Catalog operations
        "catalog_uri",
        "catalog_url",
        # Phase 4: Bucket operations
        "bucket_object_info",
        "bucket_object_link",
        "bucket_object_text",
        "bucket_object_fetch",
        # Phase 5: Package operations
        "package_browse",
        "package_diff",
        # Phase 6: Query operations
        "athena_query_validate",
        "athena_query_execute",
        "tabulator_bucket_query",
        # Phase 7: Admin operations (may require auth)
        "tabulator_open_query_status",
        "tabulator_table_rename",
        # Phase 8: Workflow operations
        "workflow_template_apply",
    ]

    # Custom test configurations for specific tools
    custom_configs = {
        "catalog_configure": {"catalog_url": catalog_domain},
        "bucket_objects_list": {"bucket": bucket_name, "prefix": f"{test_package}/", "max_keys": 5},
        "search_catalog": {"query": test_package, "limit": 10, "scope": "bucket", "target": default_bucket},
        "search_explain": {"query": "CSV files"},
        "search_suggest": {"partial_query": test_package[:5], "limit": 5},
        "catalog_uri": {"registry": default_bucket, "package_name": test_package, "path": ".timestamp"},
        "catalog_url": {"registry": default_bucket, "package_name": test_package, "path": ".timestamp"},
        "bucket_object_info": {"s3_uri": f"{default_bucket}/{test_package}/.timestamp"},
        "bucket_object_link": {"s3_uri": f"{default_bucket}/{test_package}/.timestamp"},
        "bucket_object_text": {"s3_uri": f"{default_bucket}/{test_package}/.timestamp", "max_bytes": 200},
        "bucket_object_fetch": {"s3_uri": f"{default_bucket}/{test_package}/.timestamp", "max_bytes": 200},
        "package_browse": {"package_name": test_package, "registry": default_bucket, "recursive": False, "include_signed_urls": False, "top": 5},
        "package_diff": {"package1_name": test_package, "package2_name": test_package, "registry": default_bucket},
        "athena_query_validate": {"query": "SHOW TABLES"},
        "athena_query_execute": {"query": "SELECT 1 as test_value", "max_results": 10},
        "tabulator_bucket_query": {"bucket_name": bucket_name, "query": "SELECT 1 as test_value", "max_results": 10},
        "tabulator_open_query_status": {},
        "tabulator_table_rename": {"bucket_name": bucket_name, "table_name": "test_table_nonexistent", "new_table_name": "test_renamed"},
        "workflow_template_apply": {"template_name": "cross-package-aggregation", "workflow_id": "test-wf-001", "params": {"source_packages": [test_package], "target_package": f"{test_package}-agg"}},
    }

    # Process tools in defined order
    for tool_name in tool_order:
        if tool_name not in server_tools:
            continue

        handler = server_tools[tool_name]
        doc = inspect.getdoc(handler.fn) or "No description available"

        # Determine if operation is idempotent
        non_idempotent_keywords = ['create', 'update', 'delete', 'put', 'upload', 'set', 'add', 'remove', 'reset', 'rename']
        is_idempotent = not any(keyword in tool_name.lower() for keyword in non_idempotent_keywords)

        # Build test case
        test_case = {
            "description": doc.split('\n')[0],
            "idempotent": is_idempotent,
            "arguments": custom_configs.get(tool_name, {}),
            "response_schema": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "array",
                        "items": {
                            "type": "object"
                        }
                    }
                },
                "required": ["content"]
            }
        }

        test_config["test_tools"][tool_name] = test_case

    # Write YAML with nice formatting
    with open(output_file, 'w', encoding='utf-8') as f:
        yaml.dump(test_config, f,
                  default_flow_style=False,
                  sort_keys=False,
                  allow_unicode=True,
                  indent=2)


async def main():
    """Generate all canonical tool and resource listings."""
    # Load environment configuration from .env
    repo_root = Path(__file__).parent.parent
    env_file = repo_root / ".env"
    env_vars = dotenv_values(env_file)

    if env_vars:
        print(f"📋 Loaded configuration from .env")
        print(f"   AWS_PROFILE: {env_vars.get('AWS_PROFILE', 'not set')}")
        print(f"   AWS_DEFAULT_REGION: {env_vars.get('AWS_DEFAULT_REGION', 'not set')}")
        print(f"   QUILT_DEFAULT_BUCKET: {env_vars.get('QUILT_DEFAULT_BUCKET', 'not set')}")
    else:
        print("⚠️  No .env file found - using default test configuration")

    print("🔍 Extracting tools from MCP server...")

    # Create server instance to introspect tools
    server = create_configured_server(verbose=False)
    tools = await extract_tool_metadata(server)

    print(f"📊 Found {len(tools)} tools across {len(set(tool['module'] for tool in tools))} modules")

    print("🔍 Extracting resources from MCP registry...")
    resources = await extract_resource_metadata()

    print(f"📊 Found {len(resources)} resources across {len(set(resource['module'] for resource in resources))} modules")

    # Combine tools and resources
    all_items = tools + resources

    # Generate outputs
    output_dir = Path(__file__).parent.parent
    tests_fixtures_dir = output_dir / "tests" / "fixtures"
    scripts_tests_dir = Path(__file__).parent / "tests"

    print("📝 Generating CSV output...")
    generate_csv_output(all_items, str(tests_fixtures_dir / "mcp-list.csv"))

    print("📋 Generating JSON metadata...")
    generate_json_output(all_items, str(output_dir / "build" / "tools_metadata.json"))

    print("🧪 Generating test configuration YAML...")
    await generate_test_yaml(server, str(scripts_tests_dir / "mcp-test.yaml"), env_vars)

    print("✅ Canonical tool and resource listings generated!")
    print("📂 Files created:")
    print("   - tests/fixtures/mcp-list.csv")
    print("   - build/tools_metadata.json")
    print("   - scripts/tests/mcp-test.yaml")
    print(f"📈 Summary:")
    print(f"   - {len(tools)} tools")
    print(f"   - {len(resources)} resources")
    print(f"   - {len(all_items)} total items")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
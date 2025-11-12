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


async def generate_test_yaml(server, output_file: str, env_vars: Dict[str, str | None]):
    """Generate mcp-test.yaml configuration with all available tools and resources.

    This creates test configurations for mcp-test.py to validate the MCP server.
    Each tool gets a basic test case that can be customized as needed.
    Each resource gets test configuration with URI patterns and validation rules.
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
        "test_resources": {},
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
    default_bucket: str = env_vars.get("QUILT_DEFAULT_BUCKET") or "s3://quilt-example"
    catalog_domain: str = env_vars.get("QUILT_CATALOG_DOMAIN") or "open.quiltdata.com"
    test_package: str = env_vars.get("QUILT_TEST_PACKAGE") or "examples/wellplates"
    test_entry: str = env_vars.get("QUILT_TEST_ENTRY") or ".timestamp"
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

    # Tools with multiple test variants based on parameter combinations
    # Format: tool_name -> {"param_name": [test_value1, test_value2, ...]}
    # Special handling: if variant name contains "package", uses QUILT_TEST_PACKAGE, else QUILT_TEST_ENTRY
    tool_variants = {
        "search_catalog": {
            "scope": ["global", "bucket", "package"]
        }
    }

    # Custom test configurations for specific tools
    # For tools with variants, use tool_name.variant_value format
    custom_configs = {
        "catalog_configure": {"catalog_url": catalog_domain},
        "bucket_objects_list": {"bucket": bucket_name, "prefix": f"{test_package}/", "max_keys": 5},
        "search_catalog.global": {"query": test_entry, "limit": 10, "scope": "global"},
        "search_catalog.bucket": {"query": test_entry, "limit": 10, "scope": "bucket", "target": default_bucket},
        "search_catalog.package": {"query": test_package, "limit": 10, "scope": "package"},
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

        # Classify tool by effect type
        def classify_effect(name: str) -> str:
            """Classify tool effect based on operation keywords in name."""
            name_lower = name.lower()

            # Order matters: check more specific patterns first
            if any(kw in name_lower for kw in ['create', 'put', 'upload', 'set']):
                return 'create'
            if any(kw in name_lower for kw in ['delete', 'remove', 'reset']):
                return 'remove'
            if any(kw in name_lower for kw in ['update', 'add', 'rename']):
                return 'update'
            if any(kw in name_lower for kw in ['configure', 'toggle', 'apply', 'execute', 'generate', 'rename']):
                return 'configure'

            # Default: read-only operation
            return 'none'

        effect = classify_effect(tool_name)

        # Check if this tool has variants
        if tool_name in tool_variants:
            # Generate test cases for each variant
            for param_name, param_values in tool_variants[tool_name].items():
                for param_value in param_values:
                    variant_key = f"{tool_name}.{param_value}"

                    # Get custom config or use the variant value
                    if variant_key in custom_configs:
                        arguments = custom_configs[variant_key]
                    else:
                        # Auto-generate based on variant: "package" uses TEST_PACKAGE, others use TEST_ENTRY
                        query_value = test_package if "package" in param_value else test_entry
                        arguments = {"query": query_value, "limit": 10, param_name: param_value}

                        # Add target for bucket scope
                        if param_value == "bucket":
                            arguments["target"] = default_bucket

                    test_case = {
                        "tool": tool_name,  # Store the actual tool name
                        "description": doc.split('\n')[0],
                        "effect": effect,
                        "arguments": arguments,
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

                    test_config["test_tools"][variant_key] = test_case
        else:
            # Single test case for tools without variants
            test_case = {
                "description": doc.split('\n')[0],
                "effect": effect,
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

    # Generate resource test configuration
    print("🗂️  Generating resource test configuration...")
    registry = create_default_registry()

    import re
    for resource in registry._resources:
        uri_pattern = resource.uri_pattern
        resource_class = resource.__class__
        doc = inspect.getdoc(resource_class) or "No description available"

        # Build basic test case structure - default to JSON since most resources return JSON
        test_case = {
            "description": doc.split('\n')[0],
            "effect": "none",  # Resources are read-only
            "uri": uri_pattern,
            "uri_variables": {},
            "expected_mime_type": "application/json",  # Default to JSON
            "content_validation": {
                "type": "json",
                "min_length": 1,
                "max_length": 100000,
                "schema": {
                    "type": "object",
                    "description": "Auto-generated basic schema - customize as needed"
                }
            }
        }

        # Detect URI template variables (e.g., {database}, {table}, {bucket})
        # FastMCP supports templated URIs when registered with add_resource_fn
        # The client expands templates with actual values, and FastMCP handles routing
        variables = re.findall(r'\{(\w+)\}', uri_pattern)
        for var in variables:
            # Substitute test values for common template variables
            if var == "bucket":
                # Use bucket name from QUILT_DEFAULT_BUCKET environment variable (already loaded above)
                # Extract bucket name from s3:// URI
                bucket_name_var = default_bucket.replace("s3://", "").split("/")[0] if default_bucket.startswith("s3://") else default_bucket
                test_case["uri_variables"][var] = bucket_name_var
            elif var == "database":
                # Use default test database
                test_case["uri_variables"][var] = "default"
            elif var == "table":
                # Use a test table name
                test_case["uri_variables"][var] = "test_table"
            elif var == "name":
                # Use a test user name
                test_case["uri_variables"][var] = "test_user"
            elif var == "id":
                # Use a test workflow ID
                test_case["uri_variables"][var] = "test-workflow-001"
            else:
                # For unknown variables, mark as needing configuration
                test_case["uri_variables"][var] = f"CONFIGURE_{var.upper()}"

        # Infer content type from resource class or URI pattern
        # Most resources return JSON by default (via ResourceResponse default mime_type)
        # Only override if we know the resource returns something else
        class_name = resource_class.__name__.lower()
        uri_lower = uri_pattern.lower()

        # No special cases needed - all resources currently return JSON
        # (metadata resources return JSON data structures, not HTML)

        test_config["test_resources"][uri_pattern] = test_case

    print(f"   Generated {len(test_config['test_resources'])} resource test cases")

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
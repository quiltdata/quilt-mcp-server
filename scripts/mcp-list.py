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

async def extract_tool_metadata(server) -> List[Dict[str, Any]]:
    """Extract comprehensive metadata from all registered tools."""
    tools = []

    server_tools = await server.get_tools()
    for tool_name, handler in server_tools.items():
        # Get function signature and docstring
        sig = inspect.signature(handler.fn)
        doc = inspect.getdoc(handler.fn)

        # ERROR if tool lacks a description
        if not doc:
            raise ValueError(f"Tool '{tool_name}' is missing a docstring description!")

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

async def extract_resource_metadata(server) -> List[Dict[str, Any]]:
    """Extract comprehensive metadata from all registered resources via FastMCP."""
    resources = []

    # Get resources from FastMCP server
    static_resources = await server.get_resources()
    resource_templates = await server.get_resource_templates()

    # Process static resources
    # static_resources is a dict with URI keys and FunctionResource values
    for uri, resource in static_resources.items():
        # ERROR if resource lacks a name
        if not hasattr(resource, 'name') or not resource.name:
            raise ValueError(f"Resource '{uri}' is missing a name!")

        # ERROR if resource lacks a description
        if not hasattr(resource, 'description') or not resource.description:
            raise ValueError(f"Resource '{uri}' is missing a description!")

        resources.append({
            "type": "resource",
            "name": uri,
            "module": "resources",
            "signature": f"@mcp.resource('{uri}')",
            "description": resource.description,
            "is_async": True,
            "full_module_path": "quilt_mcp.resources",
            "handler_class": "FastMCP Resource"
        })

    # Process resource templates
    # resource_templates is a dict with URI template keys and FunctionResource values
    for uri_template, template in resource_templates.items():
        # ERROR if template lacks a name
        if not hasattr(template, 'name') or not template.name:
            raise ValueError(f"Resource template '{uri_template}' is missing a name!")

        # ERROR if template lacks a description
        if not hasattr(template, 'description') or not template.description:
            raise ValueError(f"Resource template '{uri_template}' is missing a description!")

        resources.append({
            "type": "resource",
            "name": uri_template,
            "module": "resources",
            "signature": f"@mcp.resource('{uri_template}')",
            "description": template.description,
            "is_async": True,
            "full_module_path": "quilt_mcp.resources",
            "handler_class": "FastMCP Template"
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
            "QUILT_TEST_BUCKET": env_vars.get("QUILT_TEST_BUCKET", ""),
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
    test_bucket: str = env_vars.get("QUILT_TEST_BUCKET") or "s3://quilt-example"
    catalog_domain: str = env_vars.get("QUILT_CATALOG_DOMAIN") or "open.quiltdata.com"
    test_package: str = env_vars.get("QUILT_TEST_PACKAGE") or "examples/wellplates"
    test_entry: str = env_vars.get("QUILT_TEST_ENTRY") or ".timestamp"
    bucket_name = test_bucket.replace("s3://", "").split("/")[0]

    # Auto-generate tool order from all discovered tools
    # Special case: bucket_objects_list runs FIRST to discover real objects
    all_tool_names = list(server_tools.keys())

    # Separate bucket_objects_list from others
    priority_tools = []
    if "bucket_objects_list" in all_tool_names:
        priority_tools.append("bucket_objects_list")
        all_tool_names.remove("bucket_objects_list")

    # Sort remaining tools alphabetically for deterministic ordering
    all_tool_names.sort()

    # Final order: priority tools first, then all others
    tool_order = priority_tools + all_tool_names

    # Tools with multiple test variants based on parameter combinations
    # Format: tool_name -> {"param_name": [test_value1, test_value2, ...]}
    # Special handling: if variant name contains "package", uses QUILT_TEST_PACKAGE, else QUILT_TEST_ENTRY
    # For search_catalog: Generate both "with bucket" and "without bucket" variants
    # This exercises both specific-bucket and wildcard index pattern code paths
    tool_variants = {
        "search_catalog": {
            "scope": ["global", "file", "package"],
            "bucket_mode": ["with_bucket", "no_bucket"]  # Test both code paths
        }
    }

    # Custom test configurations for specific tools
    # For tools with variants, use tool_name.variant_value format
    # Note: Empty dict {} means tool has no required params (will be auto-filled by effect classifier)
    custom_configs = {
        # Catalog operations
        "catalog_configure": {"catalog_url": catalog_domain},
        "catalog_uri": {"registry": test_bucket, "package_name": test_package, "path": ".timestamp"},
        "catalog_url": {"registry": test_bucket, "package_name": test_package, "path": ".timestamp"},

        # Bucket operations (discovery)
        "bucket_objects_list": {"bucket": bucket_name, "prefix": f"{test_package}/", "max_keys": 5},
        "bucket_object_info": {"s3_uri": f"{test_bucket}/{test_package}/.timestamp"},
        "bucket_object_link": {"s3_uri": f"{test_bucket}/{test_package}/.timestamp"},
        "bucket_object_text": {"s3_uri": f"{test_bucket}/{test_package}/.timestamp", "max_bytes": 200},
        "bucket_object_fetch": {"s3_uri": f"{test_bucket}/{test_package}/.timestamp", "max_bytes": 200},
        # bucket_objects_put: Intentionally omitted - will be skipped as 'create' effect

        # Package operations (read-only)
        "package_browse": {"package_name": test_package, "registry": test_bucket, "recursive": False, "include_signed_urls": False, "top": 5},
        "package_diff": {"package1_name": test_package, "package2_name": test_package, "registry": test_bucket},
        # package_create, package_update, package_delete: Omitted - 'create'/'update'/'remove' effects
        # package_create_from_s3: Omitted - 'create' effect

        # Search operations (search_catalog variants auto-generated, see tool_variants)
        "search_explain": {"query": "CSV files"},
        "search_suggest": {"partial_query": test_package[:5], "limit": 5},

        # Query operations
        "athena_query_validate": {"query": "SHOW TABLES"},
        "athena_query_execute": {"query": "SELECT 1 as test_value", "max_results": 10},
        "tabulator_bucket_query": {"bucket_name": bucket_name, "query": "SELECT 1 as test_value", "max_results": 10},
        "tabulator_open_query_status": {},
        # tabulator_open_query_toggle: Omitted - 'configure' effect
        # tabulator_table_create, tabulator_table_delete, tabulator_table_rename: Omitted - write effects

        # Workflow operations
        "workflow_template_apply": {"template_name": "cross-package-aggregation", "workflow_id": "test-wf-001", "params": {"source_packages": [test_package], "target_package": f"{test_package}-agg"}},
        # workflow_create, workflow_add_step, workflow_update_step: Omitted - write effects

        # Visualization operations
        # create_data_visualization: Omitted - 'create' effect
        # create_quilt_summary_files, generate_package_visualizations, generate_quilt_summarize_json: Omitted - 'create'/'generate' effects

        # Permissions operations - limit to test bucket for faster execution
        "discover_permissions": {"check_buckets": [bucket_name]},

        # Admin/Governance operations (all omitted - require special permissions and have side effects)
        # admin_user_*, admin_sso_*, admin_tabulator_*: All omitted
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
            # Generate test cases for each variant combination
            variants_config = tool_variants[tool_name]

            # Handle multi-dimensional variants (e.g., scope x bucket_mode)
            if "bucket_mode" in variants_config:
                # Special handling for search_catalog with scope and bucket combinations
                scope_values = variants_config.get("scope", ["global"])
                bucket_modes = variants_config.get("bucket_mode", ["with_bucket"])

                for scope in scope_values:
                    for bucket_mode in bucket_modes:
                        # Create variant key like "search_catalog.file.no_bucket"
                        variant_key = f"{tool_name}.{scope}.{bucket_mode}"

                        # Determine query value based on scope
                        query_value = test_package if scope == "package" else test_entry

                        # Build arguments based on bucket_mode
                        arguments = {
                            "query": query_value,
                            "limit": 10,
                            "scope": scope
                        }

                        if bucket_mode == "with_bucket":
                            arguments["bucket"] = test_bucket
                        else:  # no_bucket
                            arguments["bucket"] = ""  # Empty string tests wildcard patterns

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

                        # Add smart validation rules for search variants
                        validation = {
                            "type": "search",
                            "min_results": 1,
                            "must_contain": []
                        }

                        if scope == "file":
                            # File search must find TEST_ENTRY
                            if bucket_mode == "with_bucket":
                                validation["description"] = f"File search with specific bucket must find TEST_ENTRY ({test_entry})"
                            else:
                                validation["description"] = f"File search across all buckets (wildcard) must find TEST_ENTRY ({test_entry})"

                            validation["must_contain"].append({
                                "value": test_entry,
                                "field": "title",
                                "match_type": "substring",
                                "description": f"Must find {test_entry} in file search results (title field)"
                            })
                            validation["result_shape"] = {
                                "required_fields": ["id", "type", "title", "score"]
                            }

                        elif scope == "package":
                            # Package search should return results
                            if bucket_mode == "with_bucket":
                                validation["description"] = f"Package search with specific bucket should return results"
                            else:
                                validation["description"] = f"Package search across all buckets (wildcard) should return results"

                            validation["min_results"] = 1
                            validation["result_shape"] = {
                                "required_fields": ["id", "type", "score"]
                            }

                        elif scope == "global":
                            # Global search should find test entry
                            if bucket_mode == "with_bucket":
                                validation["description"] = "Global search with specific bucket should return results including test entry"
                            else:
                                validation["description"] = "Global search across all buckets (_all index) should return results including test entry"

                            validation["must_contain"].append({
                                "value": test_entry,
                                "field": "title",
                                "match_type": "substring",
                                "description": f"Must find TEST_ENTRY ({test_entry}) in global results (title field)"
                            })
                            validation["min_results"] = 1

                        test_case["validation"] = validation
                        test_config["test_tools"][variant_key] = test_case
            else:
                # Legacy single-parameter variant handling (for future tools if needed)
                for param_name, param_values in variants_config.items():
                    for param_value in param_values:
                        variant_key = f"{tool_name}.{param_value}"
                        arguments = {"query": test_entry, "limit": 10, param_name: param_value}
                        test_case = {
                            "tool": tool_name,
                            "description": doc.split('\n')[0],
                            "effect": effect,
                            "arguments": arguments,
                            "response_schema": {
                                "type": "object",
                                "properties": {
                                    "content": {
                                        "type": "array",
                                        "items": {"type": "object"}
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

    import re
    # Get resources from FastMCP server
    static_resources = await server.get_resources()
    resource_templates = await server.get_resource_templates()

    # Process both static resources and templates
    # Both are dicts with URI (template) keys and FunctionResource values
    all_resources = []
    for uri, resource in static_resources.items():
        # ERROR if resource lacks a description
        if not hasattr(resource, 'description') or not resource.description:
            raise ValueError(f"Resource '{uri}' is missing a description in test YAML generation!")
        all_resources.append((uri, resource.description))

    for uri_template, template in resource_templates.items():
        # ERROR if template lacks a description
        if not hasattr(template, 'description') or not template.description:
            raise ValueError(f"Resource template '{uri_template}' is missing a description in test YAML generation!")
        all_resources.append((uri_template, template.description))

    for uri_pattern, doc in all_resources:

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
                # Use bucket name from QUILT_TEST_BUCKET environment variable (already loaded above)
                # Extract bucket name from s3:// URI
                bucket_name_var = test_bucket.replace("s3://", "").split("/")[0] if test_bucket.startswith("s3://") else test_bucket
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

        # All resources return JSON by default
        # (FastMCP decorator-based resources all return JSON)

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
        print(f"   QUILT_TEST_BUCKET: {env_vars.get('QUILT_TEST_BUCKET', 'not set')}")
    else:
        print("⚠️  No .env file found - using default test configuration")

    print("🔍 Extracting tools from MCP server...")

    # Create server instance to introspect tools
    server = create_configured_server(verbose=False)
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

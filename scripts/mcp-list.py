#!/usr/bin/env python3
"""Generate canonical tool listings from MCP server code.

This script inspects the actual MCP server implementation to generate
authoritative tool listings, eliminating manual maintenance and drift.
"""

import csv
import inspect
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

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
        doc = inspect.getdoc(handler.fn) or "No description available"

        # Get module information
        module = inspect.getmodule(handler.fn)
        module_name = module.__name__ if module else "unknown"

        # Extract module short name (last component)
        if module_name.startswith("quilt_mcp.tools."):
            short_module = module_name.replace("quilt_mcp.tools.", "")
        else:
            short_module = module_name

        # Check if function is async
        is_async = inspect.iscoroutinefunction(handler.fn)

        # Build full signature string
        signature_str = f"{tool_name}{sig}"

        tools.append({
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

def generate_csv_output(tools: List[Dict[str, Any]], output_file: str):
    """Generate CSV output matching current format."""
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            "module", "function_name", "signature", "description",
            "is_async", "full_module_path"
        ])

        for tool in tools:
            writer.writerow([
                tool["module"],
                tool["name"],
                tool["signature"],
                tool["description"],
                str(tool["is_async"]),
                tool["full_module_path"]
            ])

def generate_json_output(tools: List[Dict[str, Any]], output_file: str):
    """Generate structured JSON output for tooling."""
    output = {
        "metadata": {
            "generated_by": "scripts/generate_canonical_tools.py",
            "tool_count": len(tools),
            "modules": list(set(tool["module"] for tool in tools))
        },
        "tools": tools
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

def identify_overlapping_tools(_tools: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """Identify tools with overlapping functionality that should be consolidated."""
    overlaps = {}

    # Package creation tools - NOW CONSOLIDATED
    package_creation = [
        "create_package",          # unified_package module - primary interface
        "package_create_from_s3"   # s3_package module - specialized S3 bulk processing
    ]
    overlaps["Package Creation"] = package_creation

    # Catalog/URL generation tools - REDUNDANT
    catalog_tools = [
        "catalog_url",  # auth module
        "catalog_uri"   # auth module
    ]
    overlaps["Catalog URLs"] = catalog_tools

    # Metadata template tools - PARTIAL OVERLAP
    metadata_tools = [
        "get_metadata_template",        # metadata_templates module
        "create_metadata_from_template" # metadata_examples module
    ]
    overlaps["Metadata Templates"] = metadata_tools

    # Search tools - CONSOLIDATION NEEDED
    search_tools = [
        "packages_search",           # packages module - package-specific
        "bucket_objects_search",     # buckets module - S3-specific
        "unified_search"            # search module - unified interface
    ]
    overlaps["Search Functions"] = search_tools

    # Tabulator admin overlap - DUPLICATE FUNCTIONALITY
    tabulator_admin = [
        "tabulator_open_query_status",    # tabulator module
        "tabulator_open_query_toggle",    # tabulator module
        "admin_tabulator_open_query_get", # governance module
        "admin_tabulator_open_query_set"  # governance module
    ]
    overlaps["Tabulator Admin"] = tabulator_admin

    return overlaps

def generate_consolidation_report(_tools: List[Dict[str, Any]], output_file: str):
    """Generate detailed consolidation recommendations."""

    report = {
        "breaking_changes_required": True,
        "backward_compatibility": "DEPRECATED - Will break existing clients",
        "consolidation_plan": {}
    }

    # Package Creation Consolidation - COMPLETED
    report["consolidation_plan"]["package_creation"] = {
        "action": "COMPLETED",
        "keep": ["create_package", "package_create_from_s3"],
        "removed": ["package_create", "package_update", "package_update_metadata"],
        "rationale": "create_package is now the unified primary interface with all functionality",
        "current_api": {
            "create_package": "Primary interface - handles all package creation scenarios",
            "package_create_from_s3": "Specialized tool for S3 bulk processing with organization"
        }
    }

    # Search Consolidation
    report["consolidation_plan"]["search"] = {
        "action": "BREAK_COMPATIBILITY",
        "keep": "unified_search",
        "deprecate": ["packages_search", "bucket_objects_search"],
        "rationale": "unified_search handles all search scenarios with backend selection",
        "migration": {
            "packages_search": "Replace with unified_search(scope='catalog')",
            "bucket_objects_search": "Replace with unified_search(scope='bucket', target=bucket)"
        }
    }

    # URL Generation Consolidation
    report["consolidation_plan"]["url_generation"] = {
        "action": "BREAK_COMPATIBILITY",
        "keep": "catalog_url",
        "deprecate": ["catalog_uri"],
        "rationale": "catalog_url covers all URL generation needs",
        "migration": {
            "catalog_uri": "Replace with catalog_url() - URIs are legacy"
        }
    }

    # Tabulator Admin Consolidation
    report["consolidation_plan"]["tabulator_admin"] = {
        "action": "BREAK_COMPATIBILITY",
        "keep": ["admin_tabulator_open_query_get", "admin_tabulator_open_query_set"],
        "deprecate": ["tabulator_open_query_status", "tabulator_open_query_toggle"],
        "rationale": "Admin tools provide proper permissions model",
        "migration": {
            "tabulator_open_query_status": "Replace with admin_tabulator_open_query_get",
            "tabulator_open_query_toggle": "Replace with admin_tabulator_open_query_set"
        }
    }

    # Documentation Cleanup
    report["documentation_cleanup"] = {
        "action": "REGENERATE_FROM_CODE",
        "current_issues": [
            "docs/api/TOOLS.md manually maintained - causes drift",
            "CSV file manually updated - inconsistent with code",
            "Tool descriptions in docs don't match actual docstrings"
        ],
        "solution": "Auto-generate all documentation from server introspection"
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

async def main():
    """Generate all canonical tool listings."""
    print("🔍 Extracting tools from MCP server...")

    # Create server instance to introspect tools
    server = create_configured_server(verbose=False)
    tools = await extract_tool_metadata(server)

    print(f"📊 Found {len(tools)} tools across {len(set(tool['module'] for tool in tools))} modules")

    # Generate outputs
    output_dir = Path(__file__).parent.parent
    tests_fixtures_dir = output_dir / "tests" / "fixtures"

    print("📝 Generating CSV output...")
    generate_csv_output(tools, str(tests_fixtures_dir / "mcp-list.csv"))

    print("📋 Generating JSON metadata...")
    generate_json_output(tools, str(output_dir / "build" / "tools_metadata.json"))

    print("⚠️  Generating consolidation report...")
    generate_consolidation_report(tools, str(output_dir / "build" / "consolidation_report.json"))

    # Print summary
    overlaps = identify_overlapping_tools(tools)
    print("\n🚨 OVERLAPPING TOOLS IDENTIFIED:")
    for category, tool_list in overlaps.items():
        print(f"   {category}: {len(tool_list)} tools")
        for tool in tool_list:
            print(f"     - {tool}")
        print()

    print("✅ Canonical tool listings generated!")
    print("📂 Files created:")
    print("   - tests/fixtures/mcp-list.csv")
    print("   - build/tools_metadata.json")
    print("   - build/consolidation_report.json")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
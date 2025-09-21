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
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from quilt_mcp.server import create_server

def extract_tool_metadata(server) -> List[Dict[str, Any]]:
    """Extract comprehensive metadata from all registered tools."""
    tools = []

    for tool_name, handler in server.tools.items():
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
            "generated_by": "scripts/quilt_mcp_tools_list.py",
            "tool_count": len(tools),
            "modules": list(set(tool["module"] for tool in tools))
        },
        "tools": tools
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

def identify_overlapping_tools(tools: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """Identify tools with overlapping functionality that should be consolidated."""
    overlaps = {}

    # Package creation tools - MAJOR OVERLAP
    package_creation = [
        "package_create",           # package_ops module - basic creation
        "create_package",          # unified_package module - unified interface
        "package_create", # package_management module - enhanced with templates
        "package_create_from_s3"   # s3_package module - from S3 sources
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
        "metadata_template_get",        # metadata_templates module
        "metadata_template_create" # metadata_examples module
    ]
    overlaps["Metadata Templates"] = metadata_tools

    # Search tools - CONSOLIDATION NEEDED
    search_tools = [
        "catalog_search",            # unified catalog search
        "bucket_objects_search",     # buckets module - S3-specific
    ]
    overlaps["Search Functions"] = search_tools

    # Tabulator admin overlap - DUPLICATE FUNCTIONALITY
    tabulator_admin = [
        "tabular_accessibility_get",   # governance module
        "tabular_accessibility_set",   # governance module
    ]
    overlaps["Tabulator Admin"] = tabulator_admin

    return overlaps

def generate_consolidation_report(tools: List[Dict[str, Any]], output_file: str):
    """Generate detailed consolidation recommendations."""
    overlaps = identify_overlapping_tools(tools)

    report = {
        "breaking_changes_required": True,
        "backward_compatibility": "DEPRECATED - Will break existing clients",
        "consolidation_plan": {}
    }

    # Package Creation Consolidation
    report["consolidation_plan"]["package_creation"] = {
        "action": "BREAK_COMPATIBILITY",
        "keep": "package_create",
        "deprecate": ["package_create", "create_package", "package_create_from_s3"],
        "rationale": "package_create provides all functionality with templates and validation",
        "migration": {
            "package_create": "Replace with package_create(copy_mode='all')",
            "create_package": "Replace with package_create(auto_organize=True)",
            "package_create_from_s3": "Replace with package_create(files=[bucket_prefix])"
        }
    }

    # Search Consolidation
    report["consolidation_plan"]["search"] = {
        "action": "BREAK_COMPATIBILITY",
        "keep": "catalog_search",
        "deprecate": ["packages_search", "bucket_objects_search"],
        "rationale": "catalog_search handles catalog and package scenarios with backend selection",
        "migration": {
            "packages_search": "Replace with catalog_search(scope='catalog')",
            "bucket_objects_search": "Replace with catalog_search(scope='bucket', target=bucket)"
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
        "keep": ["tabular_accessibility_get", "tabular_accessibility_set"],
        "deprecate": ["tabulator_open_query_status", "tabulator_open_query_toggle"],
        "rationale": "Governance tools provide proper permissions model",
        "migration": {
            "tabulator_open_query_status": "Replace with tabular_accessibility_get",
            "tabulator_open_query_toggle": "Replace with tabular_accessibility_set"
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

def main():
    """Generate all canonical tool listings."""
    print("🔍 Extracting tools from MCP server...")

    # Create server instance to introspect tools
    server = create_server()
    tools = extract_tool_metadata(server)

    print(f"📊 Found {len(tools)} tools across {len(set(tool['module'] for tool in tools))} modules")

    # Generate outputs
    output_dir = Path(__file__).parent.parent

    print("📝 Generating CSV output...")
    generate_csv_output(tools, output_dir / "quilt_mcp_tools_canonical.csv")

    print("📋 Generating JSON metadata...")
    generate_json_output(tools, output_dir / "build" / "tools_metadata.json")

    print("⚠️  Generating consolidation report...")
    generate_consolidation_report(tools, output_dir / "build" / "consolidation_report.json")

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
    print("   - quilt_mcp_tools_canonical.csv")
    print("   - build/tools_metadata.json")
    print("   - build/consolidation_report.json")

if __name__ == "__main__":
    main()

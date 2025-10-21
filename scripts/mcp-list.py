#!/usr/bin/env python3
"""Generate canonical tool and resource listings from MCP server code.

This script inspects the actual MCP server implementation to generate
authoritative tool and resource listings, eliminating manual maintenance and drift.
Resources are distinguished from tools with a 'type' column in the CSV output.
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


async def main():
    """Generate all canonical tool and resource listings."""
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

    print("📝 Generating CSV output...")
    generate_csv_output(all_items, str(tests_fixtures_dir / "mcp-list.csv"))

    print("📋 Generating JSON metadata...")
    generate_json_output(all_items, str(output_dir / "build" / "tools_metadata.json"))

    print("✅ Canonical tool and resource listings generated!")
    print("📂 Files created:")
    print("   - tests/fixtures/mcp-list.csv")
    print("   - build/tools_metadata.json")
    print(f"📈 Summary:")
    print(f"   - {len(tools)} tools")
    print(f"   - {len(resources)} resources")
    print(f"   - {len(all_items)} total items")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
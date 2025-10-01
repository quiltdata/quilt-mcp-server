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

    print("✅ Canonical tool listings generated!")
    print("📂 Files created:")
    print("   - tests/fixtures/mcp-list.csv")
    print("   - build/tools_metadata.json")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
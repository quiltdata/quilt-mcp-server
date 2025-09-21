#!/usr/bin/env python3
"""Generate canonical tool listings from MCP server code.

This script inspects the actual MCP server implementation to generate
authoritative tool listings, eliminating manual maintenance and drift.
"""

import argparse
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

def generate_json_output(tools: List[Dict[str, Any]], output_file: str | None = None):
    """Generate structured JSON output for tooling."""
    output = {
        "metadata": {
            "generated_by": "scripts/mcp-list.py",
            "tool_count": len(tools),
            "modules": list(set(tool["module"] for tool in tools))
        },
        "tools": tools
    }

    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
    else:
        print(json.dumps(output, indent=2, ensure_ascii=False))

def generate_html_output(tools: List[Dict[str, Any]]):
    """Generate HTML table output."""
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>MCP Tools List</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        .signature {{ font-family: monospace; font-size: 0.9em; }}
    </style>
</head>
<body>
    <h1>MCP Tools List</h1>
    <p>Total tools: {len(tools)}</p>
    <table>
        <tr>
            <th>Module</th>
            <th>Function Name</th>
            <th>Signature</th>
            <th>Description</th>
            <th>Async</th>
        </tr>
"""

    for tool in tools:
        html += f"""        <tr>
            <td>{tool['module']}</td>
            <td>{tool['name']}</td>
            <td class="signature">{tool['signature']}</td>
            <td>{tool['description']}</td>
            <td>{'Yes' if tool['is_async'] else 'No'}</td>
        </tr>
"""

    html += """    </table>
</body>
</html>"""

    print(html)

def generate_table_output(tools: List[Dict[str, Any]]):
    """Generate formatted table output to stdout."""
    if not tools:
        print("No tools found.")
        return

    # Calculate column widths
    widths = {
        'module': max(len('Module'), max(len(tool['module']) for tool in tools)),
        'name': max(len('Name'), max(len(tool['name']) for tool in tools)),
        'description': max(len('Description'), max(len(tool['description']) for tool in tools))
    }

    # Limit description width for readability
    widths['description'] = min(widths['description'], 60)

    # Header
    header = f"{'Module':<{widths['module']}} {'Name':<{widths['name']}} {'Description':<{widths['description']}} Async"
    print(header)
    print('-' * len(header))

    # Rows
    for tool in tools:
        desc = tool['description']
        if len(desc) > widths['description']:
            desc = desc[:widths['description']-3] + '...'

        async_str = 'Yes' if tool['is_async'] else 'No'
        print(f"{tool['module']:<{widths['module']}} {tool['name']:<{widths['name']}} {desc:<{widths['description']}} {async_str}")

async def main():
    """Generate tool listings with configurable output formats."""
    parser = argparse.ArgumentParser(
        description="Generate canonical tool listings from MCP server code"
    )
    parser.add_argument(
        '--json', action='store_true',
        help='Output as JSON to stdout'
    )
    parser.add_argument(
        '--html', action='store_true',
        help='Output as HTML table to stdout'
    )
    parser.add_argument(
        '--table', action='store_true',
        help='Output as formatted table to stdout'
    )

    args = parser.parse_args()

    # Create server instance to introspect tools
    server = create_configured_server(verbose=False)
    tools = await extract_tool_metadata(server)

    # Handle output format options
    if args.json:
        generate_json_output(tools)
    elif args.html:
        generate_html_output(tools)
    elif args.table:
        generate_table_output(tools)
    else:
        # Default behavior: count to stdout + CSV to tests/fixtures/mcp-list.csv
        print(f"{len(tools)}")

        # Write CSV to tests/fixtures/mcp-list.csv
        output_dir = Path(__file__).parent.parent
        tests_fixtures_dir = output_dir / "tests" / "fixtures"
        tests_fixtures_dir.mkdir(parents=True, exist_ok=True)
        generate_csv_output(tools, str(tests_fixtures_dir / "mcp-list.csv"))

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
#!/usr/bin/env python3
"""Generate split coverage summary by MCP tool.

This script processes unit and integration test coverage XML files
and generates a markdown report showing coverage by individual MCP tool.
"""

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Tuple, Any
import os
import inspect

# Add src directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def get_mcp_tools_mapping() -> Dict[str, List[str]]:
    """Get mapping of file paths to MCP tool function names.
    
    Returns:
        Dictionary mapping file paths to lists of MCP tool function names
    """
    try:
        from quilt_mcp.utils import get_tool_modules
        
        file_to_tools = {}
        
        # Get all tool modules
        tool_modules = get_tool_modules()
        
        for module in tool_modules:
            # Get module file path relative to src
            module_file = module.__file__
            if module_file:
                # Convert to relative path from src directory
                try:
                    src_path = Path(__file__).parent.parent / "src"
                    rel_path = Path(module_file).relative_to(src_path)
                    file_key = str(rel_path)
                except ValueError:
                    # Fallback if relative path conversion fails
                    file_key = module_file
                
                # Get all public functions in the module
                def make_predicate(mod: Any):
                    return lambda obj: (
                        inspect.isfunction(obj)
                        and not obj.__name__.startswith("_")
                        and obj.__module__ == mod.__name__  # Only functions defined in this module
                    )
                
                functions = inspect.getmembers(module, predicate=make_predicate(module))
                tool_names = [name for name, func in functions]
                
                if tool_names:
                    file_to_tools[file_key] = tool_names
        
        return file_to_tools
    
    except Exception as e:
        print(f"Warning: Could not discover MCP tools: {e}", file=sys.stderr)
        return {}


def parse_coverage_xml(xml_path: Path) -> Dict[str, Tuple[int, int]]:
    """Parse coverage XML file and return file-level coverage data.
    
    Args:
        xml_path: Path to coverage XML file
        
    Returns:
        Dictionary mapping file paths to (lines_covered, lines_total) tuples
    """
    if not xml_path.exists():
        print(f"Warning: Coverage XML file not found: {xml_path}", file=sys.stderr)
        return {}
    
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        file_coverage = {}
        
        # Find all class elements (which represent files in pytest-cov output)
        for package in root.findall(".//package"):
            for class_elem in package.findall("classes/class"):
                filename = class_elem.get("filename", "")
                
                # Remove "src/" prefix if present for consistency
                if filename.startswith("src/"):
                    filename = filename[4:]
                
                # Count lines
                lines = class_elem.findall("lines/line")
                lines_total = len(lines)
                
                if lines_total > 0:
                    lines_covered = sum(1 for line in lines if int(line.get("hits", "0")) > 0)
                    file_coverage[filename] = (lines_covered, lines_total)
        
        return file_coverage
    
    except ET.ParseError as e:
        print(f"Warning: Could not parse XML file {xml_path}: {e}", file=sys.stderr)
        return {}
    except Exception as e:
        print(f"Warning: Error processing XML file {xml_path}: {e}", file=sys.stderr)
        return {}


def calculate_file_coverage(
    tool_mapping: Dict[str, List[str]], 
    unit_coverage: Dict[str, Tuple[int, int]], 
    integration_coverage: Dict[str, Tuple[int, int]]
) -> List[Dict[str, Any]]:
    """Calculate coverage statistics for each file containing MCP tools.
    
    Args:
        tool_mapping: Mapping of file paths to MCP tool names
        unit_coverage: File-level unit test coverage data
        integration_coverage: File-level integration test coverage data
        
    Returns:
        List of dictionaries with file coverage statistics
    """
    file_stats = []
    
    # Sort files for consistent output
    for file_path in sorted(tool_mapping.keys()):
        tools = tool_mapping[file_path]
        
        # Get coverage for this file
        unit_covered = unit_total = 0
        integration_covered = integration_total = 0
        
        if file_path in unit_coverage:
            unit_covered, unit_total = unit_coverage[file_path]
            
        if file_path in integration_coverage:
            integration_covered, integration_total = integration_coverage[file_path]
        
        # Calculate percentages
        unit_pct = (unit_covered / unit_total * 100) if unit_total > 0 else 0.0
        integration_pct = (integration_covered / integration_total * 100) if integration_total > 0 else 0.0
        
        # Combined coverage (max of unit and integration)
        combined_covered = max(unit_covered, integration_covered)
        combined_total = max(unit_total, integration_total)
        combined_pct = (combined_covered / combined_total * 100) if combined_total > 0 else 0.0
        
        # Determine status (✅ if unit >= 100% AND integration >= 85%)
        status = "✅" if unit_pct >= 100.0 and integration_pct >= 85.0 else "❌"
        
        file_stats.append({
            "file_path": file_path,
            "tools": tools,
            "unit_covered": unit_covered,
            "unit_total": unit_total,
            "unit_pct": unit_pct,
            "integration_covered": integration_covered,
            "integration_total": integration_total,
            "integration_pct": integration_pct,
            "combined_covered": combined_covered,
            "combined_total": combined_total,
            "combined_pct": combined_pct,
            "status": status
        })
    
    return file_stats


def generate_markdown_report(file_stats: List[Dict[str, Any]]) -> str:
    """Generate markdown coverage report.
    
    Args:
        file_stats: List of file coverage statistics
        
    Returns:
        Markdown report as string
    """
    lines = [
        "# Tool Coverage Report By File",
        "",
        "| File | MCP Tools | Unit Coverage | Integration Coverage | Combined | Status |",
        "|------|-----------|---------------|---------------------|----------|--------"
    ]
    
    # Add file rows
    total_unit_covered = total_unit_total = 0
    total_integration_covered = total_integration_total = 0
    
    for stats in file_stats:
        unit_pct = stats["unit_pct"]
        integration_pct = stats["integration_pct"] 
        combined_pct = stats["combined_pct"]
        
        # Format file path (remove .py extension for cleaner display)
        file_display = stats["file_path"].replace(".py", "").replace("/", ".")
        
        # Format tools list (limit to reasonable display length)
        tools = stats["tools"]
        if len(tools) <= 3:
            tools_display = ", ".join(f"`{tool}`" for tool in tools)
        else:
            tools_display = f"`{tools[0]}`, `{tools[1]}`, `{tools[2]}` + {len(tools)-3} more"
        
        # Format percentages and counts
        unit_display = f"{unit_pct:.1f}% ({stats['unit_covered']}/{stats['unit_total']})"
        integration_display = f"{integration_pct:.1f}% ({stats['integration_covered']}/{stats['integration_total']})"
        combined_display = f"{combined_pct:.1f}%"
        
        lines.append(f"| `{file_display}` | {tools_display} | {unit_display} | {integration_display} | {combined_display} | {stats['status']} |")
        
        # Accumulate totals
        total_unit_covered += stats["unit_covered"]
        total_unit_total += stats["unit_total"]
        total_integration_covered += stats["integration_covered"]
        total_integration_total += stats["integration_total"]
    
    # Add totals row
    total_unit_pct = (total_unit_covered / total_unit_total * 100) if total_unit_total > 0 else 0.0
    total_integration_pct = (total_integration_covered / total_integration_total * 100) if total_integration_total > 0 else 0.0
    overall_status = "✅" if total_unit_pct >= 100.0 and total_integration_pct >= 85.0 else "❌"
    
    total_unit_display = f"**{total_unit_pct:.1f}%** ({total_unit_covered}/{total_unit_total})"
    total_integration_display = f"**{total_integration_pct:.1f}%** ({total_integration_covered}/{total_integration_total})"
    
    total_tools = sum(len(stats["tools"]) for stats in file_stats)
    
    lines.extend([
        f"| **TOTAL** | **{total_tools} tools** | {total_unit_display} | {total_integration_display} | - | {overall_status} |",
        "",
        "## Targets",
        "",
        "- **Unit Coverage**: 100% (error scenarios, mocked dependencies)",
        "- **Integration Coverage**: 85%+ (end-to-end workflows, real services)",
        "",
        "## Current Status",
        "",
        f"- Unit: {total_unit_pct:.1f}% ({'✅ PASS' if total_unit_pct >= 100.0 else '❌ FAIL'})",
        f"- Integration: {total_integration_pct:.1f}% ({'✅ PASS' if total_integration_pct >= 85.0 else '❌ FAIL'})",
        "",
        "## Notes",
        "",
        "- Each file containing MCP tools is listed with its coverage",
        "- Files with many tools show first 3 tools + count of remaining",
        "- Coverage is at file level since tools share the same implementation",
        "- Focus unit testing on files with <100% unit coverage",
        "- Focus integration testing on files with <85% integration coverage",
        ""
    ])
    
    return "\n".join(lines)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate split coverage summary by MCP tool")
    parser.add_argument("--unit-xml", type=Path, required=True, 
                       help="Path to unit test coverage XML file")
    parser.add_argument("--integration-xml", type=Path, required=True,
                       help="Path to integration test coverage XML file")
    parser.add_argument("--output", type=Path, required=True,
                       help="Path to output markdown file")
    
    args = parser.parse_args()
    
    try:
        # Discover MCP tools
        print("Discovering MCP tools...", file=sys.stderr)
        tool_mapping = get_mcp_tools_mapping()
        print(f"Found {len(tool_mapping)} tool files with {sum(len(tools) for tools in tool_mapping.values())} tools", file=sys.stderr)
        
        # Parse coverage XML files
        print("Parsing coverage XML files...", file=sys.stderr)
        unit_coverage = parse_coverage_xml(args.unit_xml)
        integration_coverage = parse_coverage_xml(args.integration_xml)
        
        print(f"Unit coverage: {len(unit_coverage)} files", file=sys.stderr)
        print(f"Integration coverage: {len(integration_coverage)} files", file=sys.stderr)
        
        # Calculate file-level coverage
        print("Calculating file-level coverage...", file=sys.stderr)
        file_stats = calculate_file_coverage(tool_mapping, unit_coverage, integration_coverage)
        
        # Generate markdown report
        print("Generating markdown report...", file=sys.stderr)
        report = generate_markdown_report(file_stats)
        
        # Write output file
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report)
        
        print(f"Coverage summary written to: {args.output}", file=sys.stderr)
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Version utilities for Quilt MCP Server build system.
Provides shared functionality for version management across Makefiles.
"""

import sys
import argparse
import json
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib

try:
    import jinja2
except ImportError:
    jinja2 = None


def get_version_from_pyproject(pyproject_path="pyproject.toml"):
    """Read version from pyproject.toml file."""
    try:
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
        return data["project"]["version"]
    except Exception as e:
        print(f"Error reading version from {pyproject_path}: {e}", file=sys.stderr)
        return "dev"


def generate_manifest_from_template(template_path, output_path, version):
    """Generate manifest.json from Jinja2 template."""
    if jinja2 is None:
        print("Error: jinja2 not available for template processing", file=sys.stderr)
        sys.exit(1)
    
    try:
        with open(template_path) as f:
            template_content = f.read()
        
        template = jinja2.Template(template_content)
        manifest_content = template.render(version=version)
        
        with open(output_path, "w") as f:
            f.write(manifest_content)
        
        print(f"Generated {output_path} with version {version}")
        
    except Exception as e:
        print(f"Error generating manifest from template: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Version utilities for build system")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Get version command
    version_parser = subparsers.add_parser("get-version", help="Get version from pyproject.toml")
    version_parser.add_argument("--pyproject", default="pyproject.toml", help="Path to pyproject.toml")
    
    # Generate manifest command
    manifest_parser = subparsers.add_parser("generate-manifest", help="Generate manifest.json from template")
    manifest_parser.add_argument("template", help="Path to manifest.json.j2 template")
    manifest_parser.add_argument("output", help="Path for generated manifest.json")
    manifest_parser.add_argument("--version", help="Version to use (if not provided, reads from pyproject.toml)")
    manifest_parser.add_argument("--pyproject", default="../../pyproject.toml", help="Path to pyproject.toml")
    
    args = parser.parse_args()
    
    if args.command == "get-version":
        version = get_version_from_pyproject(args.pyproject)
        print(version)
        
    elif args.command == "generate-manifest":
        version = args.version or get_version_from_pyproject(args.pyproject)
        generate_manifest_from_template(args.template, args.output, version)
        
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
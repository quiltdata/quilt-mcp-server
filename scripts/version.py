#!/usr/bin/env python3
"""
Version utilities for release management.
Provides commands to extract version information from pyproject.toml.
"""

import sys
import tomllib
from pathlib import Path


def get_version():
    """Extract version from pyproject.toml."""
    pyproject_path = Path("pyproject.toml")
    
    if not pyproject_path.exists():
        print("❌ pyproject.toml not found", file=sys.stderr)
        sys.exit(1)
    
    try:
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
        
        version = data.get("project", {}).get("version")
        if not version:
            print("❌ Version not found in pyproject.toml", file=sys.stderr)
            sys.exit(1)
        
        print(version)
        return version
        
    except Exception as e:
        print(f"❌ Error reading pyproject.toml: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main entry point."""
    if len(sys.argv) != 2:
        print("Usage: version-utils.py {get-version}", file=sys.stderr)
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "get-version":
        get_version()
    else:
        print(f"❌ Unknown command: {command}", file=sys.stderr)
        print("Available commands: get-version", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""Basic check of the test file and current status."""

import ast
import sys
import os

# Change to the repo directory
os.chdir('/Users/ernest/GitHub/quilt-mcp-server')

print("=== BASIC STATUS CHECK ===")

# Check syntax
try:
    with open('tests/test_mcp_resources.py', 'r') as f:
        content = f.read()
    ast.parse(content)
    print("✅ test_mcp_resources.py syntax is valid")
except Exception as e:
    print(f"❌ Syntax error in test file: {e}")
    sys.exit(1)

# Check if imports work
sys.path.insert(0, 'src')

try:
    from quilt_mcp.tools.governance import GovernanceService
    print("✅ GovernanceService import works")
except Exception as e:
    print(f"❌ GovernanceService import failed: {e}")

try:
    from quilt_mcp.tools.unified_package import list_available_resources
    print("✅ list_available_resources import works")
except Exception as e:
    print(f"❌ list_available_resources import failed: {e}")

print("✅ Basic checks completed")
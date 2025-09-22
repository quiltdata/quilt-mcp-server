#!/usr/bin/env python3
"""Quick syntax check for the test file."""

import ast
import sys

try:
    with open('/Users/ernest/GitHub/quilt-mcp-server/tests/test_mcp_resources.py', 'r') as f:
        content = f.read()

    # Parse the file
    ast.parse(content)
    print("✅ Syntax check passed - no syntax errors found")

except SyntaxError as e:
    print(f"❌ Syntax error: {e}")
    print(f"Line {e.lineno}: {e.text}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error reading file: {e}")
    sys.exit(1)
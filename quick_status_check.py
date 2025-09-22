#!/usr/bin/env python3
"""Quick status check to understand current state."""

import os
import sys
import subprocess

# Change to repo directory
os.chdir('/Users/ernest/GitHub/quilt-mcp-server')
sys.path.insert(0, 'src')

print("=== QUICK STATUS CHECK ===")

# Check git status
result = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True)
if result.stdout.strip():
    print("📝 Uncommitted changes found:")
    print(result.stdout)
else:
    print("✅ No uncommitted changes")

# Check current branch
result = subprocess.run(['git', 'branch', '--show-current'], capture_output=True, text=True)
print(f"🌿 Current branch: {result.stdout.strip()}")

# Quick syntax check
try:
    import ast
    with open('tests/test_mcp_resources.py', 'r') as f:
        ast.parse(f.read())
    print("✅ Test file syntax is valid")
except Exception as e:
    print(f"❌ Test file syntax error: {e}")

# Quick import check
import_tests = [
    ('quilt_mcp.tools.governance', 'GovernanceService'),
    ('quilt_mcp.tools.unified_package', 'list_available_resources')
]

for module_name, item_name in import_tests:
    try:
        module = __import__(module_name, fromlist=[item_name])
        getattr(module, item_name)
        print(f"✅ {module_name}.{item_name} imports OK")
    except Exception as e:
        print(f"❌ {module_name}.{item_name} failed: {e}")

print("\n✅ Quick status check complete")
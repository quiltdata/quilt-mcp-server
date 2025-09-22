#!/usr/bin/env python3
"""Verify that all imports in the test file actually work."""

import sys
import os

# Set up the path
repo_path = '/Users/ernest/GitHub/quilt-mcp-server'
os.chdir(repo_path)
sys.path.insert(0, os.path.join(repo_path, 'src'))

print("=== VERIFYING IMPORTS ===")
print(f"Working directory: {os.getcwd()}")
print(f"Python path includes: {os.path.join(repo_path, 'src')}")

# Test each import used in the test file
imports_to_test = [
    ('quilt_mcp.tools.governance', 'GovernanceService'),
    ('quilt_mcp.tools.governance', 'admin_users_list'),
    ('quilt_mcp.tools.governance', 'admin_roles_list'),
    ('quilt_mcp.tools.governance', 'admin_user_get'),
    ('quilt_mcp.tools.governance', 'admin_user_create'),
    ('quilt_mcp.tools.governance', 'tabular_accessibility_get'),
    ('quilt_mcp.tools.governance', 'tabular_accessibility_set'),
    ('quilt_mcp.tools.unified_package', 'list_available_resources'),
]

success_count = 0
total_count = len(imports_to_test)

for module_name, item_name in imports_to_test:
    try:
        module = __import__(module_name, fromlist=[item_name])
        item = getattr(module, item_name)
        print(f"✅ {module_name}.{item_name} - OK")
        success_count += 1
    except Exception as e:
        print(f"❌ {module_name}.{item_name} - FAILED: {e}")

print(f"\n=== SUMMARY ===")
print(f"✅ {success_count}/{total_count} imports successful")

if success_count == total_count:
    print("🎉 All imports work! The test file should be runnable.")
else:
    print("⚠️  Some imports failed. Need to fix these before running tests.")

# Also check if we can import the test modules
try:
    import pytest
    print("✅ pytest available")
except ImportError:
    print("❌ pytest not available - need to run 'uv sync --group test'")

print("\n=== READY FOR TESTING ===")
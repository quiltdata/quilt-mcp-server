#!/bin/bash
set -e
cd /Users/ernest/GitHub/quilt-mcp-server

echo "Testing updated MCP resources file..."
export PYTHONPATH=src

# Quick syntax check first
python3 -c "
import ast
with open('tests/test_mcp_resources.py', 'r') as f:
    ast.parse(f.read())
print('✅ Syntax check passed')
"

echo "Running a few key tests..."
uv sync --group test --quiet
uv run pytest tests/test_mcp_resources.py::TestGovernanceService::test_governance_service_creation -v

echo "If that worked, running all tests..."
uv run pytest tests/test_mcp_resources.py -v --tb=short
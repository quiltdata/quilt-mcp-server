#!/bin/bash
set -e
cd /Users/ernest/GitHub/quilt-mcp-server
export PYTHONPATH=src

echo "=== CYCLE 1: Testing rewritten test file ==="
echo "Syncing dependencies..."
uv sync --group test

echo "Running tests..."
uv run pytest tests/test_mcp_resources.py -v --tb=short
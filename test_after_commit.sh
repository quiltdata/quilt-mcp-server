#!/bin/bash
set -e
cd /Users/ernest/GitHub/quilt-mcp-server

echo "=== CYCLE 1: Testing after commit ==="
export PYTHONPATH=src

echo "Syncing dependencies..."
uv sync --group test

echo "Running the fixed tests..."
uv run pytest tests/test_mcp_resources.py -v --tb=short

echo "Test results above. Exit code: $?"
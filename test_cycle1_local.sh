#!/bin/bash
set -e
cd /Users/ernest/GitHub/quilt-mcp-server

echo "=== TESTING CYCLE 1 LOCALLY FIRST ==="
export PYTHONPATH=src

echo "Current branch and status:"
git branch --show-current
git status --porcelain

echo "Syncing dependencies..."
uv sync --group test

echo "Running the rewritten tests..."
uv run pytest tests/test_mcp_resources.py -v --tb=short --disable-warnings

echo "Exit code: $?"
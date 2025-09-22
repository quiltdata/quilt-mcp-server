#!/bin/bash
cd /Users/ernest/GitHub/quilt-mcp-server
export PYTHONPATH=src
echo "Running sync..."
uv sync --group test
echo "Running tests..."
uv run pytest tests/test_mcp_resources.py -v
echo "Test exit code: $?"
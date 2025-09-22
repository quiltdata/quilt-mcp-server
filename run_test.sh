#!/bin/bash
cd /Users/ernest/GitHub/quilt-mcp-server
export PYTHONPATH=src
uv sync --group test
uv run pytest tests/test_mcp_resources.py -v
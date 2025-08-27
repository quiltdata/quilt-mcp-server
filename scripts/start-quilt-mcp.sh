#!/bin/bash

# Activate virtual environment and start Quilt MCP server
cd "$(dirname "$0")"
source .venv/bin/activate
export MCP_PORT=8001
python app/main.py



#!/bin/bash
set -e

echo "[STARTUP] $(date -Iseconds) - Starting MCP server..." >&2
echo "[STARTUP] Environment variables:" >&2
env | grep -E "(FASTMCP|MCP|PORT|HOST)" | sort | sed 's/^/[STARTUP] /' >&2

echo "[STARTUP] Python path: $PYTHONPATH" >&2
echo "[STARTUP] Working directory: $(pwd)" >&2
echo "[STARTUP] Python version: $(python --version)" >&2

# Start the server with verbose output
echo "[STARTUP] Executing: python -u /app/src/main.py" >&2
exec python -u /app/src/main.py
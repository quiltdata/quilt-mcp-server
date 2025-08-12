"""Compatibility shim that imports all tool modules so their decorators run.

Historically this file contained all tool implementations. It now simply
re-exports the shared FastMCP instance and helper along with the tool
functions which live under quilt.tools.* modules.
"""

from __future__ import annotations
import os
from mcp.server.fastmcp import FastMCP

# Single FastMCP instance used across all tool modules
mcp = FastMCP("quilt")

def is_lambda_environment() -> bool:
    """Check if we're running in AWS Lambda environment."""
    return bool(os.environ.get('AWS_LAMBDA_FUNCTION_NAME'))

__all__ = [
    "mcp",
    "is_lambda_environment",
]

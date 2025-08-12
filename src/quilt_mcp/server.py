"""Core FastMCP server instance and utilities.

This module provides the main FastMCP server instance that all tools register with,
along with utility functions for environment detection.
"""

from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

# Single FastMCP instance used across all tool modules
mcp = FastMCP("quilt")

def is_lambda_environment() -> bool:
    """Check if we're running in AWS Lambda environment.
    
    Returns:
        bool: True if running in Lambda, False otherwise.
    """
    return bool(os.environ.get('AWS_LAMBDA_FUNCTION_NAME'))

__all__ = [
    "mcp",
    "is_lambda_environment",
]

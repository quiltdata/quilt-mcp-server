"""Transport adapters for MCP server.

This package contains adapters that bridge the core MCP processor with different
transport mechanisms:

- lambda_handler: AWS Lambda event processing
- fastmcp_bridge: FastMCP integration for local development
"""

from .fastmcp_bridge import FastMCPBridge

__all__ = ["FastMCPBridge"]
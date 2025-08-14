"""Unified MCP server entry point.

This server automatically detects the environment and routes requests to the
appropriate adapter:
- Lambda: Uses lambda_handler for AWS Lambda events
- Local: Uses fastmcp_bridge for development and testing

Environment variables:
- FASTMCP_TRANSPORT: 'stdio', 'sse', or 'streamable-http' (default: auto-detect)
- AWS_LAMBDA_FUNCTION_NAME: Set by Lambda runtime (auto-detected)
- LOG_LEVEL: Logging level (default: 'INFO')
"""

import logging
import os
from typing import Any, Dict, Literal

# Configure logging
log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def is_lambda_environment() -> bool:
    """Check if running in AWS Lambda."""
    return bool(os.environ.get('AWS_LAMBDA_FUNCTION_NAME'))


def get_transport() -> Literal["stdio", "sse", "streamable-http"]:
    """Get transport mode from environment or default."""
    transport = os.environ.get('FASTMCP_TRANSPORT', 'streamable-http')
    if transport in ("stdio", "sse", "streamable-http"):
        return transport
    logger.warning(f"Invalid transport '{transport}', using 'streamable-http'")
    return "streamable-http"


def main() -> None:
    """Main entry point for FastMCP server."""
    
    logger.info("Starting Quilt MCP Server")
    
    # Use FastMCP bridge
    from .adapters.fastmcp_bridge import FastMCPBridge
    
    bridge = FastMCPBridge("quilt")
    transport = get_transport()
    
    logger.info(f"Using transport: {transport}")
    
    # Run the server
    try:
        bridge.run(transport=transport)
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        raise


# Exports
__all__ = ["main", "is_lambda_environment", "get_transport"]
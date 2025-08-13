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
    """Main entry point for local development."""
    if is_lambda_environment():
        logger.info("Detected Lambda environment - handler will be called by AWS")
        return
    
    logger.info("Starting Quilt MCP Server for local development")
    
    # Use FastMCP bridge for local development
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


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """AWS Lambda handler entry point.
    
    This function is called by AWS Lambda for each request.
    
    Args:
        event: AWS Lambda event from API Gateway
        context: AWS Lambda context
        
    Returns:
        AWS Lambda response for API Gateway
    """
    from .adapters.lambda_handler import lambda_handler
    
    return lambda_handler(event, context)


# Backwards compatibility exports
__all__ = ["main", "handler", "is_lambda_environment", "get_transport"]
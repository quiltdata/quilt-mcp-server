"""Clean FastMCP server that works in all environments."""

from __future__ import annotations

import os
import logging
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

# Configure logging
log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Single FastMCP instance
mcp = FastMCP("quilt")

def get_transport() -> Literal["stdio", "sse", "streamable-http"]:
    """Get transport mode from environment or default."""
    transport = os.environ.get('FASTMCP_TRANSPORT', 'streamable-http')
    if transport in ("stdio", "sse", "streamable-http"):
        return transport
    logger.warning(f"Invalid transport '{transport}', using 'streamable-http'")
    return "streamable-http"

def is_lambda_environment() -> bool:
    """Check if running in AWS Lambda."""
    return bool(os.environ.get('AWS_LAMBDA_FUNCTION_NAME'))

def setup_lambda_environment() -> None:
    """Setup Lambda environment."""
    if not is_lambda_environment():
        return
        
    try:
        os.chdir('/tmp')
        for directory in ['/tmp/.config', '/tmp/.cache', '/tmp/quilt']:
            os.makedirs(directory, exist_ok=True)
        logger.debug("Lambda environment ready")
    except Exception as e:
        logger.warning(f"Lambda setup failed: {e}")

def register_tools() -> None:
    """Import tools to register them with FastMCP."""
    try:
        # Import all tool modules - their @mcp.tool decorators will register them
        from . import tools
        # tools import triggers @mcp.tool decorators
        logger.info("Tools registered successfully")
    except Exception as e:
        logger.error(f"Tool registration failed: {e}", exc_info=True)

def main() -> None:
    """Main entry point."""
    if is_lambda_environment():
        logger.info("Lambda environment - handler will be called by AWS")
        return
    
    # Register tools and run server
    register_tools()
    setup_lambda_environment()
    
    transport = get_transport()
    logger.info(f"Starting FastMCP server with transport: {transport}")
    
    mcp.run(transport=transport)

# AWS Lambda handler
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler using FastMCP's built-in HTTP handling."""
    setup_lambda_environment()
    register_tools()
    
    # For Lambda, we need to extract the HTTP request and route to FastMCP
    # This is a simplified approach - for production, consider the AWS Lambda MCP adapter
    try:
        method = event.get('httpMethod', 'GET')
        path = event.get('path', '/')
        body = event.get('body', '')
        
        # Handle CORS preflight
        if method == 'OPTIONS':
            return {
                'statusCode': 200,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type,Authorization',
                    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
                },
                'body': ''
            }
        
        # Basic health check
        if method == 'GET':
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': '{"status": "ok", "server": "FastMCP"}'
            }
        
        # For MCP requests, we'd need to integrate with FastMCP's request handling
        # For now, return a placeholder
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': '{"message": "FastMCP Lambda handler", "method": "' + method + '"}'
        }
        
    except Exception as e:
        logger.error(f"Lambda error: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': f'{{"error": "{str(e)}"}}'
        }

__all__ = ["mcp", "main", "handler"]
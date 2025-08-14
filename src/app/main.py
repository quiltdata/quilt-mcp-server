#!/usr/bin/env python3
"""Simple FastMCP server entry point.

This is the main entry point for running the Quilt MCP server as a standalone
web server. It removes all Lambda complexity and focuses on simplicity.

Usage:
    python main.py                    # Run on localhost:8000/mcp
    python main.py --port 3000        # Run on custom port
    python main.py --host 0.0.0.0     # Bind to all interfaces
"""

import argparse
import logging
import sys

from src.quilt_mcp.adapters.fastmcp_bridge import FastMCPBridge

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point for the FastMCP server."""
    parser = argparse.ArgumentParser(description="Quilt MCP Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--path", default="/mcp", help="HTTP path for MCP endpoint")
    parser.add_argument("--transport", default="streamable-http", 
                       choices=["stdio", "sse", "streamable-http"],
                       help="Transport protocol")
    parser.add_argument("--log-level", default="INFO",
                       choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                       help="Logging level")
    
    args = parser.parse_args()
    
    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    logger.info("Starting Quilt MCP Server")
    logger.info(f"Transport: {args.transport}")
    
    if args.transport in ["sse", "streamable-http"]:
        logger.info(f"Server will be available at: http://{args.host}:{args.port}{args.path}")
    
    # Create and run the bridge
    bridge = FastMCPBridge("quilt-mcp")
    
    try:
        bridge.run(
            transport=args.transport,
            host=args.host,
            port=args.port,
            path=args.path
        )
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""DXT entry point for Quilt MCP server with stdio transport."""

import os
import sys

# Add the bundled dependencies and app directory to Python path
base_dir = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(base_dir, 'lib'))
sys.path.insert(0, base_dir)

from quilt_mcp.utils import run_server  # pyright: ignore[reportMissingImports]


def setup_dxt_environment() -> None:
    """Configure environment for DXT execution."""
    # Force stdio transport for DXT
    os.environ["FASTMCP_TRANSPORT"] = "stdio"

    # Configure logging to avoid interfering with stdio protocol
    os.environ.setdefault("LOG_LEVEL", "WARNING")

    # Set default AWS region if not specified
    os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")


def main() -> None:
    """Main entry point for the DXT MCP server."""
    try:
        setup_dxt_environment()
        run_server()
    except KeyboardInterrupt:
        # Handle graceful shutdown
        sys.exit(0)
    except Exception as e:
        # Log errors to stderr (won't interfere with stdio MCP protocol)
        print(f"Error starting DXT MCP server: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

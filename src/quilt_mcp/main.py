#!/usr/bin/env python3
"""Entry point for uvx execution."""

import os
from quilt_mcp.utils import run_server


def main() -> None:
    """Main entry point for the MCP server."""
    # Force stdio transport for MCP (same as dxt_main.py)
    os.environ["FASTMCP_TRANSPORT"] = "stdio"
    run_server()


if __name__ == "__main__":
    main()

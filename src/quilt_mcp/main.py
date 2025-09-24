#!/usr/bin/env python3
"""Entry point for uvx execution."""

import os
from quilt_mcp.utils import run_server


def main() -> None:
    """Main entry point for the MCP server."""
    # Default to stdio transport when unset to preserve MCPB compatibility,
    # but allow callers (e.g., container entrypoints) to override.
    os.environ.setdefault("FASTMCP_TRANSPORT", "stdio")
    run_server()


if __name__ == "__main__":
    main()

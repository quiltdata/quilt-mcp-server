#!/usr/bin/env python3
"""Entry point for uvx execution."""

import os
from dotenv import load_dotenv
from quilt_mcp.utils import run_server


def main() -> None:
    """Main entry point for the MCP server."""
    # Load .env for development (project root only, not user's home directory)
    # This supports: make run-inspector, manual testing, direct uv run
    # Production (uvx) uses shell environment or MCP config instead
    load_dotenv()  # Loads from .env in current working directory

    # Default to stdio transport when unset to preserve MCPB compatibility,
    # but allow callers (e.g., container entrypoints) to override.
    os.environ.setdefault("FASTMCP_TRANSPORT", "stdio")
    run_server()


if __name__ == "__main__":
    main()

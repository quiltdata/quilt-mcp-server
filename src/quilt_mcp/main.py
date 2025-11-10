#!/usr/bin/env python3
"""Entry point for uvx execution."""

import argparse
import os
from dotenv import load_dotenv
from quilt_mcp.utils import run_server


def main() -> None:
    """Main entry point for the MCP server."""
    # Parse CLI arguments
    parser = argparse.ArgumentParser(
        description="Quilt MCP Server - Secure data access via Model Context Protocol",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--skip-banner",
        action="store_true",
        help="Skip startup banner display (useful for multi-server setups)",
    )
    args = parser.parse_args()

    # Load .env for development (project root only, not user's home directory)
    # This supports: make run-inspector, manual testing, direct uv run
    # Production (uvx) uses shell environment or MCP config instead
    load_dotenv()  # Loads from .env in current working directory

    # Default to stdio transport when unset to preserve MCPB compatibility,
    # but allow callers (e.g., container entrypoints) to override.
    os.environ.setdefault("FASTMCP_TRANSPORT", "stdio")

    # Determine skip_banner setting with precedence: CLI flag > env var > default
    skip_banner = args.skip_banner
    if not skip_banner and "MCP_SKIP_BANNER" in os.environ:
        skip_banner = os.environ.get("MCP_SKIP_BANNER", "false").lower() == "true"

    run_server(skip_banner=skip_banner)


if __name__ == "__main__":
    main()

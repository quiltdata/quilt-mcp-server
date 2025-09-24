#!/usr/bin/env python3
"""Entry point for uvx execution."""

import os
from quilt_mcp.utils import run_server


def main() -> None:
    """Main entry point for the MCP server."""
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.info("DEBUG: main() function called - entry point reached")
    
    # Default to stdio transport when unset to preserve MCPB compatibility,
    # but allow callers (e.g., container entrypoints) to override.
    transport = os.environ.get("FASTMCP_TRANSPORT", "stdio")
    logger.info("DEBUG: FASTMCP_TRANSPORT from environment: %s", transport)
    os.environ.setdefault("FASTMCP_TRANSPORT", "stdio")
    
    logger.info("DEBUG: About to call run_server()")
    run_server()
    logger.info("DEBUG: run_server() completed")


if __name__ == "__main__":
    main()

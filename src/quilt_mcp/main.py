#!/usr/bin/env python3
"""Entry point for uvx execution."""

import argparse
import os
import platform
import sys
import traceback
from dotenv import load_dotenv
from quilt_mcp.utils import run_server
from quilt_mcp.config import get_mode_config, ConfigurationError


def print_startup_error(error: Exception, error_type: str = "Startup Error") -> None:
    """Print formatted startup error diagnostic to stderr.

    Args:
        error: The exception that occurred
        error_type: Category of error (e.g., "Missing Dependency", "Configuration Error")
    """
    print("=" * 60, file=sys.stderr)
    print("QUILT MCP SERVER STARTUP ERROR", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(file=sys.stderr)
    print(f"Error Type: {error_type}", file=sys.stderr)
    print(f"Details: {error}", file=sys.stderr)
    print(file=sys.stderr)

    # Provide specific troubleshooting based on error type
    if isinstance(error, (ImportError, ModuleNotFoundError)):
        module_name = getattr(error, 'name', str(error))
        print("Troubleshooting:", file=sys.stderr)

        if 'quilt' in str(error).lower() or 'fastmcp' in str(error).lower():
            print("1. Install quilt-mcp with uv:", file=sys.stderr)
            print("   curl -LsSf https://astral.sh/uv/install.sh | sh", file=sys.stderr)
            print("   uvx quilt-mcp", file=sys.stderr)
            print(file=sys.stderr)
            print("2. Or install with pip:", file=sys.stderr)
            print("   pip install quilt-mcp", file=sys.stderr)
        else:
            print(f"1. Install missing dependency: pip install {module_name}", file=sys.stderr)

        print(file=sys.stderr)
        print("3. Restart your MCP client (e.g., Claude Desktop)", file=sys.stderr)
    elif error_type == "Configuration Error":
        print("Troubleshooting:", file=sys.stderr)
        print("1. Check the error message above for missing configuration", file=sys.stderr)
        print("2. For multitenant mode, ensure these environment variables are set:", file=sys.stderr)
        print("   - MCP_JWT_SECRET", file=sys.stderr)
        print("   - MCP_JWT_ISSUER", file=sys.stderr)
        print("   - MCP_JWT_AUDIENCE", file=sys.stderr)
        print("3. For local development, set QUILT_MULTITENANT_MODE=false or leave unset", file=sys.stderr)
    else:
        print("Troubleshooting:", file=sys.stderr)
        print("1. Check the error message above for specific issues", file=sys.stderr)
        print("2. Verify your environment variables and configuration", file=sys.stderr)
        print("3. Try running with debug output: FASTMCP_DEBUG=1 uvx quilt-mcp", file=sys.stderr)

    print(file=sys.stderr)
    print("System Info:", file=sys.stderr)
    print(f"- Python: {sys.version.split()[0]}", file=sys.stderr)
    print(f"- Platform: {platform.system().lower()}", file=sys.stderr)
    print(f"- Working Directory: {os.getcwd()}", file=sys.stderr)
    print(file=sys.stderr)
    print("For more help, visit:", file=sys.stderr)
    print("https://github.com/quiltdata/quilt-mcp-server/issues", file=sys.stderr)
    print("=" * 60, file=sys.stderr)


def main() -> None:
    """Main entry point for the MCP server."""
    try:
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

        # Validate configuration early in startup before accepting requests
        try:
            mode_config = get_mode_config()
            mode_config.validate()
            
            # Log successful validation and current mode
            mode_name = "multitenant" if mode_config.is_multitenant else "local development"
            print(f"Quilt MCP Server starting in {mode_name} mode", file=sys.stderr)
            print(f"Backend type: {mode_config.backend_type}", file=sys.stderr)
            print(f"JWT required: {mode_config.requires_jwt}", file=sys.stderr)
            print(f"Default transport: {mode_config.default_transport}", file=sys.stderr)
            
        except ConfigurationError as e:
            print_startup_error(e, "Configuration Error")
            sys.exit(1)

        # Set transport protocol based on deployment mode
        # HTTP for multitenant mode, stdio for local development mode
        # Allow callers (e.g., container entrypoints) to override via environment
        os.environ.setdefault("FASTMCP_TRANSPORT", mode_config.default_transport)

        # Determine skip_banner setting with precedence: CLI flag > env var > default
        skip_banner = args.skip_banner
        if not skip_banner and "MCP_SKIP_BANNER" in os.environ:
            skip_banner = os.environ.get("MCP_SKIP_BANNER", "false").lower() == "true"

        run_server(skip_banner=skip_banner)

    except (ImportError, ModuleNotFoundError) as e:
        print_startup_error(e, "Missing Dependency")
        sys.exit(1)

    except KeyboardInterrupt:
        print("\nQuilt MCP Server shutdown (user interrupt)", file=sys.stderr)
        sys.exit(0)

    except SystemExit:
        # Allow normal exits from argparse and other components
        raise

    except Exception as e:
        print_startup_error(e, "Unexpected Error")
        print(file=sys.stderr)
        print("Traceback:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

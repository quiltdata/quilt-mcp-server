#!/usr/bin/env python3
"""Entry point for uvx execution."""

import argparse
import os
import platform
import sys
import traceback
from dotenv import load_dotenv
from quilt_mcp.utils.common import run_server
from quilt_mcp.config import ConfigurationError, get_mode_config
from quilt_mcp.ops.exceptions import AuthenticationError


def print_startup_error(
    error: Exception,
    error_type: str = "Startup Error",
    selected_backend: str | None = None,
    selected_deployment: str | None = None,
) -> None:
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
    if selected_deployment:
        print(f"Selected deployment: {selected_deployment}", file=sys.stderr)
    if selected_backend:
        print(f"Selected backend: {selected_backend}", file=sys.stderr)
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
        print("Check the error message above for missing configuration.", file=sys.stderr)
        print("Platform backend needs QUILT_CATALOG_URL and QUILT_REGISTRY_URL.", file=sys.stderr)
        print("For legacy local development, try: uvx quilt-mcp --deployment legacy", file=sys.stderr)
    elif error_type == "Authentication Error":
        print("Troubleshooting:", file=sys.stderr)
        print("1. Run 'quilt3 login' to authenticate", file=sys.stderr)
        print("2. For legacy local development: uvx quilt-mcp --deployment legacy", file=sys.stderr)
        print("3. Try debug output: FASTMCP_DEBUG=1 uvx quilt-mcp", file=sys.stderr)
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
        parser.add_argument(
            "--backend",
            choices=["quilt3", "platform"],
            help=("Override backend implementation: quilt3 or platform. Prefer --deployment for standard setups."),
        )
        parser.add_argument(
            "--deployment",
            choices=["remote", "local", "legacy"],
            help=(
                "Deployment preset: remote (platform + http), "
                "local (platform + stdio, default), legacy (quilt3 + stdio). "
                "Can also be set via QUILT_DEPLOYMENT."
            ),
        )
        args = parser.parse_args()

        # Load .env for development (project root only, not user's home directory)
        # This supports: make run-inspector, manual testing, direct uv run
        # Production (uvx) uses shell environment or MCP config instead
        load_dotenv()  # Loads from .env in current working directory

        # Validate configuration early in startup before accepting requests
        try:
            mode_config = get_mode_config(
                backend_override=args.backend,
                deployment_mode=args.deployment,
            )
            mode_config.validate()

            # Log successful validation and current mode
            mode_name = "multiuser" if mode_config.is_multiuser else "local development"
            print(f"Quilt MCP Server starting in {mode_name} mode", file=sys.stderr)
            print(
                f"Deployment mode: {mode_config.deployment_mode.value} ({mode_config.deployment_selection_source})",
                file=sys.stderr,
            )
            print(
                f"Backend selection: {mode_config.backend_name} ({mode_config.backend_selection_source})",
                file=sys.stderr,
            )
            print(f"Backend type: {mode_config.backend_type}", file=sys.stderr)
            print(f"JWT required: {mode_config.requires_jwt}", file=sys.stderr)
            print(f"Default transport: {mode_config.default_transport}", file=sys.stderr)

        except ConfigurationError as e:
            print_startup_error(
                e,
                "Configuration Error",
                selected_backend=args.backend or mode_config.backend_name if "mode_config" in locals() else "platform",
                selected_deployment=(args.deployment or os.getenv("QUILT_DEPLOYMENT") or "local"),
            )
            sys.exit(1)

        # Set transport protocol (defaults to stdio for MCP protocol standard)
        # Docker deployments override to http via FASTMCP_TRANSPORT env var
        # setdefault() respects explicit environment variable if already set
        os.environ.setdefault("FASTMCP_TRANSPORT", mode_config.default_transport)

        # Determine skip_banner setting with precedence: CLI flag > env var > default
        skip_banner = args.skip_banner
        if not skip_banner and "MCP_SKIP_BANNER" in os.environ:
            skip_banner = os.environ.get("MCP_SKIP_BANNER", "false").lower() == "true"

        run_server(skip_banner=skip_banner)

    except (ImportError, ModuleNotFoundError) as e:
        print_startup_error(e, "Missing Dependency")
        sys.exit(1)

    except AuthenticationError as e:
        print_startup_error(e, "Authentication Error")
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

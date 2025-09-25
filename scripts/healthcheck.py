#!/usr/bin/env python3
"""
Health check script for the MCP server.
Designed to be used in Docker containers and ECS health checks.
"""

import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional


def check_health(
    url: str = "http://localhost:8080/health",
    timeout: int = 5,
    verbose: bool = False,
) -> tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """
    Check the health of the MCP server.

    Args:
        url: Health check endpoint URL
        timeout: Request timeout in seconds
        verbose: Print detailed output

    Returns:
        Tuple of (is_healthy, response_data, error_message)
    """
    start_time = time.time()

    try:
        # Create request with timeout
        request = urllib.request.Request(url, headers={"User-Agent": "HealthCheck/1.0"})

        with urllib.request.urlopen(request, timeout=timeout) as response:
            elapsed = time.time() - start_time

            # Check status code
            if response.status != 200:
                return False, None, f"HTTP {response.status}"

            # Parse JSON response
            data = json.loads(response.read().decode("utf-8"))

            # Validate response structure
            if not isinstance(data, dict):
                return False, data, "Invalid response format: not a JSON object"

            # Check status field
            status = data.get("status")
            if status != "ok":
                return False, data, f"Status not ok: {status}"

            # Validate required fields
            required_fields = ["status", "timestamp", "server"]
            missing_fields = [f for f in required_fields if f not in data]
            if missing_fields:
                return (
                    False,
                    data,
                    f"Missing required fields: {', '.join(missing_fields)}",
                )

            # Validate server info
            server_info = data.get("server", {})
            if not isinstance(server_info, dict):
                return False, data, "Invalid server info format"

            if server_info.get("name") != "quilt-mcp-server":
                return False, data, f"Unexpected server name: {server_info.get('name')}"

            if verbose:
                print(f"✓ Health check passed in {elapsed:.3f}s")
                print(f"  Status: {status}")
                print(
                    f"  Server: {server_info.get('name')} v{server_info.get('version', 'unknown')}"
                )
                print(f"  Response time: {elapsed:.3f}s")

            return True, data, None

    except urllib.error.HTTPError as e:
        return False, None, f"HTTP error: {e.code} {e.reason}"
    except urllib.error.URLError as e:
        return False, None, f"Connection error: {e.reason}"
    except json.JSONDecodeError as e:
        return False, None, f"Invalid JSON response: {e}"
    except TimeoutError:
        return False, None, f"Request timed out after {timeout}s"
    except Exception as e:
        return False, None, f"Unexpected error: {e}"


def main():
    """Main entry point for health check script."""
    import argparse

    parser = argparse.ArgumentParser(description="Health check for MCP server")
    parser.add_argument(
        "--url",
        default="http://localhost:8080/health",
        help="Health check endpoint URL (default: http://localhost:8080/health)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=5,
        help="Request timeout in seconds (default: 5)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print detailed output",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output result as JSON",
    )

    args = parser.parse_args()

    # Perform health check
    is_healthy, data, error = check_health(
        url=args.url,
        timeout=args.timeout,
        verbose=args.verbose and not args.json,
    )

    if args.json:
        # Output JSON result
        result = {
            "healthy": is_healthy,
            "error": error,
            "response": data,
            "url": args.url,
        }
        print(json.dumps(result, indent=2))
    elif not args.verbose:
        # Simple output for non-verbose mode
        if is_healthy:
            print("OK")
        else:
            print(f"FAILED: {error}", file=sys.stderr)

    # Exit with appropriate code
    sys.exit(0 if is_healthy else 1)


if __name__ == "__main__":
    main()

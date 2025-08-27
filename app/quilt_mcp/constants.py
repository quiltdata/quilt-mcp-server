"""Constants used throughout the Quilt MCP server."""

import os

# Default bucket for S3 operations (also serves as registry) - read from environment
DEFAULT_BUCKET = os.getenv("QUILT_DEFAULT_BUCKET", "")
DEFAULT_REGISTRY = DEFAULT_BUCKET  # Registry is the same as bucket

# Known test packages and entries (for testing) - read from environment
# Updated to cellpainting/jump-cpg0016-illumination for CI testing
KNOWN_TEST_PACKAGE = os.getenv("QUILT_TEST_PACKAGE", "")
KNOWN_TEST_ENTRY = os.getenv("QUILT_TEST_ENTRY", "README.md")  # Note: keeping the typo from .env

# For backward compatibility, construct full S3 object path
KNOWN_TEST_S3_OBJECT = f"{DEFAULT_BUCKET}/{KNOWN_TEST_PACKAGE}/{KNOWN_TEST_ENTRY}"

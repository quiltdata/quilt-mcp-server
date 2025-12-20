"""Constants used throughout the Quilt MCP server."""

import os

# ============================================================================
# REMOVED: DEFAULT_BUCKET and DEFAULT_REGISTRY (v0.10.0)
# ============================================================================
# Rationale: MCP server should not manage default bucket state
# LLM clients provide explicit bucket parameters based on conversation context
# Tests use QUILT_TEST_BUCKET fixture from tests/conftest.py
# ============================================================================

# Test package configuration (can reference any package in any bucket)
# These are used for basic connectivity checks only
KNOWN_TEST_PACKAGE = os.getenv("QUILT_TEST_PACKAGE", "test/raw")
KNOWN_TEST_ENTRY = os.getenv("QUILT_TEST_ENTRY", "README.md")

# ============================================================================
# REMOVED: KNOWN_TEST_S3_OBJECT (v0.10.0)
# ============================================================================
# Tests should construct full S3 URIs using test fixtures
# Example: f"{test_bucket}/{KNOWN_TEST_PACKAGE}/{KNOWN_TEST_ENTRY}"
# ============================================================================

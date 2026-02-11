"""E2E test configuration and fixtures.

This module provides authentication helpers and fixtures for E2E tests,
particularly for tests that need to work with both quilt3 and platform backends.
"""

import os
import pytest
from typing import Dict, Any
from pathlib import Path


class AuthBackend:
    """Backend-agnostic auth helper for E2E tests.

    Wraps a QuiltOps backend and provides simplified auth methods
    that work regardless of whether it's quilt3 or platform mode.

    This class abstracts away the differences between:
    - quilt3 mode: Uses session from ~/.quilt/config.yml
    - platform mode: Uses JWT from runtime context
    """

    def __init__(self, backend, backend_mode: str):
        """Initialize auth backend wrapper.

        Args:
            backend: QuiltOps backend instance (Quilt3_Backend or Platform_Backend)
            backend_mode: Backend mode string ("quilt3" or "platform")
        """
        self.backend = backend
        self.mode = backend_mode

    def get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for GraphQL requests.

        Returns:
            Dict with Authorization header and other required headers

        Raises:
            RuntimeError: If auth headers cannot be obtained
        """
        try:
            return self.backend.get_graphql_auth_headers()
        except Exception as e:
            raise RuntimeError(f"Failed to get auth headers: {e}") from e

    def get_graphql_endpoint(self) -> str:
        """Get GraphQL endpoint URL.

        Returns:
            GraphQL endpoint URL

        Raises:
            RuntimeError: If endpoint cannot be determined
        """
        try:
            return self.backend.get_graphql_endpoint()
        except Exception as e:
            raise RuntimeError(f"Failed to get GraphQL endpoint: {e}") from e

    def verify_auth(self) -> bool:
        """Verify authentication is working.

        Returns:
            True if auth is valid, False otherwise
        """
        try:
            headers = self.get_auth_headers()
            endpoint = self.get_graphql_endpoint()
            return bool(headers and endpoint)
        except Exception:
            return False


def _check_auth_available(mode: str) -> bool:
    """Check if required authentication is available.

    Args:
        mode: Backend mode ("quilt3" or "platform")

    Returns:
        True if auth is available for the mode
    """
    if mode == "quilt3":
        # Check if quilt3 config exists
        config_file = Path.home() / ".quilt" / "config.yml"
        return config_file.exists()
    elif mode == "platform":
        # Check if platform env vars are set and JWT is discoverable
        if not (
            os.getenv("PLATFORM_TEST_ENABLED") and os.getenv("QUILT_CATALOG_URL") and os.getenv("QUILT_REGISTRY_URL")
        ):
            return False
        from quilt_mcp.auth.jwt_discovery import JWTDiscovery

        return JWTDiscovery.is_available()
    return False


def _check_test_bucket_available() -> str:
    """Get test bucket or skip test if not available.

    Returns:
        Test bucket name (without s3:// prefix)

    Raises:
        pytest.skip: If QUILT_TEST_BUCKET not set
    """
    bucket = os.getenv("QUILT_TEST_BUCKET", "").replace("s3://", "")
    if not bucket:
        pytest.skip("QUILT_TEST_BUCKET environment variable not set")
    return bucket


def _check_athena_available() -> bool:
    """Check if Athena workgroup is accessible.

    Returns:
        True if Athena is available
    """
    workgroup = os.getenv("ATHENA_WORKGROUP", "primary")
    return bool(workgroup)


@pytest.fixture
def auth_backend(backend_mode):
    """Provide authenticated backend for E2E tests.

    Automatically selects quilt3 or platform backend based on
    backend_mode parametrization.

    Args:
        backend_mode: From tests/conftest.py (quilt3|platform)

    Returns:
        AuthBackend: Wrapper with auth helper methods

    Raises:
        pytest.skip: If required credentials not available
    """
    from quilt_mcp.ops.factory import QuiltOpsFactory

    # Verify credentials are available
    if not _check_auth_available(backend_mode):
        pytest.skip(f"Authentication not available for {backend_mode} mode")

    # Create backend using factory (respects backend_mode env vars set by fixture)
    backend = QuiltOpsFactory.create()

    # Return wrapped backend
    return AuthBackend(backend, backend_mode)


@pytest.fixture
def tabulator_backend(auth_backend):
    """Provide backend with tabulator operations.

    This is an alias for clarity - auth_backend.backend already has
    tabulator methods via TabulatorMixin.

    Args:
        auth_backend: AuthBackend wrapper from auth_backend fixture

    Returns:
        QuiltOps backend with tabulator methods
    """
    return auth_backend.backend

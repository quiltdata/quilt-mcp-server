"""JWT discovery service for Quilt MCP server."""

from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Optional, cast

from quilt_mcp.context.runtime_context import get_runtime_auth
from quilt_mcp.ops.exceptions import AuthenticationError
from quilt_mcp.utils.common import get_jwt_from_auth_config

logger = logging.getLogger(__name__)


class JWTDiscovery:
    """Discover JWT credentials from multiple sources."""

    @staticmethod
    def discover() -> Optional[str]:
        """Discover JWT token from available sources.

        Priority order:
        1. Runtime context (middleware-provided)
        2. quilt3 session
        3. Auto-generation (if QUILT_ALLOW_TEST_JWT=true)
        """
        runtime_token = _get_runtime_token()
        if runtime_token:
            return runtime_token

        session_token = _get_token_from_quilt3_session()
        if session_token:
            return session_token

        if _allow_test_jwt():
            return _generate_test_jwt()

        return None

    @staticmethod
    def discover_or_raise() -> str:
        """Discover JWT token or raise a helpful error."""
        token = JWTDiscovery.discover()
        if token:
            return token
        raise AuthenticationError(
            "JWT token not found. Options:\n"
            "1. Run 'quilt3 login' to authenticate\n"
            "2. For development: set QUILT_ALLOW_TEST_JWT=true"
        )

    @staticmethod
    def is_available() -> bool:
        """Return True if any JWT source is available."""
        return JWTDiscovery.discover() is not None


def _get_runtime_token() -> Optional[str]:
    runtime_auth = get_runtime_auth()
    if runtime_auth and runtime_auth.access_token:
        return runtime_auth.access_token
    return None


def _get_token_from_quilt3_session() -> Optional[str]:
    # Try quilt3 session headers first
    try:
        import quilt3

        quilt_session = quilt3.session.get_session()
        if hasattr(quilt_session, "headers"):
            headers = quilt_session.headers
            auth_header = headers.get("Authorization") or headers.get("authorization")
            if auth_header and auth_header.startswith("Bearer "):
                bearer_token = cast(str, auth_header[7:].strip())
                if bearer_token:
                    return bearer_token
    except Exception as exc:  # pragma: no cover - environment dependent
        logger.debug("Failed to get JWT from quilt3 session: %s", exc)

    # Fall back to auth.json if registry URL is available
    registry_url = os.getenv("QUILT_REGISTRY_URL")
    if registry_url:
        token = get_jwt_from_auth_config(registry_url)
        if token:
            return token

    return None


def _allow_test_jwt() -> bool:
    return os.getenv("QUILT_ALLOW_TEST_JWT", "false").lower() == "true"


def _generate_test_jwt() -> str:
    secret = "test-secret-for-jwt-generation"
    return _generate_jwt(secret, subject_prefix="test")


def _generate_jwt(secret: str, *, subject_prefix: str) -> str:
    import jwt as pyjwt

    now = int(time.time())
    claims = {
        "id": f"{subject_prefix}-user",
        "uuid": str(uuid.uuid4()),
        "iat": now,
        "exp": now + 3600,
    }
    return pyjwt.encode(claims, secret, algorithm="HS256")

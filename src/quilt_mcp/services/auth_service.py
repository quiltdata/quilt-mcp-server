"""Authentication service factory for Quilt MCP server."""

from __future__ import annotations

import logging
import os
from typing import Literal, Optional, Protocol, cast

import boto3

from quilt_mcp.services.iam_auth_service import IAMAuthService
from quilt_mcp.services.auth_metrics import record_auth_mode
from quilt_mcp.services.jwt_auth_service import JWTAuthService
from quilt_mcp.services.jwt_decoder import JwtConfigError, get_jwt_decoder

logger = logging.getLogger(__name__)

AuthMode = Literal["iam", "jwt"]


class AuthServiceError(RuntimeError):
    """Raised when authentication cannot be resolved."""

    def __init__(self, message: str, *, code: str = "auth_error") -> None:
        super().__init__(message)
        self.code = code


class AuthServiceProtocol(Protocol):
    """Protocol for authentication services."""

    auth_type: AuthMode

    def get_boto3_session(self) -> boto3.Session:
        """Return a boto3 session for the current request."""


_AUTH_SERVICE: Optional[AuthServiceProtocol] = None
_JWT_MODE_ENABLED: Optional[bool] = None


def _parse_bool(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_jwt_mode_enabled() -> bool:
    """Return whether JWT mode is enabled (cached at first call)."""
    global _JWT_MODE_ENABLED
    if _JWT_MODE_ENABLED is None:
        _JWT_MODE_ENABLED = _parse_bool(os.getenv("MCP_REQUIRE_JWT"), default=False)
    return _JWT_MODE_ENABLED


def reset_auth_service() -> None:
    """Reset cached auth mode/service (used in tests)."""
    global _AUTH_SERVICE, _JWT_MODE_ENABLED
    _AUTH_SERVICE = None
    _JWT_MODE_ENABLED = None


def _validate_jwt_mode() -> None:
    decoder = get_jwt_decoder()
    try:
        decoder.validate_config()
    except JwtConfigError as exc:
        raise AuthServiceError(str(exc), code="jwt_config_error") from exc


def get_auth_service() -> AuthServiceProtocol:
    """Return the shared auth service instance for the configured mode."""
    global _AUTH_SERVICE
    if _AUTH_SERVICE is None:
        if get_jwt_mode_enabled():
            _validate_jwt_mode()
            _AUTH_SERVICE = cast(AuthServiceProtocol, JWTAuthService())
            logger.info("Authentication mode selected: JWT")
            record_auth_mode("jwt")
        else:
            _AUTH_SERVICE = cast(AuthServiceProtocol, IAMAuthService())
            logger.info("Authentication mode selected: IAM")
            record_auth_mode("iam")
    assert _AUTH_SERVICE is not None
    return _AUTH_SERVICE

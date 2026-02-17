"""Authentication service abstraction and factory for Quilt MCP server."""

from __future__ import annotations

from abc import ABC, abstractmethod
import logging
import os
from typing import Literal, Optional, cast

import boto3

from quilt_mcp.config import get_mode_config
from quilt_mcp.services.iam_auth_service import IAMAuthService
from quilt_mcp.services.auth_metrics import record_auth_mode
from quilt_mcp.services.protocols.auth import AuthServiceProtocol
from quilt_mcp.services.jwt_auth_service import JWTAuthService

logger = logging.getLogger(__name__)

AuthMode = Literal["iam", "jwt"]


class AuthServiceError(RuntimeError):
    """Raised when authentication cannot be resolved."""

    def __init__(self, message: str, *, code: str = "auth_error") -> None:
        super().__init__(message)
        self.code = code


class AuthService(ABC):
    """Abstract base class for authentication services."""

    auth_type: AuthMode

    @abstractmethod
    def get_session(self) -> boto3.Session:
        """Return a boto3 session for the current request."""

    @abstractmethod
    def is_valid(self) -> bool:
        """Return whether the credentials are valid."""

    @abstractmethod
    def get_user_identity(self) -> dict[str, str | None]:
        """Return user identity information for the current request."""

    def get_boto3_session(self) -> boto3.Session:
        return self.get_session()


def create_auth_service() -> AuthServiceProtocol:
    """
    Create a new auth service instance for the configured mode.

    Note: JWT mode no longer validates configuration at startup.
    Validation happens at the GraphQL backend when credentials are requested.
    """
    mode_config = get_mode_config()

    if mode_config.requires_jwt:
        logger.info("Authentication mode selected: JWT (pass-through to GraphQL)")
        record_auth_mode("jwt")
        return cast(AuthServiceProtocol, JWTAuthService())

    logger.info("Authentication mode selected: IAM")
    record_auth_mode("iam")
    return cast(AuthServiceProtocol, IAMAuthService())

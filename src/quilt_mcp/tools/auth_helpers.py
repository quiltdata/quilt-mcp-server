"""Shared authorization helpers for Quilt MCP tools.

These helpers provide authentication using IAM/quilt3 credentials for desktop workflows.
Tools can call the helpers to obtain boto3 clients using local credentials.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Literal, Optional

import boto3

from quilt_mcp.services.auth_service import AuthService, get_auth_service

logger = logging.getLogger(__name__)


AuthType = Literal["iam"]


@dataclass
class AuthorizationContext:
    """Result payload returned to tool modules."""

    authorized: bool
    auth_type: AuthType = "iam"
    session: Optional[boto3.Session] = None
    s3_client: Any | None = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def error_response(self) -> Dict[str, Any]:
        """Generate a standardized error response."""
        return {
            "error": self.error or "Authorization failed",
            "authorized": False,
            "auth_type": self.auth_type,
        }


def _build_s3_client(session: boto3.Session) -> Optional[Any]:
    try:
        return session.client("s3")
    except Exception as exc:  # pragma: no cover - unexpected boto3 failure
        logger.error("Failed to build s3 client from session: %s", exc)
        return None


def _base_authorization(
    tool_name: str,
    tool_args: Dict[str, Any],
    *,
    require_s3: bool,
) -> AuthorizationContext:
    auth_service: AuthService = get_auth_service()
    session = auth_service.get_iam_session()
    s3_client = _build_s3_client(session) if require_s3 else None

    if require_s3 and s3_client is None:
        return AuthorizationContext(
            authorized=False,
            auth_type="iam",
            error="Failed to construct S3 client from IAM credentials",
        )

    return AuthorizationContext(
        authorized=True,
        auth_type="iam",
        session=session,
        s3_client=s3_client,
    )


def check_s3_authorization(tool_name: str, tool_args: Optional[Dict[str, Any]] = None) -> AuthorizationContext:
    """Return S3 authorization context for bucket-oriented tools."""
    context = _base_authorization(tool_name, tool_args or {}, require_s3=True)
    if not context.authorized and context.error:
        logger.debug("S3 authorization failed for %s: %s", tool_name, context.error)
    return context


def check_package_authorization(
    tool_name: str,
    tool_args: Optional[Dict[str, Any]] = None,
) -> AuthorizationContext:
    """Return authorization context for package/GraphQL tools."""
    context = _base_authorization(tool_name, tool_args or {}, require_s3=False)
    if not context.authorized and context.error:
        logger.debug("Package authorization failed for %s: %s", tool_name, context.error)
    return context

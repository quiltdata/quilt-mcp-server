"""Shared authorization helpers for Quilt MCP tools.

These helpers provide authentication using IAM/quilt3 credentials for desktop workflows.
Tools can call the helpers to obtain boto3 clients using local credentials.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Literal, Optional

import boto3

from quilt_mcp.context.request_context import RequestContext
from quilt_mcp.services.auth_service import AuthServiceError, AuthService, create_auth_service
from quilt_mcp.services.jwt_auth_service import JwtAuthServiceError

logger = logging.getLogger(__name__)


AuthType = Literal["iam", "jwt"]


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


def _resolve_auth_service(
    auth_service: AuthService | None,
    context: Optional[RequestContext] = None,
) -> AuthService:
    if auth_service is None:
        if context is not None:
            return context.auth_service  # type: ignore[no-any-return]
        return create_auth_service()
    return auth_service


def _base_authorization(
    tool_name: str,
    tool_args: Dict[str, Any],
    *,
    require_s3: bool,
    auth_service: AuthService | None = None,
    context: Optional[RequestContext] = None,
) -> AuthorizationContext:
    auth_service = _resolve_auth_service(auth_service, context)
    if auth_service.auth_type == "jwt":
        if not auth_service.is_valid():
            return AuthorizationContext(
                authorized=False,
                auth_type=auth_service.auth_type,
                error="JWT authentication required",
            )
        session = None
        s3_client = None
        if require_s3:
            try:
                session = auth_service.get_boto3_session()
                s3_client = _build_s3_client(session)
            except (AuthServiceError, JwtAuthServiceError) as exc:
                return AuthorizationContext(
                    authorized=False,
                    auth_type=auth_service.auth_type,
                    error=str(exc),
                )
            if s3_client is None:
                return AuthorizationContext(
                    authorized=False,
                    auth_type=auth_service.auth_type,
                    error="Failed to construct S3 client from JWT credentials",
                )
        return AuthorizationContext(
            authorized=True,
            auth_type=auth_service.auth_type,
            session=session,
            s3_client=s3_client,
        )

    try:
        session = auth_service.get_boto3_session()
    except (AuthServiceError, JwtAuthServiceError) as exc:
        return AuthorizationContext(
            authorized=False,
            auth_type=auth_service.auth_type,
            error=str(exc),
        )
    except Exception as exc:  # pragma: no cover - unexpected auth failure
        logger.error("Unexpected auth service error for %s: %s", tool_name, exc)
        return AuthorizationContext(
            authorized=False,
            auth_type=auth_service.auth_type,
            error="Authentication failed",
        )
    s3_client = _build_s3_client(session) if require_s3 else None

    if require_s3 and s3_client is None:
        return AuthorizationContext(
            authorized=False,
            auth_type=auth_service.auth_type,
            error="Failed to construct S3 client from AWS credentials",
        )

    return AuthorizationContext(
        authorized=True,
        auth_type=auth_service.auth_type,
        session=session,
        s3_client=s3_client,
    )


def check_s3_authorization(
    tool_name: str,
    tool_args: Optional[Dict[str, Any]] = None,
    *,
    auth_service: AuthService | None = None,
    context: Optional[RequestContext] = None,
) -> AuthorizationContext:
    """Return S3 authorization context for bucket-oriented tools."""
    auth_context = _base_authorization(
        tool_name,
        tool_args or {},
        require_s3=True,
        auth_service=auth_service,
        context=context,
    )
    if not auth_context.authorized and auth_context.error:
        logger.debug("S3 authorization failed for %s: %s", tool_name, auth_context.error)
    return auth_context


def check_package_authorization(
    tool_name: str,
    tool_args: Optional[Dict[str, Any]] = None,
    *,
    auth_service: AuthService | None = None,
    context: Optional[RequestContext] = None,
) -> AuthorizationContext:
    """Return authorization context for package/GraphQL tools."""
    auth_context = _base_authorization(
        tool_name,
        tool_args or {},
        require_s3=False,
        auth_service=auth_service,
        context=context,
    )
    if not auth_context.authorized and auth_context.error:
        logger.debug("Package authorization failed for %s: %s", tool_name, auth_context.error)
    return auth_context

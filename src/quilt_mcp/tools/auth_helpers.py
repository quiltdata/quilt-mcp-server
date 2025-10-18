"""Shared authorization helpers for Quilt MCP tools.

These helpers provide a unified bridge between JWT-authenticated web requests
and legacy IAM/quilt3 authenticated desktop workflows.  Tools can call the
helpers to obtain boto3 clients while automatically respecting strict JWT
mode and surfacing informative authorization errors.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Literal, Optional

import boto3

from quilt_mcp.services.auth_service import AuthService, JwtContext, get_auth_service
from quilt_mcp.services.bearer_auth_service import AuthorizationDecision

logger = logging.getLogger(__name__)


AuthType = Literal["jwt", "iam"]


@dataclass
class AuthorizationContext:
    """Result payload returned to tool modules."""

    authorized: bool
    auth_type: Optional[AuthType] = None
    session: Optional[boto3.Session] = None
    s3_client: Any | None = None
    error: Optional[str] = None
    strict: bool = False
    decision: Optional[AuthorizationDecision] = None
    jwt_context: Optional[JwtContext] = None
    claims: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def error_response(self) -> Dict[str, Any]:
        """Generate a standardized error response."""
        payload: Dict[str, Any] = {
            "error": self.error or "Authorization failed",
            "authorized": False,
        }
        if self.auth_type:
            payload["auth_type"] = self.auth_type
        if self.strict:
            payload["strict_mode"] = True
        if self.decision:
            if self.decision.missing_permissions:
                payload["missing_permissions"] = self.decision.missing_permissions
            if self.decision.missing_buckets:
                payload["missing_buckets"] = self.decision.missing_buckets
        return payload


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
    jwt_context = auth_service.get_jwt_context()

    if jwt_context:
        decision = auth_service.authorize_jwt_tool(jwt_context, tool_name, tool_args)
        if not decision.allowed:
            reason = decision.reason or "JWT authorization denied"
            logger.warning("JWT authorization denied for %s: %s", tool_name, reason)
            return AuthorizationContext(
                authorized=False,
                auth_type="jwt",
                error=reason,
                decision=decision,
                jwt_context=jwt_context,
                claims=dict(jwt_context.result.claims),
            )

        session = jwt_context.session
        s3_client = _build_s3_client(session) if require_s3 else None
        if require_s3 and s3_client is None:
            return AuthorizationContext(
                authorized=False,
                auth_type="jwt",
                error="Failed to construct S3 client from JWT credentials",
                decision=decision,
                jwt_context=jwt_context,
                claims=dict(jwt_context.result.claims),
            )

        return AuthorizationContext(
            authorized=True,
            auth_type="jwt",
            session=session,
            s3_client=s3_client,
            decision=decision,
            jwt_context=jwt_context,
            claims=dict(jwt_context.result.claims),
            metadata={
                "bearer_token": jwt_context.result.token,
                "aws_role_arn": jwt_context.result.aws_role_arn,
            },
        )

    if auth_service.require_jwt():
        logger.warning("Strict JWT mode enabled but no JWT auth context present for %s", tool_name)
        return AuthorizationContext(
            authorized=False,
            auth_type=None,
            strict=True,
            error="JWT authentication required but not provided",
        )

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
        claims={},
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
    if context.authorized and context.auth_type == "jwt" and context.jwt_context:
        context.metadata.setdefault("authorization_header", f"Bearer {context.jwt_context.result.token}")
    if not context.authorized and context.error:
        logger.debug("Package authorization failed for %s: %s", tool_name, context.error)
    return context

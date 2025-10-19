"""Authentication service bridging JWT and IAM credential flows.

This module exposes a lightweight service that inspects the active runtime
context and returns boto3 sessions derived from either JWT authentication
metadata (web deployments) or legacy IAM/quilt3 authentication (desktop
deployments).  The helpers are intentionally small so tool modules can share
consistent auth behaviour without duplicating boto3 session bootstrap logic.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import boto3

from quilt_mcp.runtime_context import RuntimeAuthState, get_runtime_auth
from quilt_mcp.services.bearer_auth_service import (
    AuthorizationDecision,
    JwtAuthResult,
    get_bearer_auth_service,
)


@dataclass(frozen=True)
class JwtContext:
    """Container for normalized JWT runtime data."""

    result: JwtAuthResult
    session: boto3.Session
    auth_state: RuntimeAuthState


class AuthService:
    """Resolve authentication context for Quilt MCP tools."""

    def __init__(self) -> None:
        self._bearer_service = get_bearer_auth_service()
        self._iam_session: Optional[boto3.Session] = None
        self._require_jwt = os.getenv("MCP_REQUIRE_JWT", "false").lower() == "true"

    # ------------------------------------------------------------------
    # Runtime helpers
    # ------------------------------------------------------------------

    def require_jwt(self) -> bool:
        """Return True when strict JWT mode is enabled."""
        return self._require_jwt

    def get_runtime_auth(self) -> Optional[RuntimeAuthState]:
        """Expose the current runtime auth state (if any)."""
        return get_runtime_auth()

    # ------------------------------------------------------------------

    def get_jwt_context(self) -> Optional[JwtContext]:
        """Return runtime JWT context when available."""
        auth_state = self.get_runtime_auth()
        if not auth_state or auth_state.scheme != "jwt":
            return None

        extras = auth_state.extras or {}
        jwt_result = extras.get("jwt_auth_result")
        if not isinstance(jwt_result, JwtAuthResult):
            return None

        session = extras.get("boto3_session")
        if not isinstance(session, boto3.Session):
            session = self._bearer_service.build_boto3_session(jwt_result)

        return JwtContext(result=jwt_result, session=session, auth_state=auth_state)

    def authorize_jwt_tool(
        self,
        jwt_context: JwtContext,
        tool_name: str,
        tool_args: Dict[str, Any],
    ) -> AuthorizationDecision:
        """Authorize a tool invocation using JWT permissions."""
        return self._bearer_service.authorize_tool(jwt_context.result, tool_name, tool_args)

    # ------------------------------------------------------------------
    # IAM / quilt3 fallback helpers
    # ------------------------------------------------------------------

    def _runtime_boto3_session_from_extras(self) -> Optional[boto3.Session]:
        """Attempt to build a session from runtime extras (IAM path)."""
        auth_state = self.get_runtime_auth()
        if not auth_state:
            return None

        extras = auth_state.extras or {}
        session = extras.get("boto3_session")
        if isinstance(session, boto3.Session):
            return session

        credentials = extras.get("aws_credentials")
        if isinstance(credentials, dict):
            access_key = credentials.get("access_key_id")
            secret_key = credentials.get("secret_access_key")
            session_token = credentials.get("session_token")
            region = credentials.get("region") or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
            if access_key and secret_key:
                return boto3.Session(
                    aws_access_key_id=access_key,
                    aws_secret_access_key=secret_key,
                    aws_session_token=session_token,
                    region_name=region or "us-east-1",
                )

        return None

    def _quilt3_session(self) -> Optional[boto3.Session]:
        """Return a boto3 session sourced from quilt3 when available."""
        try:
            import quilt3  # type: ignore
        except Exception:
            return None

        disable_quilt3_session = os.getenv("QUILT_DISABLE_QUILT3_SESSION") == "1"
        try:
            if disable_quilt3_session and "unittest.mock" not in type(quilt3).__module__:
                return None
            if hasattr(quilt3, "logged_in") and quilt3.logged_in():
                if hasattr(quilt3, "get_boto3_session"):
                    session = quilt3.get_boto3_session()
                    if isinstance(session, boto3.Session):
                        return session
        except Exception:
            return None
        return None

    def get_iam_session(self) -> boto3.Session:
        """Return (and cache) the fallback IAM/quilt3 boto3 session."""
        if self._iam_session is not None:
            return self._iam_session

        session = self._runtime_boto3_session_from_extras() or self._quilt3_session() or boto3.Session()
        self._iam_session = session
        return session


_AUTH_SERVICE: Optional[AuthService] = None


def get_auth_service() -> AuthService:
    """Return the shared AuthService instance."""
    global _AUTH_SERVICE
    if _AUTH_SERVICE is None:
        _AUTH_SERVICE = AuthService()
    return _AUTH_SERVICE

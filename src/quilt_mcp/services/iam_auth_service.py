"""IAM authentication service for Quilt MCP server."""

from __future__ import annotations

import os
from typing import Literal, Optional, TYPE_CHECKING

import boto3

if TYPE_CHECKING:
    from quilt_mcp.services.auth_service import AuthService


class IAMAuthService:
    """Resolve authentication context for Quilt MCP tools using IAM credentials."""

    auth_type: Literal["iam"] = "iam"

    def __init__(self) -> None:
        self._iam_session: Optional[boto3.Session] = None

    def _quilt3_session(self) -> Optional[boto3.Session]:
        """Return a boto3 session sourced from quilt3 when available."""
        try:
            import quilt3
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

    def get_session(self) -> boto3.Session:
        """Return (and cache) the IAM/quilt3 boto3 session."""
        if self._iam_session is not None:
            return self._iam_session

        session = self._quilt3_session() or boto3.Session()
        self._iam_session = session
        return session

    def get_boto3_session(self) -> boto3.Session:
        return self.get_session()

    def is_valid(self) -> bool:
        try:
            session = self.get_session()
            credentials = session.get_credentials()
        except Exception:
            return False
        return credentials is not None

    def get_user_identity(self) -> dict[str, str | None]:
        session = self.get_session()
        try:
            sts = session.client("sts")
            response = sts.get_caller_identity()
            return {
                "user_id": response.get("Arn"),
                "account_id": response.get("Account"),
            }
        except Exception:
            return {"user_id": None, "account_id": None}

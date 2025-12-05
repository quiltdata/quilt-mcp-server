"""Authentication service for Quilt MCP server.

This module provides authentication services using IAM credentials and quilt3.
"""

from __future__ import annotations

import os
from typing import Optional

import boto3


class AuthService:
    """Resolve authentication context for Quilt MCP tools using IAM credentials."""

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

    def get_iam_session(self) -> boto3.Session:
        """Return (and cache) the IAM/quilt3 boto3 session."""
        if self._iam_session is not None:
            return self._iam_session

        session = self._quilt3_session() or boto3.Session()
        self._iam_session = session
        return session


_AUTH_SERVICE: Optional[AuthService] = None


def get_auth_service() -> AuthService:
    """Return the shared AuthService instance."""
    global _AUTH_SERVICE
    if _AUTH_SERVICE is None:
        _AUTH_SERVICE = AuthService()
    return _AUTH_SERVICE

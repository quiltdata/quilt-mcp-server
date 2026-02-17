"""Protocol contracts for authentication services.

These protocols decouple call sites from concrete auth service implementations
to avoid service import cycles.
"""

from __future__ import annotations

from typing import Literal, Protocol

import boto3


AuthMode = Literal["iam", "jwt"]


class AuthServiceProtocol(Protocol):
    """Runtime contract used by services/tools that need auth sessions."""

    auth_type: AuthMode

    def get_session(self) -> boto3.Session: ...

    def get_boto3_session(self) -> boto3.Session: ...

    def is_valid(self) -> bool: ...

    def get_user_identity(self) -> dict[str, str | None]: ...

"""Request-scoped context for MCP tool execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RequestContext:
    """Holds request-scoped services and identifiers."""

    request_id: str
    tenant_id: str
    user_id: str | None
    auth_service: Any
    permission_service: Any
    workflow_service: Any

    def __post_init__(self) -> None:
        if self.request_id is None:
            raise TypeError("request_id is required and cannot be None")
        if self.tenant_id is None:
            raise TypeError("tenant_id is required and cannot be None")
        if self.auth_service is None:
            raise TypeError("auth_service is required and cannot be None")
        if self.permission_service is None:
            raise TypeError("permission_service is required and cannot be None")
        if self.workflow_service is None:
            raise TypeError("workflow_service is required and cannot be None")

    @property
    def is_authenticated(self) -> bool:
        return bool(self.auth_service.is_valid())

    def get_boto_session(self):
        return self.auth_service.get_boto3_session()

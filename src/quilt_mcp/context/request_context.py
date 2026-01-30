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

    def discover_permissions(self, **kwargs):
        return self.permission_service.discover_permissions(**kwargs)

    def check_bucket_access(self, bucket: str, operations: list[str] | None = None):
        return self.permission_service.check_bucket_access(bucket=bucket, operations=operations)

    def create_workflow(self, workflow_id: str, name: str, description: str = "", metadata: dict[str, Any] | None = None):
        return self.workflow_service.create_workflow(
            workflow_id=workflow_id,
            name=name,
            description=description,
            metadata=metadata,
        )

    def add_workflow_step(
        self,
        workflow_id: str,
        step_id: str,
        description: str,
        step_type: str = "manual",
        dependencies: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        return self.workflow_service.add_step(
            workflow_id=workflow_id,
            step_id=step_id,
            description=description,
            step_type=step_type,
            dependencies=dependencies,
            metadata=metadata,
        )

    def update_workflow_step(
        self,
        workflow_id: str,
        step_id: str,
        status: str,
        result: dict[str, Any] | None = None,
        error_message: str | None = None,
    ):
        return self.workflow_service.update_step(
            workflow_id=workflow_id,
            step_id=step_id,
            status=status,
            result=result,
            error_message=error_message,
        )

    def get_workflow_status(self, workflow_id: str):
        return self.workflow_service.get_status(workflow_id)

    def list_workflows(self):
        return self.workflow_service.list_all()

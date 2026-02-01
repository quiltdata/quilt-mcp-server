"""RequestContextFactory for request-scoped service creation."""

from __future__ import annotations

import os
import uuid
from typing import Literal, Optional

from quilt_mcp.context.exceptions import ServiceInitializationError, TenantValidationError
from quilt_mcp.context.tenant_extraction import extract_tenant_id
from quilt_mcp.context.request_context import RequestContext
from quilt_mcp.runtime_context import get_runtime_auth
from quilt_mcp.services.auth_service import AuthService, create_auth_service
from quilt_mcp.config import get_mode_config
from quilt_mcp.services.iam_auth_service import IAMAuthService
from quilt_mcp.services.jwt_auth_service import JWTAuthService
from quilt_mcp.services.permissions_service import PermissionDiscoveryService
from quilt_mcp.services.workflow_service import WorkflowService
from quilt_mcp.storage.file_storage import FileBasedWorkflowStorage


class RequestContextFactory:
    """Factory for creating request-scoped contexts and services."""

    def __init__(self, mode: str = "auto") -> None:
        mode_config = get_mode_config()
        if mode == "auto":
            self.mode: Literal["single-user", "multitenant"] = mode_config.tenant_mode
        else:
            # Validate that mode is one of the expected values
            if mode not in ("single-user", "multitenant"):
                raise ValueError(f"Invalid mode: {mode}. Must be 'single-user' or 'multitenant'")
            self.mode = mode  # type: ignore[assignment]

    def create_context(
        self,
        *,
        tenant_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> RequestContext:
        auth_state = get_runtime_auth()
        extracted_tenant = extract_tenant_id(auth_state)
        resolved_tenant = self._resolve_tenant(tenant_id, extracted_tenant)
        resolved_request_id = request_id or str(uuid.uuid4())

        try:
            auth_service = self._create_auth_service()
        except Exception as exc:
            raise ServiceInitializationError("AuthService", str(exc)) from exc

        try:
            permission_service = self._create_permission_service(auth_service)
        except Exception as exc:
            raise ServiceInitializationError("PermissionService", str(exc)) from exc

        try:
            workflow_service = self._create_workflow_service(resolved_tenant)
        except Exception as exc:
            raise ServiceInitializationError("WorkflowService", str(exc)) from exc

        user_id = auth_service.get_user_identity().get("user_id")

        return RequestContext(
            request_id=resolved_request_id,
            tenant_id=resolved_tenant,
            user_id=user_id,
            auth_service=auth_service,
            permission_service=permission_service,
            workflow_service=workflow_service,
        )

    def _resolve_tenant(self, tenant_id: Optional[str], extracted_tenant: Optional[str]) -> str:
        if self.mode == "multitenant":
            resolved = tenant_id or extracted_tenant
            if not resolved:
                raise TenantValidationError(self.mode)
            return resolved
        if tenant_id is not None:
            raise TenantValidationError(self.mode)
        return "default"

    def _create_auth_service(self) -> AuthService:
        mode_config = get_mode_config()
        runtime_auth = get_runtime_auth()

        if runtime_auth and runtime_auth.access_token:
            return JWTAuthService()  # type: ignore[return-value]

        if mode_config.requires_jwt:
            raise ServiceInitializationError("AuthService", "JWT authentication required but missing.")

        return IAMAuthService()  # type: ignore[return-value]

    def _create_permission_service(self, auth_service: AuthService) -> PermissionDiscoveryService:
        return PermissionDiscoveryService(auth_service)

    def _create_workflow_service(self, tenant_id: str) -> WorkflowService:
        storage = FileBasedWorkflowStorage()
        return WorkflowService(tenant_id=tenant_id, storage=storage)

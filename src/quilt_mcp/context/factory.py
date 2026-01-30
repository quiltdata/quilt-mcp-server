"""RequestContextFactory for request-scoped service creation."""

from __future__ import annotations

import os
import uuid
from typing import Optional

from quilt_mcp.context.exceptions import ServiceInitializationError, TenantValidationError
from quilt_mcp.context.request_context import RequestContext
from quilt_mcp.runtime_context import get_runtime_auth
from quilt_mcp.services.auth_service import AuthService, create_auth_service, get_jwt_mode_enabled
from quilt_mcp.services.iam_auth_service import IAMAuthService
from quilt_mcp.services.jwt_auth_service import JWTAuthService


def _parse_bool(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "multitenant"}


class RequestContextFactory:
    """Factory for creating request-scoped contexts and services."""

    def __init__(self, mode: str = "auto") -> None:
        self.mode = self._determine_mode(mode)

    def _determine_mode(self, mode: str) -> str:
        if mode and mode != "auto":
            return mode
        env_value = os.getenv("QUILT_MULTITENANT_MODE")
        if env_value is None:
            return "single-user"
        return "multitenant" if _parse_bool(env_value, default=False) else "single-user"

    def create_context(
        self,
        *,
        tenant_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> RequestContext:
        resolved_tenant = self._resolve_tenant(tenant_id)
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

    def _resolve_tenant(self, tenant_id: Optional[str]) -> str:
        if self.mode == "multitenant":
            if not tenant_id:
                raise TenantValidationError(self.mode)
            return tenant_id
        if tenant_id is not None:
            raise TenantValidationError(self.mode)
        return "default"

    def _create_auth_service(self) -> AuthService:
        runtime_auth = get_runtime_auth()
        if runtime_auth and runtime_auth.access_token:
            return JWTAuthService()

        if get_jwt_mode_enabled():
            raise ServiceInitializationError("AuthService", "JWT authentication required but missing.")

        return IAMAuthService()

    def _create_permission_service(self, auth_service: AuthService):
        return object()

    def _create_workflow_service(self, tenant_id: str):
        return object()

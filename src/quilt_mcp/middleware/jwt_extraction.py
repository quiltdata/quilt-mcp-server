"""JWT extraction middleware for HTTP transports (NO VALIDATION)."""

from __future__ import annotations

import logging
import os
from typing import Optional, cast

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from quilt_mcp.context.runtime_context import (
    RuntimeAuthState,
    get_runtime_environment,
    push_runtime_context,
    reset_runtime_context,
)

logger = logging.getLogger(__name__)
FALLBACK_JWT_ENV_VAR = "QUILT_FALLBACK_JWT"


class JwtExtractionMiddleware(BaseHTTPMiddleware):
    """
    Extract JWT bearer tokens from Authorization header.

    This middleware performs NO validation - it only extracts the token
    and puts it in the runtime context. All validation happens at the
    GraphQL backend layer.
    """

    # Health check endpoints that don't require JWT
    HEALTH_PATHS = {"/", "/health", "/healthz"}

    def __init__(self, app, *, require_jwt: bool = True) -> None:
        super().__init__(app)
        self.require_jwt = require_jwt

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip JWT for health check endpoints
        if request.url.path in self.HEALTH_PATHS:
            return cast(Response, await call_next(request))

        if not self.require_jwt:
            return cast(Response, await call_next(request))

        request_id = _get_request_id(request)
        auth_header = request.headers.get("authorization")

        if not auth_header:
            fallback_token = os.getenv(FALLBACK_JWT_ENV_VAR, "").strip()
            if fallback_token:
                logger.warning(
                    "Using %s fallback token for unauthenticated request (request_id=%s, path=%s)",
                    FALLBACK_JWT_ENV_VAR,
                    request_id,
                    request.url.path,
                )
                return await self._run_with_token(request, call_next, token=fallback_token)

            logger.warning("JWT required but missing Authorization header (request_id=%s)", request_id)
            return _error_response(
                401,
                "JWT authentication required. Provide Authorization: Bearer header.",
            )

        if not auth_header.lower().startswith("bearer "):
            logger.warning("Invalid Authorization header format (request_id=%s)", request_id)
            return _error_response(401, "Invalid Authorization header. Expected Bearer token.")

        token = auth_header[7:].strip()
        if not token:
            logger.warning("Empty Bearer token provided (request_id=%s)", request_id)
            return _error_response(401, "JWT authentication required. Provide Authorization: Bearer header.")

        return await self._run_with_token(request, call_next, token=token)

    async def _run_with_token(self, request: Request, call_next, *, token: str) -> Response:
        # Extract token WITHOUT validation - GraphQL will validate
        # Claims are empty because we don't validate locally
        auth_state = RuntimeAuthState(scheme="Bearer", access_token=token, claims={})
        token_handle = push_runtime_context(environment=get_runtime_environment(), auth=auth_state)
        try:
            response: Response = await call_next(request)
        finally:
            reset_runtime_context(token_handle)

        return response


def _get_request_id(request: Request) -> Optional[str]:
    return request.headers.get("mcp-session-id") or request.headers.get("x-request-id")


def _error_response(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": message})

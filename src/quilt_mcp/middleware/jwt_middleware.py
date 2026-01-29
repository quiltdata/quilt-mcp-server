"""JWT authentication middleware for HTTP transports."""

from __future__ import annotations

import logging
import time
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from quilt_mcp.runtime_context import (
    RuntimeAuthState,
    get_runtime_environment,
    push_runtime_context,
    reset_runtime_context,
)
from quilt_mcp.services.auth_metrics import record_jwt_validation
from quilt_mcp.services.jwt_decoder import JwtDecodeError, get_jwt_decoder

logger = logging.getLogger(__name__)


class JwtAuthMiddleware(BaseHTTPMiddleware):
    """Extract and validate JWT bearer tokens, populating runtime auth state."""

    # Health check endpoints that don't require JWT authentication
    HEALTH_PATHS = {"/", "/health", "/healthz"}

    def __init__(self, app, *, require_jwt: bool = True) -> None:
        super().__init__(app)
        self.require_jwt = require_jwt
        self.decoder = get_jwt_decoder()

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip JWT auth for health check endpoints
        if request.url.path in self.HEALTH_PATHS:
            response_obj: Response = await call_next(request)
            return response_obj

        if not self.require_jwt:
            response_obj: Response = await call_next(request)
            return response_obj

        request_id = _get_request_id(request)
        auth_header = request.headers.get("authorization")

        if not auth_header:
            logger.warning("JWT authentication required but missing Authorization header (request_id=%s)", request_id)
            record_jwt_validation("failure", reason="missing_header")
            return _error_response(
                401,
                "JWT authentication required. Provide Authorization: Bearer header.",
            )

        if not auth_header.lower().startswith("bearer "):
            logger.warning("Invalid Authorization header format (request_id=%s)", request_id)
            record_jwt_validation("failure", reason="invalid_header")
            return _error_response(401, "Invalid Authorization header. Expected Bearer token.")

        token = auth_header[7:].strip()
        if not token:
            logger.warning("Empty Bearer token provided (request_id=%s)", request_id)
            record_jwt_validation("failure", reason="empty_token")
            return _error_response(401, "JWT authentication required. Provide Authorization: Bearer header.")

        start = time.perf_counter()
        try:
            claims = self.decoder.decode(token)
        except JwtDecodeError as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.warning("JWT validation failed (%s) request_id=%s", exc.code, request_id)
            logger.info("JWT validation completed in %.2fms (request_id=%s)", duration_ms, request_id)
            record_jwt_validation("failure", duration_ms=duration_ms, reason=exc.code)
            return _error_response(403, f"Invalid JWT: {exc.detail}")

        duration_ms = (time.perf_counter() - start) * 1000
        logger.info("JWT validation completed in %.2fms (request_id=%s)", duration_ms, request_id)
        record_jwt_validation("success", duration_ms=duration_ms)

        auth_state = RuntimeAuthState(scheme="Bearer", access_token=token, claims=claims)
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

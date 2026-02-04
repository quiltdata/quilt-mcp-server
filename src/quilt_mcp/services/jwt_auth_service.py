"""JWT-based authentication service for Quilt MCP server."""

from __future__ import annotations

import time
from typing import Any, Dict, Literal

from quilt_mcp.runtime_context import (
    get_runtime_auth,
    get_runtime_claims,
)
from quilt_mcp.services.jwt_decoder import JwtDecodeError, get_jwt_decoder


class JwtAuthServiceError(RuntimeError):
    """Raised when JWT auth cannot be resolved."""

    def __init__(self, message: str, *, code: str = "jwt_auth_error") -> None:
        super().__init__(message)
        self.code = code


class JWTAuthService:
    """Resolve authentication context for Quilt MCP tools using JWT claims."""

    auth_type: Literal["jwt"] = "jwt"
    _ALLOWED_CLAIMS = {"id", "uuid", "exp"}

    def __init__(self) -> None:
        self._decoder = get_jwt_decoder()

    def get_session(self):
        """JWT auth does not provide AWS credentials."""
        runtime_auth = get_runtime_auth()
        if runtime_auth is None:
            raise JwtAuthServiceError(
                "JWT authentication required. Provide Authorization: Bearer header.",
                code="missing_jwt",
            )

        claims = runtime_auth.claims or get_runtime_claims()
        if not claims and runtime_auth.access_token:
            try:
                self._decoder.decode(runtime_auth.access_token)
            except JwtDecodeError as exc:
                raise JwtAuthServiceError(f"Invalid JWT: {exc.detail}", code=exc.code) from exc

        raise JwtAuthServiceError(
            "AWS credentials are not available for JWT authentication.",
            code="aws_not_supported",
        )

    def get_boto3_session(self):
        return self.get_session()

    def is_valid(self) -> bool:
        runtime_auth = get_runtime_auth()
        if runtime_auth is None:
            return False

        claims = runtime_auth.claims or {}
        if not claims and runtime_auth.access_token:
            try:
                claims = self._decoder.decode(runtime_auth.access_token)
            except JwtDecodeError:
                return False

        if set(claims.keys()) - self._ALLOWED_CLAIMS:
            return False

        if not (claims.get("id") or claims.get("uuid")):
            return False

        exp = claims.get("exp")
        if exp is None:
            return False
        try:
            return float(exp) > time.time()
        except (TypeError, ValueError):
            return False

    def get_user_identity(self) -> Dict[str, str | None]:
        runtime_auth = get_runtime_auth()
        claims: Dict[str, Any] = {}
        if runtime_auth:
            claims = runtime_auth.claims or {}
            if not claims and runtime_auth.access_token:
                try:
                    claims = self._decoder.decode(runtime_auth.access_token)
                except JwtDecodeError:
                    claims = {}

        if set(claims.keys()) - self._ALLOWED_CLAIMS:
            claims = {}

        user_id = claims.get("id") or claims.get("uuid")
        if not user_id:
            return {"user_id": None, "email": None, "name": None}

        return {
            "user_id": user_id,
            "email": claims.get("email"),
            "name": claims.get("name"),
        }

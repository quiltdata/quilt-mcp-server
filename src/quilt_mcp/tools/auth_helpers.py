"""Helpers for JWT-based tool authorization."""

from __future__ import annotations

from typing import Any, Dict, Optional


from quilt_mcp.runtime_context import get_runtime_auth
from quilt_mcp.services.bearer_auth_service import JwtAuthResult, get_bearer_auth_service


def _runtime_jwt_result() -> Optional[JwtAuthResult]:
    auth_state = get_runtime_auth()
    if not auth_state or auth_state.scheme not in {"jwt", "bearer"}:
        return None

    extras = auth_state.extras or {}
    stored = extras.get("jwt_auth_result")
    if isinstance(stored, JwtAuthResult):
        return stored

    claims = auth_state.claims or {}
    return JwtAuthResult(
        token=auth_state.access_token or "runtime-token",
        claims=claims,
        permissions=claims.get("permissions", []),
        buckets=claims.get("buckets", []),
        roles=claims.get("roles", []),
        aws_credentials=extras.get("aws_credentials"),
        aws_role_arn=extras.get("aws_role_arn"),
        user_id=claims.get("sub") or claims.get("id"),
        username=claims.get("username"),
        raw_payload=claims,
    )


def _authorization_failure(reason: str) -> Dict[str, Any]:
    return {
        "authorized": False,
        "error": reason,
    }


def _authorize_tool(tool_name: str, tool_args: Dict[str, Any]) -> tuple[Optional[JwtAuthResult], Optional[Dict[str, Any]]]:
    """Authorize a tool using the active JWT context."""

    auth_result = _runtime_jwt_result()
    if not auth_result:
        return None, _authorization_failure("JWT authentication required")

    service = get_bearer_auth_service()
    decision = service.authorize_tool(auth_result, tool_name, tool_args or {})
    if not decision.allowed:
        reason = decision.reason or "Authorization denied"
        return None, _authorization_failure(reason)

    return auth_result, None


def check_s3_authorization(tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
    """Authorize S3 tool access based on runtime JWT claims."""

    auth_result, failure = _authorize_tool(tool_name, tool_args)
    if failure:
        return failure

    service = get_bearer_auth_service()

    try:
        client = service.build_boto3_client(auth_result, "s3")
    except Exception as exc:  # pragma: no cover - bubbled up for troubleshooting
        return _authorization_failure(f"Failed to construct S3 client: {exc}")

    return {
        "authorized": True,
        "s3_client": client,
        "claims": auth_result.claims,
    }


def check_package_authorization(tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
    """Authorize package tools using the active JWT context."""

    auth_result, failure = _authorize_tool(tool_name, tool_args)
    if failure:
        return failure

    return {
        "authorized": True,
        "claims": auth_result.claims,
    }

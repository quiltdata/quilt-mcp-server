"""Helpers for JWT-based tool authorization."""

from __future__ import annotations

from typing import Any, Dict, Optional


from quilt_mcp.runtime_context import get_runtime_auth
from quilt_mcp.services.bearer_auth_service import JwtAuthResult, get_bearer_auth_service


def _runtime_jwt_result() -> Optional[JwtAuthResult]:
    import logging
    logger = logging.getLogger(__name__)
    
    auth_state = get_runtime_auth()
    
    logger.info("🔍 _runtime_jwt_result: Checking for JWT in runtime context")
    logger.info("  - Has auth_state: %s", bool(auth_state))
    logger.info("  - Auth scheme: %s", auth_state.scheme if auth_state else None)
    
    if not auth_state or auth_state.scheme not in {"jwt", "bearer"}:
        logger.warning("❌ No JWT in runtime context (scheme=%s)", auth_state.scheme if auth_state else None)
        return None

    extras = auth_state.extras or {}
    stored = extras.get("jwt_auth_result")
    
    if isinstance(stored, JwtAuthResult):
        logger.info("✅ Found cached JWT result in runtime context")
        logger.info("  - User: %s", stored.username or stored.user_id)
        logger.info("  - Buckets: %d", len(stored.buckets))
        logger.info("  - Permissions: %d", len(stored.permissions))
        return stored

    logger.info("⚠️  Building JWT result from runtime claims")
    claims = auth_state.claims or {}
    result = JwtAuthResult(
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
    logger.info("  - Built result with %d buckets, %d permissions", len(result.buckets), len(result.permissions))
    return result


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

"""Tenant extraction helpers for multiuser mode."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from quilt_mcp.runtime_context import RuntimeAuthState
from quilt_mcp.services.jwt_decoder import JwtDecodeError, get_jwt_decoder


_TENANT_CLAIM_KEYS = ("tenant_id", "tenant", "org_id", "organization_id")


def _extract_from_mapping(mapping: Dict[str, Any]) -> Optional[str]:
    for key in _TENANT_CLAIM_KEYS:
        value = mapping.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _extract_from_session_metadata(auth_state: RuntimeAuthState) -> Optional[str]:
    extras = auth_state.extras or {}
    tenant = _extract_from_mapping(extras)
    if tenant:
        return tenant

    session_metadata = extras.get("session_metadata")
    if isinstance(session_metadata, dict):
        return _extract_from_mapping(session_metadata)

    return None


def extract_tenant_id(auth_state: Optional[RuntimeAuthState]) -> Optional[str]:
    """Extract tenant id from auth state, JWT, or environment fallback."""
    if auth_state is not None:
        if auth_state.claims:
            tenant = _extract_from_mapping(auth_state.claims)
            if tenant:
                return tenant

        tenant = _extract_from_session_metadata(auth_state)
        if tenant:
            return tenant

        if auth_state.access_token:
            decoder = get_jwt_decoder()
            try:
                claims = decoder.decode(auth_state.access_token)
            except JwtDecodeError:
                claims = {}
            tenant = _extract_from_mapping(claims)
            if tenant:
                return tenant

    env_tenant = os.getenv("QUILT_TENANT_ID") or os.getenv("QUILT_TENANT")
    if env_tenant and env_tenant.strip():
        return env_tenant.strip()

    return None

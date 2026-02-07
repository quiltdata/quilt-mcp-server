"""User identity extraction helpers."""

from __future__ import annotations

from typing import Optional

from quilt_mcp.runtime_context import RuntimeAuthState


def extract_user_id(auth_state: Optional[RuntimeAuthState]) -> Optional[str]:
    """
    Extract user ID from auth state claims.

    Note: This does NOT decode JWTs. It only extracts from claims
    already present in the auth state (populated by middleware or
    GraphQL response).

    Args:
        auth_state: Runtime authentication state with claims

    Returns:
        User ID (from 'id' or 'uuid' claim) or None if not present
    """
    if not auth_state or not auth_state.claims:
        return None

    claims = auth_state.claims
    return claims.get("id") or claims.get("uuid")

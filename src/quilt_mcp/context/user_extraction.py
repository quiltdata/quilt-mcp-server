"""User identity extraction helpers."""

from __future__ import annotations

from typing import Optional

from quilt_mcp.runtime_context import RuntimeAuthState
from quilt_mcp.services.jwt_decoder import JwtDecodeError, get_jwt_decoder


_ALLOWED_CLAIMS = {"id", "uuid", "exp"}


def _extract_from_claims(claims: dict) -> Optional[str]:
    if not claims:
        return None
    if set(claims.keys()) - _ALLOWED_CLAIMS:
        return None
    return claims.get("id") or claims.get("uuid")


def extract_user_id(auth_state: Optional[RuntimeAuthState]) -> Optional[str]:
    """Extract user ID from auth state or JWT."""
    if not auth_state:
        return None

    user_id = _extract_from_claims(auth_state.claims)
    if user_id:
        return user_id

    if auth_state.access_token:
        try:
            claims = get_jwt_decoder().decode(auth_state.access_token)
        except JwtDecodeError:
            return None
        return _extract_from_claims(claims)

    return None

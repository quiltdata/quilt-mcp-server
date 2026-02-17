"""Shared helpers for request-context construction."""

from __future__ import annotations

import uuid
from typing import Optional

from quilt_mcp.context.runtime_context import RuntimeAuthState
from quilt_mcp.context.user_extraction import extract_user_id


def generate_request_id(request_id: Optional[str]) -> str:
    """Return provided request id or generate a UUID4 id."""
    return request_id or str(uuid.uuid4())


def resolve_user_id_from_auth(auth_state: Optional[RuntimeAuthState]) -> Optional[str]:
    """Resolve user id from runtime auth state."""
    return extract_user_id(auth_state)

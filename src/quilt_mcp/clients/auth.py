"""Authentication helpers for stateless HTTP clients."""

from __future__ import annotations

from typing import Optional


def extract_bearer_token(authorization: Optional[str]) -> Optional[str]:
    """Extract bearer token from Authorization header."""

    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization[7:].strip()
    return token or None

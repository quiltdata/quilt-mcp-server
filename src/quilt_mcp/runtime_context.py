"""Runtime context helpers for Quilt MCP server.

This module provides per-request runtime context so tools can determine
whether they are serving desktop clients (stdio/quilt3) or web clients
that authenticate with JWTs. A context variable keeps the environment
and authentication metadata isolated between concurrent requests.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class RuntimeAuthState:
    """Authentication details for the active request/environment."""

    scheme: str
    access_token: Optional[str] = None
    claims: Dict[str, Any] = field(default_factory=dict)
    extras: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RuntimeContextState:
    """Top-level runtime context shared with MCP tools."""

    environment: str
    auth: Optional[RuntimeAuthState] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


_default_state = RuntimeContextState(environment="desktop")
_runtime_context_var: ContextVar[RuntimeContextState] = ContextVar(
    "quilt_runtime_context",
    default=_default_state,
)


def get_runtime_state() -> RuntimeContextState:
    """Return the current runtime context state."""
    return _runtime_context_var.get()


def get_runtime_environment() -> str:
    """Return the current runtime environment identifier."""
    return get_runtime_state().environment


def get_runtime_auth() -> Optional[RuntimeAuthState]:
    """Return the authentication state for the current context."""
    return get_runtime_state().auth


def get_runtime_access_token() -> Optional[str]:
    """Return the access token (if any) from the current auth state."""
    auth = get_runtime_auth()
    return auth.access_token if auth else None


def get_runtime_claims() -> Dict[str, Any]:
    """Return the claims dictionary stored in the current auth state."""
    auth = get_runtime_auth()
    return dict(auth.claims) if auth and auth.claims else {}


def get_runtime_metadata() -> Dict[str, Any]:
    """Return metadata associated with the current runtime context."""
    return get_runtime_state().metadata


def set_default_environment(environment: str) -> None:
    """Set the process-wide default environment and update current context."""
    if not environment:
        return

    global _default_state
    _default_state = replace(_default_state, environment=environment)
    _runtime_context_var.set(_default_state)


def push_runtime_context(
    *,
    environment: str,
    auth: Optional[RuntimeAuthState] = None,
    metadata: Optional[Dict[str, Any]] = None,
):
    """Push a new runtime context onto the context variable stack."""
    state = RuntimeContextState(environment=environment, auth=auth, metadata=dict(metadata or {}))
    return _runtime_context_var.set(state)


def reset_runtime_context(token) -> None:
    """Reset the runtime context to a previous state using a token."""
    _runtime_context_var.reset(token)


def set_runtime_environment(environment: str) -> None:
    """Update the current runtime environment."""
    if not environment:
        return

    state = get_runtime_state()
    _runtime_context_var.set(replace(state, environment=environment))


def set_runtime_auth(auth: Optional[RuntimeAuthState]) -> None:
    """Update the current authentication state."""
    state = get_runtime_state()
    _runtime_context_var.set(replace(state, auth=auth))


def clear_runtime_auth() -> None:
    """Remove any authentication from the current context."""
    set_runtime_auth(None)


def update_runtime_metadata(**updates: Any) -> None:
    """Merge provided key/value pairs into the runtime metadata."""
    state = get_runtime_state()
    metadata = dict(state.metadata)
    for key, value in updates.items():
        if value is None:
            metadata.pop(key, None)
        else:
            metadata[key] = value
    _runtime_context_var.set(replace(state, metadata=metadata))

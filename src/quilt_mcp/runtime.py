"""Request-scoped runtime context for stateless Quilt MCP server."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Dict, Iterator, Optional


_active_token: ContextVar[Optional[str]] = ContextVar("quilt_mcp_active_token", default=None)
_request_metadata: ContextVar[Optional[Dict[str, Any]]] = ContextVar("quilt_mcp_request_metadata", default=None)


def get_active_token() -> Optional[str]:
    """Return the bearer token for the current request, if any."""

    return _active_token.get()


def get_request_metadata() -> Dict[str, Any]:
    """Return metadata associated with the current request."""

    metadata = _request_metadata.get()
    return dict(metadata) if metadata else {}


@contextmanager
def request_context(token: Optional[str], metadata: Optional[Dict[str, Any]] = None) -> Iterator[None]:
    """Context manager that sets the active token and metadata for a request."""

    token_token = _active_token.set(token)
    metadata_token = _request_metadata.set(dict(metadata or {}) if metadata else None)
    try:
        yield
    finally:
        _active_token.reset(token_token)
        _request_metadata.reset(metadata_token)

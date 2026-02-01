"""Context variable helpers for request-scoped RequestContext."""

from __future__ import annotations

from contextvars import ContextVar
from typing import Optional

from quilt_mcp.context.exceptions import ContextNotAvailableError
from quilt_mcp.context.request_context import RequestContext


_current_context: ContextVar[Optional[RequestContext]] = ContextVar(
    "quilt_request_context",
    default=None,
)


def set_current_context(context: RequestContext):
    """Set the current request context and return a reset token."""
    return _current_context.set(context)


def reset_current_context(token) -> None:
    """Reset the current request context to a previous token."""
    _current_context.reset(token)


def get_current_context() -> RequestContext:
    """Return the current request context or raise if missing."""
    context = _current_context.get()
    if context is None:
        raise ContextNotAvailableError()
    return context

"""Helpers for integrating RequestContext with tool execution."""

from __future__ import annotations

import inspect
from functools import wraps
from typing import Any, Callable, Mapping, Optional

from quilt_mcp.context.factory import RequestContextFactory
from quilt_mcp.context.propagation import reset_current_context, set_current_context
from quilt_mcp.runtime_context import RuntimeAuthState


def extract_auth_info(headers: Optional[Mapping[str, str]]) -> Optional[RuntimeAuthState]:
    """Extract bearer token from headers for runtime auth state."""
    if not headers:
        return None
    auth_header = headers.get("authorization") or headers.get("Authorization")
    if not auth_header:
        return None
    if not auth_header.lower().startswith("bearer "):
        return None
    token = auth_header[7:].strip()
    if not token:
        return None
    return RuntimeAuthState(scheme="Bearer", access_token=token, claims={})


def wrap_tool_with_context(func: Callable[..., Any], factory: RequestContextFactory) -> Callable[..., Any]:
    """Wrap a tool function so it runs with a RequestContext."""
    if inspect.iscoroutinefunction(func):

        @wraps(func)
        async def _async_wrapper(*args: Any, **kwargs: Any) -> Any:
            context = factory.create_context()
            token = set_current_context(context)
            try:
                return await func(*args, **kwargs)
            finally:
                reset_current_context(token)

        _async_wrapper.__signature__ = inspect.signature(func)
        return _async_wrapper

    @wraps(func)
    def _wrapper(*args: Any, **kwargs: Any) -> Any:
        context = factory.create_context()
        token = set_current_context(context)
        try:
            return func(*args, **kwargs)
        finally:
            reset_current_context(token)

    _wrapper.__signature__ = inspect.signature(func)
    return _wrapper

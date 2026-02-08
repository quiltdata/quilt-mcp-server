"""Helpers for integrating RequestContext with tool execution."""

from __future__ import annotations

import inspect
from functools import wraps
from typing import Any, Callable, Mapping, Optional

from quilt_mcp.context.factory import RequestContextFactory
from quilt_mcp.context.runtime_context import RuntimeAuthState


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
    """Wrap a tool function so it runs with a RequestContext.

    The wrapper injects context as a keyword argument, allowing tools to receive
    explicit context parameters without exposing them in the MCP schema.
    """
    # Create modified signature that excludes 'context' parameter
    # This prevents Pydantic/MCP from seeing context as a required param
    original_sig = inspect.signature(func)
    new_params = [p for p in original_sig.parameters.values() if p.name != "context"]
    modified_sig = original_sig.replace(parameters=new_params)

    if inspect.iscoroutinefunction(func):

        @wraps(func)
        async def _async_wrapper(*args: Any, **kwargs: Any) -> Any:
            context = factory.create_context()
            return await func(*args, context=context, **kwargs)

        _async_wrapper.__signature__ = modified_sig  # type: ignore[attr-defined]
        return _async_wrapper

    @wraps(func)
    def _wrapper(*args: Any, **kwargs: Any) -> Any:
        context = factory.create_context()
        return func(*args, context=context, **kwargs)

    _wrapper.__signature__ = modified_sig  # type: ignore[attr-defined]
    return _wrapper

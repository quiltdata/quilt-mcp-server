"""Decorators for tool call logging and monitoring."""

import functools
from typing import Any, Callable, Dict, Optional

from .tool_logger import log_tool_call_end, log_tool_call_start


def log_tool_call(func: Callable) -> Callable:
    """Decorator to log tool calls with timing and results.

    Usage:
        @log_tool_call
        def my_tool(action: str, params: Dict) -> Dict:
            ...
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Extract tool name from function
        tool_name = func.__name__

        # Try to extract action and params from kwargs
        action = kwargs.get("action")
        params = kwargs.get("params", {})

        # Start logging
        context = log_tool_call_start(
            tool_name=tool_name,
            action=action,
            params=params,
        )

        try:
            # Execute the tool
            result = func(*args, **kwargs)

            # Log success
            log_tool_call_end(
                context=context,
                result=result,
                success=True,
            )

            return result

        except Exception as e:
            # Log failure
            log_tool_call_end(
                context=context,
                result=None,
                success=False,
                error=str(e),
            )
            raise

    return wrapper


def log_async_tool_call(func: Callable) -> Callable:
    """Decorator to log async tool calls with timing and results.

    Usage:
        @log_async_tool_call
        async def my_async_tool(action: str, params: Dict) -> Dict:
            ...
    """

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        # Extract tool name from function
        tool_name = func.__name__

        # Try to extract action and params from kwargs
        action = kwargs.get("action")
        params = kwargs.get("params", {})

        # Start logging
        context = log_tool_call_start(
            tool_name=tool_name,
            action=action,
            params=params,
        )

        try:
            # Execute the tool
            result = await func(*args, **kwargs)

            # Log success
            log_tool_call_end(
                context=context,
                result=result,
                success=True,
            )

            return result

        except Exception as e:
            # Log failure
            log_tool_call_end(
                context=context,
                result=None,
                success=False,
                error=str(e),
            )
            raise

    return wrapper

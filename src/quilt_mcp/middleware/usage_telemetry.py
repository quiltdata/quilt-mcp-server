"""FastMCP middleware recording every tool call to Mixpanel.

The ``on_call_tool`` hook is the one place every tool passes through, so this is
the only instrumentation point needed — tools stay unaware of telemetry.

Also feeds the existing ``TelemetryCollector``, which already models tool calls
but until now only ever saw synthetic ``auth.*`` entries.
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

try:
    from fastmcp.server.middleware import Middleware

    MIDDLEWARE_AVAILABLE = True
except ImportError:  # pragma: no cover - older fastmcp without middleware
    Middleware = object  # type: ignore[assignment,misc]
    MIDDLEWARE_AVAILABLE = False


def _client_info(context: Any) -> tuple[str, str]:
    """Name and version of the calling MCP client.

    This is what separates Claude Code traffic from Qurator traffic in the
    metrics, so it is read per call rather than cached at startup.
    """
    try:
        info = context.fastmcp_context.session.client_params.clientInfo
        return (info.name or "unknown", info.version or "unknown")
    except Exception:
        return ("unknown", "unknown")


class UsageTelemetryMiddleware(Middleware):
    """Records one Mixpanel event per tool call, successful or not."""

    async def on_call_tool(self, context: Any, call_next: Any) -> Any:
        from quilt_mcp.telemetry import mixpanel

        tool_name = getattr(getattr(context, "message", None), "name", "unknown")
        client_name, client_version = _client_info(context)
        started = time.perf_counter()
        # BaseException, not Exception: asyncio.CancelledError is a BaseException, so
        # catching Exception would book every cancelled or client-disconnected call as
        # a success and make the slowest tools look the healthiest.
        error: BaseException | None = None
        try:
            return await call_next(context)
        except BaseException as exc:
            error = exc
            raise
        finally:
            elapsed = time.perf_counter() - started
            try:
                mixpanel.track_tool_call(
                    tool_name=tool_name,
                    execution_time=elapsed,
                    success=error is None,
                    error_type=type(error).__name__ if error else None,
                    client_name=client_name,
                    client_version=client_version,
                )
                _record_to_collector(tool_name, elapsed, error)
            except Exception as exc:  # noqa: BLE001 — telemetry must never surface
                logger.debug("Usage telemetry failed for %s: %s", tool_name, exc)


def _record_to_collector(tool_name: str, elapsed: float, error: BaseException | None) -> None:
    """Mirror the call into the local TelemetryCollector session history."""
    from quilt_mcp.telemetry.collector import get_telemetry_collector

    collector = get_telemetry_collector()
    collector.record_tool_call(
        tool_name=tool_name,
        args={},  # args are hashed by the collector; not needed for usage counts
        execution_time=elapsed,
        success=error is None,
        # The collector's signature takes an Exception. A BaseException such as
        # CancelledError still counts as a failure via success=False; only its class
        # name is dropped here, and the Mixpanel event carries it.
        error=error if isinstance(error, Exception) else None,
    )


def install(mcp: Any) -> bool:
    """Attach usage telemetry to a FastMCP server if it's enabled and supported.

    Idempotent — attaching twice would double-count every tool call.
    Returns True when the middleware is now attached.
    """
    from quilt_mcp.telemetry import mixpanel

    if not MIDDLEWARE_AVAILABLE or not mixpanel.enabled():
        return False
    existing = getattr(mcp, "middleware", None) or []
    if any(isinstance(m, UsageTelemetryMiddleware) for m in existing):
        return True
    try:
        mcp.add_middleware(UsageTelemetryMiddleware())
    except Exception as exc:  # noqa: BLE001
        logger.debug("Could not attach usage telemetry: %s", exc)
        return False

    import atexit

    atexit.register(mixpanel.wait_for_pending)
    return True

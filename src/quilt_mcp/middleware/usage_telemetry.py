"""FastMCP middleware recording every tool call to Mixpanel.

The ``on_call_tool`` hook is the one place every tool passes through, so this is
the only instrumentation point needed — tools stay unaware of telemetry.

Also feeds the existing ``TelemetryCollector``, which already models tool calls
but until now only ever saw synthetic ``auth.*`` entries.
"""

from __future__ import annotations

import hashlib
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


def _distinct_id() -> str:
    """The Quilt user this call belongs to, or a stable anonymous stand-in.

    Mixpanel joins MCP events to catalog events on this property, so a literal
    "anonymous" for every authenticated call would make the whole comparison
    impossible. When identity cannot be resolved — stdio with no JWT, or claims
    without an id — the access token's hash stands in, so one unidentified caller
    stays one distinct_id instead of collapsing everyone into a single user. The
    token itself never leaves this function.
    """
    try:
        from quilt_mcp.context.runtime_context import get_runtime_auth
        from quilt_mcp.context.user_extraction import extract_user_id

        auth = get_runtime_auth()
        user_id = extract_user_id(auth)
        if user_id:
            return user_id
        token = getattr(auth, "access_token", None)
        if token:
            return "anon-" + hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]
    except Exception:  # noqa: BLE001 — telemetry must never surface
        pass
    return "anonymous"


def _returned_failure(result: Any) -> str | None:
    """Error type for a tool that reported failure by returning, not raising.

    Most tools here catch their own exceptions and return this repo's standard
    ``{"success": False, "error": ...}`` (``utils.common.format_error_response``).
    Treating only a raised exception as failure books those as successes, which
    would put the success rate near 100% no matter how badly a tool was doing.
    Returns None when the result is not a self-reported failure.
    """
    payload = result
    # fastmcp wraps a tool's return value; the dict is on structured_content.
    structured = getattr(result, "structured_content", None)
    if structured is not None:
        payload = structured
    if isinstance(payload, dict) and payload.get("success") is False:
        return "ToolReportedFailure"
    return None


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
        returned_error: str | None = None
        try:
            result = await call_next(context)
            returned_error = _returned_failure(result)
            return result
        except BaseException as exc:
            error = exc
            raise
        finally:
            elapsed = time.perf_counter() - started
            try:
                error_type = type(error).__name__ if error else returned_error
                mixpanel.track_tool_call(
                    tool_name=tool_name,
                    execution_time=elapsed,
                    success=error_type is None,
                    error_type=error_type,
                    distinct_id=_distinct_id(),
                    client_name=client_name,
                    client_version=client_version,
                )
                _record_to_collector(tool_name, elapsed, error, returned_error)
            except Exception as exc:  # noqa: BLE001 — telemetry must never surface
                logger.debug("Usage telemetry failed for %s: %s", tool_name, exc)


def _record_to_collector(
    tool_name: str,
    elapsed: float,
    error: BaseException | None,
    returned_error: str | None = None,
) -> None:
    """Mirror the call into the local TelemetryCollector session history."""
    from quilt_mcp.telemetry.collector import get_telemetry_collector

    collector = get_telemetry_collector()
    collector.record_tool_call(
        tool_name=tool_name,
        args={},  # args are hashed by the collector; not needed for usage counts
        execution_time=elapsed,
        success=error is None and returned_error is None,
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

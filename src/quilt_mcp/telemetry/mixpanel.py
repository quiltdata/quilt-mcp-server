"""Mixpanel usage telemetry for MCP tool calls.

Records one event per tool call so we can see which MCP capabilities are actually
used, and from where. The event contract is shared verbatim with
platform-mcp-server (`telemetry.py` there) — same event name, same property
names — because both servers report into one Mixpanel project and the whole point
is comparing traffic between clients. Changing a name here without changing it
there silently splits the data.

Event shape follows the catalog's own convention (a single event name with a
``type`` discriminator, see catalog/app/utils/tracking.jsx).

Sends are fire-and-forget: telemetry must never fail or slow a tool call.
"""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from typing import Any

logger = logging.getLogger(__name__)

MIXPANEL_URL = "https://api.mixpanel.com/track"
EVENT_NAME = "MCP"
SERVER_NAME = "quilt-mcp-server"

_executor: ThreadPoolExecutor | None = None
# Tool calls arrive concurrently, so every mutation of _inflight is taken under this
# lock: prune-then-append is a read-modify-write, and interleaving it drops a future,
# which would make the atexit drain miss an event. Bounded so a stalled endpoint
# cannot grow the list for the life of the process.
_INFLIGHT_MAX = 256
_inflight: deque = deque(maxlen=_INFLIGHT_MAX)
_inflight_lock = threading.Lock()


def project_token() -> str:
    return os.environ.get("MIXPANEL_PROJECT_TOKEN", "")


def _opted_out() -> bool:
    """Honor quilt3's kill switch: any value except an explicit falsey one disables."""
    value = os.environ.get("QUILT_DISABLE_USAGE_METRICS", "")
    if value.lower() in ("false", "no", "0"):
        return False
    return bool(value)


def _local_only() -> bool:
    """Whether the operator asked for telemetry to stay on the box.

    Mixpanel is off-box egress, so MCP_TELEMETRY_LOCAL_ONLY — the existing setting
    whose whole purpose is "do not ship my data anywhere" (honored by
    collector.py's transport selection) — must suppress it too. Read from the env
    rather than TelemetryConfig so this stays a pure function with no import cycle.
    """
    return os.environ.get("MCP_TELEMETRY_LOCAL_ONLY", "").lower() == "true"


def _telemetry_disabled_level() -> bool:
    """Whether MCP_TELEMETRY_LEVEL turns collection off entirely."""
    return os.environ.get("MCP_TELEMETRY_LEVEL", "").lower() == "disabled"


def enabled() -> bool:
    """True when a Mixpanel token is configured and no opt-out applies."""
    if not project_token():
        return False
    return not (_opted_out() or _local_only() or _telemetry_disabled_level())


def _server_version() -> str:
    try:
        from quilt_mcp import __version__

        return __version__
    except Exception:
        return "unknown"


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        # Two workers matches the existing HTTPTransport; telemetry gets no more
        # of the process than that.
        _executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="mixpanel")
    return _executor


def _post(event: dict[str, Any]) -> None:
    try:
        import requests

        requests.post(MIXPANEL_URL, json=[event], timeout=5)
    except Exception as exc:  # noqa: BLE001 — telemetry must never surface
        logger.debug("Mixpanel send failed: %s", exc)


def track_tool_call(
    tool_name: str,
    execution_time: float,
    success: bool,
    error_type: str | None = None,
    distinct_id: str | None = None,
    client_name: str | None = None,
    client_version: str | None = None,
) -> None:
    """Queue one Mixpanel event for a tool call. Never raises."""
    if not enabled():
        return
    event = {
        "event": EVENT_NAME,
        "properties": {
            "token": project_token(),
            "type": "tool_call",
            "tool": tool_name,
            "success": success,
            "error_type": error_type,
            "duration_ms": round(execution_time * 1000, 1),
            "client_name": client_name or "unknown",
            "client_version": client_version or "unknown",
            "server": SERVER_NAME,
            "server_version": _server_version(),
            "distinct_id": distinct_id or "anonymous",
            "time": int(time.time()),
            "$insert_id": str(uuid.uuid4()),
        },
    }
    try:
        future = _get_executor().submit(_post, event)
        with _inflight_lock:
            pending = [f for f in _inflight if not f.done()]
            _inflight.clear()
            _inflight.extend(pending)
            _inflight.append(future)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Mixpanel queue failed: %s", exc)


def wait_for_pending(timeout: float = 5.0) -> None:
    """Let queued sends finish. Called at exit so a short-lived stdio session
    doesn't drop its events."""
    from concurrent.futures import wait

    try:
        with _inflight_lock:
            pending = [f for f in _inflight if not f.done()]
        if pending:
            wait(pending, timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Mixpanel drain failed: %s", exc)

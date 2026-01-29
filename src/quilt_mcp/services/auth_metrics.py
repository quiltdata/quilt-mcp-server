"""Lightweight auth metrics helpers (logs + optional telemetry hooks)."""

from __future__ import annotations

import logging
import threading
from collections import Counter
from typing import Optional

logger = logging.getLogger(__name__)

_COUNTERS: Counter[tuple[str, str, Optional[str]]] = Counter()
_LOCK = threading.Lock()


def _record_counter(event: str, status: str, reason: Optional[str] = None) -> None:
    with _LOCK:
        _COUNTERS[(event, status, reason)] += 1


def _record_telemetry(event: str, status: str, duration_ms: Optional[float], reason: Optional[str]) -> None:
    try:
        from quilt_mcp.telemetry.collector import get_telemetry_collector
    except Exception:
        return

    try:
        collector = get_telemetry_collector()
        if not collector.config.enabled:
            return
        collector.record_tool_call(
            tool_name=f"auth.{event}",
            args={"status": status, "reason": reason or ""},
            execution_time=(duration_ms or 0) / 1000,
            success=status == "success",
            context={"reason": reason} if reason else None,
        )
    except Exception:
        logger.debug("Failed to emit auth telemetry for %s", event)


def record_auth_mode(mode: str) -> None:
    _record_counter("mode", mode)
    _record_telemetry("mode", mode, None, None)


def record_jwt_validation(status: str, *, duration_ms: Optional[float] = None, reason: Optional[str] = None) -> None:
    _record_counter("jwt_validation", status, reason)
    _record_telemetry("jwt_validation", status, duration_ms, reason)


def record_role_assumption(status: str, *, duration_ms: Optional[float] = None, reason: Optional[str] = None) -> None:
    _record_counter("role_assumption", status, reason)
    _record_telemetry("role_assumption", status, duration_ms, reason)

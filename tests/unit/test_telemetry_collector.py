"""Behavioral tests for the telemetry collector."""

from __future__ import annotations

import time

from dataclasses import replace

import pytest

from quilt_mcp.telemetry.collector import TelemetryCollector, TelemetryConfig, TelemetryLevel


def make_config(**overrides) -> TelemetryConfig:
    base = TelemetryConfig(
        enabled=True,
        level=TelemetryLevel.STANDARD,
        local_only=True,
        endpoint=None,
        batch_size=10,
        flush_interval=60,
        privacy_level="standard",
        session_timeout=3600,
    )
    return replace(base, **overrides) if overrides else base


def test_cleanup_old_sessions_resets_current_session():
    """Cleaning up old sessions should clear the active session pointer."""

    collector = TelemetryCollector(make_config())
    session_id = collector.start_session("analysis")
    collector.sessions[session_id].start_time = time.time() - 10_000
    collector.current_session_id = session_id

    removed = collector.cleanup_old_sessions(max_age_seconds=60)

    assert removed == 1
    assert collector.current_session_id is None
    assert session_id not in collector.sessions


def test_record_tool_call_auto_starts_session_and_filters_context():
    """Recording a tool call should create a session and hash sensitive data."""

    collector = TelemetryCollector(make_config())
    collector.current_session_id = None
    collector.privacy_manager.hash_args = lambda args: "hashed"  # type: ignore[assignment]
    collector.privacy_manager.filter_context = lambda ctx: {"user_intent": ctx.get("user_intent")}

    collector.record_tool_call(
        tool_name="demo_tool",
        args={"secret": "value"},
        execution_time=0.42,
        success=True,
        result={"payload": "ok"},
        context={"user_intent": "explore", "extra": "ignored"},
    )

    auto_session_id = collector.current_session_id
    assert auto_session_id is not None
    assert auto_session_id in collector.sessions
    session = collector.sessions[auto_session_id]
    assert session.total_calls == 0  # not populated until end_session
    assert len(session.tool_calls) == 1
    call = session.tool_calls[0]
    assert call.args_hash == "hashed"
    assert call.context == {"user_intent": "explore"}


def test_performance_metrics_reflect_completed_sessions():
    """Aggregated metrics should track session completion and call counts."""

    collector = TelemetryCollector(make_config())
    session_id = collector.start_session("batch")
    collector.record_tool_call("tool_a", {"a": 1}, 1.0, True)
    collector.record_tool_call("tool_b", {"b": 2}, 0.5, False, error=RuntimeError("boom"))
    collector.end_session(session_id, completed=False)

    metrics = collector.get_performance_metrics()

    assert metrics["total_sessions"] == 1
    assert metrics["completed_sessions"] == 0
    assert metrics["total_tool_calls"] == 2
    assert metrics["tool_usage"]["tool_a"] == 1
    assert metrics["tool_usage"]["tool_b"] == 1

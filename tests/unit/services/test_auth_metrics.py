"""Unit tests for auth metrics helpers."""

from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace

from quilt_mcp.services import auth_metrics


def setup_function():
    auth_metrics._COUNTERS.clear()


def test_record_auth_mode_increments_counter():
    auth_metrics.record_auth_mode("iam")

    assert auth_metrics._COUNTERS[("mode", "iam", None)] == 1


def test_record_telemetry_returns_when_collector_import_missing_function(monkeypatch):
    fake_collector_module = ModuleType("quilt_mcp.telemetry.collector")
    monkeypatch.setitem(sys.modules, "quilt_mcp.telemetry.collector", fake_collector_module)

    auth_metrics._record_telemetry("mode", "iam", None, None)


def test_record_telemetry_skips_when_disabled(monkeypatch):
    class StubCollector:
        def __init__(self):
            self.config = SimpleNamespace(enabled=False)
            self.calls = 0

        def record_tool_call(self, **kwargs):
            self.calls += 1

    collector = StubCollector()
    fake_collector_module = ModuleType("quilt_mcp.telemetry.collector")
    fake_collector_module.get_telemetry_collector = lambda: collector
    monkeypatch.setitem(sys.modules, "quilt_mcp.telemetry.collector", fake_collector_module)

    auth_metrics._record_telemetry("jwt_validation", "success", 50.0, None)
    assert collector.calls == 0


def test_record_telemetry_records_tool_call(monkeypatch):
    class StubCollector:
        def __init__(self):
            self.config = SimpleNamespace(enabled=True)
            self.calls = []

        def record_tool_call(self, **kwargs):
            self.calls.append(kwargs)

    collector = StubCollector()
    fake_collector_module = ModuleType("quilt_mcp.telemetry.collector")
    fake_collector_module.get_telemetry_collector = lambda: collector
    monkeypatch.setitem(sys.modules, "quilt_mcp.telemetry.collector", fake_collector_module)

    auth_metrics.record_jwt_validation("success", duration_ms=250.0, reason="ok")

    assert len(collector.calls) == 1
    call = collector.calls[0]
    assert call["tool_name"] == "auth.jwt_validation"
    assert call["execution_time"] == 0.25
    assert call["success"] is True
    assert call["context"] == {"reason": "ok"}


def test_record_telemetry_logs_debug_when_collector_fails(monkeypatch, caplog):
    class StubCollector:
        def __init__(self):
            self.config = SimpleNamespace(enabled=True)

        def record_tool_call(self, **kwargs):
            raise RuntimeError("collector error")

    fake_collector_module = ModuleType("quilt_mcp.telemetry.collector")
    fake_collector_module.get_telemetry_collector = lambda: StubCollector()
    monkeypatch.setitem(sys.modules, "quilt_mcp.telemetry.collector", fake_collector_module)

    caplog.set_level("DEBUG")
    auth_metrics._record_telemetry("role_assumption", "failure", 10.0, "bad creds")
    assert "Failed to emit auth telemetry" in caplog.text

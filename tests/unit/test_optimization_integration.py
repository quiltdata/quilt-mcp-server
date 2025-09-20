"""Behavioral tests for optimization integration helpers."""

from __future__ import annotations

import os
from contextlib import nullcontext

import pytest

# Disable auto patching during import
os.environ.setdefault("MCP_OPTIMIZATION_ENABLED", "false")

from quilt_mcp.optimization import integration as opt_integration


class DummyServer:
    def __init__(self):
        self._tools = {"demo_tool": lambda x: x}
        self.run_called_with = None

    def run(self, transport):
        self.run_called_with = transport


class DummyInterceptor:
    def __init__(self):
        self.calls = []

    def intercept_tool_call(self, func):
        def wrapper(*args, **kwargs):
            self.calls.append((args, kwargs))
            return func(*args, **kwargs)

        return wrapper

    def get_optimization_report(self):
        return {"wrapped": len(self.calls)}


class DummyTelemetry:
    def get_performance_metrics(self):
        return {"total_tool_calls": 5}


@pytest.fixture
def dummy_components(monkeypatch: pytest.MonkeyPatch):
    server = DummyServer()
    interceptor = DummyInterceptor()
    telemetry = DummyTelemetry()

    monkeypatch.setattr(opt_integration, "create_configured_server", lambda verbose=False: server)
    monkeypatch.setattr(opt_integration, "get_tool_interceptor", lambda: interceptor)
    monkeypatch.setattr(opt_integration, "get_telemetry_collector", lambda: telemetry)

    return server, interceptor, telemetry


def test_server_disabled_skips_optimization_components(dummy_components):
    server, interceptor, telemetry = dummy_components

    optimized = opt_integration.OptimizedMCPServer(enable_optimization=False)

    assert optimized.optimization_enabled is False
    assert optimized.interceptor is None
    assert optimized.telemetry is None
    assert optimized.mcp_server is server


def test_server_enabled_wraps_tools_and_reports(dummy_components):
    server, interceptor, telemetry = dummy_components
    original_tool = server._tools["demo_tool"]

    optimized = opt_integration.OptimizedMCPServer(enable_optimization=True)

    wrapped_tool = server._tools["demo_tool"]
    assert wrapped_tool is not original_tool
    wrapped_tool("payload")
    assert interceptor.calls

    stats = optimized.get_optimization_stats()
    assert stats["optimization_enabled"] is True
    assert stats["wrapped"] == 1
    assert stats["total_tool_calls"] == 5


def test_run_with_context_returns_nullcontext_when_disabled(dummy_components):
    optimized = opt_integration.OptimizedMCPServer(enable_optimization=False)

    context = optimized.run_with_optimization_context()
    assert isinstance(context, nullcontext)


def test_run_optimized_server_validates_transport(monkeypatch: pytest.MonkeyPatch):
    server = DummyServer()
    monkeypatch.setenv("MCP_OPTIMIZATION_ENABLED", "false")
    monkeypatch.setenv("FASTMCP_TRANSPORT", "invalid-transport")
    monkeypatch.setattr(opt_integration, "create_optimized_server", lambda: server)

    opt_integration.run_optimized_server()

    assert server.run_called_with == "stdio"

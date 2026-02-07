"""Behavior-driven tests for telemetry transports."""

from __future__ import annotations

import json
import pathlib
import types
import sys

import pytest

from quilt_mcp.telemetry import transport as telemetry_transport


def test_local_file_transport_embeds_transport_marker(tmp_path: pathlib.Path):
    """Local transport should include a transport marker in the written record."""

    target = tmp_path / "telemetry.jsonl"
    t = telemetry_transport.LocalFileTransport(file_path=str(target))

    result = t.send_session({"session": "demo"})

    assert result is True
    raw = target.read_text().strip().splitlines()
    assert len(raw) == 1
    record = json.loads(raw[0])
    assert record["transport"] == "local_file"


def test_http_transport_includes_transport_marker(monkeypatch: pytest.MonkeyPatch):
    """HTTP transport payloads should use quilt3-compatible schema."""

    calls = {}

    class DummyFuture:
        def done(self):
            return True

    class DummyResponse:
        status_code = 200
        text = "ok"

    class DummyFuturesSession:
        def __init__(self, executor=None):
            self.headers = {}

        def post(self, url, *, json, timeout):  # type: ignore[override]
            calls["url"] = url
            calls["payload"] = json
            calls["timeout"] = timeout
            return DummyFuture()

    # Mock requests_futures
    dummy_requests_futures = types.SimpleNamespace(sessions=types.SimpleNamespace(FuturesSession=DummyFuturesSession))
    monkeypatch.setitem(sys.modules, "requests_futures.sessions", dummy_requests_futures.sessions)

    http = telemetry_transport.HTTPTransport("https://example.com/api")

    assert http.send_session({"session": "demo", "tool_name": "test_tool"}) is True
    # Verify quilt3-compatible schema
    assert calls["payload"]["telemetry_schema_version"] == telemetry_transport.TELEMETRY_SCHEMA_VERSION
    assert calls["payload"]["client_type"] == telemetry_transport.TELEMETRY_CLIENT_TYPE
    assert calls["payload"]["api_name"] == "test_tool"
    assert "mcp_data" in calls["payload"]


def test_cloudwatch_transport_marks_transport(monkeypatch: pytest.MonkeyPatch):
    """CloudWatch transport should annotate log entries with the transport name."""

    put_calls = []

    class DummyClient:
        class exceptions:
            class ResourceAlreadyExistsException(Exception):
                pass

        def __init__(self, *args, **kwargs):
            pass

        def create_log_group(self, **_kwargs):
            raise self.exceptions.ResourceAlreadyExistsException()

        def create_log_stream(self, **_kwargs):
            raise self.exceptions.ResourceAlreadyExistsException()

        def put_log_events(self, **kwargs):
            put_calls.append(kwargs)

        def describe_log_groups(self, **_kwargs):
            return {"logGroups": []}

    class DummyBoto3:
        def client(self, *_args, **_kwargs):
            return DummyClient()

    monkeypatch.setitem(sys.modules, "boto3", DummyBoto3())

    cw = telemetry_transport.CloudWatchTransport(log_group="demo-group", log_stream="demo-stream")

    assert cw.send_session({"session": "demo"}) is True
    assert put_calls
    payload = json.loads(put_calls[0]["logEvents"][0]["message"])  # first event
    assert payload["transport"] == "cloudwatch"

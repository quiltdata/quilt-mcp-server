"""Behavior-driven tests for telemetry transports."""

from __future__ import annotations

import json
import pathlib
import types
import sys
import builtins

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


def test_local_file_transport_batch_read_and_availability_failures(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
):
    target = tmp_path / "telemetry.jsonl"
    t = telemetry_transport.LocalFileTransport(file_path=str(target))
    assert t.send_batch([{"a": 1}, {"b": 2}]) is True
    assert len(t.read_sessions()) == 2
    assert len(t.read_sessions(limit=1)) == 1

    target.write_text('{"type":"session","data":{"ok":1}}\nnot-json\n{"type":"session","data":{"ok":2}}\n')
    sessions = t.read_sessions()
    assert sessions == [{"ok": 1}, {"ok": 2}]

    monkeypatch.setattr(pathlib.Path, "write_text", lambda *_a, **_k: (_ for _ in ()).throw(OSError("nope")))
    assert t.is_available() is False


def test_http_transport_import_error_and_cleanup(monkeypatch: pytest.MonkeyPatch):
    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "requests_futures.sessions":
            raise ImportError("missing")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    http = telemetry_transport.HTTPTransport("https://example.com")
    assert http.is_available() is False
    assert http.send_session({"tool_name": "x"}) is False
    assert http.send_batch([{"tool_name": "x"}]) is False


def test_http_transport_pending_and_wait(monkeypatch: pytest.MonkeyPatch):
    class Future:
        def __init__(self, done: bool):
            self._done = done

        def done(self):
            return self._done

    class DummySession:
        def __init__(self):
            self.headers = {}

        def post(self, *_args, **_kwargs):
            return Future(False)

    http = telemetry_transport.HTTPTransport.__new__(telemetry_transport.HTTPTransport)
    http.endpoint = "https://example.com"
    http.api_key = None
    http.timeout = 5
    http.session = DummySession()
    http.pending_reqs = [Future(True), Future(False)]

    http.cleanup_completed_requests()
    assert len(http.pending_reqs) == 1

    monkeypatch.setattr(
        "quilt_mcp.telemetry.transport.wait", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("wait-fail"))
    )
    http.wait_for_pending(timeout=1)  # should not raise


def test_http_send_batch_exception_path():
    http = telemetry_transport.HTTPTransport.__new__(telemetry_transport.HTTPTransport)
    http.session = object()
    http.pending_reqs = []
    http.cleanup_completed_requests = lambda: None

    def _raise(_session_data):
        raise RuntimeError("boom")

    http.send_session = _raise  # type: ignore[method-assign]
    assert http.send_batch([{"x": 1}]) is False


def test_cloudwatch_send_batch_chunking_and_unavailable(monkeypatch: pytest.MonkeyPatch):
    calls = []

    class DummyClient:
        class exceptions:
            class ResourceAlreadyExistsException(Exception):
                pass

        def create_log_group(self, **_kwargs):
            return None

        def create_log_stream(self, **_kwargs):
            return None

        def put_log_events(self, **kwargs):
            calls.append(kwargs)

        def describe_log_groups(self, **_kwargs):
            return {"logGroups": [{"logGroupName": "x"}]}

    cw = telemetry_transport.CloudWatchTransport.__new__(telemetry_transport.CloudWatchTransport)
    cw.log_group = "g"
    cw.log_stream = "s"
    cw.client = DummyClient()

    batch = [{"idx": i} for i in range(1501)]
    assert cw.send_batch(batch) is True
    assert len(calls) == 2  # chunked by 1000
    assert len(calls[0]["logEvents"]) == 1000
    assert len(calls[1]["logEvents"]) == 501
    assert cw.is_available() is True

    cw.client = None
    assert cw.send_session({"x": 1}) is False
    assert cw.send_batch([{"x": 1}]) is False
    assert cw.is_available() is False


def test_create_transport_branches_and_cleanup_registration(monkeypatch: pytest.MonkeyPatch):
    class Cfg:
        local_only = False
        endpoint = None

    local_cfg = Cfg()
    local_cfg.local_only = True
    t = telemetry_transport.create_transport(local_cfg)
    assert isinstance(t, telemetry_transport.LocalFileTransport)

    http_cfg = Cfg()
    http_cfg.endpoint = "https://example.com"
    t2 = telemetry_transport.create_transport(http_cfg)
    assert isinstance(t2, telemetry_transport.HTTPTransport)

    cw_cfg = Cfg()
    cw_cfg.endpoint = "cloudwatch:my-group"
    t3 = telemetry_transport.create_transport(cw_cfg)
    assert isinstance(t3, telemetry_transport.CloudWatchTransport)

    default_cfg = Cfg()
    t4 = telemetry_transport.create_transport(default_cfg)
    assert isinstance(t4, telemetry_transport.HTTPTransport)

    class DummyHTTP:
        def __init__(self):
            self.called = False

        def wait_for_pending(self):
            self.called = True

    dummy = DummyHTTP()
    telemetry_transport.register_http_transport(dummy)  # type: ignore[arg-type]
    telemetry_transport.cleanup_pending_requests()
    assert dummy.called is True

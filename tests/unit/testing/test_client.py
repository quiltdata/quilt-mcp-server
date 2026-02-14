from __future__ import annotations

import io
import json
from unittest.mock import Mock, patch

import pytest
import requests

from quilt_mcp.testing.client import MCPTester


class StubResponse:
    def __init__(self, *, status_code=200, headers=None, payload=None, text=""):
        self.status_code = status_code
        self.headers = headers or {"content-type": "application/json"}
        self._payload = payload or {"result": {}}
        self.text = text or json.dumps(self._payload)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status={self.status_code}")

    def json(self):
        return self._payload


def test_http_transport_requires_endpoint():
    with pytest.raises(ValueError, match="endpoint required"):
        MCPTester(transport="http")


def test_stdio_transport_requires_inputs():
    with pytest.raises(ValueError, match="process or"):
        MCPTester(transport="stdio")


def test_http_request_success_and_session_headers(monkeypatch):
    tester = MCPTester(endpoint="http://localhost:8000/mcp", transport="http", jwt_token="tok-1234567890")
    response = StubResponse(payload={"result": {"ok": True}})
    monkeypatch.setattr(tester.session, "post", lambda *_args, **_kwargs: response)

    result = tester._make_http_request("tools/list")
    assert result == {"ok": True}
    assert "Authorization" in tester.session.headers


def test_http_request_sse_parsing(monkeypatch):
    tester = MCPTester(endpoint="http://localhost:8000/mcp", transport="http")
    response = StubResponse(
        headers={"content-type": "text/event-stream"},
        text='event: message\ndata: {"result":{"ok":true}}\n',
    )
    monkeypatch.setattr(tester.session, "post", lambda *_args, **_kwargs: response)

    result = tester._make_http_request("tools/list")
    assert result == {"ok": True}


def test_http_request_401_and_403_errors(monkeypatch):
    tester = MCPTester(endpoint="http://localhost:8000/mcp", transport="http", jwt_token="token-abcdefgh12345678")

    monkeypatch.setattr(tester.session, "post", lambda *_args, **_kwargs: StubResponse(status_code=401))
    with pytest.raises(Exception, match="JWT token rejected"):
        tester._make_http_request("tools/list")

    monkeypatch.setattr(tester.session, "post", lambda *_args, **_kwargs: StubResponse(status_code=403))
    with pytest.raises(Exception, match="Authorization failed"):
        tester._make_http_request("tools/list")


def test_http_request_wraps_request_exception(monkeypatch):
    tester = MCPTester(endpoint="http://localhost:8000/mcp", transport="http")

    def _raise(*_args, **_kwargs):
        raise requests.exceptions.RequestException("network")

    monkeypatch.setattr(tester.session, "post", _raise)
    with pytest.raises(Exception, match="HTTP request failed"):
        tester._make_http_request("tools/list")


def test_http_request_invalid_json_from_sse(monkeypatch):
    tester = MCPTester(endpoint="http://localhost:8000/mcp", transport="http")
    response = StubResponse(headers={"content-type": "text/event-stream"}, text="event: message\n")
    monkeypatch.setattr(tester.session, "post", lambda *_args, **_kwargs: response)
    with pytest.raises(Exception, match="No data field found in SSE response"):
        tester._make_http_request("tools/list")


def test_stdio_request_success_error_and_invalid_json():
    stdin = io.StringIO()
    stdout = io.StringIO('{"result":{"ok":true}}\n')
    tester = MCPTester(transport="stdio", process=Mock(stdin=stdin, stdout=stdout))

    result = tester._make_stdio_request("tools/list")
    assert result == {"ok": True}

    stdout_error = io.StringIO('{"error":"bad"}\n')
    tester_error = MCPTester(transport="stdio", process=Mock(stdin=io.StringIO(), stdout=stdout_error))
    with pytest.raises(Exception, match="JSON-RPC error"):
        tester_error._make_stdio_request("tools/list")

    stdout_bad = io.StringIO("not json\n")
    tester_bad = MCPTester(transport="stdio", process=Mock(stdin=io.StringIO(), stdout=stdout_bad))
    with pytest.raises(Exception, match="Invalid JSON response"):
        tester_bad._make_stdio_request("tools/list")


def test_make_request_switches_transport(monkeypatch):
    tester_http = MCPTester(endpoint="http://localhost:8000/mcp", transport="http")
    monkeypatch.setattr(tester_http, "_make_http_request", lambda *_args, **_kwargs: {"via": "http"})
    assert tester_http._make_request("tools/list") == {"via": "http"}

    tester_stdio = MCPTester(
        transport="stdio", process=Mock(stdin=io.StringIO(), stdout=io.StringIO('{"result":{}}\n'))
    )
    monkeypatch.setattr(tester_stdio, "_make_stdio_request", lambda *_args, **_kwargs: {"via": "stdio"})
    assert tester_stdio._make_request("tools/list") == {"via": "stdio"}


def test_initialize_and_tool_helpers(monkeypatch):
    tester = MCPTester(transport="stdio", process=Mock(stdin=io.StringIO(), stdout=io.StringIO('{"result":{}}\n')))

    calls = []
    monkeypatch.setattr(
        tester, "_make_request", lambda method, params=None: calls.append((method, params)) or {"tools": []}
    )
    monkeypatch.setattr(tester, "_send_notification", lambda method, params=None: calls.append((method, params)))

    tester.initialize()
    tester.list_tools()
    tester.call_tool("x", {"a": 1})
    tester.list_resources()
    tester.read_resource("auth://status")

    methods = [m for m, _ in calls]
    assert "initialize" in methods
    assert "notifications/initialized" in methods
    assert "tools/list" in methods
    assert "tools/call" in methods
    assert "resources/list" in methods
    assert "resources/read" in methods


def test_send_notification_noop_for_http_and_writes_for_stdio(monkeypatch):
    tester_http = MCPTester(endpoint="http://localhost:8000/mcp", transport="http")
    tester_http._send_notification("notifications/initialized")

    stdin = io.StringIO()
    tester_stdio = MCPTester(transport="stdio", process=Mock(stdin=stdin, stdout=io.StringIO()))
    monkeypatch.setattr("quilt_mcp.testing.client.time.sleep", lambda _x: None)
    tester_stdio._send_notification("notifications/initialized", {"x": 1})
    written = stdin.getvalue()
    assert '"method": "notifications/initialized"' in written

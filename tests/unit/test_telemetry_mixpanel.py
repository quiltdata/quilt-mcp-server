"""Unit tests for the Mixpanel usage-telemetry transport."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from quilt_mcp.telemetry import mixpanel


@pytest.fixture(autouse=True)
def clear_inflight():
    mixpanel._inflight.clear()
    yield
    mixpanel._inflight.clear()


@pytest.fixture
def token_set(monkeypatch):
    monkeypatch.setenv("MIXPANEL_PROJECT_TOKEN", "tok123")
    monkeypatch.delenv("QUILT_DISABLE_USAGE_METRICS", raising=False)


class TestEnabled:
    def test_disabled_without_token(self, monkeypatch):
        monkeypatch.delenv("MIXPANEL_PROJECT_TOKEN", raising=False)
        assert mixpanel.enabled() is False

    def test_enabled_with_token(self, token_set):
        assert mixpanel.enabled() is True

    def test_quilt_kill_switch_disables(self, token_set, monkeypatch):
        monkeypatch.setenv("QUILT_DISABLE_USAGE_METRICS", "1")
        assert mixpanel.enabled() is False

    @pytest.mark.parametrize("value", ["false", "no", "0", "False"])
    def test_explicit_falsey_does_not_disable(self, token_set, monkeypatch, value):
        monkeypatch.setenv("QUILT_DISABLE_USAGE_METRICS", value)
        assert mixpanel.enabled() is True


class TestTrackToolCall:
    def _capture(self, **kwargs):
        sent: list[dict] = []
        with patch.object(mixpanel, "_post", lambda event: sent.append(event)):
            # Run inline instead of on the pool so the assertion is deterministic.
            with patch.object(mixpanel, "_get_executor") as executor:
                executor.return_value.submit = lambda fn, event: _Done(fn(event))
                mixpanel.track_tool_call(**kwargs)
        return sent

    def test_no_event_when_disabled(self, monkeypatch):
        monkeypatch.delenv("MIXPANEL_PROJECT_TOKEN", raising=False)
        assert self._capture(tool_name="x", execution_time=0.1, success=True) == []

    def test_event_shape_matches_contract(self, token_set):
        sent = self._capture(
            tool_name="packages_list",
            execution_time=0.25,
            success=True,
            distinct_id="alice",
            client_name="claude-code",
            client_version="2.0.0",
        )
        assert len(sent) == 1
        props = sent[0]["properties"]
        # Event name and type discriminator are shared with platform-mcp-server;
        # a change here splits the data across two servers.
        assert sent[0]["event"] == "MCP"
        assert props["type"] == "tool_call"
        assert props["tool"] == "packages_list"
        assert props["success"] is True
        assert props["error_type"] is None
        assert props["duration_ms"] == 250.0
        assert props["client_name"] == "claude-code"
        assert props["client_version"] == "2.0.0"
        assert props["distinct_id"] == "alice"
        assert props["server"] == "quilt-mcp-server"
        assert props["token"] == "tok123"
        assert "$insert_id" in props

    def test_failure_carries_error_type(self, token_set):
        sent = self._capture(
            tool_name="package_create",
            execution_time=0.01,
            success=False,
            error_type="ValidationError",
        )
        props = sent[0]["properties"]
        assert props["success"] is False
        assert props["error_type"] == "ValidationError"

    def test_unknown_client_defaults(self, token_set):
        sent = self._capture(tool_name="x", execution_time=0.0, success=True)
        assert sent[0]["properties"]["client_name"] == "unknown"
        assert sent[0]["properties"]["distinct_id"] == "anonymous"

    def test_queue_failure_never_raises(self, token_set):
        with patch.object(mixpanel, "_get_executor", side_effect=RuntimeError("no pool")):
            mixpanel.track_tool_call(tool_name="x", execution_time=0.0, success=True)

    def test_post_failure_never_raises(self, token_set):
        with patch("requests.post", side_effect=RuntimeError("network down")):
            mixpanel._post({"event": "MCP", "properties": {}})


class _Done:
    """Minimal already-completed future stand-in."""

    def __init__(self, result=None):
        self._result = result

    def done(self) -> bool:
        return True


class TestLocalOnlyAndLevel:
    """MCP_TELEMETRY_LOCAL_ONLY means "do not ship my data anywhere". Mixpanel is
    off-box egress, so it must be suppressed — collector.py gates its own HTTP
    transport on the same flag."""

    def test_local_only_suppresses_mixpanel(self, token_set, monkeypatch):
        monkeypatch.setenv("MCP_TELEMETRY_LOCAL_ONLY", "true")
        assert mixpanel.enabled() is False

    def test_local_only_false_does_not_suppress(self, token_set, monkeypatch):
        monkeypatch.setenv("MCP_TELEMETRY_LOCAL_ONLY", "false")
        assert mixpanel.enabled() is True

    def test_telemetry_level_disabled_suppresses(self, token_set, monkeypatch):
        monkeypatch.setenv("MCP_TELEMETRY_LEVEL", "disabled")
        assert mixpanel.enabled() is False

    def test_other_levels_do_not_suppress(self, token_set, monkeypatch):
        monkeypatch.setenv("MCP_TELEMETRY_LEVEL", "standard")
        assert mixpanel.enabled() is True

    def test_local_only_blocks_the_actual_send(self, token_set, monkeypatch):
        """Not just the flag — no event may be queued."""
        monkeypatch.setenv("MCP_TELEMETRY_LOCAL_ONLY", "true")
        sent = []
        with patch.object(mixpanel, "_post", lambda e: sent.append(e)):
            mixpanel.track_tool_call(tool_name="x", execution_time=0.1, success=True)
        assert sent == []


class TestInflightBookkeeping:
    def test_inflight_is_bounded(self):
        """A stalled endpoint must not grow the list for the process lifetime."""
        assert mixpanel._inflight.maxlen == mixpanel._INFLIGHT_MAX

    def test_no_pending_future_is_dropped_under_concurrency(self, token_set):
        """Prune-then-append is a read-modify-write; interleaving it dropped futures,
        which made the atexit drain miss events.

        The sends are held open so every future stays pending — a completed future is
        legitimately pruned, so only pending ones can show the race.
        """
        import threading

        release = threading.Event()
        count = 24

        with patch.object(mixpanel, "_post", lambda e: release.wait(10)):
            threads = [
                threading.Thread(
                    target=mixpanel.track_tool_call,
                    kwargs={"tool_name": f"t{i}", "execution_time": 0.0, "success": True},
                )
                for i in range(count)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            # Every send is still blocked, so nothing may have been pruned.
            assert len(mixpanel._inflight) == count
            release.set()
            mixpanel.wait_for_pending(timeout=15)

        assert all(f.done() for f in mixpanel._inflight)

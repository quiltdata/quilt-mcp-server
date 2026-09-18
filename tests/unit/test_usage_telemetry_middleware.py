"""Unit tests for the usage-telemetry middleware's outcome and identity logic.

Each test here fails without its corresponding fix; together they cover the three
review findings on PR #315:

- a tool that reports failure by *returning* ``{"success": False}`` must not be
  booked as a success (most tools in this repo report that way),
- an authenticated call must carry the Quilt user as ``distinct_id``, since that is
  the only property joining MCP events to catalog events,
- the executor's work queue must be bounded, not just the reference deque.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from quilt_mcp.context.runtime_context import (
    RuntimeAuthState,
    push_runtime_context,
    reset_runtime_context,
)
from quilt_mcp.middleware import usage_telemetry as ut
from quilt_mcp.telemetry import mixpanel


class _Result:
    """Stand-in for fastmcp's ToolResult, which carries the dict on this attr."""

    def __init__(self, structured_content):
        self.structured_content = structured_content


class TestReturnedFailure:
    def test_standard_error_response_is_a_failure(self):
        # The shape utils.common.format_error_response produces.
        payload = {"success": False, "error": "bucket not found"}
        assert ut._returned_failure(payload) == "ToolReportedFailure"

    def test_wrapped_in_tool_result(self):
        assert ut._returned_failure(_Result({"success": False, "error": "x"})) == "ToolReportedFailure"

    def test_success_payload_is_not_a_failure(self):
        assert ut._returned_failure({"success": True, "data": []}) is None

    @pytest.mark.parametrize("payload", [None, "text", [], {}, {"no_success_key": 1}, _Result(None)])
    def test_non_failure_shapes_are_not_failures(self, payload):
        assert ut._returned_failure(payload) is None


class TestDistinctId:
    @pytest.fixture
    def _ctx(self):
        tokens = []
        yield tokens
        for t in reversed(tokens):
            reset_runtime_context(t)

    def test_authenticated_call_carries_the_user_id(self, _ctx):
        auth = RuntimeAuthState(scheme="Bearer", access_token="tok", claims={"id": "u-42"})
        _ctx.append(push_runtime_context(environment="web", auth=auth))
        assert ut._distinct_id() == "u-42"

    def test_token_hash_stands_in_when_identity_is_unresolved(self, _ctx):
        auth = RuntimeAuthState(scheme="Bearer", access_token="tok", claims={})
        _ctx.append(push_runtime_context(environment="web", auth=auth))
        got = ut._distinct_id()
        assert got.startswith("anon-") and len(got) == len("anon-") + 16
        # Same caller, same id — otherwise one user looks like many.
        assert got == ut._distinct_id()
        # The token itself must never appear in the event.
        assert "tok" not in got

    def test_distinct_ids_differ_per_token(self, _ctx):
        a = RuntimeAuthState(scheme="Bearer", access_token="tok-a", claims={})
        _ctx.append(push_runtime_context(environment="web", auth=a))
        first = ut._distinct_id()
        b = RuntimeAuthState(scheme="Bearer", access_token="tok-b", claims={})
        _ctx.append(push_runtime_context(environment="web", auth=b))
        assert ut._distinct_id() != first

    def test_no_auth_falls_back_to_anonymous(self, _ctx):
        _ctx.append(push_runtime_context(environment="desktop", auth=None))
        assert ut._distinct_id() == "anonymous"

    def test_never_raises_when_context_blows_up(self):
        with patch.object(ut, "hashlib", None):  # force an internal error
            with patch(
                "quilt_mcp.context.runtime_context.get_runtime_auth",
                side_effect=RuntimeError("boom"),
            ):
                assert ut._distinct_id() == "anonymous"


class TestPendingBound:
    @pytest.fixture(autouse=True)
    def _clean(self, monkeypatch):
        monkeypatch.setenv("MIXPANEL_PROJECT_TOKEN", "tok123")
        monkeypatch.delenv("QUILT_DISABLE_USAGE_METRICS", raising=False)
        mixpanel._inflight.clear()
        yield
        mixpanel._inflight.clear()

    def test_event_dropped_once_pending_hits_the_bound(self):
        class _Stalled:
            def done(self):
                return False

        # Simulate a stalled endpoint: the bound of un-finished sends is already met.
        mixpanel._inflight.extend(_Stalled() for _ in range(mixpanel._PENDING_MAX))
        submitted = []
        with patch.object(mixpanel, "_get_executor") as executor:
            executor.return_value.submit = lambda fn, event: submitted.append(event)
            mixpanel.track_tool_call(tool_name="x", execution_time=0.1, success=True)
        # Nothing new handed to the pool — its work queue is unbounded, so this is
        # the only thing keeping the backlog from growing for the process lifetime.
        assert submitted == []
        assert len(mixpanel._inflight) == mixpanel._PENDING_MAX

    def test_event_still_sent_below_the_bound(self):
        submitted = []
        with patch.object(mixpanel, "_get_executor") as executor:
            executor.return_value.submit = lambda fn, event: submitted.append(event)
            mixpanel.track_tool_call(tool_name="x", execution_time=0.1, success=True)
        assert len(submitted) == 1

    def test_pending_bound_is_below_the_deque_bound(self):
        # Otherwise the deque would silently evict futures the atexit drain needs.
        assert mixpanel._PENDING_MAX < mixpanel._INFLIGHT_MAX

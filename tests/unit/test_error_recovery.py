"""Behavioral tests for the error recovery toolkit.

These tests exercise the public APIs in ``quilt_mcp.tools.error_recovery``
to verify fallback handling, retry behaviour, and health check aggregation.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from quilt_mcp.tools import error_recovery


def test_batch_operation_marks_failure_when_fallback_returns_error():
    """Fallback results that report failure should propagate as failures."""

    def primary_operation(*_args, **_kwargs):
        return {"success": False, "error": "primary failed"}

    def fallback_operation(*_args, **_kwargs):
        return {"success": False, "error": "fallback also failed"}

    operations = [
        {
            "name": "critical_operation",
            "func": primary_operation,
            "fallback": fallback_operation,
        }
    ]

    result = error_recovery.batch_operation_with_recovery(operations)

    assert result["success"] is False
    operation_result = result["results"][0]
    assert operation_result["success"] is False
    # The fallback metadata should still be present inside the nested result
    assert operation_result.get("result") is not None
    assert operation_result["result"]["_fallback_used"] is True
    assert operation_result["error"] == "fallback also failed"


def test_with_retry_respects_retry_condition():
    """Retry decorator should stop when retry_condition rejects the error."""

    call_count = {"value": 0}

    @error_recovery.with_retry(
        max_attempts=3,
        delay=0.1,
        retry_condition=lambda exc: isinstance(exc, ValueError),
    )
    def sometimes_fails():
        call_count["value"] += 1
        if call_count["value"] == 1:
            raise KeyError("do not retry this")
        return {"success": True}

    with patch("time.sleep") as sleep_mock:
        with pytest.raises(KeyError):
            sometimes_fails()

    # KeyError is not retryable so no sleeps should have occurred
    sleep_mock.assert_not_called()
    assert call_count["value"] == 1


def test_health_check_collects_recommendations(monkeypatch: pytest.MonkeyPatch):
    """Health check should gather meaningful recovery recommendations."""

    monkeypatch.setattr(error_recovery, "_check_auth_status", lambda: {"status": "ok"})

    def failing_permissions():
        raise Exception("Access denied to bucket")

    monkeypatch.setattr(error_recovery, "_check_permissions_discovery", failing_permissions)
    monkeypatch.setattr(
        error_recovery,
        "_check_athena_connectivity",
        lambda: {"athena_available": True, "workgroups": 1},
    )
    monkeypatch.setattr(
        error_recovery,
        "_check_package_operations",
        lambda: {"package_ops_available": True},
    )

    result = error_recovery.health_check_with_recovery()

    assert result["success"] is True
    assert result["overall_health"] == "degraded"

    recommendations = set(result["recovery_recommendations"])
    assert any("Check IAM permissions" in rec for rec in recommendations)
    assert any("Access denied" in rec or "permissions" in rec.lower() for rec in recommendations)

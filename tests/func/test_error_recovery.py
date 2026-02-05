import pytest

from quilt_mcp.tools import error_recovery


def test_with_retry_retries_on_failure():
    calls = {"count": 0}

    @error_recovery.with_retry(max_attempts=3, delay=0.0)
    def flaky():
        calls["count"] += 1
        if calls["count"] < 3:
            return {"success": False, "error": "transient"}
        return {"success": True}

    result = flaky()
    assert result["success"] is True
    assert calls["count"] == 3


def test_batch_operation_with_recovery_uses_fallback():
    def primary():
        raise RuntimeError("boom")

    def fallback():
        return {"success": True, "fallback": True}

    results = error_recovery.batch_operation_with_recovery(
        [
            {"name": "primary", "func": primary, "fallback": fallback},
        ]
    )

    assert results["success"] is True
    assert results["results"][0].get("_fallback_used") is True


def test_health_check_with_recovery_degrades_on_failure(monkeypatch):
    monkeypatch.setattr(error_recovery, "_check_auth_status", lambda: {"success": False, "error": "auth failure"})
    monkeypatch.setattr(
        error_recovery,
        "_check_permissions_discovery",
        lambda: {"success": False, "error": "permissions failure"},
    )
    monkeypatch.setattr(
        error_recovery,
        "_check_athena_connectivity",
        lambda: {"success": False, "error": "athena timeout"},
    )
    monkeypatch.setattr(
        error_recovery,
        "_check_package_operations",
        lambda: {"success": False, "error": "package failure"},
    )

    result = error_recovery.health_check_with_recovery()
    assert result.overall_health in {"degraded", "unhealthy"}
    assert isinstance(result.recovery_recommendations, list)

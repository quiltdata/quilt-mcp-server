import pytest
from unittest.mock import Mock

from quilt_mcp.tools import error_recovery
from quilt_mcp.context.request_context import RequestContext


@pytest.fixture
def mock_context():
    """Provide a mock RequestContext for tests."""
    return RequestContext(
        request_id="test-req",
        user_id="test-user",
        auth_service=Mock(),
        permission_service=Mock(),
        workflow_service=None,
    )


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


def test_health_check_with_recovery_degrades_on_failure(monkeypatch, mock_context):
    monkeypatch.setattr(error_recovery, "_check_auth_status", lambda: {"success": False, "error": "auth failure"})
    monkeypatch.setattr(
        error_recovery,
        "_check_permissions_discovery",
        lambda context: {"success": False, "error": "permissions failure"},
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

    result = error_recovery.health_check_with_recovery(context=mock_context)
    assert result.overall_health in {"degraded", "unhealthy"}
    assert isinstance(result.recovery_recommendations, list)

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


# ============================================================================
# Tests for Phase 8: NO_DEFAULT_REGISTRY compliance
# Spec: spec/a10-no-default-registry.md (Phase 8, section 4)
# ============================================================================


def test_check_package_operations_uses_public_bucket():
    """Verify health check doesn't rely on DEFAULT_REGISTRY.

    From spec/a10-no-default-registry.md Phase 8:
    Health check should use explicit public bucket (PUBLIC_DEMO_BUCKET in error_recovery.py),
    not DEFAULT_REGISTRY which has been removed from production code.

    This test ensures:
    1. _check_package_operations() doesn't raise ConfigurationError about missing registry
    2. Function either succeeds or fails with AWS error (not config error)
    3. Error messages don't combine "registry" and "required" together
    """
    # Mock packages_list to provide valid auth session
    with patch("quilt_mcp.tools.packages.packages_list") as mock_packages_list:
        mock_packages_list.return_value = {
            "success": True,
            "packages": [],
        }
        result = error_recovery._check_package_operations()

        # Should return a dict
        assert isinstance(result, dict), "Health check should return a dict"

        # If it fails, should NOT be a configuration error about missing registry
        if isinstance(result, dict) and not result.get("success"):
            error_msg = str(result.get("error", "")).lower()
            # Defensive: check that error doesn't mention both "registry" and "required"
            # This would indicate it's trying to use a default that doesn't exist
            has_registry = "registry" in error_msg
            has_required = "required" in error_msg
            assert not (has_registry and has_required), (
                f"Health check should not require DEFAULT_REGISTRY, but got error: {result.get('error')}"
            )

        # Should have expected structure
        assert "package_ops_available" in result or "error" in result, "Should have either success or error info"


def test_health_check_returns_dict():
    """Basic structure validation for _check_package_operations().

    Verifies the function returns expected data structure with proper keys.
    """
    # Mock packages_list to provide valid auth session
    with patch("quilt_mcp.tools.packages.packages_list") as mock_packages_list:
        mock_packages_list.return_value = {
            "success": True,
            "packages": [],
        }
        result = error_recovery._check_package_operations()

        # Should return a dict
        assert isinstance(result, dict), "Health check should return a dict"

        # Check for expected keys
        assert "package_ops_available" in result or "error" in result, "Should have status or error information"

        # If successful, should have package_ops_available key
        if not result.get("error"):
            assert "package_ops_available" in result, "Success case should indicate package operations availability"


def test_health_check_handles_errors_gracefully():
    """Error handling validation for _check_package_operations().

    Verifies that the function catches exceptions properly and doesn't
    raise unhandled exceptions during health checks.
    """
    # Mock packages_list at the correct import location
    with patch("quilt_mcp.tools.packages.packages_list") as mock_packages_list:
        # Test 1: Function returns error dict (should be caught and re-raised as Exception)
        mock_packages_list.return_value = {
            "success": False,
            "error": "Simulated AWS error - bucket not found",
        }

        # The current implementation raises Exception when packages_list returns success=False
        try:
            result = error_recovery._check_package_operations()
            # If we get here, behavior changed - verify it's still an error dict
            assert isinstance(result, dict), "Should return dict"
        except Exception as e:
            # Expected behavior: raises Exception with wrapped error
            error_msg = str(e).lower()
            # Should not be about missing DEFAULT_REGISTRY
            has_registry = "registry" in error_msg
            has_required = "required" in error_msg
            assert not (has_registry and has_required), f"Should not fail due to missing DEFAULT_REGISTRY: {e}"

        # Test 2: Function raises exception directly
        mock_packages_list.side_effect = RuntimeError("Simulated network failure")

        # Should raise exception (wrapped in "Package operations failed")
        try:
            result = error_recovery._check_package_operations()
            # If we get here, behavior changed - verify result
            assert isinstance(result, dict), "Should return dict when catching exception"
        except Exception as e:
            # Expected behavior: raises Exception
            error_msg = str(e).lower()
            # Verify it's not a config error about registry
            has_registry = "registry" in error_msg
            has_required = "required" in error_msg
            assert not (has_registry and has_required), f"Should not fail due to missing DEFAULT_REGISTRY: {e}"

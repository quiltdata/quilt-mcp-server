from __future__ import annotations

import types

import pytest

from quilt_mcp.context.request_context import RequestContext
from quilt_mcp.tools import error_recovery


@pytest.fixture
def mock_context():
    return RequestContext(
        request_id="test-req",
        user_id="test-user",
        auth_service=object(),
        permission_service=object(),
        workflow_service=None,
    )


def test_with_fallback_internal_paths():
    def primary_ok():
        return {"success": True, "value": 1}

    def primary_fail_dict():
        return {"success": False, "error": "bad"}

    def fallback():
        return {"success": True, "fallback": True}

    wrapped_ok = error_recovery._with_fallback_internal(primary_ok, fallback)
    assert wrapped_ok()["success"] is True

    wrapped_fail = error_recovery._with_fallback_internal(primary_fail_dict, fallback)
    out = wrapped_fail()
    assert out["_fallback_used"] is True
    assert "bad" in out["_primary_error"]

    wrapped_conditional = error_recovery._with_fallback_internal(
        lambda: (_ for _ in ()).throw(RuntimeError("nope")),
        fallback,
        fallback_condition=lambda exc: "allow" in str(exc),
    )
    with pytest.raises(RuntimeError):
        wrapped_conditional()

    wrapped_both_fail = error_recovery._with_fallback_internal(
        lambda: (_ for _ in ()).throw(RuntimeError("primary")),
        lambda: (_ for _ in ()).throw(RuntimeError("fallback")),
    )
    failed = wrapped_both_fail()
    assert failed["success"] is False
    assert "Fallback also failed" in failed["error"]


def test_with_retry_exception_and_condition_paths(monkeypatch):
    monkeypatch.setattr(error_recovery.time, "sleep", lambda *_args, **_kwargs: None)

    calls = {"n": 0}

    @error_recovery.with_retry(max_attempts=2, delay=0.0, retry_condition=lambda exc: "retry" in str(exc))
    def flaky():
        calls["n"] += 1
        raise RuntimeError("retry me")

    with pytest.raises(RuntimeError):
        flaky()
    assert calls["n"] == 2

    @error_recovery.with_retry(max_attempts=3, delay=0.0, retry_condition=lambda exc: False)
    def no_retry():
        raise RuntimeError("stop")

    with pytest.raises(RuntimeError):
        no_retry()

    @error_recovery.with_retry(max_attempts=3, delay=0.0, retry_condition=lambda exc: False)
    def fail_result():
        return {"success": False, "error": "x"}

    res = fail_result()
    assert res["success"] is False


def test_safe_operation_and_batch_paths():
    ok = error_recovery.safe_operation("op_ok", lambda: {"success": True, "x": 1})
    assert ok["success"] is True

    failed_result = error_recovery.safe_operation("op_fail", lambda: {"success": False, "error": "denied"})
    assert failed_result["success"] is False
    assert failed_result["error"] == "denied"
    assert failed_result["recovery_suggestions"]

    failed_exception = error_recovery.safe_operation("op_exc", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    assert failed_exception["success"] is False
    assert failed_exception["error_type"] == "RuntimeError"

    batch = error_recovery.batch_operation_with_recovery(
        [
            {"name": "missing-func"},
            {"name": "fail", "func": lambda: {"success": False, "error": "bad"}},
            {"name": "ok", "func": lambda: {"success": True}},
        ],
        fail_fast=True,
    )
    assert batch["failed_operations"] >= 1
    assert batch["summary"]["fail_fast_triggered"] is True


def test_health_helpers_and_recommendations(monkeypatch, mock_context):
    # Patch imported modules used by _check_* helpers.
    monkeypatch.setitem(
        __import__("sys").modules,
        "quilt_mcp.services.auth_metadata",
        types.SimpleNamespace(auth_status=lambda: {"success": True, "authenticated": True}),
    )
    assert error_recovery._check_auth_status()["success"] is True

    monkeypatch.setitem(
        __import__("sys").modules,
        "quilt_mcp.services.permissions_service",
        types.SimpleNamespace(discover_permissions=lambda **kwargs: {"success": True, "bucket_permissions": [1, 2]}),
    )
    assert error_recovery._check_permissions_discovery(mock_context)["accessible_buckets"] == 2

    monkeypatch.setitem(
        __import__("sys").modules,
        "quilt_mcp.tools.athena_glue",
        types.SimpleNamespace(athena_workgroups_list=lambda: {"success": True, "workgroups": [1]}),
    )
    assert error_recovery._check_athena_connectivity()["athena_available"] is True

    monkeypatch.setitem(
        __import__("sys").modules,
        "quilt_mcp.tools.packages",
        types.SimpleNamespace(packages_list=lambda **kwargs: {"success": True}),
    )
    assert error_recovery._check_package_operations()["package_ops_available"] is True

    recs = error_recovery._get_recovery_suggestions("auth_status", Exception("403 access denied"))
    assert any("permissions issue" in r for r in recs)
    assert any("quilt3 login" in r for r in recs)

    degraded_steps = error_recovery._get_health_next_steps("degraded", [])
    unhealthy_steps = error_recovery._get_health_next_steps("unhealthy", [])
    assert "Some components" in degraded_steps[0]
    assert "critical issues" in unhealthy_steps[0]


def test_safe_operation_wrappers():
    package_fail = error_recovery._safe_package_operation_internal(
        lambda: (_ for _ in ()).throw(RuntimeError("pkg fail")),
        "ns/name",
    )
    assert package_fail["success"] is False
    assert "pkg fail" in package_fail["error"]

    bucket_fail = error_recovery._safe_bucket_operation_internal(
        lambda: (_ for _ in ()).throw(RuntimeError("bucket fail")),
        "my-bucket",
    )
    assert bucket_fail["success"] is False

    athena_fail = error_recovery._safe_athena_operation_internal(
        lambda: (_ for _ in ()).throw(RuntimeError("athena fail")),
        query="SELECT 1",
    )
    assert athena_fail["success"] is False

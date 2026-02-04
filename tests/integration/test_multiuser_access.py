"""Integration tests for multiuser catalog access patterns."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from queue import Queue

import pytest

from quilt_mcp.config import reset_mode_config, set_test_mode_config
from quilt_mcp.context.factory import RequestContextFactory
from quilt_mcp.exceptions import OperationNotSupportedError
from quilt_mcp.services.permissions_service import bucket_recommendations_get


class _StubAuth:
    def __init__(self, user_id: str):
        self._user_id = user_id
        self.auth_type = "jwt"

    def is_valid(self) -> bool:
        return True

    def get_user_identity(self):
        return {"user_id": self._user_id}

    def get_boto3_session(self):
        raise AssertionError("boto3 session should not be requested in multiuser tests")


class _StubPermissionService:
    def __init__(self, buckets: list[str]):
        self._buckets = buckets

    def bucket_recommendations_get(self, source_bucket=None, operation_type="package_creation", user_context=None):
        return {"buckets": list(self._buckets), "user_context": user_context}

    def discover_permissions(self, check_buckets=None, include_cross_account=False, force_refresh=False):
        return {"buckets": list(self._buckets)}

    def check_bucket_access(self, bucket: str, operations=None):
        return {"bucket": bucket, "allowed": True}


@pytest.mark.integration
def test_multiple_users_list_same_buckets(monkeypatch):
    set_test_mode_config(multiuser_mode=True)
    try:
        factory = RequestContextFactory(mode="multiuser")
        user_ids = iter(["alice", "bob"])
        buckets = ["shared-bucket"]

        def make_auth():
            return _StubAuth(next(user_ids))

        monkeypatch.setattr(factory, "_create_auth_service", make_auth)
        monkeypatch.setattr(
            factory,
            "_create_permission_service",
            lambda auth_service: _StubPermissionService(buckets),
        )
        monkeypatch.setattr(factory, "_create_workflow_service", lambda: None)

        context_a = factory.create_context()
        context_b = factory.create_context()

        resp_a = bucket_recommendations_get(context=context_a, user_context={"user_id": context_a.user_id})
        resp_b = bucket_recommendations_get(context=context_b, user_context={"user_id": context_b.user_id})

        assert resp_a["buckets"] == resp_b["buckets"] == buckets
        assert resp_a["user_context"]["user_id"] == "alice"
        assert resp_b["user_context"]["user_id"] == "bob"
    finally:
        reset_mode_config()


@pytest.mark.integration
def test_stateless_operations_only(monkeypatch):
    set_test_mode_config(multiuser_mode=True)
    try:
        factory = RequestContextFactory(mode="multiuser")
        monkeypatch.setattr(factory, "_create_auth_service", lambda: _StubAuth("alice"))
        monkeypatch.setattr(factory, "_create_permission_service", lambda auth_service: _StubPermissionService([]))
        monkeypatch.setattr(factory, "_create_workflow_service", lambda: None)

        context = factory.create_context()

        with pytest.raises(OperationNotSupportedError, match="Workflows are not available in multiuser mode"):
            context.create_workflow("workflow-1", "Example Workflow")
    finally:
        reset_mode_config()


@pytest.mark.integration
def test_concurrent_users_stateless(monkeypatch):
    set_test_mode_config(multiuser_mode=True)
    try:
        factory = RequestContextFactory(mode="multiuser")
        buckets = ["shared-bucket"]
        user_queue: Queue[str] = Queue()
        for user_id in ["user-1", "user-2", "user-3", "user-4"]:
            user_queue.put(user_id)

        def make_auth():
            return _StubAuth(user_queue.get_nowait())

        monkeypatch.setattr(factory, "_create_auth_service", make_auth)
        monkeypatch.setattr(
            factory,
            "_create_permission_service",
            lambda auth_service: _StubPermissionService(buckets),
        )
        monkeypatch.setattr(factory, "_create_workflow_service", lambda: None)

        def _create_context():
            return factory.create_context()

        with ThreadPoolExecutor(max_workers=4) as executor:
            contexts = list(executor.map(lambda _: _create_context(), range(4)))

        assert all(context.workflow_service is None for context in contexts)
        assert {context.user_id for context in contexts} == {"user-1", "user-2", "user-3", "user-4"}
    finally:
        reset_mode_config()

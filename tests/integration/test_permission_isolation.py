"""Integration tests for permission cache isolation."""

from __future__ import annotations

from quilt_mcp.services.permissions_service import PermissionDiscoveryService


class _StubSession:
    def __init__(self, label: str):
        self.label = label
        self.clients = {}

    def client(self, name: str):
        client = object()
        self.clients[name] = client
        return client


class _StubAuthService:
    def __init__(self, session):
        self._session = session

    def get_boto3_session(self):
        return self._session

    def is_valid(self):
        return True

    def get_user_identity(self):
        return {"user_id": f"user-{self._session.label}"}


def test_permission_cache_isolated_between_instances():
    service_a = PermissionDiscoveryService(_StubAuthService(_StubSession("a")))
    service_b = PermissionDiscoveryService(_StubAuthService(_StubSession("b")))

    service_a._discovery.permission_cache["bucket-a"] = "value-a"
    service_b._discovery.permission_cache["bucket-b"] = "value-b"

    assert "bucket-a" in service_a._discovery.permission_cache
    assert "bucket-a" not in service_b._discovery.permission_cache
    assert "bucket-b" in service_b._discovery.permission_cache


def test_permission_service_uses_correct_session_clients():
    session_a = _StubSession("a")
    session_b = _StubSession("b")
    service_a = PermissionDiscoveryService(_StubAuthService(session_a))
    service_b = PermissionDiscoveryService(_StubAuthService(session_b))

    assert service_a._discovery.s3_client is session_a.clients["s3"]
    assert service_b._discovery.s3_client is session_b.clients["s3"]

"""Unit tests for PermissionDiscoveryService."""

from __future__ import annotations

import time

from botocore.exceptions import ClientError

from quilt_mcp.services.permission_discovery import AWSPermissionDiscovery
from quilt_mcp.services.permissions_service import PermissionDiscoveryService


class _StubSession:
    def __init__(self):
        self.clients = {}

    def client(self, name: str):
        client = object()
        self.clients[name] = client
        return client


class _StubS3Client:
    def list_objects_v2(self, **kwargs):
        return {}

    def get_bucket_location(self, **kwargs):
        return {"LocationConstraint": "us-east-1"}

    def head_object(self, **kwargs):
        raise ClientError({"Error": {"Code": "NotFound"}}, "HeadObject")

    def get_bucket_acl(self, **kwargs):
        return {}


class _StubSessionWithS3:
    def __init__(self):
        self.s3 = _StubS3Client()

    def client(self, name: str):
        if name == "s3":
            return self.s3
        return object()


class _StubAuthService:
    def __init__(self, session):
        self._session = session

    def get_boto3_session(self):
        return self._session

    def is_valid(self):
        return True

    def get_user_identity(self):
        return {"user_id": "user-1"}


def test_permission_service_initializes_clients_from_auth_session():
    session = _StubSession()
    auth_service = _StubAuthService(session)

    service = PermissionDiscoveryService(auth_service)

    discovery = service._discovery
    assert discovery.sts_client is session.clients["sts"]
    assert discovery.iam_client is session.clients["iam"]
    assert discovery.s3_client is session.clients["s3"]


def test_permission_service_cache_is_instance_scoped():
    service_a = PermissionDiscoveryService(_StubAuthService(_StubSession()))
    service_b = PermissionDiscoveryService(_StubAuthService(_StubSession()))

    assert service_a._discovery.permission_cache is not service_b._discovery.permission_cache
    assert service_a._discovery.identity_cache is not service_b._discovery.identity_cache
    assert service_a._discovery.bucket_list_cache is not service_b._discovery.bucket_list_cache


def test_permission_cache_ttl_is_instance_specific():
    service_a = PermissionDiscoveryService(_StubAuthService(_StubSession()), cache_ttl=1)
    service_b = PermissionDiscoveryService(_StubAuthService(_StubSession()), cache_ttl=10)

    assert service_a._discovery.permission_cache.ttl == 1
    assert service_b._discovery.permission_cache.ttl == 10


def test_permission_cache_invalidation_is_isolated():
    service_a = PermissionDiscoveryService(_StubAuthService(_StubSession()))
    service_b = PermissionDiscoveryService(_StubAuthService(_StubSession()))

    service_a._discovery.permission_cache["bucket-a"] = "value-a"
    service_b._discovery.permission_cache["bucket-b"] = "value-b"

    service_a._discovery.permission_cache.clear()

    assert "bucket-a" not in service_a._discovery.permission_cache
    assert "bucket-b" in service_b._discovery.permission_cache


def test_permission_service_singleton_accessor_removed():
    import quilt_mcp.services.permissions_service as permissions_service

    assert not hasattr(permissions_service, "get_permission_discovery")


def test_permission_wrappers_use_passed_service():
    from quilt_mcp.services.permissions_service import (
        bucket_recommendations_get,
        check_bucket_access,
        discover_permissions,
    )

    class _StubService:
        def __init__(self):
            self.calls = []

        def discover_permissions(self, **kwargs):
            self.calls.append(("discover_permissions", kwargs))
            return {"success": True}

        def check_bucket_access(self, **kwargs):
            self.calls.append(("check_bucket_access", kwargs))
            return {"success": True}

        def bucket_recommendations_get(self, **kwargs):
            self.calls.append(("bucket_recommendations_get", kwargs))
            return {"success": True}

    service = _StubService()

    discover_permissions(permission_service=service)
    check_bucket_access("bucket", permission_service=service)
    bucket_recommendations_get(permission_service=service)

    call_names = [call[0] for call in service.calls]
    assert call_names == [
        "discover_permissions",
        "check_bucket_access",
        "bucket_recommendations_get",
    ]


def test_permission_cache_key_generation():
    discovery = AWSPermissionDiscovery(session=_StubSessionWithS3())
    discovery.discover_bucket_permissions("example-bucket")

    assert "bucket_permissions_example-bucket" in discovery.permission_cache


def test_permission_cache_expiration():
    discovery = AWSPermissionDiscovery(cache_ttl=1, session=_StubSessionWithS3())
    discovery.permission_cache["key"] = "value"

    time.sleep(1.1)
    assert "key" not in discovery.permission_cache

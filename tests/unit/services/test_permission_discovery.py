from __future__ import annotations

from datetime import datetime, timezone

import pytest
from botocore.exceptions import ClientError
from cachetools import TTLCache

from quilt_mcp.services.permission_discovery import (
    AWSPermissionDiscovery,
    BucketInfo,
    PermissionLevel,
    UserIdentity,
)


def _client_error(code: str, operation: str = "Op") -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": code}}, operation)


class _StubSession:
    def __init__(self, clients: dict[str, object]):
        self._clients = clients

    def client(self, name: str):
        if name not in self._clients:
            raise RuntimeError(f"missing client {name}")
        return self._clients[name]


class _StubSTS:
    def __init__(self, response):
        self._response = response

    def get_caller_identity(self):
        return self._response


class _StubS3ListOnly:
    def __init__(self, buckets):
        self._buckets = buckets

    def list_buckets(self):
        return {"Buckets": [{"Name": b} for b in self._buckets]}


class _StubS3Permission:
    def __init__(
        self,
        *,
        list_error: ClientError | None = None,
        location_error: ClientError | None = None,
        head_error: ClientError | None = None,
        acl_error: ClientError | None = None,
    ):
        self.list_error = list_error
        self.location_error = location_error
        self.head_error = head_error
        self.acl_error = acl_error

    def list_buckets(self):
        if self.list_error:
            raise self.list_error
        return {"Buckets": []}

    def list_objects_v2(self, **_kwargs):
        if self.list_error:
            raise self.list_error
        return {}

    def get_bucket_location(self, **_kwargs):
        if self.location_error:
            raise self.location_error
        return {"LocationConstraint": "us-east-1"}

    def head_object(self, **_kwargs):
        if self.head_error:
            raise self.head_error
        return {}

    def get_bucket_acl(self, **_kwargs):
        if self.acl_error:
            raise self.acl_error
        return {}


def _fresh_discovery() -> AWSPermissionDiscovery:
    d = AWSPermissionDiscovery.__new__(AWSPermissionDiscovery)
    d.cache_ttl = 3600
    d.permission_cache = TTLCache(maxsize=1000, ttl=3600)
    d.identity_cache = TTLCache(maxsize=10, ttl=3600)
    d.bucket_list_cache = TTLCache(maxsize=10, ttl=1800)
    return d


def test_initialize_aws_clients_uses_session_and_optional_failures(monkeypatch):
    session_clients = {
        "sts": object(),
        "iam": object(),
        "s3": object(),
        # purposely omit glue/athena
    }
    discovery = _fresh_discovery()
    discovery._initialize_aws_clients(_StubSession(session_clients))

    assert discovery.sts_client is session_clients["sts"]
    assert discovery.iam_client is session_clients["iam"]
    assert discovery.s3_client is session_clients["s3"]
    assert discovery.glue_client is None
    assert discovery.athena_client is None

    # default boto3 path
    created = {}
    monkeypatch.setattr("quilt_mcp.services.permission_discovery.boto3.client", lambda name: created.setdefault(name, object()))
    discovery2 = _fresh_discovery()
    discovery2._initialize_aws_clients(None)
    assert discovery2.sts_client is created["sts"]
    assert discovery2.iam_client is created["iam"]
    assert discovery2.s3_client is created["s3"]


def test_discover_user_identity_parses_types_and_uses_cache():
    discovery = _fresh_discovery()
    discovery.sts_client = _StubSTS(
        {"UserId": "u", "Arn": "arn:aws:iam::123456789012:user/alice", "Account": "123456789012"}
    )
    identity = discovery.discover_user_identity()
    assert identity.user_type == "user"
    assert identity.user_name == "alice"

    # cache hit should not require sts mutation
    discovery.sts_client = _StubSTS({"UserId": "x", "Arn": "arn:aws:iam::1:role/ignored", "Account": "1"})
    cached = discovery.discover_user_identity()
    assert cached == identity

    # role branch
    discovery2 = _fresh_discovery()
    discovery2.sts_client = _StubSTS(
        {"UserId": "r", "Arn": "arn:aws:iam::123456789012:role/my-role/session", "Account": "123456789012"}
    )
    assert discovery2.discover_user_identity().user_type == "role"

    # federated branch
    discovery3 = _fresh_discovery()
    discovery3.sts_client = _StubSTS(
        {"UserId": "f", "Arn": "arn:aws:sts::123456789012:federated-user/bob", "Account": "123456789012"}
    )
    assert discovery3.discover_user_identity().user_type == "federated"


def test_discover_bucket_permissions_access_denied_short_circuit():
    discovery = _fresh_discovery()
    discovery.s3_client = _StubS3Permission(list_error=_client_error("AccessDenied"))
    result = discovery.discover_bucket_permissions("secret")
    assert result.permission_level == PermissionLevel.NO_ACCESS
    assert result.can_list is False


def test_discover_bucket_permissions_full_access_path():
    discovery = _fresh_discovery()
    discovery.s3_client = _StubS3Permission(
        location_error=_client_error("AccessDenied"),  # forces unknown region path
        head_error=_client_error("NotFound"),
        acl_error=_client_error("AccessDenied"),
    )

    result = discovery.discover_bucket_permissions("public")
    assert result.permission_level == PermissionLevel.FULL_ACCESS
    assert result.can_list is True
    assert result.can_read is True
    assert result.can_write is True


def test_discover_accessible_buckets_with_owned_and_error_bucket(monkeypatch):
    discovery = _fresh_discovery()
    discovery.s3_client = _StubS3ListOnly(["ok-bucket", "bad-bucket"])

    def _discover(name: str):
        if name == "bad-bucket":
            raise RuntimeError("boom")
        return BucketInfo(name, "us-east-1", PermissionLevel.READ_ONLY, True, False, True, datetime.now(timezone.utc), None)

    monkeypatch.setattr(discovery, "discover_bucket_permissions", _discover)
    result = discovery.discover_accessible_buckets()
    assert len(result) == 2
    assert any(b.name == "bad-bucket" and b.permission_level == PermissionLevel.NO_ACCESS for b in result)


def test_discover_accessible_buckets_fallback_env_candidates(monkeypatch):
    discovery = _fresh_discovery()

    class _DeniedS3:
        def list_buckets(self):
            raise _client_error("AccessDenied")

    discovery.s3_client = _DeniedS3()
    monkeypatch.setenv("QUILT_ENABLE_FALLBACK_DISCOVERY", "1")
    monkeypatch.setenv("QUILT_KNOWN_BUCKETS", "s3://env-bucket/a,plain-bucket")
    monkeypatch.setattr(discovery, "_discover_buckets_via_graphql", lambda: set())
    monkeypatch.setattr(discovery, "_discover_buckets_via_glue", lambda: [])
    monkeypatch.setattr(discovery, "_discover_buckets_via_athena", lambda: [])
    monkeypatch.setattr(
        discovery,
        "discover_bucket_permissions",
        lambda n: BucketInfo(n, "us-east-1", PermissionLevel.LIST_ONLY, False, False, True, datetime.now(timezone.utc), None),
    )

    result = discovery.discover_accessible_buckets()
    names = {b.name for b in result}
    assert "env-bucket" in names
    assert "plain-bucket" in names


def test_statement_applies_to_user_variants():
    discovery = _fresh_discovery()
    identity = UserIdentity("id", "arn:aws:iam::123:user/alice", "123", "user", "alice")

    assert discovery._statement_applies_to_user({"AWS": "*"}, identity) is True
    assert discovery._statement_applies_to_user({"AWS": ["arn:aws:iam::123:user/alice"]}, identity) is True
    assert discovery._statement_applies_to_user({"AWS": ["arn:aws:iam::123:role/any"]}, identity) is True
    assert discovery._statement_applies_to_user({"AWS": ["arn:aws:iam::999:user/other"]}, identity) is False
    assert discovery._statement_applies_to_user("not-a-dict", identity) is False


def test_small_helpers_and_cache_stats():
    discovery = _fresh_discovery()
    no_access = discovery._build_no_access_bucket("b", RuntimeError("x"))
    assert no_access.name == "b"
    assert no_access.permission_level == PermissionLevel.NO_ACCESS

    assert discovery._extract_bucket_from_s3_uri("s3://bucket/key") == "bucket"
    assert discovery._extract_bucket_from_s3_uri("plain") == "plain"

    stats = discovery.get_cache_stats()
    assert stats["cache_ttl"] == 3600

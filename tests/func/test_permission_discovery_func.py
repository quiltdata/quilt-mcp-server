"""Func-suite coverage for permission discovery engine internals."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from botocore.exceptions import ClientError
from cachetools import TTLCache

from quilt_mcp.services.permission_discovery import AWSPermissionDiscovery, BucketInfo, PermissionLevel, UserIdentity


def _client_error(code: str, operation: str = "Op") -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": code}}, operation)


def _fresh_discovery() -> AWSPermissionDiscovery:
    d = AWSPermissionDiscovery.__new__(AWSPermissionDiscovery)
    d.cache_ttl = 3600
    d.permission_cache = TTLCache(maxsize=1000, ttl=3600)
    d.identity_cache = TTLCache(maxsize=10, ttl=3600)
    d.bucket_list_cache = TTLCache(maxsize=10, ttl=1800)
    return d


def test_func_bucket_permission_and_operations_paths(monkeypatch):
    d = _fresh_discovery()

    class S3:
        def list_objects_v2(self, **_kwargs):
            return {}

        def get_bucket_location(self, **_kwargs):
            return {"LocationConstraint": "us-west-2"}

        def head_object(self, **_kwargs):
            raise _client_error("NotFound", "HeadObject")

        def get_bucket_acl(self, **_kwargs):
            raise _client_error("AccessDenied", "GetBucketAcl")

        def get_bucket_policy(self, **_kwargs):
            return {"Policy": '{"Statement":[{"Effect":"Allow","Principal":{"AWS":"*"},"Action":"s3:*"}]}'}

    d.s3_client = S3()
    d.discover_user_identity = lambda: UserIdentity("id", "arn:aws:iam::123:user/a", "123", "user", "a")
    info = d.discover_bucket_permissions("bucket-a")
    assert info.permission_level == PermissionLevel.FULL_ACCESS

    ops = d.test_bucket_operations("bucket-a", ["list", "read", "write", "bogus"])
    assert ops["list"] is True and ops["read"] is True and ops["write"] is True and ops["bogus"] is False


def test_func_discover_accessible_with_fallback_sources(monkeypatch):
    d = _fresh_discovery()

    class DeniedS3:
        def list_buckets(self):
            raise _client_error("AccessDenied", "ListBuckets")

    d.s3_client = DeniedS3()
    monkeypatch.setenv("QUILT_ENABLE_FALLBACK_DISCOVERY", "1")
    monkeypatch.setenv("QUILT_KNOWN_BUCKETS", "s3://env-bucket/x,plain-bucket")
    monkeypatch.setattr(d, "_discover_buckets_via_graphql", lambda: {"graphql-bucket"})
    monkeypatch.setattr(d, "_discover_buckets_via_glue", lambda: ["glue-bucket"])
    monkeypatch.setattr(d, "_discover_buckets_via_athena", lambda: ["athena-bucket"])
    monkeypatch.setattr(
        d,
        "discover_bucket_permissions",
        lambda n: BucketInfo(n, "us-east-1", PermissionLevel.LIST_ONLY, False, False, True, datetime.now(timezone.utc), None),
    )

    result = d.discover_accessible_buckets()
    names = {b.name for b in result}
    assert {"graphql-bucket", "env-bucket", "plain-bucket"} <= names


def test_func_glue_athena_graphql_helpers(monkeypatch):
    d = _fresh_discovery()

    class GluePaginator:
        def __init__(self, pages):
            self.pages = pages

        def paginate(self, **_kwargs):
            return self.pages

    class Glue:
        def get_paginator(self, name):
            if name == "get_databases":
                return GluePaginator([{"DatabaseList": [{"Name": "db1"}]}])
            return GluePaginator([{"TableList": [{"StorageDescriptor": {"Location": "s3://glue-bucket/path"}}]}])

    d.glue_client = Glue()
    assert "glue-bucket" in d._discover_buckets_via_glue()

    class AthenaPaginator:
        def paginate(self):
            return [{"WorkGroups": [{"Name": "wg"}]}]

    class Athena:
        def get_paginator(self, _name):
            return AthenaPaginator()

        def get_work_group(self, **_kwargs):
            return {"WorkGroup": {"Configuration": {"ResultConfiguration": {"OutputLocation": "s3://athena-bucket/out"}}}}

    d.athena_client = Athena()
    assert "athena-bucket" in d._discover_buckets_via_athena()

    monkeypatch.setattr("quilt_mcp.services.permission_discovery.quilt3.logged_in", lambda: None, raising=False)
    assert d._discover_buckets_via_graphql() == set()


def test_func_write_access_fallback_and_indicators():
    d = _fresh_discovery()
    d.discover_user_identity = lambda: UserIdentity("id", "arn:aws:iam::123:user/a", "123", "user", "a")

    class STS:
        def simulate_principal_policy(self, **_kwargs):
            return {"EvaluationResults": [{"EvalDecision": "allowed"}]}

    d.sts_client = STS()
    assert d._check_iam_write_permissions("bucket-a") is True

    class S3Fallback:
        def list_buckets(self):
            return {"Buckets": [{"Name": "bucket-a"}]}

        def get_bucket_policy(self, **_kwargs):
            raise _client_error("NoSuchBucketPolicy", "GetBucketPolicy")

        def get_bucket_versioning(self, **_kwargs):
            raise _client_error("AccessDenied", "GetBucketVersioning")

        def get_bucket_notification_configuration(self, **_kwargs):
            return {}

        def list_objects_v2(self, **_kwargs):
            return {}

    d.s3_client = S3Fallback()
    assert d._determine_write_access_fallback("bucket-a") is True

    assert d._statement_applies_to_user({"AWS": "*"}, d.discover_user_identity()) is True

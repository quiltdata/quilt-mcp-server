"""Unit tests for Platform_Backend bucket operations."""

from __future__ import annotations

import pytest

from quilt_mcp.ops.exceptions import BackendError, NotFoundError, ValidationError
from quilt_mcp.context.runtime_context import (
    RuntimeAuthState,
    get_runtime_environment,
    push_runtime_context,
    reset_runtime_context,
)


def _push_jwt_context(claims=None):
    auth_state = RuntimeAuthState(
        scheme="Bearer",
        access_token="test-token",
        claims=claims
        or {
            "id": "user-1",
            "uuid": "uuid-1",
            "exp": 9999999999,
        },
    )
    return push_runtime_context(environment=get_runtime_environment(), auth=auth_state)


def _make_backend(monkeypatch, claims=None):
    monkeypatch.setenv("QUILT_CATALOG_URL", "https://example.quiltdata.com")
    monkeypatch.setenv("QUILT_REGISTRY_URL", "https://registry.example.com")
    monkeypatch.setenv("QUILT_GRAPHQL_ENDPOINT", "https://registry.example.com/graphql")
    token = _push_jwt_context(claims)
    try:
        from quilt_mcp.backends.platform_backend import Platform_Backend

        return Platform_Backend()
    finally:
        reset_runtime_context(token)


# ---------------------------------------------------------------------
# Bucket Listing
# ---------------------------------------------------------------------


def test_list_buckets_basic(monkeypatch):
    """List buckets from GraphQL."""
    backend = _make_backend(monkeypatch)
    backend.execute_graphql_query = lambda *args, **kwargs: {
        "data": {
            "bucketConfigs": [
                {"name": "bucket-alpha"},
                {"name": "bucket-beta"},
                {"name": "bucket-gamma"},
            ]
        }
    }

    buckets = backend.list_buckets()
    assert len(buckets) == 3
    assert [b.name for b in buckets] == ["bucket-alpha", "bucket-beta", "bucket-gamma"]


def test_list_buckets_transforms_to_bucket_info(monkeypatch):
    """Verify Bucket_Info construction."""
    backend = _make_backend(monkeypatch)
    backend.execute_graphql_query = lambda *args, **kwargs: {"data": {"bucketConfigs": [{"name": "test-bucket"}]}}

    buckets = backend.list_buckets()
    assert len(buckets) == 1

    bucket = buckets[0]
    assert bucket.name == "test-bucket"
    # Platform backend sets these to default values
    assert bucket.region == "unknown"
    assert bucket.access_level == "unknown"
    assert bucket.created_date is None


def test_list_buckets_empty_result(monkeypatch):
    """Handle no buckets configured."""
    backend = _make_backend(monkeypatch)
    backend.execute_graphql_query = lambda *args, **kwargs: {"data": {"bucketConfigs": []}}

    buckets = backend.list_buckets()
    assert buckets == []


def test_list_buckets_includes_name(monkeypatch):
    """Verify name extraction from GraphQL response."""
    backend = _make_backend(monkeypatch)
    backend.execute_graphql_query = lambda *args, **kwargs: {
        "data": {
            "bucketConfigs": [
                {"name": "my-data-bucket"},
                {"name": "my-analytics-bucket"},
            ]
        }
    }

    buckets = backend.list_buckets()
    names = [b.name for b in buckets]
    assert "my-data-bucket" in names
    assert "my-analytics-bucket" in names


# ---------------------------------------------------------------------
# Catalog Configuration
# ---------------------------------------------------------------------


def test_configure_catalog_sets_catalog_url(monkeypatch):
    """Reject dynamic catalog configuration."""
    from quilt_mcp.backends.platform_backend import Platform_Backend

    monkeypatch.setenv("QUILT_CATALOG_URL", "https://example.quiltdata.com")
    monkeypatch.setenv("QUILT_REGISTRY_URL", "https://registry.example.com")
    monkeypatch.setenv("QUILT_GRAPHQL_ENDPOINT", "https://registry.example.com/graphql")
    token = _push_jwt_context({"id": "user-1", "uuid": "uuid-1", "exp": 9999999999})
    try:
        backend = Platform_Backend()
        with pytest.raises(ValidationError):
            backend.configure_catalog("https://my-catalog.quiltdata.com")
    finally:
        reset_runtime_context(token)


def test_configure_catalog_derives_registry_url(monkeypatch):
    """Reject catalog to registry derivation."""
    from quilt_mcp.backends.platform_backend import Platform_Backend

    monkeypatch.setenv("QUILT_CATALOG_URL", "https://example.quiltdata.com")
    monkeypatch.setenv("QUILT_REGISTRY_URL", "https://registry.example.com")
    monkeypatch.setenv("QUILT_GRAPHQL_ENDPOINT", "https://registry.example.com/graphql")
    token = _push_jwt_context({"id": "user-1", "uuid": "uuid-1", "exp": 9999999999})
    try:
        backend = Platform_Backend()
        with pytest.raises(ValidationError):
            backend.configure_catalog("https://example.quiltdata.com")
    finally:
        reset_runtime_context(token)


def test_configure_catalog_handles_custom_domains(monkeypatch):
    """Reject custom domain configuration."""
    from quilt_mcp.backends.platform_backend import Platform_Backend

    monkeypatch.setenv("QUILT_CATALOG_URL", "https://example.quiltdata.com")
    monkeypatch.setenv("QUILT_REGISTRY_URL", "https://registry.example.com")
    monkeypatch.setenv("QUILT_GRAPHQL_ENDPOINT", "https://registry.example.com/graphql")
    token = _push_jwt_context({"id": "user-1", "uuid": "uuid-1", "exp": 9999999999})
    try:
        backend = Platform_Backend()
        with pytest.raises(ValidationError):
            backend.configure_catalog("https://nightly.quilttest.com")
    finally:
        reset_runtime_context(token)


def test_configure_catalog_preserves_existing_registry(monkeypatch):
    """Reject attempts to override static registry."""
    from quilt_mcp.backends.platform_backend import Platform_Backend

    monkeypatch.setenv("QUILT_CATALOG_URL", "https://example.quiltdata.com")
    monkeypatch.setenv("QUILT_REGISTRY_URL", "https://registry.example.com")
    monkeypatch.setenv("QUILT_GRAPHQL_ENDPOINT", "https://registry.example.com/graphql")
    token = _push_jwt_context({"id": "user-1", "uuid": "uuid-1", "exp": 9999999999})
    try:
        backend = Platform_Backend()
        with pytest.raises(ValidationError):
            backend.configure_catalog("https://new-catalog.com")
    finally:
        reset_runtime_context(token)


# ---------------------------------------------------------------------
# Catalog Config Retrieval
# ---------------------------------------------------------------------


def test_get_catalog_config_success(monkeypatch):
    """Fetch config.json from catalog."""
    backend = _make_backend(monkeypatch)

    class DummyResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "region": "us-west-2",
                "apiGatewayEndpoint": "https://api.example.com",
                "registryUrl": "https://registry.example.com",
                "analyticsBucket": "quilt-prod-analyticsbucket-abc123",
            }

    backend._session.get = lambda *args, **kwargs: DummyResponse()

    config = backend.get_catalog_config("https://example.quiltdata.com")
    assert config.region == "us-west-2"
    assert config.registry_url == "https://registry.example.com"
    assert config.api_gateway_endpoint == "https://api.example.com"


def test_get_catalog_config_parses_stack_prefix(monkeypatch):
    """Extract stack prefix from analyticsBucket."""
    backend = _make_backend(monkeypatch)

    class DummyResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "region": "us-east-1",
                "apiGatewayEndpoint": "https://api.example.com",
                "registryUrl": "https://registry.example.com",
                "analyticsBucket": "quilt-demo-analyticsbucket-xyz789",
            }

    backend._session.get = lambda *args, **kwargs: DummyResponse()

    config = backend.get_catalog_config("https://demo.quiltdata.com")
    assert config.stack_prefix == "quilt-demo"
    assert config.analytics_bucket == "quilt-demo-analyticsbucket-xyz789"
    assert config.tabulator_data_catalog == "quilt-quilt-demo-tabulator"


def test_get_catalog_config_handles_missing_fields(monkeypatch):
    """Handle optional fields."""
    backend = _make_backend(monkeypatch)

    class DummyResponse:
        def raise_for_status(self):
            pass

        def json(self):
            # Missing required field 'region'
            return {
                "apiGatewayEndpoint": "https://api.example.com",
                "registryUrl": "https://registry.example.com",
                "analyticsBucket": "quilt-test-analyticsbucket-123",
            }

    backend._session.get = lambda *args, **kwargs: DummyResponse()

    with pytest.raises(BackendError, match="Missing required field 'region'"):
        backend.get_catalog_config("https://test.quiltdata.com")

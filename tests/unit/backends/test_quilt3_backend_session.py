from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from quilt_mcp.backends.quilt3_backend_session import Quilt3_Backend_Session
from quilt_mcp.ops.exceptions import AuthenticationError, BackendError, ValidationError


class _Backend(Quilt3_Backend_Session):
    def __init__(self, quilt3, requests, boto3):
        self.quilt3 = quilt3
        self.requests = requests
        self.boto3 = boto3


def _make_backend():
    session_obj = SimpleNamespace(
        get_session=MagicMock(),
        get_registry_url=MagicMock(return_value="https://registry.example.com"),
        create_botocore_session=MagicMock(return_value=object()),
    )
    quilt3 = SimpleNamespace(
        logged_in=MagicMock(return_value="https://example.quiltdata.com"),
        session=session_obj,
        config=MagicMock(),
    )
    boto3 = SimpleNamespace(client=MagicMock(return_value={"client": "default"}), Session=MagicMock())
    return _Backend(quilt3=quilt3, requests=SimpleNamespace(), boto3=boto3)


def test_backend_get_auth_status_and_registry_url(monkeypatch):
    backend = _make_backend()
    monkeypatch.setattr("quilt_mcp.utils.common.get_dns_name_from_url", lambda _u: "example.quiltdata.com")

    status = backend._backend_get_auth_status()
    assert status.is_authenticated is True
    assert status.catalog_name == "example.quiltdata.com"
    assert status.registry_url is None

    # logged_in failure should gracefully return unauthenticated instead of raising.
    backend.quilt3.logged_in.side_effect = RuntimeError("bad")
    status2 = backend._backend_get_auth_status()
    assert status2.is_authenticated is False
    assert status2.catalog_name is None

    assert backend.get_registry_url() == "https://registry.example.com"
    delattr(backend.quilt3.session, "get_registry_url")
    assert backend.get_registry_url() is None


def test_get_and_transform_catalog_config(monkeypatch):
    backend = _make_backend()
    response = SimpleNamespace(
        raise_for_status=lambda: None,
        json=lambda: {
            "region": "us-east-1",
            "apiGatewayEndpoint": "https://api.example.com",
            "registryUrl": "https://registry.example.com",
            "analyticsBucket": "quilt-staging-analyticsbucket-abc",
        },
    )
    session = SimpleNamespace(get=lambda *args, **kwargs: response)
    backend.quilt3.session.get_session.return_value = session

    monkeypatch.setattr("quilt_mcp.utils.common.normalize_url", lambda u, **kwargs: u.rstrip("/"))
    config = backend.get_catalog_config("https://example.quiltdata.com/")
    assert config.region == "us-east-1"
    assert config.stack_prefix == "quilt-staging"
    assert config.tabulator_data_catalog == "quilt-quilt-staging-tabulator"

    with pytest.raises(ValidationError):
        backend.get_catalog_config("")

    backend.quilt3.session.get_session.return_value = None
    with pytest.raises(AuthenticationError):
        backend.get_catalog_config("https://example.quiltdata.com")

    # Missing required fields in transform should raise BackendError.
    with pytest.raises(BackendError):
        backend._transform_catalog_config({"region": "x"})


def test_configure_catalog_and_graphql_endpoint(monkeypatch):
    backend = _make_backend()
    backend.configure_catalog("https://example.quiltdata.com")
    backend.quilt3.config.assert_called_once()

    with pytest.raises(ValidationError):
        backend.configure_catalog("")

    monkeypatch.setattr(
        backend,
        "get_catalog_config",
        lambda _url: SimpleNamespace(registry_url="https://registry.example.com"),
    )
    monkeypatch.setattr("quilt_mcp.utils.common.graphql_endpoint", lambda url: f"{url}/graphql")
    gql = backend.get_graphql_endpoint()
    assert gql == "https://registry.example.com/graphql"

    backend.quilt3.logged_in.return_value = None
    with pytest.raises(BackendError):
        backend.get_graphql_endpoint()

    assert backend._get_graphql_endpoint("s3://my-registry") == "https://my-registry.quiltdata.com/graphql"
    with pytest.raises(ValidationError):
        backend._get_graphql_endpoint("https://not-s3")


def test_get_graphql_auth_headers():
    backend = _make_backend()
    backend.quilt3.session.get_session.return_value = SimpleNamespace(headers={"Authorization": "Bearer abc"})
    headers = backend.get_graphql_auth_headers()
    assert headers["Authorization"] == "Bearer abc"

    backend.quilt3.session.get_session.return_value = SimpleNamespace()
    assert backend.get_graphql_auth_headers() == {}


def test_get_aws_client_priority_runtime_and_quilt3(monkeypatch):
    backend = _make_backend()

    runtime_client = {"client": "runtime"}
    runtime_session = SimpleNamespace(client=lambda service_name, region_name=None: runtime_client)
    monkeypatch.setattr(
        "quilt_mcp.backends.quilt3_backend_session._runtime_boto3_session",
        lambda: runtime_session,
    )
    assert backend.get_aws_client("s3") == runtime_client

    # No runtime session: use quilt3 botocore session via boto3.Session
    monkeypatch.setattr("quilt_mcp.backends.quilt3_backend_session._runtime_boto3_session", lambda: None)
    boto3_client = {"client": "quilt3"}
    session_instance = SimpleNamespace(client=lambda service_name, region_name=None: boto3_client)
    backend.boto3.Session = MagicMock(return_value=session_instance)
    assert backend.get_aws_client("athena", region="us-west-2") == boto3_client


def test_get_aws_client_fallback_and_errors(monkeypatch, tmp_path):
    backend = _make_backend()
    monkeypatch.setattr("quilt_mcp.backends.quilt3_backend_session._runtime_boto3_session", lambda: None)

    # quilt3 not configured -> fallback to default boto3.client
    backend.quilt3.session.create_botocore_session.side_effect = RuntimeError("no quilt3")
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    default_client = {"client": "default"}
    backend.boto3.client = MagicMock(return_value=default_client)
    assert backend.get_aws_client("s3") == default_client

    # quilt3 configured but invalid session -> AuthenticationError
    config_dir = home / ".quilt"
    config_dir.mkdir()
    (config_dir / "config.yml").write_text("x", encoding="utf-8")
    with pytest.raises(AuthenticationError):
        backend.get_aws_client("s3")

    backend.boto3 = None
    with pytest.raises(BackendError):
        backend.get_aws_client("s3")

    # Alias method
    backend2 = _make_backend()
    monkeypatch.setattr("quilt_mcp.backends.quilt3_backend_session._runtime_boto3_session", lambda: None)
    backend2.quilt3.session.create_botocore_session.side_effect = RuntimeError("no quilt3")
    home2 = tmp_path / "home2"
    home2.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home2)
    assert backend2.get_boto3_client("s3") == {"client": "default"}

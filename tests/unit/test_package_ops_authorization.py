from __future__ import annotations

import pytest
import quilt3

from quilt_mcp.tools import packages
from quilt_mcp.tools.auth_helpers import AuthorizationContext
from quilt_mcp.models import PackageCreateError, CatalogUrlSuccess


class FakeQuiltService:
    def __init__(self) -> None:
        self.calls: dict[str, dict] = {}

    def create_package_revision(self, **kwargs):
        self.calls["create_package_revision"] = kwargs
        s3_uris = kwargs.get("s3_uris", [])
        # Convert S3 URIs to file entries (dict format expected by PackageCreateSuccess)
        files = [{"logical_path": uri.split("/")[-1], "source": uri} for uri in s3_uris]
        return {
            "top_hash": "deadbeef",
            "entries_added": len(s3_uris),
            "files": files,
        }


@pytest.fixture
def fake_service(monkeypatch):
    service = FakeQuiltService()
    monkeypatch.setattr(packages, "quilt_service", service)
    return service


def _authorized_context(auth_type: str = "jwt") -> AuthorizationContext:
    return AuthorizationContext(authorized=True, auth_type=auth_type, session=None, s3_client=None)


def test_package_create_attaches_auth_type(monkeypatch, fake_service):
    monkeypatch.setattr(packages, "check_package_authorization", lambda *_, **__: _authorized_context("jwt"))

    # Mock S3 client to avoid actual S3 calls
    class MockS3Client:
        def head_object(self, **kwargs):
            return {"ContentLength": 100}

    monkeypatch.setattr(packages, "get_s3_client", lambda: MockS3Client())

    # Mock catalog_url to avoid dependency on catalog module
    def mock_catalog_url(registry, package_name=None, path="", catalog_host=""):
        return CatalogUrlSuccess(
            catalog_url="https://example.com/b/test-bucket/packages/team/example",
            view_type="package",
            bucket="test-bucket",
            package_name="team/example",
        )

    # Import the catalog module within packages to mock it
    from quilt_mcp.tools import catalog

    monkeypatch.setattr(catalog, "catalog_url", mock_catalog_url)

    # Mock quilt3 package operations
    class MockPackage:
        def __init__(self):
            self.top_hash = "deadbeef"

        def set(self, key, s3_uri):
            pass

        def push(self, *args, **kwargs):
            pass

    monkeypatch.setattr(packages.quilt3, "Package", lambda: MockPackage())

    result = packages.package_create(
        package_name="team/example",
        s3_uris=["s3://bucket/object"],
        registry="s3://test-bucket",
    )

    # Verify the result is a success response with proper auth_type
    assert result.success is True
    assert result.auth_type == "jwt"
    assert result.package_name == "team/example"


def test_package_create_respects_strict_mode(monkeypatch, fake_service):
    strict_ctx = AuthorizationContext(
        authorized=False,
        auth_type=None,
        session=None,
        s3_client=None,
        error="JWT required",
        strict=True,
    )
    monkeypatch.setattr(packages, "check_package_authorization", lambda *_, **__: strict_ctx)

    result = packages.package_create(
        package_name="team/example",
        s3_uris=["s3://bucket/object"],
        registry="s3://test-bucket",
    )

    # The result should be an error since authorization failed
    assert isinstance(result, PackageCreateError)
    assert "Authorization failed" in result.error or "JWT required" in result.error

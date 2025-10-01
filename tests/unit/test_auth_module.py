"""Updated tests for auth module stateless behaviour."""

from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager

import pytest

from quilt_mcp.runtime import request_context
from quilt_mcp.tools import auth


@contextmanager
def runtime_token(token: str | None):
    with request_context(token, metadata={"session_id": "auth"} if token else None):
        yield


def test_extract_catalog_name_from_url():
    assert auth._extract_catalog_name_from_url("https://demo.quiltdata.com") == "demo.quiltdata.com"
    assert auth._extract_catalog_name_from_url("https://www.example.com") == "example.com"


def test_extract_bucket_from_registry():
    assert auth._extract_bucket_from_registry("s3://bucket") == "bucket"
    assert auth._extract_bucket_from_registry("bucket") == "bucket"


def test_catalog_url_defaults(monkeypatch):
    monkeypatch.delenv("QUILT_CATALOG_URL", raising=False)
    result = auth.catalog_url("s3://bucket", package_name="user/pkg", path="data.csv")
    assert result["status"] == "success"
    assert result["catalog_host"] == "demo.quiltdata.com"


def test_catalog_info_authenticated(monkeypatch):
    monkeypatch.setenv("QUILT_CATALOG_URL", "https://catalog.example.com")
    with runtime_token("token"):
        result = auth.catalog_info()
    assert result["catalog_name"] == "catalog.example.com"
    assert result["is_authenticated"] is True


def test_auth_status_authenticated(monkeypatch):
    monkeypatch.setenv("QUILT_CATALOG_URL", "https://catalog.example.com")
    with runtime_token("token"):
        result = auth.auth_status()
    assert result["status"] == "authenticated"
    assert result["catalog_url"] == "https://catalog.example.com"
    assert result["search_available"] is True


def test_auth_status_not_authenticated(monkeypatch):
    monkeypatch.delenv("QUILT_CATALOG_URL", raising=False)
    with runtime_token(None):
        result = auth.auth_status()
    assert result["status"] == "not_authenticated"
    assert result["search_available"] is False


def test_configure_catalog_sets_env(monkeypatch):
    monkeypatch.delenv("QUILT_CATALOG_URL", raising=False)
    result = auth.configure_catalog("https://example.com")
    assert result["status"] == "success"
    assert os.environ["QUILT_CATALOG_URL"] == "https://example.com"


def test_switch_catalog(monkeypatch):
    monkeypatch.delenv("QUILT_CATALOG_URL", raising=False)
    result = auth.switch_catalog("demo")
    assert result["status"] == "success"
    assert os.environ["QUILT_CATALOG_URL"] == "https://demo.quiltdata.com"


def test_filesystem_status_tmpdir(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setenv("QUILT_MCP_TMPDIR", tmpdir)
        result = auth.filesystem_status()
    assert result["temp_writable"] is True

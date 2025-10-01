"""Stateless tests for auth module behaviour."""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import patch

import pytest

from quilt_mcp.runtime import request_context
from quilt_mcp.tools import auth


@contextmanager
def runtime_token(token: str | None):
    with request_context(token, metadata={"session_id": "auth"} if token else None):
        yield


def test_catalog_url_uses_env(monkeypatch):
    monkeypatch.setenv("QUILT_CATALOG_URL", "https://catalog.example.com")
    result = auth.catalog_url("s3://bucket", package_name="user/pkg", path="data.csv")
    assert result["status"] == "success"
    assert "catalog.example.com" in result["catalog_url"]


def test_catalog_uri_without_env(monkeypatch):
    monkeypatch.delenv("QUILT_CATALOG_URL", raising=False)
    monkeypatch.delenv("QUILT_CATALOG_DOMAIN", raising=False)
    result = auth.catalog_uri("s3://bucket", package_name="user/pkg", path="data.csv")
    assert result["status"] == "success"
    assert result["quilt_plus_uri"].startswith("quilt+s3://bucket")


def test_catalog_info_uses_resolved_host(monkeypatch):
    monkeypatch.setenv("QUILT_CATALOG_URL", "https://catalog.example.com")
    result = auth.catalog_info()
    assert result["status"] == "success"
    assert result["catalog_name"] == "catalog.example.com"


def test_auth_status_not_authenticated(monkeypatch):
    monkeypatch.delenv("QUILT_CATALOG_URL", raising=False)
    with runtime_token(None):
        result = auth.auth_status()

    assert result["status"] == "not_authenticated"
    assert result["search_available"] is False


def test_auth_status_authenticated(monkeypatch):
    monkeypatch.setenv("QUILT_CATALOG_URL", "https://catalog.example.com")
    with runtime_token("token"):
        result = auth.auth_status()

    assert result["status"] == "authenticated"
    assert result["catalog_url"] == "https://catalog.example.com"
    assert result["search_available"] is True

"""Stateless tests for package_management metadata update using catalog clients."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Dict
from unittest.mock import Mock, patch

import pytest

from quilt_mcp.runtime import request_context
from quilt_mcp.tools import package_management


@contextmanager
def runtime_token(token: str | None):
    metadata = {"session_id": "pkg-mgr-tests"} if token else None
    with request_context(token, metadata=metadata):
        yield


@pytest.mark.asyncio
async def test_metadata_update_requires_token(monkeypatch):
    monkeypatch.setenv("QUILT_CATALOG_URL", "https://catalog.example.com")
    result = package_management.package_update_metadata("user/pkg", {"key": "value"})
    assert result["success"] is False
    assert "Authorization token" in result["error"]


@pytest.mark.asyncio
async def test_metadata_update_requires_catalog(monkeypatch):
    with runtime_token("token"):
        result = package_management.package_update_metadata("user/pkg", {"key": "value"})
    assert result["success"] is False
    assert "Catalog URL" in result["error"]


@pytest.mark.asyncio
async def test_metadata_update_merges_existing(monkeypatch):
    captured = {}

    def fake_query(**kwargs):
        captured.update(kwargs)
        return {
            "package": {
                "name": "user/pkg",
                "hash": "hash",
                "entries": {"edges": []},
                "metadata": {"existing": True},
            }
        }

    def fake_update(**kwargs):
        captured.update({"update": kwargs})
        return {"top_hash": "updated"}

    monkeypatch.setenv("QUILT_CATALOG_URL", "https://catalog.example.com")
    monkeypatch.setattr(
        "quilt_mcp.clients.catalog.catalog_graphql_query",
        fake_query,
    )
    monkeypatch.setattr(
        "quilt_mcp.clients.catalog.catalog_package_update",
        fake_update,
    )

    with runtime_token("token"):
        result = package_management.package_update_metadata(
            package_name="user/pkg",
            metadata={"new": "value"},
            registry="https://catalog.example.com",
            merge_with_existing=True,
        )

    assert captured["registry_url"] == "https://catalog.example.com"
    update_call = captured["update"]
    assert update_call["package_name"] == "user/pkg"
    assert update_call["metadata"]["existing"] is True
    assert update_call["metadata"]["new"] == "value"
    assert update_call["auth_token"] == "token"
    assert result["success"] is True
    assert result["top_hash"] == "updated"


@pytest.mark.asyncio
async def test_metadata_update_replace(monkeypatch):
    def fake_query(**_kwargs):
        return {
            "package": {
                "name": "user/pkg",
                "hash": "hash",
                "metadata": {"old": True},
            }
        }

    captured = {}

    def fake_update(**kwargs):
        captured.update(kwargs)
        return {"top_hash": "hash2"}

    monkeypatch.setenv("QUILT_CATALOG_URL", "https://catalog.example.com")
    monkeypatch.setattr("quilt_mcp.clients.catalog.catalog_graphql_query", fake_query)
    monkeypatch.setattr("quilt_mcp.clients.catalog.catalog_package_update", fake_update)

    with runtime_token("token"):
        result = package_management.package_update_metadata(
            package_name="user/pkg",
            metadata={"replacement": True},
            merge_with_existing=False,
        )

    assert captured["metadata"] == {"replacement": True}
    assert result["success"] is True
    assert result["top_hash"] == "hash2"


@pytest.mark.asyncio
async def test_metadata_update_handles_errors(monkeypatch):
    def fake_query(**_kwargs):
        return {"package": {"name": "user/pkg", "metadata": {}}}

    monkeypatch.setenv("QUILT_CATALOG_URL", "https://catalog.example.com")
    monkeypatch.setattr("quilt_mcp.clients.catalog.catalog_graphql_query", fake_query)
    monkeypatch.setattr(
        "quilt_mcp.clients.catalog.catalog_package_update",
        lambda **_: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    with runtime_token("token"):
        result = package_management.package_update_metadata("user/pkg", {"new": "value"})

    assert result["success"] is False
    assert "Failed to update package metadata" in result["error"]
    assert "boom" in result.get("cause", "")

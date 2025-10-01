"""Stateless tests for s3_package using catalog clients."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Dict
from unittest.mock import Mock

import pytest

from quilt_mcp.runtime import request_context
from quilt_mcp.tools import s3_package


@contextmanager
def runtime_token(token: str | None):
    metadata = {"session_id": "s3-package-tests"} if token else None
    with request_context(token, metadata=metadata):
        yield


@pytest.fixture(autouse=True)
def reset_recommended_bucket_cache():
    yield


@pytest.mark.asyncio
async def test_package_create_from_s3_requires_token(monkeypatch):
    monkeypatch.setenv("QUILT_CATALOG_URL", "https://catalog.example.com")
    result = s3_package.package_create_from_s3("bucket", "user/pkg")
    assert result["success"] is False
    assert "Authorization token" in result["error"]


@pytest.mark.asyncio
async def test_package_create_from_s3_requires_catalog(monkeypatch):
    monkeypatch.delenv("QUILT_CATALOG_URL", raising=False)
    with runtime_token("token"):
        result = s3_package.package_create_from_s3("bucket", "user/pkg")
    assert result["success"] is False
    assert "Catalog URL" in result["error"]


@pytest.mark.asyncio
async def test_package_create_from_s3_dry_run(monkeypatch):
    class FakePaginator:
        def paginate(self, **_kwargs):
            return [
                {
                    "Contents": [
                        {"Key": "data/file1.csv", "Size": 1024},
                        {"Key": "docs/readme.md", "Size": 512},
                    ]
                }
            ]

    fake_client = Mock()
    fake_client.get_paginator.return_value = FakePaginator()

    monkeypatch.setenv("QUILT_CATALOG_URL", "https://catalog.example.com")
    monkeypatch.setattr(s3_package, "get_s3_client", lambda: fake_client)
    monkeypatch.setattr(
        "quilt_mcp.tools.quilt_summary.create_quilt_summary_files",
        lambda **_: {"success": True, "visualization_count": 0},
    )

    with runtime_token("token"):
        result = s3_package.package_create_from_s3(
            source_bucket="bucket",
            package_name="user/pkg",
            dry_run=True,
            auto_organize=True,
        )

    assert result["success"] is True
    assert result["action"] == "preview"
    assert result["registry"].startswith("s3://")
    structure = result["structure_preview"]
    assert structure["total_files"] == 2
    assert structure["total_size_mb"] >= 0


@pytest.mark.asyncio
async def test_package_create_from_s3_creates_package(monkeypatch):
    captured_call: Dict[str, object] = {}

    class FakePaginator:
        def paginate(self, **_kwargs):
            return [
                {
                    "Contents": [
                        {"Key": "data/file1.csv", "Size": 1_024},
                    ]
                }
            ]

    def fake_catalog_create(**kwargs):
        captured_call.update(kwargs)
        return {
            "top_hash": "hash",
            "entries_added": 1,
            "files": [{"logical_path": "data/file1.csv"}],
            "warnings": ["client-warning"],
        }

    monkeypatch.setenv("QUILT_CATALOG_URL", "https://catalog.example.com")
    fake_client = Mock()
    fake_client.get_paginator.return_value = FakePaginator()
    monkeypatch.setattr(s3_package, "get_s3_client", lambda: fake_client)
    monkeypatch.setattr(
        "quilt_mcp.tools.quilt_summary.create_quilt_summary_files",
        lambda **_: {"success": True, "visualization_count": 0},
    )
    monkeypatch.setattr(
        "quilt_mcp.clients.catalog.catalog_package_create",
        fake_catalog_create,
    )

    with runtime_token("token"):
        result = s3_package.package_create_from_s3(
            source_bucket="bucket",
            package_name="user/pkg",
            dry_run=False,
            auto_organize=False,
            metadata={"description": "test", "readme_content": "Hello"},
        )

    assert captured_call["registry_url"].startswith("s3://")
    assert captured_call["package_name"] == "user/pkg"
    assert captured_call["s3_uris"]
    assert captured_call["auth_token"] == "token"
    assert "readme" not in captured_call["metadata"]
    assert result["success"] is True
    assert result["message"].startswith("Package 'user/pkg' created")


@pytest.mark.asyncio
async def test_package_create_from_s3_handles_catalog_error(monkeypatch):
    class FakePaginator:
        def paginate(self, **_kwargs):
            return [{"Contents": [{"Key": "data/file.csv", "Size": 1_024}]}]

    monkeypatch.setenv("QUILT_CATALOG_URL", "https://catalog.example.com")
    fake_client = Mock()
    fake_client.get_paginator.return_value = FakePaginator()
    monkeypatch.setattr(s3_package, "get_s3_client", lambda: fake_client)
    monkeypatch.setattr(
        "quilt_mcp.tools.quilt_summary.create_quilt_summary_files",
        lambda **_: {"success": True, "visualization_count": 0},
    )
    monkeypatch.setattr(
        "quilt_mcp.clients.catalog.catalog_package_create",
        lambda **_: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    with runtime_token("token"):
        result = s3_package.package_create_from_s3("bucket", "user/pkg")

    assert result["success"] is False
    assert "Failed to create package" in result["error"]
    assert "boom" in result["error"]

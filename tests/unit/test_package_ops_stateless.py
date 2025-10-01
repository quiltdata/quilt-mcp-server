"""Stateless package_ops tests covering catalog client usage."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Dict
from unittest.mock import patch

import pytest

from quilt_mcp.runtime import request_context
from quilt_mcp.tools import package_ops


@contextmanager
def runtime_token(token: str | None):
    with request_context(token, metadata={"session_id": "session"} if token else None):
        yield


def test_package_create_calls_catalog_client(monkeypatch):
    captured: Dict[str, dict] = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return {
            "top_hash": "tophash",
            "entries_added": 2,
            "files": [
                {"logical_path": "file1.csv", "source": "s3://bucket/file1.csv"},
                {"logical_path": "file2.csv", "source": "s3://bucket/file2.csv"},
            ],
            "warnings": ["note"],
        }

    monkeypatch.setattr(
        "quilt_mcp.clients.catalog.catalog_package_create",
        fake_create,
    )

    metadata = {"description": "demo", "readme_content": "hello"}

    with runtime_token("token"):
        result = package_ops.package_create(
            package_name="user/pkg",
            s3_uris=["s3://bucket/file1.csv", "s3://bucket/file2.csv"],
            registry="https://registry.example.com",
            metadata=metadata,
            message="msg",
            flatten=True,
            copy_mode="all",
        )

    assert captured["registry_url"] == "https://registry.example.com"
    assert captured["package_name"] == "user/pkg"
    assert captured["auth_token"] == "token"
    assert captured["s3_uris"] == ["s3://bucket/file1.csv", "s3://bucket/file2.csv"]
    assert captured["message"] == "msg"
    assert captured["copy_mode"] == "all"
    # readme fields removed when handed to client
    assert "readme" not in captured["metadata"]
    assert "readme_content" not in captured["metadata"]

    assert result["status"] == "success"
    assert result["top_hash"] == "tophash"
    assert result["entries_added"] == 2
    assert set(result["warnings"]) == {
        "note",
        "README content moved from metadata to package file (README.md)",
    }


def test_package_create_requires_token():
    result = package_ops.package_create(
        package_name="user/pkg",
        s3_uris=["s3://bucket/file.csv"],
        registry="https://registry.example.com",
    )

    assert result["success"] is False
    assert "Authorization token" in result["error"]


def test_package_create_handles_client_error(monkeypatch):
    def boom(**_kwargs):
        raise RuntimeError("upstream failure")

    monkeypatch.setattr("quilt_mcp.clients.catalog.catalog_package_create", boom)

    with runtime_token("token"):
        result = package_ops.package_create(
            package_name="user/pkg",
            s3_uris=["s3://bucket/file.csv"],
            registry="https://registry.example.com",
        )

    assert result["error"].startswith("Failed to create package")
    assert "upstream failure" in result["error"]


def test_package_update_calls_catalog_client(monkeypatch):
    captured: Dict[str, dict] = {}

    def fake_update(**kwargs):
        captured.update(kwargs)
        return {
            "top_hash": "hash",
            "files_added": [{"logical_path": "file.csv"}],
            "warnings": [],
        }

    monkeypatch.setattr("quilt_mcp.clients.catalog.catalog_package_update", fake_update)

    with runtime_token("token"):
        result = package_ops.package_update(
            package_name="user/pkg",
            s3_uris=["s3://bucket/file.csv"],
            registry="https://registry.example.com",
            metadata={"note": "x"},
            message="Added",
            copy_mode="none",
        )

    assert captured["registry_url"] == "https://registry.example.com"
    assert captured["package_name"] == "user/pkg"
    assert captured["auth_token"] == "token"
    assert captured["message"] == "Added"
    assert captured["copy_mode"] == "none"
    assert captured["metadata"] == {"note": "x"}
    assert result["status"] == "success"
    assert result["files_added"] == [{"logical_path": "file.csv"}]


def test_package_update_requires_token():
    result = package_ops.package_update(
        package_name="user/pkg",
        s3_uris=["s3://bucket/file.csv"],
        registry="https://registry.example.com",
    )

    assert result["success"] is False
    assert "Authorization token" in result["error"]


def test_package_delete_calls_catalog_client(monkeypatch):
    called = {}

    def fake_delete(**kwargs):
        called.update(kwargs)
        return {"status": "ok"}

    monkeypatch.setattr("quilt_mcp.clients.catalog.catalog_package_delete", fake_delete)

    with runtime_token("token"):
        result = package_ops.package_delete(
            package_name="user/pkg",
            registry="https://registry.example.com",
        )

    assert called["package_name"] == "user/pkg"
    assert called["registry_url"] == "https://registry.example.com"
    assert called["auth_token"] == "token"
    assert result["status"] == "success"


def test_package_delete_requires_token():
    result = package_ops.package_delete(
        package_name="user/pkg",
        registry="https://registry.example.com",
    )

    assert result["success"] is False
    assert "Authorization token" in result["error"]

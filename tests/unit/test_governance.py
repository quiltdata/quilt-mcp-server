"""Stateless governance tool tests."""

from __future__ import annotations

from contextlib import contextmanager

import pytest

from quilt_mcp.runtime import request_context
from quilt_mcp.tools import governance


@contextmanager
def runtime_token(token: str | None):
    metadata = {"session_id": "governance-tests"} if token else None
    with request_context(token, metadata=metadata):
        yield


def test_governance_discovery_lists_known_actions():
    result = governance.governance(action=None)
    assert "actions" in result
    assert "users_list" in result["actions"]
    assert "roles_list" in result["actions"]
    assert "tabulator_open_query_get" in result["actions"]


@pytest.mark.asyncio
async def test_admin_users_list_requires_token(monkeypatch):
    monkeypatch.setenv("QUILT_CATALOG_URL", "https://catalog.example.com")
    result = await governance.admin_users_list()
    assert result["success"] is False
    assert "Authorization token" in result["error"]


@pytest.mark.asyncio
async def test_admin_users_list_requires_catalog(monkeypatch):
    monkeypatch.delenv("QUILT_CATALOG_URL", raising=False)
    with runtime_token("token"):
        result = await governance.admin_users_list()
    assert result["success"] is False
    assert "Catalog URL" in result["error"]


@pytest.mark.asyncio
async def test_admin_users_list_unavailable_with_token(monkeypatch):
    monkeypatch.setenv("QUILT_CATALOG_URL", "https://catalog.example.com")
    with runtime_token("token"):
        result = await governance.admin_users_list()
    assert result["success"] is False
    assert "Admin APIs" in result["error"]


@pytest.mark.asyncio
async def test_admin_user_get_empty_name():
    result = await governance.admin_user_get("")
    assert result["success"] is False
    assert "Username cannot be empty" in result["error"]


@pytest.mark.asyncio
async def test_admin_user_create_validates_email(monkeypatch):
    result = await governance.admin_user_create(
        name="user",
        email="invalid",
        role="member",
    )
    assert result["success"] is False
    assert "Invalid email format" in result["error"]


@pytest.mark.asyncio
async def test_admin_user_delete_requires_name():
    result = await governance.admin_user_delete("")
    assert result["success"] is False
    assert "Username cannot be empty" in result["error"]


@pytest.mark.asyncio
async def test_admin_user_set_email_requires_token(monkeypatch):
    monkeypatch.setenv("QUILT_CATALOG_URL", "https://catalog.example.com")
    result = await governance.admin_user_set_email("user", "user@example.com")
    assert result["success"] is False
    assert "Authorization token" in result["error"]


@pytest.mark.asyncio
async def test_admin_roles_list_requires_token(monkeypatch):
    monkeypatch.setenv("QUILT_CATALOG_URL", "https://catalog.example.com")
    result = await governance.admin_roles_list()
    assert result["success"] is False
    assert "Authorization token" in result["error"]


@pytest.mark.asyncio
async def test_admin_sso_config_set_validates_dict(monkeypatch):
    monkeypatch.setenv("QUILT_CATALOG_URL", "https://catalog.example.com")
    with runtime_token("token"):
        result = await governance.admin_sso_config_set("")
    assert result["success"] is False
    assert "must be a non-empty dictionary" in result["error"]


@pytest.mark.asyncio
async def test_admin_tabulator_create_requires_fields():
    result = await governance.admin_tabulator_create("", "", "")
    assert result["success"] is False
    assert "Bucket name cannot be empty" in result["error"]


@pytest.mark.asyncio
async def test_admin_tabulator_open_query_get_requires_token(monkeypatch):
    monkeypatch.setenv("QUILT_CATALOG_URL", "https://catalog.example.com")
    result = await governance.admin_tabulator_open_query_get()
    assert result["success"] is False
    assert "Authorization token" in result["error"]


@pytest.mark.asyncio
async def test_admin_tabulator_open_query_set_requires_bool():
    result = await governance.admin_tabulator_open_query_set("yes")
    assert result["success"] is False
    assert "boolean" in result["error"]


@pytest.mark.asyncio
async def test_admin_tabulator_open_query_set_requires_token(monkeypatch):
    monkeypatch.setenv("QUILT_CATALOG_URL", "https://catalog.example.com")
    result = await governance.admin_tabulator_open_query_set(True)
    assert result["success"] is False
    assert "Authorization token" in result["error"]


def test_governance_unknown_action_returns_error():
    result = governance.governance(action="unknown")
    assert result["success"] is False
    assert "Unknown governance action" in result["error"]

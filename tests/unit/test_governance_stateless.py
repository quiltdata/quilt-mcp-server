"""Stateless governance tool tests."""

from __future__ import annotations

import pytest

from quilt_mcp.runtime import request_context
from quilt_mcp.tools import governance


@pytest.mark.asyncio
async def test_admin_users_list_requires_token():
    result = await governance.admin_users_list()
    assert result["success"] is False
    assert "Authorization token" in result["error"]


@pytest.mark.asyncio
async def test_admin_users_list_not_implemented(monkeypatch):
    with request_context("token", metadata={}):
        monkeypatch.setenv("QUILT_CATALOG_URL", "https://catalog.example.com")
        result = await governance.admin_users_list()
    assert "not yet available" in result["error"]


@pytest.mark.asyncio
async def test_admin_user_create_validates_email(monkeypatch):
    with request_context("token", metadata={}):
        monkeypatch.setenv("QUILT_CATALOG_URL", "https://catalog.example.com")
        result = await governance.admin_user_create("name", "invalid", "role")
    assert "Invalid email" in result["error"]

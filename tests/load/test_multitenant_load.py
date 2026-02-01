"""Load tests for multitenant context creation."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from quilt_mcp.context.factory import RequestContextFactory


@pytest.mark.slow
def test_multitenant_context_creation_under_load(monkeypatch):
    factory = RequestContextFactory(mode="multitenant")

    class _StubAuth:
        def get_user_identity(self):
            return {"user_id": "user"}

    monkeypatch.setattr(factory, "_create_auth_service", lambda: _StubAuth())
    monkeypatch.setattr(factory, "_create_permission_service", lambda auth_service: object())
    monkeypatch.setattr(factory, "_create_workflow_service", lambda tenant_id: object())

    tenants = [f"tenant-{i}" for i in range(10)]

    def _create_context(index: int):
        tenant_id = tenants[index % len(tenants)]
        return factory.create_context(tenant_id=tenant_id)

    with ThreadPoolExecutor(max_workers=8) as executor:
        contexts = list(executor.map(_create_context, range(100)))

    assert len(contexts) == 100

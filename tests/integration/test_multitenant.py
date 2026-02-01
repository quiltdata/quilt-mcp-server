"""Integration tests for multitenant context creation."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from quilt_mcp.context.factory import RequestContextFactory
from quilt_mcp.services.workflow_service import WorkflowService
from quilt_mcp.storage.file_storage import FileBasedWorkflowStorage


@pytest.mark.integration
def test_multitenant_contexts_are_isolated(tmp_path, monkeypatch):
    storage = FileBasedWorkflowStorage(base_dir=tmp_path)
    factory = RequestContextFactory(mode="multitenant")

    class _StubAuth:
        def get_user_identity(self):
            return {"user_id": "user"}

    monkeypatch.setattr(factory, "_create_auth_service", lambda: _StubAuth())
    monkeypatch.setattr(factory, "_create_permission_service", lambda auth_service: object())
    monkeypatch.setattr(
        factory,
        "_create_workflow_service",
        lambda tenant_id: WorkflowService(tenant_id=tenant_id, storage=storage),
    )

    tenants = [f"tenant-{i}" for i in range(6)]

    def _create_context(tenant_id: str):
        return factory.create_context(tenant_id=tenant_id)

    with ThreadPoolExecutor(max_workers=6) as executor:
        contexts = list(executor.map(_create_context, tenants))

    assert {context.tenant_id for context in contexts} == set(tenants)
    assert len({id(context.workflow_service) for context in contexts}) == len(tenants)


@pytest.mark.integration
def test_single_user_mode_ignores_multitenant_inputs(monkeypatch):
    factory = RequestContextFactory(mode="single-user")

    class _StubAuth:
        def get_user_identity(self):
            return {"user_id": "user"}

    monkeypatch.setattr(factory, "_create_auth_service", lambda: _StubAuth())
    monkeypatch.setattr(factory, "_create_permission_service", lambda auth_service: object())
    monkeypatch.setattr(factory, "_create_workflow_service", lambda tenant_id: object())

    context = factory.create_context()
    assert context.tenant_id == "default"

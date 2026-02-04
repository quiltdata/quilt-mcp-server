"""Integration tests for multiuser context creation."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from quilt_mcp.context.factory import RequestContextFactory


@pytest.mark.integration
def test_multiuser_contexts_are_isolated(monkeypatch):
    factory = RequestContextFactory(mode="multiuser")

    class _StubAuth:
        def get_user_identity(self):
            return {"user_id": "user"}

    monkeypatch.setattr(factory, "_create_auth_service", lambda: _StubAuth())
    monkeypatch.setattr(factory, "_create_permission_service", lambda auth_service: object())
    monkeypatch.setattr(factory, "_create_workflow_service", lambda: None)

    def _create_context():
        return factory.create_context()

    with ThreadPoolExecutor(max_workers=6) as executor:
        contexts = list(executor.map(lambda _: _create_context(), range(6)))

    assert all(context.workflow_service is None for context in contexts)
    assert len({context.request_id for context in contexts}) == len(contexts)


@pytest.mark.integration
def test_single_user_mode_ignores_multiuser_inputs(monkeypatch):
    factory = RequestContextFactory(mode="single-user")

    class _StubAuth:
        def get_user_identity(self):
            return {"user_id": "user"}

    monkeypatch.setattr(factory, "_create_auth_service", lambda: _StubAuth())
    monkeypatch.setattr(factory, "_create_permission_service", lambda auth_service: object())
    monkeypatch.setattr(factory, "_create_workflow_service", lambda: object())

    context = factory.create_context()
    assert context.workflow_service is not None

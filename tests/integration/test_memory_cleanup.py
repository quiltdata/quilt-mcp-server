"""Integration tests for request-scoped service cleanup."""

from __future__ import annotations

import gc
import weakref

from quilt_mcp.context.factory import RequestContextFactory


def test_auth_service_is_gc_eligible_after_context_deletion(monkeypatch):
    factory = RequestContextFactory(mode="single-user")

    class _Sentinel:
        def get_user_identity(self):
            return {}

    monkeypatch.setattr(factory, "_create_auth_service", lambda: _Sentinel())

    context = factory.create_context()
    ref = weakref.ref(context.auth_service)
    del context
    gc.collect()

    assert ref() is None


def test_multiple_request_cycles_do_not_leak(monkeypatch):
    factory = RequestContextFactory(mode="single-user")

    class _Sentinel:
        def get_user_identity(self):
            return {}

    monkeypatch.setattr(factory, "_create_auth_service", lambda: _Sentinel())

    refs = []
    for _ in range(5):
        context = factory.create_context()
        refs.append(weakref.ref(context.auth_service))
        del context
    gc.collect()

    assert all(ref() is None for ref in refs)

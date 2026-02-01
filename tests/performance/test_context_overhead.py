"""Performance tests for request context creation."""

from __future__ import annotations

import time

from quilt_mcp.context.factory import RequestContextFactory
from quilt_mcp.config import set_test_mode_config


def test_context_creation_overhead_under_10ms(monkeypatch):
    set_test_mode_config(multitenant_mode=False)

    factory = RequestContextFactory(mode="single-user")

    class _StubAuthService:
        def get_user_identity(self):
            return {}

        def is_valid(self):
            return True

        def get_boto3_session(self):
            return None

    monkeypatch.setattr(factory, "_create_auth_service", lambda: _StubAuthService())

    iterations = 100
    start = time.perf_counter()
    for _ in range(iterations):
        _ = factory.create_context()
    elapsed = time.perf_counter() - start
    avg_ms = (elapsed / iterations) * 1000

    assert avg_ms < 10, f"Average context creation time {avg_ms:.2f}ms exceeds 10ms"

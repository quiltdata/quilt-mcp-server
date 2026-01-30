"""Unit tests for request context exceptions."""

from __future__ import annotations

from quilt_mcp.context.exceptions import (
    ContextNotAvailableError,
    ServiceInitializationError,
    TenantValidationError,
)


def test_context_exceptions_are_exception_types():
    assert isinstance(ContextNotAvailableError("missing"), Exception)
    assert isinstance(ServiceInitializationError("auth", "failed"), Exception)
    assert isinstance(TenantValidationError("single-user"), Exception)

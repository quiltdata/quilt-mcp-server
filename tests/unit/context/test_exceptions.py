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


def test_context_not_available_error_has_clear_message():
    error = ContextNotAvailableError()

    message = str(error).lower()
    assert "request context" in message
    assert "not available" in message

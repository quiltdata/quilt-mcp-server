"""Unit tests for request context exceptions."""

from __future__ import annotations

from quilt_mcp.context.exceptions import (
    ContextNotAvailableError,
    ServiceInitializationError,
)


def test_context_exceptions_are_exception_types():
    assert isinstance(ContextNotAvailableError("missing"), Exception)
    assert isinstance(ServiceInitializationError("auth", "failed"), Exception)


def test_context_not_available_error_has_clear_message():
    error = ContextNotAvailableError()

    message = str(error).lower()
    assert "request context" in message
    assert "not available" in message


def test_service_initialization_error_includes_service_and_reason():
    error = ServiceInitializationError("auth_service", "missing credentials")

    message = str(error).lower()
    assert "auth_service" in message
    assert "missing credentials" in message

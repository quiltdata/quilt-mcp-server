"""Unit tests for request context exceptions."""

from __future__ import annotations

import pytest

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


def test_service_initialization_error_includes_service_and_reason():
    error = ServiceInitializationError("auth_service", "missing credentials")

    message = str(error).lower()
    assert "auth_service" in message
    assert "missing credentials" in message


@pytest.mark.parametrize("mode", ["single-user", "multiuser"])
def test_tenant_validation_error_includes_mode(mode):
    error = TenantValidationError(mode)

    message = str(error).lower()
    assert mode in message
    assert "tenant" in message

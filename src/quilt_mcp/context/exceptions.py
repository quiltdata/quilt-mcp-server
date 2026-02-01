"""Exceptions for request context handling."""

from __future__ import annotations


class ContextNotAvailableError(RuntimeError):
    """Raised when request context is accessed outside a request."""

    def __init__(self, message: str | None = None) -> None:
        if message is None:
            message = (
                "Request context is not available. Ensure you are calling this inside an active MCP request handler."
            )
        super().__init__(message)


class ServiceInitializationError(RuntimeError):
    """Raised when a request-scoped service fails to initialize."""

    def __init__(self, service_name: str, reason: str) -> None:
        message = f"Failed to initialize {service_name}: {reason}"
        super().__init__(message)
        self.service_name = service_name
        self.reason = reason


class TenantValidationError(ValueError):
    """Raised when tenant validation fails for the selected mode."""

    def __init__(self, mode: str, message: str | None = None) -> None:
        if message is None:
            if mode == "single-user":
                message = "Tenant validation failed for single-user mode. Tenant information must not be provided."
            elif mode == "multitenant":
                message = "Tenant validation failed for multitenant mode. Tenant information is required."
            else:
                message = (
                    f"Tenant validation failed for {mode} mode. "
                    "Tenant information is required or forbidden based on the mode."
                )
        super().__init__(message)
        self.mode = mode

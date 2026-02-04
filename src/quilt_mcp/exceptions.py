"""Shared exception types for Quilt MCP server."""

from __future__ import annotations


class QuiltMCPError(RuntimeError):
    """Base exception for Quilt MCP server errors."""

    def __init__(self, message: str, *, error_code: str = "quilt_mcp_error") -> None:
        super().__init__(message)
        self.error_code = error_code


class OperationNotSupportedError(QuiltMCPError):
    """Operation not supported in current mode."""

    def __init__(self, message: str, mode: str = "multiuser") -> None:
        super().__init__(
            f"{message} (Current mode: {mode})",
            error_code="OPERATION_NOT_SUPPORTED",
        )

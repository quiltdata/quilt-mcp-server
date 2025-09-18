"""Operation framework for Quilt MCP Server.

This module provides a flexible operation execution system that supports:
- Configuration injection for isolated operation execution
- Structured result types for consistent response formatting
- Error categorization with comprehensive failure mode handling
- Resource lifecycle management for proper cleanup
- Extensible architecture for different operation types

The operation framework follows these principles:
- Configuration-driven operation execution (no global state)
- Consistent result formatting across all operations
- Comprehensive error categorization and handling
- Proper resource lifecycle management
- Type safety with clear interfaces

Example usage:
    from quilt_mcp.operations.quilt3.auth import check_auth_status
    from quilt_mcp.config.quilt3 import Quilt3Config

    # Create configuration
    config = Quilt3Config(registry_url="s3://my-bucket")

    # Execute operation with configuration
    result = check_auth_status(config)

    # Handle result
    if result.success:
        print(f"Auth status: {result.data}")
    else:
        print(f"Error ({result.error_type}): {result.message}")
"""

from __future__ import annotations

# Re-export main operation classes for easy access
from .base import (
    Operation,
    OperationResult,
    SuccessResult,
    ErrorResult,
    OperationError,
    NetworkError,
    AuthenticationError,
    AuthorizationError,
    ConfigurationError,
)

__all__ = [
    "Operation",
    "OperationResult",
    "SuccessResult",
    "ErrorResult",
    "OperationError",
    "NetworkError",
    "AuthenticationError",
    "AuthorizationError",
    "ConfigurationError",
]
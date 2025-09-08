"""Quilt MCP Utilities - Composable utility functions for Quilt operations.

This package provides reusable utility functions extracted from the existing tools
to eliminate code duplication and provide a consistent foundation for operations.

The utilities are organized into logical groups:
- aws: AWS operations including session management, S3, registry, and authentication
- package: Package operations including manifest handling and validation
- object: Object operations including metadata and retrieval
- data: Data handling and content operations
- search: Search and query utilities

All utilities follow consistent patterns:
- Dependency injection for testability
- Pure functions where possible
- Comprehensive error handling
- Type annotations and documentation
- BDD test coverage
"""

from __future__ import annotations

# Import AWS utilities for easy access
from .aws import (
    # Session management
    create_session,
    get_session_credentials,
    validate_session,
    SessionError,
    # S3 operations
    create_client,
    list_objects,
    get_object,
    put_object,
    delete_object,
    object_exists,
    S3Error,
    # Registry operations
    get_registry_url,
    list_packages,
    get_package_metadata,
    validate_registry_access,
    RegistryError,
    # Authentication utilities
    get_credentials,
    validate_credentials,
    get_caller_identity,
    is_quilt_authenticated,
    get_credential_type,
    AuthError,
)

__version__ = "0.1.0"

__all__ = [
    # Session management
    "create_session",
    "get_session_credentials",
    "validate_session",
    "SessionError",
    # S3 operations
    "create_client",
    "list_objects",
    "get_object",
    "put_object",
    "delete_object",
    "object_exists",
    "S3Error",
    # Registry operations
    "get_registry_url",
    "list_packages",
    "get_package_metadata",
    "validate_registry_access",
    "RegistryError",
    # Authentication utilities
    "get_credentials",
    "validate_credentials",
    "get_caller_identity",
    "is_quilt_authenticated",
    "get_credential_type",
    "AuthError",
]

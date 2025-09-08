"""AWS operations utilities.

This module provides composable utilities for AWS operations including:
- Session management with dual credential support (Quilt3 + native AWS)
- S3 operations with streaming and retry support
- Registry operations with pagination
- Authentication utilities with credential fallback

All utilities support dependency injection and follow consistent error handling patterns.
"""

from __future__ import annotations

from .session import (
    create_session,
    get_session_credentials, 
    validate_session,
    SessionError,
)
from .s3 import (
    create_client,
    list_objects,
    get_object,
    put_object,
    delete_object,
    object_exists,
    S3Error,
)
from .registry import (
    get_registry_url,
    list_packages,
    get_package_metadata,
    validate_registry_access,
    RegistryError,
)
from .auth import (
    get_credentials,
    validate_credentials,
    get_caller_identity,
    is_quilt_authenticated,
    get_credential_type,
    AuthError,
)

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
"""Custom exceptions for the QuiltOps abstraction layer.

This module defines domain-specific exceptions that provide clear error context
and debugging information for QuiltOps operations across different backends.
"""

from typing import Dict, Any, Optional


class AuthenticationError(Exception):
    """Exception raised when authentication fails.

    This exception is raised when JWT tokens are invalid, quilt3 sessions
    are expired or corrupted, or when no valid authentication method is available.

    Attributes:
        context: Dictionary containing authentication-specific error details
                such as auth method, error codes, and remediation steps.
    """

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        """Initialize AuthenticationError with message and optional context.

        Args:
            message: Human-readable error message
            context: Optional dictionary with error details for debugging
        """
        super().__init__(message)
        self.context = context or {}


class BackendError(Exception):
    """Exception raised when backend operations fail.

    This exception is raised when quilt3 library calls or Platform GraphQL
    operations fail due to network issues, API errors, or backend-specific problems.

    Attributes:
        context: Dictionary containing backend-specific error details
                such as backend type, operation name, and original exception info.
    """

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        """Initialize BackendError with message and optional context.

        Args:
            message: Human-readable error message
            context: Optional dictionary with error details for debugging
        """
        super().__init__(message)
        self.context = context or {}


class ValidationError(Exception):
    """Exception raised when input validation fails.

    This exception is raised when domain objects (Package_Info, Content_Info, etc.)
    have invalid field values or when operation parameters don't meet requirements.

    Attributes:
        context: Dictionary containing validation-specific error details
                such as field names, validation rules, and error types.
    """

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        """Initialize ValidationError with message and optional context.

        Args:
            message: Human-readable error message
            context: Optional dictionary with error details for debugging
        """
        super().__init__(message)
        self.context = context or {}


class NotFoundError(Exception):
    """Exception raised when requested resources are not found.

    This exception is raised when packages, content, catalogs, or other resources
    cannot be found in the specified registry or location.

    Attributes:
        context: Dictionary containing resource-specific error details
                such as resource type, identifier, and search location.
    """

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        """Initialize NotFoundError with message and optional context.

        Args:
            message: Human-readable error message
            context: Optional dictionary with error details for debugging
        """
        super().__init__(message)
        self.context = context or {}


class PermissionError(Exception):
    """Exception raised when user lacks permission for operation.

    This exception is raised when the user doesn't have sufficient permissions
    to perform the requested operation, such as creating packages, accessing
    admin functions, or reading restricted content.

    Attributes:
        context: Dictionary containing permission-specific error details
                such as required permissions, user role, and resource access level.
    """

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        """Initialize PermissionError with message and optional context.

        Args:
            message: Human-readable error message
            context: Optional dictionary with error details for debugging
        """
        super().__init__(message)
        self.context = context or {}

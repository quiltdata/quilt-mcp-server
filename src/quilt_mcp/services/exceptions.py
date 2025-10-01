"""Custom exceptions for QuiltService operations.

This module defines a hierarchy of exceptions for better error handling
in QuiltService operations, enabling precise error reporting and handling
without exposing underlying quilt3 implementation details.
"""


class QuiltServiceError(Exception):
    """Base exception for all QuiltService errors.

    All QuiltService-specific exceptions inherit from this base class,
    allowing callers to catch all service errors with a single exception type.
    """

    pass


class AdminNotAvailableError(QuiltServiceError):
    """Admin operations are not available.

    Raised when attempting admin operations but quilt3.admin modules
    are not installed or available in the current environment.
    """

    pass


class UserNotFoundError(QuiltServiceError):
    """User does not exist.

    Raised when attempting to retrieve or modify a user that does not
    exist in the catalog.
    """

    pass


class UserAlreadyExistsError(QuiltServiceError):
    """User already exists.

    Raised when attempting to create a user that already exists in the
    catalog.
    """

    pass


class RoleNotFoundError(QuiltServiceError):
    """Role does not exist.

    Raised when attempting to retrieve or modify a role that does not
    exist in the catalog.
    """

    pass


class RoleAlreadyExistsError(QuiltServiceError):
    """Role already exists.

    Raised when attempting to create a role that already exists in the
    catalog.
    """

    pass


class PackageNotFoundError(QuiltServiceError):
    """Package does not exist.

    Raised when attempting to retrieve or modify a package that does not
    exist in the registry.
    """

    pass


class BucketNotFoundError(QuiltServiceError):
    """Bucket does not exist or is not accessible.

    Raised when attempting to access an S3 bucket that does not exist or
    the current user does not have permission to access.
    """

    pass

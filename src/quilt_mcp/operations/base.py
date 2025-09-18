"""Base operation classes and result type framework.

This module defines the abstract base classes and result types that all
operations inherit from. It provides:

- Abstract Operation base class with configuration injection interface
- OperationResult hierarchy for structured success/error responses
- Error categorization for different types of operation failures
- Result serialization support for MCP response formatting
- Resource lifecycle management for proper cleanup

Design principles:
- Abstract base class enforces consistent operation interface
- Type-safe result hierarchy with clear success/failure states
- Comprehensive error categorization for different failure modes
- JSON-compatible result serialization for MCP compatibility
- Proper resource management with context manager support
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Union
from dataclasses import dataclass, field
import datetime
import traceback

from ..config.base import Configuration


# Error hierarchy for operation failures
class OperationError(Exception):
    """Base exception for all operation-related errors.

    This is the root of the operation error hierarchy.
    All operation-specific exceptions should inherit from this.
    """

    pass


class NetworkError(OperationError):
    """Exception raised for network-related operation failures.

    This should be used for errors during network operations such as:
    - Connection timeouts
    - DNS resolution failures
    - HTTP request failures
    - Network connectivity issues
    """

    pass


class AuthenticationError(OperationError):
    """Exception raised for authentication-related failures.

    This should be used for errors during authentication such as:
    - Invalid credentials
    - Missing authentication information
    - Authentication token expiration
    - Authentication service unavailability
    """

    pass


class AuthorizationError(OperationError):
    """Exception raised for authorization-related failures.

    This should be used for errors when authenticated user lacks permissions:
    - Insufficient permissions for requested operation
    - Resource access denied
    - Operation not allowed for user role
    - Policy violations
    """

    pass


class ConfigurationError(OperationError):
    """Exception raised for configuration-related failures.

    This should be used for errors in operation configuration:
    - Invalid configuration parameters
    - Missing required configuration
    - Configuration validation failures
    - Incompatible configuration combinations
    """

    pass


@dataclass
class OperationResult(ABC):
    """Abstract base class for all operation results.

    This provides a consistent interface for operation results,
    whether successful or failed. All result types inherit from this.

    Attributes:
        success: True if operation succeeded, False if it failed
        timestamp: ISO timestamp when result was created
        operation_id: Optional identifier for the operation
    """

    success: bool
    timestamp: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    operation_id: Optional[str] = None

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for serialization.

        Returns:
            Dictionary representation suitable for JSON serialization
        """
        pass

    @classmethod
    @abstractmethod
    def from_dict(cls, data: Dict[str, Any]) -> OperationResult:
        """Create result instance from dictionary data.

        Args:
            data: Dictionary containing result data

        Returns:
            New result instance of appropriate type
        """
        pass


@dataclass
class SuccessResult(OperationResult):
    """Result for successful operations.

    This represents a successful operation outcome with optional data payload.

    Attributes:
        success: Always True for SuccessResult
        data: Optional data payload from the operation
        message: Optional success message
    """

    success: bool = field(default=True, init=False)
    data: Optional[Dict[str, Any]] = None
    message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert success result to dictionary.

        Returns:
            Dictionary with success status, data, and metadata
        """
        result = {
            "success": self.success,
            "timestamp": self.timestamp,
        }

        if self.operation_id:
            result["operation_id"] = self.operation_id

        if self.data is not None:
            result["data"] = self.data

        if self.message:
            result["message"] = self.message

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SuccessResult:
        """Create SuccessResult from dictionary.

        Args:
            data: Dictionary containing result data

        Returns:
            New SuccessResult instance
        """
        return cls(
            data=data.get("data"),
            message=data.get("message"),
            timestamp=data.get("timestamp", datetime.datetime.now(datetime.timezone.utc).isoformat()),
            operation_id=data.get("operation_id"),
        )


@dataclass
class ErrorResult(OperationResult):
    """Result for failed operations.

    This represents a failed operation outcome with error details and
    categorization for proper handling.

    Attributes:
        success: Always False for ErrorResult
        error_type: Category of error (network, auth, config, authz)
        message: Human-readable error message
        details: Optional additional error details
        traceback: Optional exception traceback for debugging
    """

    success: bool = field(default=False, init=False)
    error_type: str = ""
    message: str = ""
    details: Optional[Dict[str, Any]] = None
    traceback: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert error result to dictionary.

        Returns:
            Dictionary with error status, type, message, and metadata
        """
        result = {
            "success": self.success,
            "error_type": self.error_type,
            "message": self.message,
            "timestamp": self.timestamp,
        }

        if self.operation_id:
            result["operation_id"] = self.operation_id

        if self.details:
            result["details"] = self.details

        if self.traceback:
            result["traceback"] = self.traceback

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ErrorResult:
        """Create ErrorResult from dictionary.

        Args:
            data: Dictionary containing error result data

        Returns:
            New ErrorResult instance
        """
        return cls(
            error_type=data.get("error_type", "unknown"),
            message=data.get("message", ""),
            details=data.get("details"),
            traceback=data.get("traceback"),
            timestamp=data.get("timestamp", datetime.datetime.now(datetime.timezone.utc).isoformat()),
            operation_id=data.get("operation_id"),
        )

    @classmethod
    def from_exception(
        cls, exc: Exception, operation_id: Optional[str] = None, include_traceback: bool = False
    ) -> ErrorResult:
        """Create ErrorResult from an exception.

        Args:
            exc: Exception that occurred during operation
            operation_id: Optional operation identifier
            include_traceback: Whether to include exception traceback

        Returns:
            New ErrorResult with appropriate error categorization
        """
        # Categorize the error based on exception type
        if isinstance(exc, NetworkError):
            error_type = "network"
        elif isinstance(exc, AuthenticationError):
            error_type = "auth"
        elif isinstance(exc, AuthorizationError):
            error_type = "authz"
        elif isinstance(exc, ConfigurationError):
            error_type = "config"
        else:
            error_type = "unknown"

        return cls(
            error_type=error_type,
            message=str(exc),
            details={"exception_type": type(exc).__name__},
            traceback=traceback.format_exc() if include_traceback else None,
            operation_id=operation_id,
        )


class Operation(ABC):
    """Abstract base class for all operations.

    This defines the interface that all operation classes must implement.
    It provides configuration injection, lifecycle management, and consistent
    execution patterns while allowing subclasses to define their specific
    operation logic.

    Operations are designed to be:
    - Configuration-driven (no global state dependencies)
    - Resource-safe (proper cleanup via context manager)
    - Type-safe (clear interfaces and result types)
    - Testable (isolated execution with mocked configurations)

    Subclasses must implement:
    - execute(): Perform the actual operation and return result
    """

    def __init__(self, config: Configuration):
        """Initialize operation with configuration.

        Args:
            config: Configuration instance for this operation

        Raises:
            ConfigurationError: If configuration is invalid
        """
        self.config = config
        self._resources_acquired = False

    def __enter__(self) -> Operation:
        """Enter context manager and acquire resources.

        Returns:
            Self for use in with statement
        """
        self._acquire_resources()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager and cleanup resources.

        Args:
            exc_type: Exception type if exception occurred
            exc_val: Exception value if exception occurred
            exc_tb: Exception traceback if exception occurred
        """
        self._cleanup_resources()

    def _acquire_resources(self) -> None:
        """Acquire any resources needed for operation execution.

        Subclasses can override this to acquire specific resources
        like network connections, file handles, etc.
        """
        self._resources_acquired = True

    def _cleanup_resources(self) -> None:
        """Clean up any resources acquired during operation execution.

        This method is always called, even if the operation fails.
        Subclasses can override this to clean up specific resources.
        """
        self._resources_acquired = False

    @abstractmethod
    def execute(self) -> OperationResult:
        """Execute the operation and return result.

        This method contains the core operation logic and must be
        implemented by all subclasses.

        Returns:
            OperationResult indicating success or failure

        Raises:
            OperationError: For operation-specific failures
        """
        pass

    def execute_safely(self, operation_id: Optional[str] = None) -> OperationResult:
        """Execute operation with comprehensive error handling.

        This method wraps execute() with error handling and resource management
        to ensure consistent behavior and proper cleanup.

        Args:
            operation_id: Optional identifier for this operation execution

        Returns:
            OperationResult with success or error details
        """
        try:
            # Validate configuration before execution
            if not self.config.is_valid():
                validation_result = self.config.validate()
                return ErrorResult(
                    error_type="config",
                    message=f"Configuration validation failed: {'; '.join(validation_result.errors)}",
                    operation_id=operation_id,
                )

            # Execute with resource management
            with self:
                result = self.execute()

                # Ensure result has operation_id if provided
                if operation_id and not result.operation_id:
                    result.operation_id = operation_id

                return result

        except (NetworkError, AuthenticationError, AuthorizationError, ConfigurationError) as e:
            # Handle known operation errors
            return ErrorResult.from_exception(e, operation_id=operation_id)
        except Exception as e:
            # Handle unexpected errors
            return ErrorResult(
                error_type="unknown",
                message=f"Unexpected error during operation: {str(e)}",
                details={"exception_type": type(e).__name__},
                operation_id=operation_id,
            )

    def validate_config_or_raise(self) -> None:
        """Validate configuration and raise ConfigurationError if invalid.

        This is a convenience method for operations that want to validate
        configuration early and raise an exception on failure.

        Raises:
            ConfigurationError: If configuration validation fails
        """
        if not self.config.is_valid():
            validation_result = self.config.validate()
            error_msg = "Configuration validation failed:\n" + "\n".join(
                f"  - {error}" for error in validation_result.errors
            )
            raise ConfigurationError(error_msg)

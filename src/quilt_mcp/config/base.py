"""Base configuration classes and validation framework.

This module defines the abstract base classes and validation framework
that all configuration types inherit from. It provides:

- Abstract Configuration base class with validation interface
- ConfigValidationResult for structured validation responses
- Error hierarchy for different types of configuration errors
- Serialization support for debugging and persistence

Design principles:
- Abstract base class enforces consistent validation interface
- Type-safe validation results with clear success/failure states
- Comprehensive error categorization for different failure modes
- JSON-compatible serialization format
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List
from dataclasses import dataclass


class ConfigurationError(Exception):
    """Base exception for all configuration-related errors.

    This is the root of the configuration error hierarchy.
    All configuration-specific exceptions should inherit from this.
    """

    pass


class ValidationError(ConfigurationError):
    """Exception raised when configuration validation fails.

    This should be used for errors during configuration validation,
    such as invalid URLs, missing required values, or format violations.
    """

    pass


class SerializationError(ConfigurationError):
    """Exception raised when configuration serialization fails.

    This should be used for errors during to_dict/from_dict operations,
    such as unsupported data types or corruption during roundtrip.
    """

    pass


@dataclass
class ConfigValidationResult:
    """Result of configuration validation with success state and error details.

    This provides a structured way to return validation results,
    including success/failure state and detailed error information.

    Attributes:
        success: True if validation passed, False otherwise
        errors: List of error messages describing validation failures
    """

    success: bool
    errors: List[str]

    @property
    def is_valid(self) -> bool:
        """Alias for success property for more readable code."""
        return self.success

    @property
    def error_count(self) -> int:
        """Number of validation errors found."""
        return len(self.errors)

    def add_error(self, error: str) -> None:
        """Add an error message and mark validation as failed.

        Args:
            error: Error message to add
        """
        self.errors.append(error)
        self.success = False

    @classmethod
    def success_result(cls) -> ConfigValidationResult:
        """Create a successful validation result."""
        return cls(success=True, errors=[])

    @classmethod
    def failure_result(cls, errors: List[str]) -> ConfigValidationResult:
        """Create a failed validation result with error messages.

        Args:
            errors: List of error messages

        Returns:
            ConfigValidationResult with success=False and provided errors
        """
        return cls(success=False, errors=errors.copy())


class Configuration(ABC):
    """Abstract base class for all configuration types.

    This defines the interface that all configuration classes must implement.
    It provides common functionality for validation and serialization while
    allowing subclasses to define their specific configuration logic.

    Subclasses must implement:
    - validate(): Perform configuration-specific validation
    - to_dict(): Convert configuration to dictionary
    - from_dict(): Create configuration from dictionary (class method)
    """

    @abstractmethod
    def validate(self) -> ConfigValidationResult:
        """Validate this configuration and return detailed results.

        This method should check all configuration values and return
        a ConfigValidationResult indicating success or failure with
        detailed error messages.

        Returns:
            ConfigValidationResult with validation status and errors
        """
        pass

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to a dictionary for serialization.

        The returned dictionary should be JSON-compatible and contain
        all configuration data needed to recreate the configuration
        via from_dict().

        Returns:
            Dictionary representation of configuration

        Raises:
            SerializationError: If configuration cannot be serialized
        """
        pass

    @classmethod
    @abstractmethod
    def from_dict(cls, data: Dict[str, Any]) -> Configuration:
        """Create configuration instance from dictionary data.

        This should be the inverse of to_dict() - any configuration
        serialized with to_dict() should be recreatable with from_dict().

        Args:
            data: Dictionary containing configuration data

        Returns:
            New configuration instance

        Raises:
            SerializationError: If data cannot be deserialized
            ValidationError: If resulting configuration is invalid
        """
        pass

    def is_valid(self) -> bool:
        """Check if this configuration is valid.

        This is a convenience method that performs validation
        and returns just the success/failure status.

        Returns:
            True if configuration is valid, False otherwise
        """
        result = self.validate()
        return result.success

    def validate_or_raise(self) -> None:
        """Validate configuration and raise ValidationError if invalid.

        This is a convenience method for cases where you want to
        validate and immediately raise an exception on failure.

        Raises:
            ValidationError: If configuration validation fails
        """
        result = self.validate()
        if not result.success:
            error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {error}" for error in result.errors)
            raise ValidationError(error_msg)

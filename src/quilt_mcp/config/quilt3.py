"""Quilt3-specific configuration implementation.

This module provides Quilt3Config class that handles:
- Registry URL validation (S3 bucket format)
- Optional catalog URL validation (HTTP/HTTPS format)
- Environment variable integration (QUILT_REGISTRY_URL, QUILT_CATALOG_URL)
- Configuration loading with priority-based resolution
- Comprehensive validation with clear error messages

Design principles:
- No dependencies on global quilt3 state
- Clear validation error messages with actionable guidance
- Environment variable support with explicit parameter precedence
- JSON-compatible serialization for debugging and persistence
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from .base import Configuration, ConfigValidationResult, ValidationError, SerializationError


class Quilt3Config(Configuration):
    """Configuration for Quilt3 operations with registry and catalog URLs.

    This configuration class handles Quilt3-specific settings including:
    - Registry URL (required): S3 bucket where packages are stored
    - Catalog URL (optional): HTTP/HTTPS URL for Quilt catalog interface

    The configuration supports multiple instantiation patterns:
    - Direct instantiation with parameters
    - Environment variable loading
    - Dictionary-based creation
    - Priority-based resolution (explicit > environment > defaults)

    Example usage:
        # Direct instantiation
        config = Quilt3Config(registry_url="s3://my-bucket")

        # From environment variables
        config = Quilt3Config.from_environment()

        # From dictionary
        config = Quilt3Config.from_dict({"registry_url": "s3://my-bucket"})

        # Validate configuration
        result = config.validate()
        if not result.success:
            for error in result.errors:
                print(f"Configuration error: {error}")
    """

    def __init__(
        self,
        registry_url: Optional[str] = None,
        catalog_url: Optional[str] = None
    ):
        """Initialize Quilt3Config with registry and optional catalog URLs.

        Args:
            registry_url: S3 URL for the Quilt package registry (e.g., "s3://my-bucket")
            catalog_url: Optional HTTP/HTTPS URL for the Quilt catalog interface
        """
        self.registry_url = registry_url
        self.catalog_url = catalog_url

    def validate(self) -> ConfigValidationResult:
        """Validate the Quilt3 configuration.

        Performs comprehensive validation of:
        - Registry URL format and requirements
        - Catalog URL format (if provided)
        - Required field presence

        Returns:
            ConfigValidationResult with validation status and detailed error messages
        """
        result = ConfigValidationResult.success_result()

        # Validate registry URL (required)
        if not self.registry_url:
            result.add_error("Registry URL is required")
        else:
            registry_errors = self._validate_registry_url(self.registry_url)
            for error in registry_errors:
                result.add_error(error)

        # Validate catalog URL (optional)
        if self.catalog_url:
            catalog_errors = self._validate_catalog_url(self.catalog_url)
            for error in catalog_errors:
                result.add_error(error)

        return result

    def _validate_registry_url(self, url: str) -> list[str]:
        """Validate registry URL format.

        Registry URL must be a valid S3 URL with bucket name only (no path).

        Args:
            url: Registry URL to validate

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        if not url or not url.strip():
            errors.append("Registry URL cannot be empty")
            return errors

        # Must start with s3://
        if not url.startswith("s3://"):
            errors.append(
                "Registry URL must start with 's3://' (e.g., 's3://my-bucket')"
            )
            return errors

        # Parse the URL
        try:
            parsed = urlparse(url)
        except Exception:
            errors.append("Registry URL has invalid format")
            return errors

        # Must have a bucket name
        if not parsed.netloc:
            errors.append("Registry URL must specify a bucket name (e.g., 's3://my-bucket')")
            return errors

        # Should not have a path (registry is bucket-level)
        if parsed.path and parsed.path != "/":
            errors.append(
                "Registry URL should specify bucket only, not a path "
                "(e.g., 's3://my-bucket' not 's3://my-bucket/path')"
            )

        # Validate bucket name format (basic validation)
        bucket_name = parsed.netloc
        if not self._is_valid_s3_bucket_name(bucket_name):
            errors.append(
                f"Registry bucket name '{bucket_name}' is not a valid S3 bucket name. "
                "Bucket names must be 3-63 characters, contain only lowercase letters, "
                "numbers, periods, and hyphens, and not start/end with periods or hyphens."
            )

        return errors

    def _validate_catalog_url(self, url: str) -> list[str]:
        """Validate catalog URL format.

        Catalog URL must be a valid HTTP or HTTPS URL.

        Args:
            url: Catalog URL to validate

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        if not url or not url.strip():
            # Catalog URL is optional, so empty is not an error
            return errors

        # Must be HTTP or HTTPS
        if not (url.startswith("http://") or url.startswith("https://")):
            errors.append(
                "Catalog URL must start with 'http://' or 'https://' "
                "(e.g., 'https://catalog.example.com')"
            )
            return errors

        # Parse the URL
        try:
            parsed = urlparse(url)
        except Exception:
            errors.append("Catalog URL has invalid format")
            return errors

        # Must have a hostname
        if not parsed.netloc:
            errors.append(
                "Catalog URL must specify a hostname "
                "(e.g., 'https://catalog.example.com')"
            )

        return errors

    def _is_valid_s3_bucket_name(self, bucket_name: str) -> bool:
        """Check if bucket name follows S3 naming rules.

        Basic validation for S3 bucket names:
        - 3-63 characters long
        - Only lowercase letters, numbers, periods, and hyphens
        - Must start and end with letter or number
        - Cannot have consecutive periods

        Args:
            bucket_name: Bucket name to validate

        Returns:
            True if bucket name is valid, False otherwise
        """
        if not bucket_name or len(bucket_name) < 3 or len(bucket_name) > 63:
            return False

        # Must start and end with alphanumeric
        if not (bucket_name[0].isalnum() and bucket_name[-1].isalnum()):
            return False

        # Only allowed characters
        if not re.match(r'^[a-z0-9.\-]+$', bucket_name):
            return False

        # No consecutive periods
        if '..' in bucket_name:
            return False

        return True

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary for serialization.

        Returns:
            Dictionary representation of configuration with all non-None values

        Raises:
            SerializationError: If configuration cannot be serialized
        """
        try:
            result = {}

            if self.registry_url is not None:
                result["registry_url"] = self.registry_url

            if self.catalog_url is not None:
                result["catalog_url"] = self.catalog_url

            return result

        except Exception as e:
            raise SerializationError(f"Failed to serialize Quilt3Config: {e}")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Quilt3Config':
        """Create Quilt3Config from dictionary data.

        Args:
            data: Dictionary containing configuration data

        Returns:
            New Quilt3Config instance

        Raises:
            SerializationError: If data cannot be deserialized
        """
        try:
            return cls(
                registry_url=data.get("registry_url"),
                catalog_url=data.get("catalog_url")
            )
        except Exception as e:
            raise SerializationError(f"Failed to deserialize Quilt3Config: {e}")

    @classmethod
    def from_environment(cls) -> 'Quilt3Config':
        """Create Quilt3Config from environment variables.

        Reads configuration from:
        - QUILT_REGISTRY_URL: Registry URL
        - QUILT_CATALOG_URL: Catalog URL (optional)

        Returns:
            New Quilt3Config instance with values from environment
        """
        return cls(
            registry_url=os.environ.get("QUILT_REGISTRY_URL"),
            catalog_url=os.environ.get("QUILT_CATALOG_URL")
        )

    @classmethod
    def with_defaults(cls, **kwargs) -> 'Quilt3Config':
        """Create Quilt3Config with explicit parameters taking precedence over environment.

        This method follows the priority order:
        1. Explicit keyword arguments
        2. Environment variables
        3. None (no defaults for required fields)

        Args:
            **kwargs: Configuration parameters (registry_url, catalog_url)

        Returns:
            New Quilt3Config instance with priority-based configuration
        """
        # Start with environment variables
        env_config = cls.from_environment()

        # Override with explicit parameters
        registry_url = kwargs.get("registry_url", env_config.registry_url)
        catalog_url = kwargs.get("catalog_url", env_config.catalog_url)

        return cls(
            registry_url=registry_url,
            catalog_url=catalog_url
        )
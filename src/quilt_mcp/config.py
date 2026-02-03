"""Configuration for MCP resources."""

import os


class ResourceConfig:
    """Configuration for MCP resources."""

    # Enable/disable resource framework
    RESOURCES_ENABLED: bool = os.getenv("QUILT_MCP_RESOURCES_ENABLED", "true").lower() == "true"

    # Resource cache TTL (seconds)
    RESOURCE_CACHE_TTL: int = int(os.getenv("QUILT_MCP_RESOURCE_CACHE_TTL", "300"))

    # Enable resource caching
    RESOURCE_CACHE_ENABLED: bool = os.getenv("QUILT_MCP_RESOURCE_CACHE_ENABLED", "false").lower() == "true"

    # Log resource access
    RESOURCE_ACCESS_LOGGING: bool = os.getenv("QUILT_MCP_RESOURCE_ACCESS_LOGGING", "true").lower() == "true"


class HttpConfig:
    """Configuration for HTTP requests."""

    # Timeout for all service HTTP requests (seconds)
    # Used for GraphQL queries, catalog API calls, and other HTTP operations
    SERVICE_TIMEOUT: int = int(os.getenv("QUILT_SERVICE_TIMEOUT", "60"))


# Global config instances
resource_config = ResourceConfig()
http_config = HttpConfig()

# Mode Configuration Management

from typing import List, Literal, Optional


class ConfigurationError(Exception):
    """Raised when configuration validation fails."""

    pass


class ModeConfig:
    """Centralized mode configuration management.

    This singleton class manages all deployment mode decisions through a single
    boolean environment variable QUILT_MULTIUSER_MODE, providing properties
    for all mode-related decisions and validation of required configuration.
    """

    def __init__(self, multiuser_mode: Optional[bool] = None):
        """Initialize ModeConfig with environment variable parsing.

        Args:
            multiuser_mode: Override for testing. If None, reads from environment.
        """
        if multiuser_mode is not None:
            self._multiuser_mode = multiuser_mode
        else:
            self._multiuser_mode = self._parse_bool(os.getenv("QUILT_MULTIUSER_MODE"), default=False)

    @staticmethod
    def _parse_bool(value: Optional[str], default: bool = False) -> bool:
        """Parse boolean environment variable value."""
        if value is None:
            return default
        return value.lower() in ("true", "1", "yes", "on")

    @property
    def is_multiuser(self) -> bool:
        """True if running in multiuser production mode."""
        return self._multiuser_mode

    @property
    def is_local_dev(self) -> bool:
        """True if running in local development mode."""
        return not self._multiuser_mode

    @property
    def backend_type(self) -> Literal["quilt3", "graphql"]:
        """Backend type based on deployment mode."""
        return "graphql" if self.is_multiuser else "quilt3"

    @property
    def requires_jwt(self) -> bool:
        """True if JWT authentication is required."""
        return self.is_multiuser

    @property
    def allows_filesystem_state(self) -> bool:
        """True if filesystem state persistence is allowed."""
        return self.is_local_dev

    @property
    def allows_quilt3_library(self) -> bool:
        """True if quilt3 library session usage is allowed."""
        return self.is_local_dev

    @property
    def tenant_mode(self) -> Literal["single-user", "multiuser"]:
        """Tenant mode for context factory."""
        return "multiuser" if self.is_multiuser else "single-user"

    @property
    def requires_graphql(self) -> bool:
        """True if GraphQL backend is required."""
        return self.is_multiuser

    @property
    def default_transport(self) -> Literal["stdio", "http"]:
        """Default transport protocol based on deployment mode."""
        return "http" if self.is_multiuser else "stdio"

    def validate(self) -> None:
        """Validate configuration for current mode.

        Raises:
            ConfigurationError: When configuration validation fails
        """
        errors = self.get_validation_errors()
        if errors:
            raise ConfigurationError(f"Invalid configuration: {'; '.join(errors)}")

    def get_validation_errors(self) -> List[str]:
        """Return list of configuration validation errors."""
        errors = []
        if self.is_multiuser:
            errors.extend(self._get_multiuser_validation_errors())
        return errors

    def _get_multiuser_validation_errors(self) -> List[str]:
        """Get validation errors specific to multiuser mode."""
        errors = []

        # Check required JWT configuration
        if not os.getenv("MCP_JWT_SECRET"):
            errors.append("Multiuser mode requires MCP_JWT_SECRET environment variable")

        if not os.getenv("MCP_JWT_ISSUER"):
            errors.append("Multiuser mode requires MCP_JWT_ISSUER environment variable")

        if not os.getenv("MCP_JWT_AUDIENCE"):
            errors.append("Multiuser mode requires MCP_JWT_AUDIENCE environment variable")

        if not os.getenv("QUILT_CATALOG_URL"):
            errors.append("Multiuser mode requires QUILT_CATALOG_URL environment variable")

        if not os.getenv("QUILT_REGISTRY_URL"):
            errors.append("Multiuser mode requires QUILT_REGISTRY_URL environment variable")

        return errors


# Global singleton instance
_mode_config_instance: Optional[ModeConfig] = None


def get_mode_config() -> ModeConfig:
    """Get singleton ModeConfig instance."""
    global _mode_config_instance
    if _mode_config_instance is None:
        _mode_config_instance = ModeConfig()
    return _mode_config_instance


def reset_mode_config() -> None:
    """Reset ModeConfig singleton (used in tests)."""
    global _mode_config_instance
    _mode_config_instance = None


def create_test_mode_config(multiuser_mode: bool) -> ModeConfig:
    """Create a ModeConfig instance for testing without affecting the singleton.

    Args:
        multiuser_mode: Whether to enable multiuser mode

    Returns:
        ModeConfig instance configured for testing
    """
    return ModeConfig(multiuser_mode=multiuser_mode)


def set_test_mode_config(multiuser_mode: bool) -> None:
    """Set a test ModeConfig instance as the singleton (used in tests).

    Args:
        multiuser_mode: Whether to enable multiuser mode
    """
    global _mode_config_instance
    _mode_config_instance = ModeConfig(multiuser_mode=multiuser_mode)

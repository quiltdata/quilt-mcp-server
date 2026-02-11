"""Configuration for MCP resources."""

import os
from typing import List, Literal, Optional


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


class ConfigurationError(Exception):
    """Raised when configuration validation fails."""

    pass


class ModeConfig:
    """Centralized mode configuration management.

    This singleton class manages all deployment mode decisions through a single
    boolean environment variable QUILT_MULTIUSER_MODE, providing properties
    for all mode-related decisions and validation of required configuration.
    """

    def __init__(self, multiuser_mode: Optional[bool] = None, backend_override: Optional[str] = None):
        """Initialize ModeConfig with environment variable parsing.

        Args:
            multiuser_mode: Override for testing. If None, reads from environment.
            backend_override: Explicit backend selection ("quilt3" or "platform").
        """
        self._backend_override_input = backend_override
        self._backend_type, self._backend_selection_source = self._select_backend(
            multiuser_mode=multiuser_mode,
            backend_override=backend_override,
        )

    @staticmethod
    def _parse_bool(value: Optional[str], default: bool = False) -> bool:
        """Parse boolean environment variable value."""
        if value is None:
            return default
        return value.lower() in ("true", "1", "yes", "on")

    @staticmethod
    def _normalize_backend(backend: str) -> Literal["quilt3", "graphql"]:
        """Normalize user-facing backend names to internal backend types."""
        normalized = backend.lower().strip()
        if normalized == "platform":
            return "graphql"
        if normalized in {"quilt3", "graphql"}:
            return normalized  # type: ignore[return-value]
        raise ConfigurationError(f"Invalid backend '{backend}'. Expected one of: quilt3, platform")

    @classmethod
    def _select_backend(
        cls,
        multiuser_mode: Optional[bool],
        backend_override: Optional[str],
    ) -> tuple[Literal["quilt3", "graphql"], Literal["cli", "legacy-env", "default", "test"]]:
        """Resolve backend with precedence: explicit override > legacy env > default."""
        if backend_override is not None:
            return cls._normalize_backend(backend_override), "cli"

        if multiuser_mode is not None:
            return ("graphql" if multiuser_mode else "quilt3"), "test"

        legacy_mode = os.getenv("QUILT_MULTIUSER_MODE")
        if legacy_mode is not None:
            return ("graphql" if cls._parse_bool(legacy_mode) else "quilt3"), "legacy-env"

        return "graphql", "default"

    @property
    def is_multiuser(self) -> bool:
        """True if running in multiuser production mode."""
        return self.backend_type == "graphql"

    @property
    def is_local_dev(self) -> bool:
        """True if running in local development mode."""
        return self.backend_type == "quilt3"

    @property
    def backend_type(self) -> Literal["quilt3", "graphql"]:
        """Backend type based on deployment mode."""
        return self._backend_type

    @property
    def backend_name(self) -> Literal["quilt3", "platform"]:
        """User-facing backend name."""
        return "platform" if self.backend_type == "graphql" else "quilt3"

    @property
    def backend_selection_source(self) -> Literal["cli", "legacy-env", "default", "test"]:
        """Source that determined backend selection."""
        return self._backend_selection_source

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
    def requires_graphql(self) -> bool:
        """True if GraphQL backend is required."""
        return self.backend_type == "graphql"

    @property
    def default_transport(self) -> Literal["stdio", "http"]:
        """Default transport protocol for MCP server.

        Returns stdio by default (MCP protocol standard for CLI tools).
        Docker deployments override to http via FASTMCP_TRANSPORT environment variable.
        """
        return "stdio"

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
        """Get validation errors for platform backend mode."""
        errors = []

        if not os.getenv("QUILT_CATALOG_URL"):
            errors.append("Platform backend requires QUILT_CATALOG_URL environment variable")

        if not os.getenv("QUILT_REGISTRY_URL"):
            errors.append("Platform backend requires QUILT_REGISTRY_URL environment variable")

        return errors


# Global singleton instance
_mode_config_instance: Optional[ModeConfig] = None


def get_mode_config(backend_override: Optional[str] = None) -> ModeConfig:
    """Get singleton ModeConfig instance."""
    global _mode_config_instance
    if _mode_config_instance is None or (
        backend_override is not None and _mode_config_instance._backend_override_input != backend_override
    ):
        _mode_config_instance = ModeConfig(backend_override=backend_override)
    return _mode_config_instance


def reset_mode_config() -> None:
    """Reset ModeConfig singleton (used in tests)."""
    global _mode_config_instance
    _mode_config_instance = None


def create_test_mode_config(multiuser_mode: bool, backend_override: Optional[str] = None) -> ModeConfig:
    """Create a ModeConfig instance for testing without affecting the singleton.

    Args:
        multiuser_mode: Whether to enable multiuser mode

    Returns:
        ModeConfig instance configured for testing
    """
    return ModeConfig(multiuser_mode=multiuser_mode, backend_override=backend_override)


def set_test_mode_config(multiuser_mode: bool, backend_override: Optional[str] = None) -> None:
    """Set a test ModeConfig instance as the singleton (used in tests).

    Args:
        multiuser_mode: Whether to enable multiuser mode
    """
    global _mode_config_instance
    _mode_config_instance = ModeConfig(multiuser_mode=multiuser_mode, backend_override=backend_override)

"""Configuration for MCP resources."""

import os
from enum import Enum
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


class DeploymentMode(str, Enum):
    """High-level deployment mode presets."""

    REMOTE = "remote"
    LOCAL = "local"
    LEGACY = "legacy"


class ModeConfig:
    """Centralized mode configuration management.

    This singleton class manages deployment mode decisions through high-level
    deployment presets while preserving backward compatibility with legacy envs.
    """

    def __init__(
        self,
        multiuser_mode: Optional[bool] = None,
        backend_override: Optional[str] = None,
        deployment_mode: Optional[str | DeploymentMode] = None,
    ):
        """Initialize ModeConfig with environment variable parsing.

        Args:
            multiuser_mode: Override for testing. If None, reads from environment.
            backend_override: Explicit backend selection ("quilt3" or "platform").
            deployment_mode: Explicit deployment selection ("remote", "local", "legacy").
        """
        self._backend_override_input = backend_override
        self._deployment_override_input = deployment_mode
        self._deployment_mode, self._deployment_selection_source = self._resolve_deployment(
            deployment_mode=deployment_mode,
            multiuser_mode=multiuser_mode,
            backend_override=backend_override,
        )
        mode_backend, mode_transport = self._resolve_mode_backend_transport(self._deployment_mode)
        self._backend_type, self._backend_selection_source = self._select_backend(
            multiuser_mode=multiuser_mode,
            backend_override=backend_override,
            mode_backend=mode_backend,
            deployment_selection_source=self._deployment_selection_source,
        )
        self._default_transport = mode_transport

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

    @staticmethod
    def _parse_deployment_mode(
        deployment_mode: str | DeploymentMode,
    ) -> DeploymentMode:
        """Parse deployment mode from string or enum."""
        if isinstance(deployment_mode, DeploymentMode):
            return deployment_mode

        normalized = deployment_mode.lower().strip()
        try:
            return DeploymentMode(normalized)
        except ValueError as exc:
            raise ConfigurationError(
                f"Invalid deployment mode '{deployment_mode}'. Expected one of: remote, local, legacy"
            ) from exc

    @classmethod
    def _resolve_deployment(
        cls,
        deployment_mode: Optional[str | DeploymentMode],
        multiuser_mode: Optional[bool],
        backend_override: Optional[str],
    ) -> tuple[DeploymentMode, Literal["deployment-cli", "deployment-env", "legacy-env", "default", "test", "cli"]]:
        """Resolve deployment with precedence:
        explicit deployment > QUILT_DEPLOYMENT > explicit backend > legacy env > default.
        """
        if deployment_mode is not None:
            return cls._parse_deployment_mode(deployment_mode), "deployment-cli"

        env_deployment = os.getenv("QUILT_DEPLOYMENT")
        if env_deployment:
            return cls._parse_deployment_mode(env_deployment), "deployment-env"

        if multiuser_mode is not None:
            return (DeploymentMode.LOCAL if multiuser_mode else DeploymentMode.LEGACY), "test"

        if backend_override is not None:
            normalized_backend = cls._normalize_backend(backend_override)
            return (DeploymentMode.LOCAL if normalized_backend == "graphql" else DeploymentMode.LEGACY), "cli"

        legacy_mode = os.getenv("QUILT_MULTIUSER_MODE")
        if legacy_mode is not None:
            return (DeploymentMode.LOCAL if cls._parse_bool(legacy_mode) else DeploymentMode.LEGACY), "legacy-env"

        return DeploymentMode.LOCAL, "default"

    @staticmethod
    def _resolve_mode_backend_transport(
        deployment_mode: DeploymentMode,
    ) -> tuple[Literal["quilt3", "graphql"], Literal["stdio", "http"]]:
        """Resolve backend and default transport from deployment mode."""
        if deployment_mode == DeploymentMode.REMOTE:
            return "graphql", "http"
        if deployment_mode == DeploymentMode.LOCAL:
            return "graphql", "stdio"
        return "quilt3", "stdio"

    @classmethod
    def _select_backend(
        cls,
        multiuser_mode: Optional[bool],
        backend_override: Optional[str],
        mode_backend: Literal["quilt3", "graphql"],
        deployment_selection_source: Literal[
            "deployment-cli",
            "deployment-env",
            "legacy-env",
            "default",
            "test",
            "cli",
        ],
    ) -> tuple[
        Literal["quilt3", "graphql"],
        Literal["cli", "deployment-cli", "deployment-env", "legacy-env", "default", "test"],
    ]:
        """Resolve backend with precedence: explicit override > deployment preset."""
        if backend_override is not None:
            return cls._normalize_backend(backend_override), "cli"
        if multiuser_mode is not None:
            return mode_backend, "test"
        if deployment_selection_source in {"deployment-cli", "deployment-env", "legacy-env", "default"}:
            return mode_backend, deployment_selection_source
        return mode_backend, "default"

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
    def backend_selection_source(
        self,
    ) -> Literal["cli", "deployment-cli", "deployment-env", "legacy-env", "default", "test"]:
        """Source that determined backend selection."""
        return self._backend_selection_source

    @property
    def deployment_mode(self) -> DeploymentMode:
        """Resolved deployment mode."""
        return self._deployment_mode

    @property
    def deployment_selection_source(
        self,
    ) -> Literal["deployment-cli", "deployment-env", "legacy-env", "default", "test", "cli"]:
        """Source that determined deployment selection."""
        return self._deployment_selection_source

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
        """Default transport protocol for MCP server from deployment mode."""
        return self._default_transport

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


def get_mode_config(
    backend_override: Optional[str] = None,
    deployment_mode: Optional[str | DeploymentMode] = None,
) -> ModeConfig:
    """Get singleton ModeConfig instance."""
    global _mode_config_instance
    if (
        _mode_config_instance is None
        or (backend_override is not None and _mode_config_instance._backend_override_input != backend_override)
        or (deployment_mode is not None and _mode_config_instance._deployment_override_input != deployment_mode)
    ):
        _mode_config_instance = ModeConfig(backend_override=backend_override, deployment_mode=deployment_mode)
    return _mode_config_instance


def reset_mode_config() -> None:
    """Reset ModeConfig singleton (used in tests)."""
    global _mode_config_instance
    _mode_config_instance = None


def create_test_mode_config(
    multiuser_mode: bool,
    backend_override: Optional[str] = None,
    deployment_mode: Optional[str | DeploymentMode] = None,
) -> ModeConfig:
    """Create a ModeConfig instance for testing without affecting the singleton.

    Args:
        multiuser_mode: Whether to enable multiuser mode

    Returns:
        ModeConfig instance configured for testing
    """
    return ModeConfig(
        multiuser_mode=multiuser_mode,
        backend_override=backend_override,
        deployment_mode=deployment_mode,
    )


def set_test_mode_config(
    multiuser_mode: bool,
    backend_override: Optional[str] = None,
    deployment_mode: Optional[str | DeploymentMode] = None,
) -> None:
    """Set a test ModeConfig instance as the singleton (used in tests).

    Args:
        multiuser_mode: Whether to enable multiuser mode
    """
    global _mode_config_instance
    _mode_config_instance = ModeConfig(
        multiuser_mode=multiuser_mode,
        backend_override=backend_override,
        deployment_mode=deployment_mode,
    )

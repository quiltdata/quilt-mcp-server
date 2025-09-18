"""Configuration framework for Quilt MCP Server.

This module provides a flexible configuration system that supports:
- Environment variable integration
- Configuration validation with clear error messages
- Serialization for debugging and persistence
- Extensible architecture for different configuration types

The configuration framework follows these principles:
- Type safety with comprehensive validation
- Clear error messages with actionable guidance
- No dependencies on global state
- Consistent API across all configuration types

Example usage:
    from quilt_mcp.config.quilt3 import Quilt3Config

    # Create configuration from environment
    config = Quilt3Config.from_environment()

    # Validate configuration
    result = config.validate()
    if not result.success:
        for error in result.errors:
            print(f"Configuration error: {error}")

    # Serialize for debugging
    config_dict = config.to_dict()
"""

from __future__ import annotations

# Re-export main configuration classes for easy access
from .base import (
    Configuration,
    ConfigValidationResult,
    ConfigurationError,
    ValidationError,
    SerializationError,
)

# Re-export Quilt3-specific configuration
from .quilt3 import Quilt3Config

__all__ = [
    "Configuration",
    "ConfigValidationResult",
    "ConfigurationError",
    "ValidationError",
    "SerializationError",
    "Quilt3Config",
]
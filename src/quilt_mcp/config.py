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

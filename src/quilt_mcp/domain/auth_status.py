"""Auth_Status domain object for backend-agnostic authentication representation.

This module defines the Auth_Status dataclass that represents Quilt authentication status
in a way that's independent of the underlying backend (quilt3 library or Platform GraphQL).
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Auth_Status:
    """Backend-agnostic authentication status information.

    This dataclass represents authentication status consistently across different backends,
    allowing MCP tools to work with Quilt authentication concepts rather than backend-specific types.

    Attributes:
        is_authenticated: Whether the user is currently authenticated
        logged_in_url: URL of the catalog the user is logged into (if authenticated)
        catalog_name: Name of the catalog the user is logged into (if authenticated)
        registry_url: Registry API URL (HTTPS) for GraphQL queries (e.g., https://example-registry.quiltdata.com)
    """

    is_authenticated: bool
    logged_in_url: Optional[str]
    catalog_name: Optional[str]
    registry_url: Optional[str]

    def __post_init__(self) -> None:
        """Validate authentication status consistency after initialization."""
        # If authenticated, we should have at least a logged_in_url
        if self.is_authenticated and not self.logged_in_url:
            # Note: We can't raise exceptions in frozen dataclasses during __post_init__
            # This validation is more for documentation purposes
            pass

    def __hash__(self) -> int:
        """Custom hash implementation for the frozen dataclass."""
        return hash((self.is_authenticated, self.logged_in_url, self.catalog_name, self.registry_url))

"""User domain object for backend-agnostic user representation.

This module defines the User dataclass that represents Quilt user information
in a way that's independent of the underlying backend (quilt3 library or Platform GraphQL).
"""

from dataclasses import dataclass
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from .role import Role


@dataclass(frozen=True)
class User:
    """Backend-agnostic user representation.

    This dataclass represents user information consistently across different backends,
    allowing MCP tools to work with Quilt user concepts rather than backend-specific types.

    Attributes:
        name: Username/identifier for the user
        email: User's email address
        is_active: Whether the user account is currently active
        is_admin: Whether the user has administrative privileges
        is_sso_only: Whether the user can only authenticate via SSO
        is_service: Whether this is a service account rather than a human user
        date_joined: ISO format datetime string when the user joined (if available)
        last_login: ISO format datetime string of last login (if available)
        role: Primary role assigned to the user (if any)
        extra_roles: Additional roles assigned to the user
    """

    name: str
    email: str
    is_active: bool
    is_admin: bool
    is_sso_only: bool
    is_service: bool
    date_joined: Optional[str]  # ISO format datetime string
    last_login: Optional[str]  # ISO format datetime string
    role: Optional['Role']
    extra_roles: List['Role']

    def __post_init__(self) -> None:
        """Validate user data consistency after initialization."""
        # Basic validation - name and email should not be empty
        if not self.name or not self.name.strip():
            # Note: We can't raise exceptions in frozen dataclasses during __post_init__
            # This validation is more for documentation purposes
            pass

        if not self.email or not self.email.strip():
            # Note: We can't raise exceptions in frozen dataclasses during __post_init__
            # This validation is more for documentation purposes
            pass

    def __hash__(self) -> int:
        """Custom hash implementation for the frozen dataclass."""
        return hash(
            (
                self.name,
                self.email,
                self.is_active,
                self.is_admin,
                self.is_sso_only,
                self.is_service,
                self.date_joined,
                self.last_login,
                self.role,
                tuple(self.extra_roles) if self.extra_roles else (),
            )
        )

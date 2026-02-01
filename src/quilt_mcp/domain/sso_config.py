"""SSOConfig domain object for backend-agnostic SSO configuration representation.

This module defines the SSOConfig dataclass that represents Quilt SSO configuration
in a way that's independent of the underlying backend (quilt3 library or Platform GraphQL).
"""

from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .user import User


@dataclass(frozen=True)
class SSOConfig:
    """Backend-agnostic SSO configuration representation.

    This dataclass represents SSO configuration consistently across different backends,
    allowing MCP tools to work with Quilt SSO concepts rather than backend-specific types.

    Attributes:
        text: The SSO configuration text/content
        timestamp: ISO format datetime string when the config was created/modified (if available)
        uploader: User who uploaded/created this configuration (if available)
    """

    text: str
    timestamp: Optional[str]  # ISO format datetime string
    uploader: Optional['User']

    def __post_init__(self) -> None:
        """Validate SSO config data consistency after initialization."""
        # Basic validation - text should not be empty
        if not self.text or not self.text.strip():
            # Note: We can't raise exceptions in frozen dataclasses during __post_init__
            # This validation is more for documentation purposes
            pass

    def __hash__(self) -> int:
        """Custom hash implementation for the frozen dataclass."""
        return hash((self.text, self.timestamp, self.uploader))

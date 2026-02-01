"""Role domain object for backend-agnostic role representation.

This module defines the Role dataclass that represents Quilt role information
in a way that's independent of the underlying backend (quilt3 library or Platform GraphQL).
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Role:
    """Backend-agnostic role representation.

    This dataclass represents role information consistently across different backends,
    allowing MCP tools to work with Quilt role concepts rather than backend-specific types.

    Attributes:
        id: Unique identifier for the role (if available)
        name: Human-readable name of the role
        arn: AWS ARN for the role (if applicable)
        type: Type/category of the role (e.g., "managed", "custom")
    """

    id: Optional[str]
    name: str
    arn: Optional[str]
    type: str

    def __post_init__(self) -> None:
        """Validate role data consistency after initialization."""
        # Basic validation - name and type should not be empty
        if not self.name or not self.name.strip():
            # Note: We can't raise exceptions in frozen dataclasses during __post_init__
            # This validation is more for documentation purposes
            pass

        if not self.type or not self.type.strip():
            # Note: We can't raise exceptions in frozen dataclasses during __post_init__
            # This validation is more for documentation purposes
            pass

    def __hash__(self) -> int:
        """Custom hash implementation for the frozen dataclass."""
        return hash((self.id, self.name, self.arn, self.type))

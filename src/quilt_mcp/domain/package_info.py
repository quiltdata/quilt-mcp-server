"""Package_Info domain object for backend-agnostic package representation.

This module defines the Package_Info dataclass that represents Quilt package metadata
in a way that's independent of the underlying backend (quilt3 library or Platform GraphQL).
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class Package_Info:
    """Backend-agnostic package information.

    This dataclass represents package metadata consistently across different backends,
    allowing MCP tools to work with Quilt concepts rather than backend-specific types.

    Attributes:
        name: Package name (e.g., "user/package-name")
        description: Optional package description
        tags: List of tags associated with the package
        modified_date: ISO 8601 formatted modification date
        registry: Registry URL where the package is stored
        bucket: S3 bucket name containing the package
        top_hash: Hash identifying the package version
    """

    name: str
    description: Optional[str]
    tags: List[str]
    modified_date: str
    registry: str
    bucket: str
    top_hash: str

    def __post_init__(self) -> None:
        """Validate required fields after initialization."""
        # All validation is handled by dataclass field requirements
        # Optional validation logic could be added here if needed
        pass

    def __hash__(self) -> int:
        """Custom hash implementation that handles the tags list."""
        return hash(
            (
                self.name,
                self.description,
                tuple(self.tags),  # Convert list to tuple for hashing
                self.modified_date,
                self.registry,
                self.bucket,
                self.top_hash,
            )
        )

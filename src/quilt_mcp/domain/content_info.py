"""Content_Info domain object for backend-agnostic content representation.

This module defines the Content_Info dataclass that represents Quilt content/file metadata
in a way that's independent of the underlying backend (quilt3 library or Platform GraphQL).
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Content_Info:
    """Backend-agnostic content information.

    This dataclass represents content metadata consistently across different backends,
    allowing MCP tools to work with Quilt concepts rather than backend-specific types.

    Attributes:
        path: File or directory path within the package
        size: File size in bytes (None for directories or unknown)
        type: Content type ('file' or 'directory')
        modified_date: ISO 8601 formatted modification date (optional)
        download_url: URL for downloading the content (optional)
    """

    path: str
    size: Optional[int]
    type: str
    modified_date: Optional[str]
    download_url: Optional[str]

    def __post_init__(self) -> None:
        """Validate required fields after initialization."""
        # All validation is handled by dataclass field requirements
        # Optional validation logic could be added here if needed
        pass

    def __hash__(self) -> int:
        """Custom hash implementation for hashable dataclass."""
        return hash((
            self.path,
            self.size,
            self.type,
            self.modified_date,
            self.download_url
        ))

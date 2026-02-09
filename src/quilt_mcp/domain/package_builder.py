"""Package builder domain objects for internal package construction.

This module defines typed structures for building packages in a backend-agnostic way.
Both Quilt3_Backend and Platform_Backend use these structures internally, converting
to their native formats only during push operations.
"""

from typing import TypedDict, Any, NotRequired


class PackageEntry(TypedDict):
    """Internal representation of a package entry during construction.

    Attributes:
        logicalKey: Logical path within the package (e.g., "data/file.csv") - required
        physicalKey: S3 URI of the file (e.g., "s3://bucket/path/file.csv") - required
        hash: Content hash (computed during push, None during construction) - optional
        size: File size in bytes (computed during push, None during construction) - optional
        meta: Entry-level metadata dictionary - optional
    """

    logicalKey: str
    physicalKey: str
    hash: NotRequired[str | None]
    size: NotRequired[int | None]
    meta: NotRequired[dict[str, Any] | None]


class PackageBuilder(TypedDict):
    """Internal representation of a package during construction.

    This structure represents a package being built before it's pushed to the registry.
    Backends maintain this structure during package construction and convert it to
    their native format (quilt3.Package or GraphQL mutation) during push.

    Attributes:
        entries: List of package entries to include (required)
        metadata: Package-level metadata dictionary (optional)
    """

    entries: list[PackageEntry]
    metadata: NotRequired[dict[str, Any]]

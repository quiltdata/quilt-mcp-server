"""Scope handlers for Elasticsearch search - Strategy Pattern.

Each handler encapsulates the logic for a specific search scope:
- FileScopeHandler: Searches only file/object indices
- PackageEntryScopeHandler: Searches only package entry indices
- GlobalScopeHandler: Searches both file and package indices
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional

from .base import SearchResult

logger = logging.getLogger(__name__)


class ScopeHandler(ABC):
    """Abstract base class for scope-specific search handlers."""

    @abstractmethod
    def build_index_pattern(self, buckets: List[str]) -> str:
        """Build Elasticsearch index pattern for this scope.

        Args:
            buckets: List of bucket names (already normalized)

        Returns:
            Comma-separated index pattern string

        Raises:
            ValueError: If buckets list is empty
        """
        pass

    @abstractmethod
    def parse_result(self, hit: Dict[str, Any], bucket_name: str) -> Optional[SearchResult]:
        """Parse a search result hit into a SearchResult.

        Args:
            hit: Elasticsearch hit document
            bucket_name: Bucket name extracted from index

        Returns:
            SearchResult or None if parsing fails
        """
        pass

    @abstractmethod
    def get_expected_result_type(self) -> str:
        """Get the expected result type for this scope.

        Returns:
            Result type string ("file", "packageEntry", or "mixed")
        """
        pass


class FileScopeHandler(ScopeHandler):
    """Handler for file-only searches."""

    def build_index_pattern(self, buckets: List[str]) -> str:
        """Build index pattern for file indices only.

        Example:
            ["bucket1", "bucket2"] -> "bucket1,bucket2"
        """
        if not buckets:
            raise ValueError("Cannot build index pattern: bucket list is empty")
        return ",".join(buckets)

    def parse_result(self, hit: Dict[str, Any], bucket_name: str) -> Optional[SearchResult]:
        """Parse a file result from Elasticsearch hit."""
        source = hit.get("_source", {})
        index_name = hit.get("_index", "")

        # File result
        key = source.get("key", "")
        size = source.get("size", 0)
        last_modified = source.get("last_modified", "")
        content_type = source.get("content_type") or source.get("contentType") or ""

        # Extract extension
        extension = ""
        if key and "." in key:
            extension = key.rsplit(".", 1)[-1]
        else:
            ext_from_source = source.get("ext", "")
            if ext_from_source:
                extension = ext_from_source.lstrip(".")

        # Construct S3 URI
        s3_uri = f"s3://{bucket_name}/{key}" if key else None

        return SearchResult(
            id=hit.get("_id", ""),
            type="file",
            name=key,
            title=key.split("/")[-1] if key else "Unknown",
            description=f"Object in {bucket_name}",
            s3_uri=s3_uri,
            size=size,
            last_modified=last_modified,
            metadata={
                **source,
                "_index": index_name,
            },
            score=hit.get("_score", 0.0),
            backend="elasticsearch",
            bucket=bucket_name,
            content_type=content_type,
            extension=extension,
        )

    def get_expected_result_type(self) -> str:
        return "file"


class PackageEntryScopeHandler(ScopeHandler):
    """Handler for package ENTRY searches ONLY.

    IMPORTANT: This handler ONLY processes package ENTRY documents, not manifest documents.
    Package entries have fields: entry_pk, entry_lk, entry_hash, entry_size

    Manifest documents (ptr_name, mnfst_name) are handled by PackageHandler (currently disabled).
    """

    def build_index_pattern(self, buckets: List[str]) -> str:
        """Build index pattern for package indices only.

        Example:
            ["bucket1", "bucket2"] -> "bucket1_packages,bucket2_packages"
        """
        if not buckets:
            raise ValueError("Cannot build index pattern: bucket list is empty")
        return ",".join(f"{b}_packages" for b in buckets)

    def parse_result(self, hit: Dict[str, Any], bucket_name: str) -> Optional[SearchResult]:
        """Parse a package ENTRY result from Elasticsearch hit.

        CRITICAL: This ONLY parses ENTRY documents (entry_pk, entry_lk).
        Manifest documents (ptr_name, mnfst_name) are REJECTED and return None.
        """
        source = hit.get("_source", {})
        index_name = hit.get("_index", "")

        # ONLY parse ENTRY documents - reject manifests
        # entry_pk format: "package_name@hash" or just "package_name"
        entry_pk = source.get("entry_pk", "")
        entry_lk = source.get("entry_lk", "")

        # Extract package name from entry fields ONLY
        package_name = ""
        if entry_pk:
            # Extract package name (everything before @ if present)
            package_name = entry_pk.split("@")[0] if "@" in entry_pk else entry_pk
        elif entry_lk:
            # entry_lk is the logical key (file path within package)
            # Package name is NOT in entry_lk, it's in entry_pk
            # If we only have entry_lk, we can't determine package name
            logger.debug(
                f"Entry document has entry_lk but no entry_pk. Cannot determine package name. "
                f"Document ID: {hit.get('_id', 'unknown')}"
            )
            return None

        # VALIDATION: Entry documents MUST have entry_pk or entry_lk
        if not entry_pk and not entry_lk:
            # This is likely a manifest document - reject it
            if source.get("ptr_name") or source.get("mnfst_name"):
                logger.debug(
                    f"Skipping manifest document (ptr_name/mnfst_name) in packageEntry scope. "
                    f"Document ID: {hit.get('_id', 'unknown')}"
                )
            else:
                logger.error(
                    f"PACKAGE ENTRY VALIDATION FAILED: Document from index '{index_name}' "
                    f"missing entry fields (entry_pk, entry_lk). "
                    f"Document ID: {hit.get('_id', 'unknown')}, "
                    f"Available fields: {list(source.keys())[:10]}"
                )
            return None

        # Get size from entry fields ONLY
        size = source.get("entry_size", 0)

        # Get last modified from entry metadata ONLY
        last_modified = ""
        if "entry_metadata" in source:
            entry_metadata = source.get("entry_metadata", {})
            if isinstance(entry_metadata, dict):
                last_modified = entry_metadata.get("last_modified", "")

        # Get hash from entry fields ONLY
        entry_hash = source.get("entry_hash", "")

        # Construct S3 URI for the entry file (NOT the package manifest)
        # entry_lk is the file path within the package
        s3_uri = None
        if bucket_name and entry_lk:
            # Entries point to actual data files in the bucket
            s3_uri = f"s3://{bucket_name}/{entry_lk}"

        return SearchResult(
            id=hit.get("_id", ""),
            type="packageEntry",
            name=entry_lk or entry_pk,  # Use logical key (file path) as name
            title=entry_lk.split("/")[-1] if entry_lk else entry_pk,  # Use filename as title
            description=f"Package entry: {package_name}" if package_name else "Package entry",
            s3_uri=s3_uri,
            size=size,
            last_modified=last_modified,
            metadata={
                **source,
                "_index": index_name,
                "package_name": package_name,  # Add extracted package name to metadata
            },
            score=hit.get("_score", 0.0),
            backend="elasticsearch",
            bucket=bucket_name,
            content_type="",  # Entry can be any file type
            extension=entry_lk.rsplit(".", 1)[-1] if entry_lk and "." in entry_lk else "",
        )

    def get_expected_result_type(self) -> str:
        return "packageEntry"


class GlobalScopeHandler(ScopeHandler):
    """Handler for global searches (both files and packages)."""

    def __init__(self):
        self.file_handler = FileScopeHandler()
        self.package_handler = PackageEntryScopeHandler()

    def build_index_pattern(self, buckets: List[str]) -> str:
        """Build index pattern for both file and package indices.

        Example:
            ["bucket1"] -> "bucket1,bucket1_packages"
        """
        if not buckets:
            raise ValueError("Cannot build index pattern: bucket list is empty")

        file_indices = buckets
        package_indices = [f"{b}_packages" for b in buckets]
        return ",".join(file_indices + package_indices)

    def parse_result(self, hit: Dict[str, Any], bucket_name: str) -> Optional[SearchResult]:
        """Parse either file or package result based on index name."""
        index_name = hit.get("_index", "")

        # Detect type from index name
        if "_packages" in index_name:
            return self.package_handler.parse_result(hit, bucket_name)
        else:
            return self.file_handler.parse_result(hit, bucket_name)

    def get_expected_result_type(self) -> str:
        return "mixed"

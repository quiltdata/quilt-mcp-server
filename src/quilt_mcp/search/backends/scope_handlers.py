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
    """Handler for package entry searches."""

    def build_index_pattern(self, buckets: List[str]) -> str:
        """Build index pattern for package indices only.

        Example:
            ["bucket1", "bucket2"] -> "bucket1_packages,bucket2_packages"
        """
        if not buckets:
            raise ValueError("Cannot build index pattern: bucket list is empty")
        return ",".join(f"{b}_packages" for b in buckets)

    def parse_result(self, hit: Dict[str, Any], bucket_name: str) -> Optional[SearchResult]:
        """Parse a package entry result from Elasticsearch hit.

        Package indices can contain two types of documents:
        1. Package manifest documents (ptr_name, mnfst_name, mnfst_hash, mnfst_stats)
        2. Package entry documents (entry_pk, entry_lk, entry_hash, entry_size)
        """
        source = hit.get("_source", {})
        index_name = hit.get("_index", "")

        # Try package manifest fields first (ptr_name, mnfst_name)
        package_name = source.get("ptr_name", source.get("mnfst_name", ""))

        # If not found, try package entry fields (entry_pk, entry_lk)
        if not package_name:
            # entry_pk format: "package_name@hash" or just "package_name"
            entry_pk = source.get("entry_pk", "")
            if entry_pk:
                # Extract package name (everything before @ if present)
                package_name = entry_pk.split("@")[0] if "@" in entry_pk else entry_pk
            else:
                # Try entry_lk (logical key) as fallback
                package_name = source.get("entry_lk", "")

        # VALIDATION: Package indices MUST have some identifier
        if not package_name:
            logger.error(
                f"PACKAGE INDEX VALIDATION FAILED: Document from index '{index_name}' "
                f"missing package identifier fields (ptr_name, mnfst_name, entry_pk, entry_lk). "
                f"Document ID: {hit.get('_id', 'unknown')}, "
                f"Available fields: {list(source.keys())[:10]}"
            )
            return None

        # Get size from either manifest stats or entry size
        size = source.get("mnfst_stats", {}).get("total_bytes", 0)
        if not size:
            size = source.get("entry_size", 0)

        # Get last modified from either manifest or entry metadata
        last_modified = source.get("mnfst_last_modified", "")
        if not last_modified and "entry_metadata" in source:
            entry_metadata = source.get("entry_metadata", {})
            if isinstance(entry_metadata, dict):
                last_modified = entry_metadata.get("last_modified", "")

        # Get hash from either manifest or entry
        mnfst_hash = source.get("mnfst_hash", source.get("entry_hash", ""))

        # Construct S3 URI for package manifest
        s3_uri = None
        if bucket_name and package_name and mnfst_hash:
            s3_uri = f"s3://{bucket_name}/.quilt/packages/{package_name}/{mnfst_hash}.jsonl"

        return SearchResult(
            id=hit.get("_id", ""),
            type="packageEntry",
            name=package_name,
            title=package_name,
            description=f"Quilt package: {package_name}",
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
            content_type="application/jsonl",
            extension="jsonl",
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

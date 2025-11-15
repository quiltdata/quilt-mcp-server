"""Simplified Elasticsearch backend for unified search.

Elasticsearch has per-bucket indices:
- Object indices: {bucket_name} (files)
- Package indices: {bucket_name}_packages (packages)

This backend simply:
1. Builds the right index pattern based on scope + bucket
2. Executes one search query
3. Normalizes results to the standard format
"""

import logging
import time
from typing import Dict, List, Any, Optional

from .base import (
    SearchBackend,
    BackendType,
    BackendStatus,
    SearchResult,
    BackendResponse,
)
from ...services.quilt_service import QuiltService
from ..exceptions import (
    AuthenticationRequired,
    BackendError,
)

logger = logging.getLogger(__name__)


def escape_elasticsearch_query(query: str) -> str:
    r"""Escape special characters in Elasticsearch query_string queries.

    Elasticsearch query_string syntax treats certain characters as operators.
    This function escapes them to allow literal searches.

    Special characters that need escaping:
    + - = && || > < ! ( ) { } [ ] ^ " ~ * ? : \ /

    Args:
        query: Raw query string

    Returns:
        Escaped query string safe for query_string queries

    Examples:
        >>> escape_elasticsearch_query("team/dataset")
        'team\\/dataset'
        >>> escape_elasticsearch_query("size>100")
        'size\\>100'
    """
    # Characters that need to be escaped in Elasticsearch query_string
    # Order matters: escape backslash first to avoid double-escaping
    special_chars = [
        '\\',
        '+',
        '-',
        '=',
        '>',
        '<',
        '!',
        '(',
        ')',
        '{',
        '}',
        '[',
        ']',
        '^',
        '"',
        '~',
        '*',
        '?',
        ':',
        '/',
    ]

    # Escape each special character with a backslash
    escaped = query
    for char in special_chars:
        escaped = escaped.replace(char, '\\' + char)

    return escaped


class Quilt3ElasticsearchBackend(SearchBackend):
    """Simplified Elasticsearch backend using quilt3 search API."""

    def __init__(self, quilt_service: Optional[QuiltService] = None):
        super().__init__(BackendType.ELASTICSEARCH)
        self.quilt_service = quilt_service or QuiltService()
        self._session_available = False

    def _initialize(self):
        """Initialize backend by checking quilt3 session availability."""
        self._check_session()

    def _check_session(self):
        """Check if quilt3 session is available."""
        try:
            registry_url = self.quilt_service.get_registry_url()
            self._session_available = bool(registry_url)
            if self._session_available:
                self._update_status(BackendStatus.AVAILABLE)
            else:
                self._update_status(BackendStatus.UNAVAILABLE, "No quilt3 session configured")
                self._auth_error = AuthenticationRequired(
                    catalog_url=None,
                    cause="No quilt3 session configured",
                )
        except Exception as e:
            self._session_available = False
            self._update_status(BackendStatus.ERROR, f"Session check failed: {e}")
            self._auth_error = AuthenticationRequired(
                catalog_url=None,
                cause=f"Session check failed: {e}",
            )

    async def health_check(self) -> bool:
        """Check if Elasticsearch backend is healthy."""
        try:
            registry_url = self.quilt_service.get_registry_url()
            if registry_url:
                self._update_status(BackendStatus.AVAILABLE)
                return True
            else:
                self._update_status(BackendStatus.UNAVAILABLE, "No registry URL available")
                return False
        except Exception as e:
            self._update_status(BackendStatus.ERROR, f"Health check failed: {e}")
            return False

    def _get_available_buckets(self) -> list[str]:
        """Get list of available bucket names from catalog.

        Returns:
            List of bucket names

        Raises:
            Exception if GraphQL query fails
        """
        try:
            session = self.quilt_service.get_session()
            registry_url = self.quilt_service.get_registry_url()

            if not session or not registry_url:
                return []

            resp = session.post(
                f"{registry_url.rstrip('/')}/graphql",
                json={"query": "{ bucketConfigs { name } }"},
                timeout=30,
            )

            if resp.status_code != 200:
                logger.warning(f"Failed to fetch bucket list: HTTP {resp.status_code}")
                return []

            data = resp.json()
            configs = data.get("data", {}).get("bucketConfigs", [])
            return [config["name"] for config in configs if isinstance(config, dict) and "name" in config]
        except Exception as e:
            logger.warning(f"Failed to fetch bucket list: {e}")
            return []

    def _build_index_pattern(self, scope: str, bucket: str) -> str:
        """Build Elasticsearch index pattern based on scope and bucket.

        Args:
            scope: "file", "package", or "global"
            bucket: Bucket name (with or without s3://) or empty for all buckets

        Returns:
            Elasticsearch index pattern

        Examples:
            scope="file", bucket="mybucket" → "mybucket"
            scope="package", bucket="mybucket" → "mybucket_packages"
            scope="file", bucket="" → "bucket1,bucket2,..."
            scope="package", bucket="" → "bucket1_packages,bucket2_packages,..."
            scope="global", bucket="" → "bucket1,bucket1_packages,bucket2,bucket2_packages,..."
        """
        # Normalize bucket name (remove s3:// prefix and trailing slashes)
        if bucket:
            bucket_name = bucket.replace("s3://", "").rstrip("/").split("/")[0]
        else:
            bucket_name = ""

        # If specific bucket provided, use simple pattern
        if bucket_name:
            if scope == "file":
                return bucket_name
            elif scope == "package":
                return f"{bucket_name}_packages"
            else:  # global
                return f"{bucket_name},{bucket_name}_packages"

        # No specific bucket - need to get list of all buckets
        available_buckets = self._get_available_buckets()

        if not available_buckets:
            # Fallback to wildcard if we can't get bucket list
            # (though this may fail with "No valid indices provided")
            logger.warning("No buckets available, using wildcard pattern (may fail)")
            if scope == "file":
                return "*"
            elif scope == "package":
                return "*_packages"
            else:  # global
                return "*,*_packages"

        # Build pattern from actual bucket names
        if scope == "file":
            return ",".join(available_buckets)
        elif scope == "package":
            return ",".join(f"{b}_packages" for b in available_buckets)
        else:  # global
            # Interleave bucket and package indices
            patterns = []
            for b in available_buckets:
                patterns.extend([b, f"{b}_packages"])
            return ",".join(patterns)

    async def search(
        self,
        query: str,
        scope: str = "global",
        bucket: str = "",
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 50,
    ) -> BackendResponse:
        """Execute search using Elasticsearch."""
        # Ensure backend is initialized before searching
        self.ensure_initialized()

        start_time = time.time()

        if not self._session_available:
            auth_error = getattr(self, "_auth_error", None)
            if auth_error:
                error_msg = f"{auth_error.message}: {auth_error.cause}"
            else:
                error_msg = "Quilt3 session not available - authentication required"

            return BackendResponse(
                backend_type=self.backend_type,
                status=BackendStatus.UNAVAILABLE,
                results=[],
                error_message=error_msg,
            )

        try:
            # Build index pattern
            index_pattern = self._build_index_pattern(scope, bucket)

            # Build query DSL
            escaped_query = escape_elasticsearch_query(query)
            dsl_query: Dict[str, Any] = {
                "from": 0,
                "size": limit,
                "query": {"query_string": {"query": escaped_query}},
            }

            # Apply filters if provided
            if filters:
                filter_clauses: List[Dict[str, Any]] = []

                if filters.get("file_extensions"):
                    filter_clauses.append({"terms": {"ext": [ext.lstrip(".") for ext in filters["file_extensions"]]}})
                if filters.get("size_gt"):
                    filter_clauses.append({"range": {"size": {"gt": filters["size_gt"]}}})
                if filters.get("size_min"):
                    filter_clauses.append({"range": {"size": {"gte": filters["size_min"]}}})
                if filters.get("size_max"):
                    filter_clauses.append({"range": {"size": {"lte": filters["size_max"]}}})
                if filters.get("created_after"):
                    filter_clauses.append({"range": {"last_modified": {"gte": filters["created_after"]}}})
                if filters.get("created_before"):
                    filter_clauses.append({"range": {"last_modified": {"lte": filters["created_before"]}}})

                if filter_clauses:
                    dsl_query["query"] = {
                        "bool": {
                            "must": [{"query_string": {"query": escaped_query}}],
                            "filter": filter_clauses,
                        }
                    }

            # Execute search
            search_api = self.quilt_service.get_search_api()
            response = search_api(query=dsl_query, index=index_pattern, limit=limit)

            if "error" in response:
                raise BackendError(
                    backend_name="elasticsearch",
                    cause=response["error"],
                    authenticated=self._session_available,
                    catalog_url=self.quilt_service.get_registry_url() if self._session_available else None,
                )

            # Convert results
            hits = response.get("hits", {}).get("hits", [])
            results = self._normalize_results(hits)

            query_time = (time.time() - start_time) * 1000

            return BackendResponse(
                backend_type=self.backend_type,
                status=BackendStatus.AVAILABLE,
                results=results,
                total=len(results),
                query_time_ms=query_time,
            )

        except Exception as e:
            query_time = (time.time() - start_time) * 1000
            self._update_status(BackendStatus.ERROR, str(e))

            error_message = str(e)
            if isinstance(e, BackendError):
                error_message = f"{e.message}: {e.cause}"

            return BackendResponse(
                backend_type=self.backend_type,
                status=BackendStatus.ERROR,
                results=[],
                query_time_ms=query_time,
                error_message=error_message,
            )

    def _normalize_results(self, hits: List[Dict[str, Any]]) -> List[SearchResult]:
        """Normalize Elasticsearch results to standard format.

        Detects type from index name:
        - Indices ending with "_packages" are packages
        - All other indices are files

        Uses only 'name' field per spec 19 - no logical_key or package_name.
        """
        results = []

        for hit in hits:
            source = hit.get("_source", {})
            index_name = hit.get("_index", "")

            # Detect type from index name
            is_package = index_name.endswith("_packages")

            # Extract bucket name from index
            if is_package:
                bucket_name = index_name.rsplit("_packages", 1)[0]
            else:
                bucket_name = index_name

            if is_package:
                # Package result
                package_name = source.get("ptr_name", source.get("mnfst_name", ""))
                size = source.get("mnfst_stats", {}).get("total_bytes", 0)
                last_modified = source.get("mnfst_last_modified", "")
                mnfst_hash = source.get("mnfst_hash", "")

                # Construct S3 URI for package manifest
                s3_uri = None
                if bucket_name and package_name and mnfst_hash:
                    s3_uri = f"s3://{bucket_name}/.quilt/packages/{package_name}/{mnfst_hash}.jsonl"

                result = SearchResult(
                    id=hit.get("_id", ""),
                    type="package",
                    name=package_name,  # ONLY field needed!
                    title=package_name,
                    description=f"Quilt package: {package_name}",
                    s3_uri=s3_uri,
                    size=size,
                    last_modified=last_modified,
                    metadata=source,
                    score=hit.get("_score", 0.0),
                    backend="elasticsearch",
                    bucket=bucket_name,
                    content_type="application/jsonl",
                    extension="jsonl",
                )
            else:
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

                result = SearchResult(
                    id=hit.get("_id", ""),
                    type="file",
                    name=key,  # ONLY field needed!
                    title=key.split("/")[-1] if key else "Unknown",
                    description=f"Object in {bucket_name}",
                    s3_uri=s3_uri,
                    size=size,
                    last_modified=last_modified,
                    metadata=source,
                    score=hit.get("_score", 0.0),
                    backend="elasticsearch",
                    bucket=bucket_name,
                    content_type=content_type,
                    extension=extension,
                )

            results.append(result)

        return results

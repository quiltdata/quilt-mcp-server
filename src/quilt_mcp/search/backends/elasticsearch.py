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
from .scope_handlers import (
    ScopeHandler,
    FileScopeHandler,
    PackageEntryScopeHandler,
    PackageScopeHandler,
    GlobalScopeHandler,
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

    IMPORTANT: Wildcards (* and ?) are NOT escaped - they remain as wildcards.
    Single * means "match all", ? means "match any single character".

    Special characters that ARE escaped:
    + - = && || > < ! ( ) { } [ ] ^ " ~ : \ /

    Args:
        query: Raw query string

    Returns:
        Escaped query string safe for query_string queries (preserving wildcards)

    Examples:
        >>> escape_elasticsearch_query("team/dataset")
        'team\\/dataset'
        >>> escape_elasticsearch_query("size>100")
        'size\\>100'
        >>> escape_elasticsearch_query("*")
        '*'
        >>> escape_elasticsearch_query("*.csv")
        '*.csv'
    """
    # Characters that need to be escaped in Elasticsearch query_string
    # Order matters: escape backslash first to avoid double-escaping
    # NOTE: * and ? are INTENTIONALLY OMITTED to preserve wildcard functionality
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

        # Initialize scope handlers
        self.scope_handlers: Dict[str, ScopeHandler] = {
            "file": FileScopeHandler(),
            "packageEntry": PackageEntryScopeHandler(),
            "package": PackageScopeHandler(),
            "global": GlobalScopeHandler(),
        }

    @staticmethod
    def is_package_index(index_name: str) -> bool:
        """Determine if an Elasticsearch index name represents a package index.

        Package indices contain "_packages" in their name, regardless of any
        suffix (e.g., reindex operations).

        Args:
            index_name: Elasticsearch index name

        Returns:
            True if this is a package index, False otherwise

        Examples:
            >>> Quilt3ElasticsearchBackend.is_package_index("mybucket_packages")
            True
            >>> Quilt3ElasticsearchBackend.is_package_index("mybucket_packages-reindex-v123")
            True
            >>> Quilt3ElasticsearchBackend.is_package_index("mybucket")
            False
            >>> Quilt3ElasticsearchBackend.is_package_index("mybucket-reindex-v456")
            False
        """
        return "_packages" in index_name

    @staticmethod
    def get_bucket_from_index(index_name: str) -> str:
        """Extract the S3 bucket name from an Elasticsearch index name.

        Handles both standard and reindexed indices:
        - Standard object index: "mybucket" → "mybucket"
        - Standard package index: "mybucket_packages" → "mybucket"
        - Reindexed object index: "mybucket-reindex-v123" → "mybucket"
        - Reindexed package index: "mybucket_packages-reindex-v456" → "mybucket"

        Args:
            index_name: Elasticsearch index name

        Returns:
            S3 bucket name (without _packages suffix or reindex suffix)

        Examples:
            >>> Quilt3ElasticsearchBackend.get_bucket_from_index("mybucket")
            'mybucket'
            >>> Quilt3ElasticsearchBackend.get_bucket_from_index("mybucket_packages")
            'mybucket'
            >>> Quilt3ElasticsearchBackend.get_bucket_from_index("mybucket-reindex-v123")
            'mybucket'
            >>> Quilt3ElasticsearchBackend.get_bucket_from_index("mybucket_packages-reindex-v456")
            'mybucket'
        """
        # Remove _packages suffix if present
        if "_packages" in index_name:
            bucket = index_name.split("_packages")[0]
        else:
            bucket = index_name

        # Remove any reindex suffix (pattern: -reindex-v{hash} or -reindex-{anything})
        if "-reindex-" in bucket:
            bucket = bucket.split("-reindex-")[0]

        return bucket

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

    def _prioritize_buckets(self, buckets: List[str]) -> List[str]:
        """Prioritize bucket list to search most relevant buckets first.

        Priority order:
        1. User's default bucket (from QUILT_DEFAULT_BUCKET env var)
        2. All other buckets in original order

        Args:
            buckets: List of bucket names

        Returns:
            Reordered list with default bucket first
        """
        if not buckets:
            return []

        # Get default bucket from environment
        try:
            import os

            default_bucket = os.getenv('QUILT_DEFAULT_BUCKET', '')
            if default_bucket:
                # Normalize to bucket name only
                default_bucket = default_bucket.replace('s3://', '').split('/')[0]

                # Move default bucket to front if it exists in the list
                if default_bucket in buckets:
                    prioritized = [default_bucket]
                    prioritized.extend([b for b in buckets if b != default_bucket])
                    return prioritized
        except Exception as e:
            logger.debug(f"Failed to prioritize default bucket: {e}")

        # Return original order if prioritization fails
        return buckets

    @staticmethod
    def normalize_bucket_name(bucket: str) -> str:
        """Normalize bucket name by removing s3:// prefix and trailing slashes.

        Args:
            bucket: Raw bucket string (e.g., "s3://my-bucket/", "my-bucket")

        Returns:
            Normalized bucket name (e.g., "my-bucket")

        Examples:
            >>> Quilt3ElasticsearchBackend.normalize_bucket_name("s3://my-bucket/path")
            'my-bucket'
            >>> Quilt3ElasticsearchBackend.normalize_bucket_name("my-bucket")
            'my-bucket'
        """
        if not bucket:
            return ""
        return bucket.replace("s3://", "").rstrip("/").split("/")[0]

    def build_index_pattern_for_scope(self, scope: str, buckets: List[str]) -> str:
        """Build Elasticsearch index pattern for given scope and bucket list.

        Delegates to the appropriate scope handler.

        Args:
            scope: "file", "packageEntry", or "global"
            buckets: List of bucket names (already normalized)

        Returns:
            Comma-separated index pattern string

        Examples:
            >>> backend.build_index_pattern_for_scope("file", ["bucket1", "bucket2"])
            'bucket1,bucket2'
            >>> backend.build_index_pattern_for_scope("packageEntry", ["bucket1"])
            'bucket1_packages'
            >>> backend.build_index_pattern_for_scope("global", ["bucket1"])
            'bucket1,bucket1_packages'

        Raises:
            ValueError: If buckets list is empty or scope is invalid
        """
        if scope not in self.scope_handlers:
            raise ValueError(f"Invalid scope: {scope}. Must be one of {list(self.scope_handlers.keys())}")

        handler = self.scope_handlers[scope]
        return handler.build_index_pattern(buckets)

    def _build_index_pattern(self, scope: str, bucket: str) -> str:
        """Build Elasticsearch index pattern based on scope and bucket.

        This method orchestrates the index pattern building by:
        1. Normalizing bucket name
        2. Getting available buckets (if needed)
        3. Prioritizing buckets (if needed)
        4. Building the pattern using pure function

        Args:
            scope: "file", "packageEntry", or "global"
            bucket: Bucket name (with or without s3://) or empty for all buckets

        Returns:
            Elasticsearch index pattern

        Examples:
            scope="file", bucket="mybucket" → "mybucket"
            scope="packageEntry", bucket="mybucket" → "mybucket_packages"
            scope="file", bucket="" → "default-bucket,bucket1,bucket2,..." (all buckets, prioritized)
            scope="packageEntry", bucket="" → "default-bucket_packages,bucket1_packages,..." (all buckets, prioritized)
            scope="global", bucket="" → "default-bucket,default-bucket_packages,..." (all buckets, prioritized)

        Note:
            When bucket is empty, we enumerate ALL available buckets from the catalog
            and build explicit comma-separated index patterns. Wildcard patterns
            like "*" or "_all" are rejected by the Quilt catalog API.

            Buckets are prioritized with user's default bucket first to ensure
            the most relevant results appear even if Elasticsearch limits apply.

            If Elasticsearch returns a 403 error due to too many indices, the
            calling code should retry with fewer buckets.
        """
        # Normalize bucket name (remove s3:// prefix and trailing slashes)
        bucket_name = self.normalize_bucket_name(bucket)

        # If specific bucket provided, use simple pattern
        if bucket_name:
            return self.build_index_pattern_for_scope(scope, [bucket_name])

        # No specific bucket - enumerate available buckets and build explicit pattern
        # Wildcard patterns (*,*_packages,_all) are rejected by Quilt catalog API
        available_buckets = self._get_available_buckets()

        if not available_buckets:
            # No buckets available - return empty pattern to trigger error
            logger.warning("No buckets available for search, returning empty pattern")
            return ""

        # Prioritize buckets with default bucket first
        prioritized_buckets = self._prioritize_buckets(available_buckets)

        # Use ALL available buckets - let Elasticsearch handle limits
        # If we hit a 403 error, the caller should implement retry logic
        return self.build_index_pattern_for_scope(scope, prioritized_buckets)

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

            # Get scope handler
            handler = self.scope_handlers.get(scope)
            if not handler:
                return BackendResponse(
                    backend_type=self.backend_type,
                    status=BackendStatus.ERROR,
                    results=[],
                    error_message=f"Invalid scope: {scope}. Must be one of {list(self.scope_handlers.keys())}",
                )

            # Build query DSL
            escaped_query = escape_elasticsearch_query(query)
            dsl_query: Dict[str, Any] = {
                "from": 0,
                "size": limit,
                "query": {"query_string": {"query": escaped_query}},
            }

            # Add query filter if handler provides it
            if hasattr(handler, 'build_query_filter'):
                dsl_query["query"] = handler.build_query_filter(escaped_query)

            # Add collapse config if handler provides it
            if hasattr(handler, 'build_collapse_config'):
                collapse_config = handler.build_collapse_config()
                if collapse_config:
                    dsl_query["collapse"] = collapse_config

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
                    # If query is already a bool query (from handler), add filters to it
                    current_query = dsl_query["query"]
                    if isinstance(current_query, dict) and "bool" in current_query:
                        # Merge filters into existing bool query
                        if "filter" not in current_query["bool"]:
                            current_query["bool"]["filter"] = []
                        current_query["bool"]["filter"].extend(filter_clauses)
                    else:
                        # Create new bool query with filters
                        dsl_query["query"] = {
                            "bool": {
                                "must": [current_query],
                                "filter": filter_clauses,
                            }
                        }

            # Execute search with retry logic for 403 errors (too many indices)
            search_api = self.quilt_service.get_search_api()

            # Try search with full index pattern first
            try:
                response = search_api(query=dsl_query, index=index_pattern, limit=limit)
            except Exception as search_error:
                # Check if error is 403 and we're searching multiple buckets
                if "403" in str(search_error) and "," in index_pattern and not bucket:
                    # 403 likely means too many indices - retry with fewer buckets
                    logger.info(
                        f"Got 403 error with {len(index_pattern.split(','))} indices, retrying with fewer buckets"
                    )

                    # Get prioritized bucket list
                    available_buckets = self._get_available_buckets()
                    prioritized_buckets = self._prioritize_buckets(available_buckets)

                    # Try with progressively fewer buckets until it works
                    # Start at 50 and reduce by 10 each time
                    for max_buckets in [50, 40, 30, 20, 10]:
                        try:
                            reduced_buckets = prioritized_buckets[:max_buckets]
                            reduced_pattern = self.build_index_pattern_for_scope(scope, reduced_buckets)

                            logger.info(
                                f"Retrying with {max_buckets} buckets ({len(reduced_pattern.split(','))} indices)"
                            )
                            response = search_api(query=dsl_query, index=reduced_pattern, limit=limit)
                            logger.info(f"✅ Search succeeded with {max_buckets} buckets")
                            break
                        except Exception as retry_error:
                            if "403" in str(retry_error):
                                logger.debug(f"Still getting 403 with {max_buckets} buckets, trying fewer")
                                continue
                            else:
                                # Different error, re-raise
                                raise
                    else:
                        # All retries failed, raise original error
                        raise search_error
                else:
                    # Not a 403 or not a multi-bucket search, re-raise
                    raise

            if "error" in response:
                raise BackendError(
                    backend_name="elasticsearch",
                    cause=response["error"],
                    authenticated=self._session_available,
                    catalog_url=self.quilt_service.get_registry_url() if self._session_available else None,
                )

            # Convert results using scope handler
            hits = response.get("hits", {}).get("hits", [])
            results = self._normalize_results(hits, scope)

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

    def _normalize_results(self, hits: List[Dict[str, Any]], scope: str) -> List[SearchResult]:
        """Normalize Elasticsearch results to standard format using scope handler.

        Args:
            hits: List of Elasticsearch hits
            scope: Search scope ("file", "packageEntry", or "global")

        Returns:
            List of normalized SearchResult objects
        """
        handler = self.scope_handlers[scope]
        results = []

        for hit in hits:
            index_name = hit.get("_index", "")
            bucket_name = self.get_bucket_from_index(index_name)

            result = handler.parse_result(hit, bucket_name)
            if result:  # None means parsing/validation failed
                results.append(result)

        return results

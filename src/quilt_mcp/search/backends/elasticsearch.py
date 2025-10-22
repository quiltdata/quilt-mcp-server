"""Elasticsearch backend that wraps existing quilt3.Bucket.search() functionality.

This backend leverages the existing Quilt3 Elasticsearch integration
rather than building new infrastructure.
"""

import logging
import time
from typing import Dict, List, Any, Optional, Union

import quilt3
from ..core.query_parser import QueryAnalysis, QueryType
from .base import (
    SearchBackend,
    BackendType,
    BackendStatus,
    SearchResult,
    BackendResponse,
)
from ...services.quilt_service import QuiltService

logger = logging.getLogger(__name__)


class Quilt3ElasticsearchBackend(SearchBackend):
    """Elasticsearch backend using existing quilt3.Bucket.search() API."""

    def __init__(self, quilt_service: Optional[QuiltService] = None):
        super().__init__(BackendType.ELASTICSEARCH)
        self.quilt_service = quilt_service or QuiltService()
        self._session_available = False
        self._check_session()

    def _check_session(self):
        """Check if quilt3 session is available."""
        try:
            # Test if we can get registry URL (indicates session is configured)
            registry_url = self.quilt_service.get_registry_url()
            self._session_available = bool(registry_url)
            if self._session_available:
                self._update_status(BackendStatus.AVAILABLE)
            else:
                self._update_status(BackendStatus.UNAVAILABLE, "No quilt3 session configured")
        except Exception as e:
            self._session_available = False
            self._update_status(BackendStatus.ERROR, f"Session check failed: {e}")

    async def health_check(self) -> bool:
        """Check if Elasticsearch backend is healthy."""
        try:
            # Simple health check by attempting to get registry URL
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

    async def search(
        self,
        query: str,
        scope: str = "global",
        target: str = "",
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 50,
    ) -> BackendResponse:
        """Execute search using quilt3.Bucket.search() or packages search API."""
        start_time = time.time()

        if not self._session_available:
            return BackendResponse(
                backend_type=self.backend_type,
                status=BackendStatus.UNAVAILABLE,
                results=[],
                error_message="Quilt3 session not available",
            )

        try:
            if scope == "bucket" and target:
                # Use bucket-specific search
                results = await self._search_bucket(query, target, filters, limit)
            elif scope == "package" and target:
                # Search within specific package (dedicated package-scoped logic pending)
                results = await self._search_package(query, target, filters, limit)
            else:
                # Global/catalog search using packages search API
                results = await self._search_global(query, filters, limit)

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

            return BackendResponse(
                backend_type=self.backend_type,
                status=BackendStatus.ERROR,
                results=[],
                query_time_ms=query_time,
                error_message=str(e),
            )

    async def _search_bucket(
        self, query: str, bucket: str, filters: Optional[Dict[str, Any]], limit: int
    ) -> List[SearchResult]:
        """Search within a specific bucket using quilt3.Bucket.search()."""
        from ...utils import suppress_stdout

        # Normalize bucket name
        bucket_uri = bucket if bucket.startswith("s3://") else f"s3://{bucket}"

        # Convert filters to Elasticsearch query if needed
        es_query = self._build_elasticsearch_query(query, filters)

        with suppress_stdout():
            bucket_obj = self.quilt_service.create_bucket(bucket_uri)
            raw_results = bucket_obj.search(es_query, limit=limit)

        return self._convert_bucket_results(raw_results, bucket)

    async def _search_package(
        self,
        query: str,
        package_name: str,
        filters: Optional[Dict[str, Any]],
        limit: int,
    ) -> List[SearchResult]:
        """Search within a specific package."""
        # TODO: implement package-scoped search directly via search API if needed
        return []

    async def _search_global(self, query: str, filters: Optional[Dict[str, Any]], limit: int) -> List[SearchResult]:
        """Global search across all stack buckets using the catalog search API."""
        search_response = self._execute_catalog_search(query=query, limit=limit, filters=filters)

        if "error" in search_response:
            raise Exception(search_response["error"])

        hits = search_response.get("hits", {}).get("hits", [])
        return self._convert_catalog_results(hits)

    def get_total_count(self, query: str, filters: Optional[Dict[str, Any]] = None) -> int:
        """Get total count of matching documents using Elasticsearch size=0 query."""
        try:
            search_response = self._execute_catalog_search(query=query, limit=0, filters=filters)
        except Exception as exc:
            raise Exception(f"Failed to get total count: {exc}") from exc

        total = search_response.get("hits", {}).get("total")
        if isinstance(total, dict) and "value" in total:
            return int(total["value"])
        if total is not None:
            return int(total)

        return len(search_response.get("hits", {}).get("hits", []))

    def _execute_catalog_search(
        self,
        query: Union[str, Dict[str, Any]],
        limit: int,
        *,
        filters: Optional[Dict[str, Any]] = None,
        from_: int = 0,
    ) -> Dict[str, Any]:
        """Execute a catalog search query via quilt3 search API."""
        try:
            search_api = self.quilt_service.get_search_api()
        except Exception as exc:
            return {"error": f"Search API unavailable: {exc}"}

        if isinstance(query, str) and not query.strip().startswith("{"):
            dsl_query: Dict[str, Any] = {
                "from": max(from_, 0),
                "size": max(limit, 0),
                "query": {"query_string": {"query": query}},
            }
        else:
            import json

            if isinstance(query, str):
                dsl_query = json.loads(query)
            else:
                dsl_query = dict(query)
            dsl_query["from"] = max(from_, 0)
            dsl_query["size"] = max(limit, 0)

        if filters:
            filter_clauses = []
            if filters.get("file_extensions"):
                filter_clauses.append({"terms": {"ext": [ext.lstrip(".") for ext in filters["file_extensions"]]}})
            if filters.get("size_gt"):
                filter_clauses.append({"range": {"size": {"gt": filters["size_gt"]}}})
            if filter_clauses:
                dsl_query.setdefault("query", {}).setdefault("bool", {}).setdefault("filter", []).extend(
                    filter_clauses
                )

        from ...tools.stack_buckets import build_stack_search_indices

        index_name = None
        try:
            index_name = build_stack_search_indices()
        except Exception:
            index_name = None

        try:
            kwargs: Dict[str, Any] = {"query": dsl_query}
            if index_name:
                kwargs["index"] = index_name
            if limit >= 0:
                kwargs["limit"] = limit
            return search_api(**kwargs)
        except Exception as exc:  # pragma: no cover - surface search API issues
            return {"error": f"Catalog search failed: {exc}"}

    def _build_elasticsearch_query(self, query: str, filters: Optional[Dict[str, Any]]) -> Union[str, Dict[str, Any]]:
        """Build Elasticsearch query from natural language and filters."""
        if not filters:
            return query

        # Build DSL query with filters
        dsl_query = {"query": {"bool": {"must": [{"query_string": {"query": query}}], "filter": []}}}

        # Add file extension filters using the proper 'ext' field
        if filters.get("file_extensions"):
            ext_terms = []
            for ext in filters["file_extensions"]:
                # Extensions should include the dot prefix as seen in enterprise repo
                ext_clean = ext.lower().lstrip(".")
                ext_terms.append(f".{ext_clean}")

            if ext_terms:
                dsl_query["query"]["bool"]["filter"].append({"terms": {"ext": ext_terms}})

        # Add size filters
        if filters.get("size_min") or filters.get("size_max"):
            size_filter: dict[str, Any] = {"range": {"size": {}}}
            if filters.get("size_min"):
                size_filter["range"]["size"]["gte"] = filters["size_min"]
            if filters.get("size_max"):
                size_filter["range"]["size"]["lte"] = filters["size_max"]
            dsl_query["query"]["bool"]["filter"].append(size_filter)

        # Add date filters
        if filters.get("created_after") or filters.get("created_before"):
            date_filter: dict[str, Any] = {"range": {"last_modified": {}}}
            if filters.get("created_after"):
                date_filter["range"]["last_modified"]["gte"] = filters["created_after"]
            if filters.get("created_before"):
                date_filter["range"]["last_modified"]["lte"] = filters["created_before"]
            dsl_query["query"]["bool"]["filter"].append(date_filter)

        return dsl_query

    def _convert_bucket_results(self, raw_results: List[Dict[str, Any]], bucket: str) -> List[SearchResult]:
        """Convert quilt3.Bucket.search() results to standard format."""
        results = []

        for hit in raw_results:
            source = hit.get("_source", {})

            # Extract key information
            key = source.get("key", "")
            size = source.get("size", 0)
            last_modified = source.get("last_modified", "")

            # Create S3 URI
            s3_uri = f"s3://{bucket}/{key}" if key else None

            # Determine if this is a package or file
            is_package = "_packages" in hit.get("_index", "")
            result_type = "package" if is_package else "file"

            result = SearchResult(
                id=hit.get("_id", ""),
                type=result_type,
                title=key.split("/")[-1] if key else "Unknown",
                description=f"Object in {bucket}",
                s3_uri=s3_uri,
                logical_key=key,
                size=size,
                last_modified=last_modified,
                metadata=source,
                score=hit.get("_score", 0.0),
                backend="elasticsearch",
            )

            results.append(result)

        return results

    def _convert_catalog_results(self, raw_results: List[Dict[str, Any]]) -> List[SearchResult]:
        """Convert catalog search results to standard format."""
        results = []

        for hit in raw_results:
            source = hit.get("_source", {})

            # Extract package information
            package_name = source.get("ptr_name", source.get("mnfst_name", ""))

            result = SearchResult(
                id=hit.get("_id", ""),
                type="package",
                title=package_name,
                description=f"Quilt package: {package_name}",
                package_name=package_name,
                metadata=source,
                score=hit.get("_score", 0.0),
                backend="elasticsearch",
            )

            results.append(result)

        return results

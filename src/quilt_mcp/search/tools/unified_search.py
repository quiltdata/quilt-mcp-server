"""Unified search tool that intelligently routes queries across backends.

This is the main user-facing search interface that provides natural language
query processing and intelligent backend selection.
"""

import time
from typing import Dict, List, Any, Optional

from ..core.query_parser import parse_query
from ..backends.base import BackendRegistry, BackendType, BackendStatus
from ..backends.elasticsearch import Quilt3ElasticsearchBackend
from ..backends.graphql import EnterpriseGraphQLBackend
from ..exceptions import (
    AuthenticationRequired,
    SearchNotAvailable,
)


class UnifiedSearchEngine:
    """Main search engine that orchestrates queries across backends."""

    def __init__(self):
        self.registry = BackendRegistry()
        self._initialize_backends()

    def _initialize_backends(self):
        """Initialize and register all available backends."""
        # Register Elasticsearch backend (wraps quilt3)
        es_backend = Quilt3ElasticsearchBackend()
        self.registry.register(es_backend)

        # Register GraphQL backend
        graphql_backend = EnterpriseGraphQLBackend()
        self.registry.register(graphql_backend)

    async def search(
        self,
        query: str,
        scope: str = "global",
        bucket: str = "",
        backend: Optional[str] = None,
        limit: int = 50,
        include_metadata: bool = True,
        explain_query: bool = False,
    ) -> Dict[str, Any]:
        """Execute unified search using single backend selection.

        Args:
            query: Natural language search query
            scope: Search scope (global, package, file)
            bucket: S3 bucket to search in (empty = all buckets)
            backend: Preferred backend (auto, elasticsearch, graphql)
            limit: Maximum results to return
            include_metadata: Include rich metadata in results
            explain_query: Include query execution explanation

        Returns:
            Unified search results with metadata and explanations
        """
        start_time = time.time()

        # Parse and analyze the query
        analysis = parse_query(query, scope, bucket)

        # Use filters extracted from query analysis
        combined_filters = analysis.filters

        # Determine which backend to use
        if backend is None or backend == "auto":
            selected_backend = self.registry._select_primary_backend()
        else:
            selected_backend = self.registry.get_backend_by_name(backend)

        # Check if we have a backend available
        if selected_backend is None:
            # Get backend statuses for detailed error message
            backend_statuses = self.registry.get_backend_statuses()

            # Check if this is authentication failure or no backends available
            all_backends = list(self.registry._backends.values())
            has_auth_error = any(hasattr(b, "_auth_error") for b in all_backends)

            if has_auth_error:
                # Authentication required
                auth_exception = AuthenticationRequired()
                error_response = auth_exception.to_response()
                error_response.update(
                    {
                        "query": query,
                        "scope": scope,
                        "bucket": bucket,
                        "results": [],
                        "total_results": 0,
                        "query_time_ms": (time.time() - start_time) * 1000,
                        "backend_used": None,
                        "backend_status": backend_statuses,
                    }
                )
                return error_response
            else:
                # No backends available (authenticated but search not available)
                search_not_available = SearchNotAvailable(
                    authenticated=True,
                    catalog_url=None,
                    cause="No search backends available",
                    backend_statuses=backend_statuses,
                )
                error_response = search_not_available.to_response()
                error_response.update(
                    {
                        "query": query,
                        "scope": scope,
                        "bucket": bucket,
                        "results": [],
                        "total_results": 0,
                        "query_time_ms": (time.time() - start_time) * 1000,
                        "backend_used": None,
                        "backend_status": backend_statuses,
                    }
                )
                return error_response

        # Execute search on selected backend
        backend_response = await selected_backend.search(query, scope, bucket, combined_filters, limit)

        # Process results
        unified_results = self._process_backend_results(backend_response, limit)

        # Apply post-processing filters only for specific cases
        # Don't apply post-filters if the query already contains ext: syntax
        if "ext:" not in query.lower():
            unified_results = self._apply_post_filters(unified_results, combined_filters or {})

        # Build response
        total_time = (time.time() - start_time) * 1000

        # Determine success based on backend response
        overall_success = backend_response.status == BackendStatus.AVAILABLE

        response = {
            "success": overall_success,
            "query": query,
            "scope": scope,
            "bucket": bucket,
            "results": unified_results,
            "total_results": len(unified_results),
            "query_time_ms": total_time,
            "backend_used": backend_response.backend_type.value if overall_success else None,
            "analysis": (
                {
                    "query_type": analysis.query_type.value,
                    "confidence": analysis.confidence,
                    "keywords": analysis.keywords,
                    "file_extensions": analysis.file_extensions,
                    "filters_applied": combined_filters,
                }
                if include_metadata
                else None
            ),
        }

        # Add error information if backend failed
        if not overall_success:
            response["error"] = backend_response.error_message or "Backend query failed"

        # Add query explanation if requested
        if explain_query:
            response["explanation"] = self._generate_explanation(analysis, backend_response, selected_backend)

        # Add backend status information
        response["backend_status"] = {
            "status": backend_response.status.value,
            "query_time_ms": backend_response.query_time_ms,
            "result_count": len(backend_response.results),
            "error": backend_response.error_message,
        }

        # Add comprehensive backend status for debugging
        from ..utils import get_search_backend_status

        response["backend_info"] = get_search_backend_status()

        return response

    def _process_backend_results(self, backend_response, limit: int) -> List[Dict[str, Any]]:
        """Process results from a single backend response.

        Args:
            backend_response: BackendResponse from the selected backend
            limit: Maximum number of results to return

        Returns:
            List of result dictionaries
        """
        if backend_response.status != BackendStatus.AVAILABLE:
            return []

        processed_results = []
        for result in backend_response.results:
            # Unified name field - works for both files and packages
            # For files: name = logical_key (path within bucket/package)
            # For packages: name = package_name (namespace/name format)
            name = (
                result.logical_key
                if result.logical_key
                else (result.package_name if result.package_name else result.name)
            )

            # Convert SearchResult to dict for JSON serialization
            result_dict = {
                "id": result.id,
                "type": result.type,
                "name": name or "",  # Unified field for all types, fallback to empty string
                "title": result.title,
                "description": result.description,
                "score": result.score,
                "backend": result.backend,
                "s3_uri": result.s3_uri,
                "bucket": getattr(result, "bucket", None),
                "content_type": getattr(result, "content_type", None),
                "extension": getattr(result, "extension", None),
                "size": result.size,
                "last_modified": result.last_modified,
                "metadata": result.metadata,
            }
            processed_results.append(result_dict)

        # Sort by score (descending) and limit results
        processed_results.sort(key=lambda x: x.get("score", 0), reverse=True)

        return processed_results[:limit]

    def _apply_post_filters(self, results: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Apply additional filtering to results that backends might have missed."""
        if not filters:
            return results

        filtered_results = []

        for result in results:
            # File extension filtering - crucial for accurate CSV file detection
            if filters.get("file_extensions"):
                # Only apply extension filtering to file results (not packages)
                if result.get("type") != "file":
                    filtered_results.append(result)
                    continue

                name = result.get("name", "")
                s3_uri = result.get("s3_uri", "")
                metadata_key = result.get("metadata", {}).get("key", "") if result.get("metadata") else ""

                # Extract file extension from name, S3 URI, or metadata key
                file_path = name or metadata_key or (s3_uri.split("/")[-1] if s3_uri else "")
                if file_path:
                    file_ext = file_path.split(".")[-1].lower() if "." in file_path else ""
                    target_extensions = [ext.lower().lstrip(".") for ext in filters["file_extensions"]]

                    if file_ext not in target_extensions:
                        continue  # Skip this result

            # Size filtering
            if filters.get("size_min") or filters.get("size_max"):
                size = result.get("size", 0)
                if isinstance(size, str):
                    try:
                        size = int(size)
                    except (ValueError, TypeError):
                        size = 0

                if filters.get("size_min") and size < filters["size_min"]:
                    continue
                if filters.get("size_max") and size > filters["size_max"]:
                    continue

            filtered_results.append(result)

        return filtered_results

    def _generate_explanation(self, analysis, backend_response, selected_backend) -> Dict[str, Any]:
        """Generate explanation of query execution.

        Args:
            analysis: Parsed query analysis
            backend_response: Response from the selected backend
            selected_backend: The backend that was used

        Returns:
            Dictionary with query execution explanation
        """
        return {
            "query_analysis": {
                "detected_type": analysis.query_type.value,
                "confidence": analysis.confidence,
                "keywords_found": analysis.keywords,
                "filters_detected": analysis.filters,
            },
            "backend_selection": {
                "selected": selected_backend.backend_type.value if selected_backend else None,
                "reasoning": f"Selected based on availability and preference. Query type: {analysis.query_type.value}",
                "status": backend_response.status.value,
            },
            "execution_summary": {
                "backend_status": backend_response.status.value,
                "success": backend_response.status == BackendStatus.AVAILABLE,
                "total_results": len(backend_response.results),
                "query_time_ms": backend_response.query_time_ms,
                "error": backend_response.error_message if backend_response.status == BackendStatus.ERROR else None,
            },
        }


# Note: UnifiedSearchEngine is exported for use by search.py
# The unified_search() wrapper function has been removed - search.py now
# calls UnifiedSearchEngine.search() directly

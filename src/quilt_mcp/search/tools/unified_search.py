"""Unified search tool that intelligently routes queries across backends.

This is the main user-facing search interface that provides natural language
query processing and intelligent backend selection.
"""

import asyncio
import time
from typing import Dict, List, Any, Optional, Union

from ..core.query_parser import parse_query, QueryType, SearchScope
from ..backends.base import BackendRegistry, BackendType, BackendStatus
from ..backends.elasticsearch import Quilt3ElasticsearchBackend
from ..backends.s3 import S3FallbackBackend
from ..backends.graphql import EnterpriseGraphQLBackend


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

        # Register S3 fallback backend
        s3_backend = S3FallbackBackend()
        self.registry.register(s3_backend)

        # Register GraphQL backend
        graphql_backend = EnterpriseGraphQLBackend()
        self.registry.register(graphql_backend)

    async def search(
        self,
        query: str,
        scope: str = "global",
        target: str = "",
        backends: Optional[List[str]] = None,
        limit: int = 50,
        include_metadata: bool = True,
        include_content_preview: bool = False,
        explain_query: bool = False,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute unified search across multiple backends.

        Args:
            query: Natural language search query
            scope: Search scope (global, catalog, package, bucket)
            target: Specific target when scope is narrow
            backends: Preferred backends (auto, elasticsearch, graphql, s3)
            limit: Maximum results to return
            include_metadata: Include rich metadata in results
            include_content_preview: Include content previews for files
            explain_query: Include query execution explanation
            filters: Additional filters

        Returns:
            Unified search results with metadata and explanations
        """
        start_time = time.time()

        # Parse and analyze the query
        analysis = parse_query(query, scope, target)

        # Merge filters from query analysis and explicit filters
        combined_filters = {**analysis.filters}
        if filters:
            combined_filters.update(filters)

        # Determine which backends to use
        if backends is None:
            backends = ["auto"]

        if backends == ["auto"] or "auto" in backends:
            selected_backends = self._select_backends(analysis)
        else:
            selected_backends = self._get_backends_by_name(backends)

        # Execute searches in parallel
        backend_responses = await self._execute_parallel_searches(
            selected_backends, query, scope, target, combined_filters, limit
        )

        # Aggregate and rank results
        unified_results = self._aggregate_results(backend_responses, limit)

        # Apply post-processing filters only for specific cases
        # Don't apply post-filters if the query already contains ext: syntax
        if "ext:" not in query.lower():
            unified_results = self._apply_post_filters(unified_results, combined_filters)

        # Build response
        total_time = (time.time() - start_time) * 1000

        response = {
            "success": True,
            "query": query,
            "scope": scope,
            "target": target,
            "results": unified_results,
            "total_results": len(unified_results),
            "query_time_ms": total_time,
            "backends_used": [
                resp.backend_type.value for resp in backend_responses if resp.status == BackendStatus.AVAILABLE
            ],
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

        # Add query explanation if requested
        if explain_query:
            response["explanation"] = self._generate_explanation(analysis, backend_responses, selected_backends)

        # Add backend status information
        response["backend_status"] = {
            backend_type.value: {
                "status": resp.status.value,
                "query_time_ms": resp.query_time_ms,
                "result_count": len(resp.results),
                "error": resp.error_message,
            }
            for backend_type, resp in zip([b.backend_type for b in selected_backends], backend_responses)
        }

        return response

    def _select_backends(self, analysis) -> List:
        """Select optimal backends based on query analysis."""
        available_backends = self.registry.get_available_backends()

        # Map suggested backend names to actual backend objects
        selected = []
        for backend_name in analysis.suggested_backends:
            backend = self.registry.get_backend_by_name(backend_name)
            if backend and backend in available_backends:
                selected.append(backend)

        # If no backends selected or available, use all available
        if not selected:
            selected = available_backends

        return selected

    def _get_backends_by_name(self, backend_names: List[str]) -> List:
        """Get backend objects by their string names."""
        backends = []
        for name in backend_names:
            backend = self.registry.get_backend_by_name(name)
            if backend:
                backends.append(backend)
        return backends

    async def _execute_parallel_searches(
        self,
        backends: List,
        query: str,
        scope: str,
        target: str,
        filters: Dict[str, Any],
        limit: int,
    ) -> List:
        """Execute searches across multiple backends in parallel."""
        tasks = []

        for backend in backends:
            task = backend.search(query, scope, target, filters, limit)
            tasks.append(task)

        # Execute all searches in parallel
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle exceptions
        backend_responses = []
        for i, response in enumerate(responses):
            if isinstance(response, Exception):
                # Create error response
                backend_responses.append(
                    type(
                        "BackendResponse",
                        (),
                        {
                            "backend_type": backends[i].backend_type,
                            "status": BackendStatus.ERROR,
                            "results": [],
                            "error_message": str(response),
                            "query_time_ms": 0,
                        },
                    )()
                )
            else:
                backend_responses.append(response)

        return backend_responses

    def _aggregate_results(self, backend_responses: List, limit: int) -> List[Dict[str, Any]]:
        """Aggregate and rank results from multiple backends."""
        all_results = []

        # Collect all results
        for response in backend_responses:
            if response.status == BackendStatus.AVAILABLE:
                for result in response.results:
                    # Convert SearchResult to dict for JSON serialization
                    result_dict = {
                        "id": result.id,
                        "type": result.type,
                        "title": result.title,
                        "description": result.description,
                        "score": result.score,
                        "backend": result.backend,
                        "s3_uri": result.s3_uri,
                        "package_name": result.package_name,
                        "logical_key": result.logical_key,
                        "size": result.size,
                        "last_modified": result.last_modified,
                        "metadata": result.metadata,
                    }
                    all_results.append(result_dict)

        # Remove duplicates based on S3 URI or logical key
        seen = set()
        unique_results = []

        for result in all_results:
            # Create a unique identifier for deduplication
            identifier = result.get("s3_uri") or result.get("logical_key") or result.get("id")

            if identifier not in seen:
                seen.add(identifier)
                unique_results.append(result)

        # Sort by score (descending) and limit results
        unique_results.sort(key=lambda x: x.get("score", 0), reverse=True)

        return unique_results[:limit]

    def _apply_post_filters(self, results: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Apply additional filtering to results that backends might have missed."""
        if not filters:
            return results

        filtered_results = []

        for result in results:
            # File extension filtering - crucial for accurate CSV file detection
            if filters.get("file_extensions"):
                logical_key = result.get("logical_key", "")
                s3_uri = result.get("s3_uri", "")
                metadata_key = result.get("metadata", {}).get("key", "") if result.get("metadata") else ""

                # Extract file extension from logical key, S3 URI, or metadata key
                file_path = logical_key or metadata_key or (s3_uri.split("/")[-1] if s3_uri else "")
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

    def _generate_explanation(self, analysis, backend_responses: List, selected_backends: List) -> Dict[str, Any]:
        """Generate explanation of query execution."""
        return {
            "query_analysis": {
                "detected_type": analysis.query_type.value,
                "confidence": analysis.confidence,
                "keywords_found": analysis.keywords,
                "filters_detected": analysis.filters,
            },
            "backend_selection": {
                "selected": [b.backend_type.value for b in selected_backends],
                "reasoning": f"Selected based on query type: {analysis.query_type.value}",
            },
            "execution_summary": {
                "successful_backends": len([r for r in backend_responses if r.status == BackendStatus.AVAILABLE]),
                "failed_backends": len([r for r in backend_responses if r.status == BackendStatus.ERROR]),
                "total_raw_results": sum(
                    len(r.results) for r in backend_responses if r.status == BackendStatus.AVAILABLE
                ),
            },
        }


# Global search engine instance
_search_engine = None


def get_search_engine() -> UnifiedSearchEngine:
    """Get or create the global search engine instance."""
    global _search_engine
    if _search_engine is None:
        _search_engine = UnifiedSearchEngine()
    return _search_engine


async def unified_search(
    query: str,
    scope: str = "global",
    target: str = "",
    backends: Optional[List[str]] = None,
    limit: int = 50,
    include_metadata: bool = True,
    include_content_preview: bool = False,
    explain_query: bool = False,
    filters: Optional[Dict[str, Any]] = None,
    count_only: bool = False,
) -> Dict[str, Any]:
    """
    Intelligent unified search across Quilt catalogs, packages, and S3 buckets.

    This tool automatically:
    - Parses natural language queries
    - Selects optimal search backends
    - Aggregates and ranks results
    - Provides context and explanations

    Args:
        query: Natural language search query
        scope: Search scope (global, catalog, package, bucket)
        target: Specific target when scope is narrow (package/bucket name)
        backends: Preferred backends (auto, elasticsearch, graphql, s3)
        limit: Maximum results to return
        include_metadata: Include rich metadata in results
        include_content_preview: Include content previews for files
        explain_query: Include query execution explanation
        filters: Additional filters (size, date, type, etc.)

    Returns:
        Unified search results with metadata, explanations, and suggestions

    Examples:
        unified_search("CSV files in genomics packages")
        unified_search("packages created last month", scope="catalog")
        unified_search("README files", scope="package", target="user/dataset")
        unified_search("files larger than 100MB", filters={"size_gt": "100MB"})
    """
    try:
        if count_only:
            # For count-only mode, use the Elasticsearch backend's get_total_count method
            engine = get_search_engine()
            elasticsearch_backend = None

            # Find the Elasticsearch backend
            available_backends = engine.registry.get_available_backends()
            elasticsearch_backend = None
            for backend in available_backends:
                if backend.backend_type.value == "elasticsearch":
                    elasticsearch_backend = backend
                    break

            if elasticsearch_backend:
                try:
                    total_count = elasticsearch_backend.get_total_count(query, filters)
                    return {
                        "success": True,
                        "total_count": total_count,
                        "query": query,
                        "scope": scope,
                        "count_only": True,
                    }
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"Count query failed: {e}",
                        "query": query,
                        "scope": scope,
                        "count_only": True,
                    }
            else:
                return {
                    "success": False,
                    "error": "Elasticsearch backend not available for count queries",
                    "query": query,
                    "scope": scope,
                    "count_only": True,
                }

        # Regular search mode
        engine = get_search_engine()
        return await engine.search(
            query=query,
            scope=scope,
            target=target,
            backends=backends,
            limit=limit,
            include_metadata=include_metadata,
            include_content_preview=include_content_preview,
            explain_query=explain_query,
            filters=filters,
        )
    except Exception as e:
        return {
            "success": False,
            "error": f"Unified search failed: {e}",
            "query": query,
            "scope": scope,
            "target": target,
        }

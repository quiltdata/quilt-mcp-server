"""Unified search tool that intelligently routes queries across backends.

This is the main user-facing search interface that provides natural language
query processing and intelligent backend selection.
"""

import asyncio
import time
from typing import Dict, List, Any, Optional, Union

from ..core.query_parser import parse_query, QueryType, SearchScope
from ..backends.base import BackendRegistry, BackendType, BackendStatus
from ..backends.graphql import EnterpriseGraphQLBackend


class UnifiedSearchEngine:
    """Main search engine that orchestrates queries across backends."""

    def __init__(self):
        self.registry = BackendRegistry()
        self._initialize_backends()

    def _initialize_backends(self):
        """Initialize and register all available backends."""
        # Register GraphQL backend as the sole backend for search operations.
        graphql_backend = EnterpriseGraphQLBackend()
        self.registry.register(graphql_backend)

    async def search(
        self,
        query: str,
        scope: str = "global",
        target: str = "",
        search_type: str = "auto",  # "auto", "packages", "objects", "both"
        backends: Optional[List[str]] = None,
        limit: int = 20,  # Reduced default limit to prevent LLM input length errors
        offset: int = 0,  # Pagination offset for retrieving additional pages
        include_metadata: bool = False,  # Changed default to False to reduce response size
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
            include_metadata: Include rich metadata in results (default: False)
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

        # Determine which backends to use (GraphQL only)
        selected_backends = self._get_backends_by_name(backends or ["graphql"])

        # Execute searches (GraphQL only – still go through shared helper for consistency)
        backend_responses = await self._execute_parallel_searches(
            selected_backends, query, scope, target, search_type, combined_filters, limit, offset
        )

        # Collect extension facets and pagination metadata from backends
        extension_counter: Dict[str, int] = {}
        object_total: Optional[int] = None
        next_cursor: Optional[str] = None

        for backend_response in backend_responses:
            raw_meta = getattr(backend_response, "raw_response", None)
            if not isinstance(raw_meta, dict):
                continue

            objects_meta = raw_meta.get("objects")
            if not isinstance(objects_meta, dict):
                continue

            for facet in objects_meta.get("ext_stats", []) or []:
                key = facet.get("key")
                count = facet.get("count", 0)
                if key:
                    extension_counter[key] = extension_counter.get(key, 0) + int(count or 0)

            total = objects_meta.get("total")
            if isinstance(total, int):
                object_total = max(object_total or 0, total)

            cursor = objects_meta.get("next_cursor")
            if isinstance(cursor, str) and cursor:
                next_cursor = cursor

        # Aggregate and rank results (single backend currently)
        unified_results = self._aggregate_results(backend_responses, limit, include_metadata)

        # Build response
        total_time = (time.time() - start_time) * 1000

        # Truncate descriptions to prevent LLM input length errors
        truncated_results = []
        for result in unified_results:
            truncated_result = result.copy()
            if truncated_result.get("description") and len(truncated_result["description"]) > 300:
                truncated_result["description"] = truncated_result["description"][:300] + "..."
            truncated_results.append(truncated_result)

        response = {
            "success": True,
            "query": query,
            "scope": scope,
            "target": target,
            "search_type": search_type,
            "results": truncated_results,
            "total_results": len(truncated_results),
            "limit": limit,
            "offset": offset,
            "has_more": len(truncated_results) == limit,  # Indicate if there might be more results
            "next_offset": offset + limit if len(truncated_results) == limit else None,
            "query_time_ms": total_time,
            "backend": "graphql",
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

        if extension_counter:
            sorted_exts = sorted(extension_counter.items(), key=lambda item: item[1], reverse=True)
            response["available_extensions"] = [
                {"extension": extension, "count": count} for extension, count in sorted_exts
            ]

        if object_total is not None:
            response["object_total"] = object_total

        if next_cursor:
            response["next_cursor"] = next_cursor
        
        # Add query explanation if requested
        if explain_query:
            response["explanation"] = self._generate_explanation(analysis, backend_responses, selected_backends)

        # Add backend status information
        response["backend_status"] = {}
        if backend_responses:
            resp = backend_responses[0]
            response["backend_status"]["graphql"] = {
                "status": resp.status.value,
                "query_time_ms": resp.query_time_ms,
                "result_count": len(resp.results),
                "error": resp.error_message,
            }

        # Add navigation suggestion if scope/target are specified
        if scope in ["bucket", "package"] and target:
            response["navigation"] = self._build_navigation_suggestion(scope, target)

        return response

    def _select_backends(self, analysis) -> List:
        """Select optimal backends based on query analysis."""
        return self._get_backends_by_name(["graphql"])

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
        search_type: str,
        filters: Dict[str, Any],
        limit: int,
        offset: int = 0,
    ) -> List:
        """Execute searches across configured backends."""
        if not backends:
            return []

        backend = backends[0]
        try:
            response = await backend.search(query, scope, target, search_type, filters, limit, offset)
            return [response]
        except Exception as exc:
            return [
                type(
                    "BackendResponse",
                    (),
                    {
                        "backend_type": backend.backend_type,
                        "status": BackendStatus.ERROR,
                        "results": [],
                        "error_message": str(exc),
                        "query_time_ms": 0,
                    },
                )()
            ]

    def _aggregate_results(self, backend_responses: List, limit: int, include_metadata: bool = False) -> List[Dict[str, Any]]:
        """Aggregate and rank results from multiple backends."""
        all_results = []

        # Collect all results
        for response in backend_responses:
            if response.status == BackendStatus.AVAILABLE:
                for result in response.results:
                    # Convert SearchResult to dict for JSON serialization with conditional metadata
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
                    }
                    
                    # Only include metadata if explicitly requested
                    if include_metadata:
                        result_dict["metadata"] = self._optimize_metadata(result.metadata)
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

    def _optimize_metadata(self, metadata: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Optimize metadata to reduce response size for LLM consumption."""
        if not metadata:
            return None
        
        # Keep only essential metadata fields to reduce token count
        essential_fields = {
            "bucket", "name", "hash", "size", "modified", "content_type", 
            "extension", "total_entries", "comment"
        }
        
        optimized = {}
        for key, value in metadata.items():
            if key in essential_fields:
                # Truncate long string values
                if isinstance(value, str) and len(value) > 200:
                    optimized[key] = value[:200] + "..."
                else:
                    optimized[key] = value
        
        return optimized if optimized else None

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

    def _build_navigation_suggestion(self, scope: str, target: str) -> Dict[str, Any]:
        """Build navigation suggestion that matches frontend's navigate tool format.
        
        Args:
            scope: Search scope (bucket, package, etc.)
            target: Target identifier (bucket name, package name, etc.)
            
        Returns:
            Dictionary with navigation suggestion that frontend can auto-execute
        """
        if scope == "bucket":
            # Clean bucket name (remove s3:// prefix if present)
            bucket_name = target.replace("s3://", "")
            return {
                "tool": "navigate",
                "params": {
                    "route": {
                        "name": "bucket.overview",
                        "params": {
                            "bucket": bucket_name,
                        },
                    },
                },
                "auto_execute": True,  # Frontend should auto-execute this navigation
                "description": f"Navigating to bucket: {bucket_name}",
                "url": f"/b/{bucket_name}",
            }
        elif scope == "package":
            # Parse package name (format: bucket/package_name)
            if "/" in target:
                bucket_name, package_name = target.split("/", 1)
            else:
                bucket_name = target
                package_name = ""
            
            return {
                "tool": "navigate",
                "params": {
                    "route": {
                        "name": "package.overview",
                        "params": {
                            "bucket": bucket_name,
                            "name": package_name,
                        },
                    },
                },
                "auto_execute": True,
                "description": f"Navigating to package: {target}",
                "url": f"/b/{bucket_name}/packages/{package_name}",
            }
        
        return {}

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
    search_type: str = "auto",  # "auto", "packages", "objects", "both"
    backends: Optional[List[str]] = None,
    limit: int = 20,  # Reduced default limit to prevent LLM input length errors
    offset: int = 0,  # Pagination offset for retrieving additional pages
    include_metadata: bool = False,  # Changed default to False to reduce response size
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
        include_metadata: Include rich metadata in results (default: False)
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
            search_type=search_type,
            backends=backends,
            limit=limit,
            offset=offset,
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

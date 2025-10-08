"""Search tools for Quilt MCP Server.

This module exposes the unified search functionality as MCP tools.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

from ..runtime import get_active_token
from ..search.tools.unified_search import unified_search as _unified_search
from ..search.tools.search_suggest import search_suggest as _search_suggest
from ..utils import format_error_response, resolve_catalog_url
from ..types.navigation import (
    NavigationContext,
    get_context_scope_and_target,
    get_context_path_prefix,
    is_prefix_context,
)

logger = logging.getLogger(__name__)


def _enhance_search_result_with_links(search_result: Dict[str, Any], query: str, scope: str, target: str, search_type: str, limit: int, offset: int) -> Dict[str, Any]:
    """Enhance search results with navigation links and context."""
    try:
        from ..utils import resolve_catalog_url
        
        catalog_base = resolve_catalog_url()
        if not catalog_base:
            return search_result
        
        # Clean catalog base URL
        if catalog_base.startswith("https://"):
            base_url = catalog_base
        elif catalog_base.startswith("http://"):
            base_url = catalog_base
        else:
            base_url = f"https://{catalog_base}"
        
        # Add search context to each result
        enhanced_results = []
        for result in search_result.get("results", []):
            enhanced_result = result.copy()
            
            # Add navigation context for each result
            if result.get("type") == "package" and result.get("package_name"):
                # Generate package navigation link
                package_name = result.get("package_name")
                bucket = result.get("metadata", {}).get("bucket", "")
                if bucket and package_name:
                    enhanced_result["navigation"] = {
                        "type": "package",
                        "url": result.get("url", f"{base_url}/b/{bucket}/packages/{package_name}"),
                        "package_name": package_name,
                        "bucket": bucket,
                    }
            elif result.get("type") == "file" and result.get("s3_uri"):
                # Generate file navigation link
                s3_uri = result.get("s3_uri", "")
                if s3_uri.startswith("s3://"):
                    parts = s3_uri[5:].split("/", 1)
                    if len(parts) == 2:
                        bucket, key = parts
                        enhanced_result["navigation"] = {
                            "type": "file",
                            "url": result.get("url", f"{base_url}/b/{bucket}/tree/{key}"),
                            "bucket": bucket,
                            "key": key,
                        }
            
            enhanced_results.append(enhanced_result)
        
        # Update the search result with enhanced results
        search_result["results"] = enhanced_results
        
        # Add search result page link
        search_params = {
            "q": query,
            "scope": scope,
            "type": search_type,
            "limit": str(limit),
            "offset": str(offset)
        }
        
        if target:
            search_params["target"] = target
        
        search_result["search_page_url"] = f"{base_url}/search?" + "&".join([f"{k}={v}" for k, v in search_params.items()])
        
        return search_result
        
    except Exception as e:
        logger.warning(f"Failed to enhance search results with links: {e}")
        return search_result


def search_discover() -> Dict[str, Any]:
    """
    Discover search capabilities and available backends.

    Returns:
        Dict with search capabilities, available backends, and configuration info.
    """
    token = get_active_token()
    if not token:
        return format_error_response("Authorization token required for search discovery")

    catalog_url = resolve_catalog_url()
    if not catalog_url:
        return format_error_response("Catalog URL not configured")

    try:
        return {
            "success": True,
            "search_capabilities": {
                "graphql_search": True,
                "unified_search": True,
            },
            "available_backends": [
                "graphql",
            ],
            "search_scopes": [
                "global",
                "catalog",
                "package",
                "bucket",
            ],
            "supported_filters": [
                "file_extensions",
                "size_gt",
                "size_lt",
                "date_after",
                "date_before",
                "content_type",
            ],
            "common_queries": [
                "CSV files",
                "genomics data",
                "files larger than 100MB",
                "packages created this month",
                "README files",
            ],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.exception(f"Error discovering search capabilities: {e}")
        return format_error_response(f"Failed to discover search capabilities: {str(e)}")


async def search_packages(
    query: str,
    scope: str = "global",
    target: str = "",
    backends: Optional[List[str]] = None,
    limit: int = 100,
    offset: int = 0,
    include_metadata: bool = False,
    explain_query: bool = False,
    filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Search for packages/collections of files.

    This is a convenience function that calls unified_search with search_type="packages".

    Args:
        query: Search query for packages (e.g., "genomics datasets", "machine learning packages")
        scope: Search scope - "global", "catalog", "package", "bucket"
        target: Specific target when scope is narrow
        backends: Preferred backends
        limit: Maximum number of results to return
        offset: Pagination offset
        include_metadata: Include rich metadata in results
        explain_query: Include query execution explanation
        filters: Additional filters

    Returns:
        Search results for packages only

    Examples:
        search_packages("genomics datasets")
        search_packages("machine learning packages", scope="catalog")
        search_packages("datasets", scope="bucket", target="quilt-sandbox-bucket")
    """
    return await unified_search(
        query=query,
        scope=scope,
        target=target,
        search_type="packages",
        backends=backends,
        limit=limit,
        offset=offset,
        include_metadata=include_metadata,
        explain_query=explain_query,
        filters=filters,
    )


async def search_objects(
    query: str,
    scope: str = "global",
    target: str = "",
    backends: Optional[List[str]] = None,
    limit: int = 100,
    offset: int = 0,
    include_metadata: bool = False,
    explain_query: bool = False,
    filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Search for individual files/objects.

    This is a convenience function that calls unified_search with search_type="objects".

    Args:
        query: Search query for files (e.g., "CSV files", "README.md", "*.parquet")
        scope: Search scope - "global", "catalog", "package", "bucket"
        target: Specific target when scope is narrow
        backends: Preferred backends
        limit: Maximum number of results to return
        offset: Pagination offset
        include_metadata: Include rich metadata in results
        explain_query: Include query execution explanation
        filters: Additional filters

    Returns:
        Search results for files/objects only

    Examples:
        search_objects("CSV files")
        search_objects("README files", scope="bucket", target="quilt-sandbox-bucket")
        search_objects("*.parquet", filters={"size_gt": "100MB"})
    """
    return await unified_search(
        query=query,
        scope=scope,
        target=target,
        search_type="objects",
        backends=backends,
        limit=limit,
        offset=offset,
        include_metadata=include_metadata,
        explain_query=explain_query,
        filters=filters,
    )


async def unified_search(
    query: str,
    scope: str = "global",
    target: str = "",
    search_type: str = "auto",  # "auto", "packages", "objects", "both"
    backends: Optional[List[str]] = None,
    limit: int = 100,  # Increased default limit for better search coverage
    offset: int = 0,  # Pagination offset for retrieving additional pages
    include_metadata: bool = False,  # Changed default to False to reduce response size
    include_content_preview: bool = False,
    explain_query: bool = False,
    filters: Optional[Dict[str, Any]] = None,
    count_only: bool = False,
) -> Dict[str, Any]:
    """
    Intelligent unified search across Quilt catalogs, packages, and S3 buckets.

    This tool supports two distinct search types:
    1. **Package Search** - Search for collections/packages of files (e.g., "genomics datasets", "machine learning packages")
    2. **Object Search** - Search for individual files/objects (e.g., "CSV files", "README.md", "*.parquet")

    The tool automatically:
    - Parses natural language queries
    - Selects appropriate search type based on query content
    - Combines and ranks results from multiple sources
    - Provides rich metadata and explanations

    Args:
        query: Natural language search query (e.g., "CSV files", "genomics data", "files larger than 100MB")
        scope: Search scope - "global" (all), "catalog" (current catalog), "package" (specific package), "bucket" (specific bucket)
        target: Specific target when scope is narrow (package name like "user/dataset" or bucket like "s3://my-bucket")
        search_type: Type of search to perform:
            - "auto" (default): Automatically detect based on query content
            - "packages": Search only for packages/collections
            - "objects": Search only for individual files/objects
            - "both": Search both packages and objects
        backends: Preferred backends - ["auto"] (intelligent selection), ["elasticsearch"], ["graphql"], ["s3"], or combinations
        limit: Maximum number of results to return (default: 100)
        offset: Pagination offset for retrieving additional pages (default: 0)
        include_metadata: Include rich metadata in results (default: False)
        include_content_preview: Include content previews for files (default: False)
        explain_query: Include query execution explanation and backend selection reasoning (default: False)
        filters: Additional filters as dict - e.g., {"file_extensions": ["csv"], "size_gt": "100MB", "date_after": "2023-01-01"}

    Returns:
        Unified search results with metadata, explanations, and suggestions

    Examples:
        # Package Search Examples
        unified_search("genomics datasets", search_type="packages")
        unified_search("machine learning packages", scope="catalog", search_type="packages")

        # Object Search Examples
        unified_search("CSV files", search_type="objects")
        unified_search("README files", search_type="objects", scope="bucket", target="quilt-sandbox-bucket")
        unified_search("*.parquet", search_type="objects", filters={"size_gt": "100MB"})

        # Auto-detection (default)
        unified_search("CSV files in genomics packages")  # Will search both packages and objects
        unified_search("datasets", search_type="auto")  # Will likely focus on packages

        # Pagination
        unified_search("CSV files", scope="bucket", target="quilt-open-ccle-virginia", limit=50, offset=20)
    """
    try:
        # Force GraphQL backend regardless of caller input
        backends = ["graphql"]

        # Simply await the async function - FastMCP supports async tools
        # This preserves the ContextVar (JWT token) from the request middleware
        # Execute the search
        search_result = await _unified_search(
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
            count_only=count_only,
        )
        
        # Enhance the result with search context and links
        if search_result.get("success"):
            search_result = _enhance_search_result_with_links(search_result, query, scope, target, search_type, limit, offset)
        
        return search_result
    except (RuntimeError, asyncio.TimeoutError, OSError) as e:
        return {
            "success": False,
            "error": f"Unified search failed: {e}",
            "query": query,
            "scope": scope,
            "target": target,
            "help": {
                "common_queries": [
                    "CSV files",
                    "genomics data",
                    "files larger than 100MB",
                    "packages created this month",
                ],
                "scopes": ["global", "catalog", "package", "bucket"],
                "backends": ["graphql"],
            },
        }


def search_suggest(
    partial_query: str,
    context: str = "",
    suggestion_types: Optional[List[str]] = None,
    limit: int = 10,
) -> Dict[str, Any]:
    """
    Get intelligent search suggestions based on partial queries and context.

    Args:
        partial_query: Partial or incomplete search query
        context: Additional context to improve suggestions
        suggestion_types: Types of suggestions to generate - ["auto"], ["query"], ["filter"], ["scope"]
        limit: Maximum number of suggestions to return

    Returns:
        Search suggestions with explanations and examples
    """
    try:
        if suggestion_types is None:
            suggestion_types = ["auto"]

        return _search_suggest(
            partial_query=partial_query,
            context=context,
            suggestion_types=suggestion_types,
            limit=limit,
        )
    except (RuntimeError, ValueError) as e:
        return {
            "success": False,
            "error": f"Search suggestions failed: {e}",
            "partial_query": partial_query,
        }


def search_explain(
    query: str,
) -> Dict[str, Any]:
    """
    Explain how a search query would be processed by the search engine.

    This action analyzes the query and returns detailed information about:
    - Query type detection (file search, package discovery, etc.)
    - Extracted keywords and filters
    - Suggested backends for optimal search
    - Confidence score for the analysis
    
    Useful for understanding how the search engine interprets your query
    and for debugging unexpected search results.

    Args:
        query: The search query to explain

    Returns:
        Dict with query analysis including:
        - success: bool indicating if explanation succeeded
        - query: The original query string
        - analysis: Detailed analysis of the query including:
            - query_type: Type of query detected (e.g., "file_search", "package_discovery")
            - scope: Search scope (e.g., "global", "catalog")
            - keywords: Extracted keywords from the query
            - file_extensions: File extensions detected in the query
            - filters: Additional filters extracted (size, date, etc.)
            - suggested_backends: Recommended backends for this query
            - confidence: Confidence score (0.0-1.0) for the analysis
        - recommendations: Suggested improvements or alternative queries

    Examples:
        search_explain("CSV files larger than 100MB")
        search_explain("genomics packages created in 2024")
        search_explain("*.parquet files containing RNA-seq data")
    """
    try:
        from ..search.core.query_parser import parse_query

        # Parse the query to get detailed analysis
        analysis = parse_query(query)

        # Format the response with rich explanation
        response = {
            "success": True,
            "query": query,
            "analysis": {
                "query_type": analysis.query_type.value,
                "query_type_description": _get_query_type_description(analysis.query_type.value),
                "scope": analysis.scope.value,
                "keywords": analysis.keywords,
                "file_extensions": analysis.file_extensions,
                "filters": {
                    **analysis.filters,
                    "size_filters": analysis.size_filters if analysis.size_filters else {},
                    "date_filters": analysis.date_filters if analysis.date_filters else {},
                },
                "suggested_backends": analysis.suggested_backends,
                "confidence": analysis.confidence,
            },
            "execution_plan": {
                "backends": analysis.suggested_backends,
                "search_strategy": _get_search_strategy(analysis),
                "expected_result_types": _get_expected_result_types(analysis),
            },
            "recommendations": _get_query_recommendations(analysis),
        }

        return response

    except Exception as e:
        logger.exception(f"Error explaining search query: {e}")
        return {
            "success": False,
            "error": f"Failed to explain search query: {str(e)}",
            "query": query,
        }


def _get_query_type_description(query_type: str) -> str:
    """Get a human-readable description of the query type."""
    descriptions = {
        "file_search": "Searching for individual files/objects",
        "package_discovery": "Discovering packages/collections of files",
        "content_search": "Searching within file contents",
        "metadata_search": "Searching based on metadata attributes",
        "analytical_search": "Analytical query (size, count, aggregations)",
        "cross_catalog": "Search across multiple catalogs",
    }
    return descriptions.get(query_type, "General search")


def _get_search_strategy(analysis) -> str:
    """Generate a human-readable search strategy description."""
    query_type = analysis.query_type.value
    
    if query_type == "file_search":
        strategy = "Search for individual files/objects matching the criteria"
        if analysis.file_extensions:
            strategy += f" with extensions: {', '.join(analysis.file_extensions)}"
        if analysis.size_filters:
            strategy += f" and size constraints"
    elif query_type == "package_discovery":
        strategy = "Search for packages/collections containing relevant datasets"
        if analysis.keywords:
            strategy += f" related to: {', '.join(analysis.keywords[:3])}"
    elif query_type == "content_search":
        strategy = "Search within file contents for matching text"
    elif query_type == "metadata_search":
        strategy = "Search based on metadata attributes and properties"
    elif query_type == "analytical_search":
        strategy = "Perform analytical query with aggregations or filters"
    else:
        strategy = "Execute general search across available backends"
    
    return strategy


def _get_expected_result_types(analysis) -> List[str]:
    """Determine what types of results to expect."""
    query_type = analysis.query_type.value
    
    if query_type == "file_search":
        return ["files", "objects"]
    elif query_type == "package_discovery":
        return ["packages", "collections"]
    elif query_type == "content_search":
        return ["files", "objects"]
    elif query_type == "metadata_search":
        return ["packages", "files"]
    elif query_type == "analytical_search":
        return ["aggregated_results", "statistics"]
    else:
        return ["mixed"]


def _get_query_recommendations(analysis) -> List[str]:
    """Generate recommendations for improving the query."""
    recommendations = []
    
    # Recommend being more specific if confidence is low
    if analysis.confidence < 0.6:
        recommendations.append(
            "Consider adding more specific keywords or file extensions to improve search accuracy"
        )
    
    # Recommend narrowing scope if searching globally
    if analysis.scope.value == "global" and not analysis.target:
        recommendations.append(
            "Consider narrowing the search scope to a specific catalog or bucket for faster results"
        )
    
    # Recommend using filters
    if not analysis.filters and not analysis.file_extensions:
        recommendations.append(
            "Add file type filters (e.g., 'CSV files') or size constraints (e.g., 'larger than 10MB') to refine results"
        )
    
    # Recommend checking query type
    if analysis.query_type.value == "file_search" and len(analysis.keywords) > 5:
        recommendations.append(
            "Your query has many keywords - consider if you're looking for a package instead of individual files"
        )
    
    return recommendations if recommendations else ["Query looks good! No specific recommendations."]


async def search(
    action: str | None = None, params: Optional[Dict[str, Any]] = None, _context: Optional[NavigationContext] = None
) -> Dict[str, Any]:
    """
    Intelligent search operations across Quilt catalogs, packages, and S3 buckets.

    Available actions:
    - discover: Discover search capabilities and available backends
    - unified_search: Intelligent unified search with automatic backend selection
    - suggest: Get intelligent search suggestions based on partial queries
    - explain: Explain how a search query would be processed

    Args:
        action: The operation to perform. If None, returns available actions.
        params: Action-specific parameters

    Returns:
        Action-specific response dictionary

    Examples:
        # Discovery mode
        result = search()

        # Discover search capabilities
        result = search(action="discover")

        # Unified search
        result = search(action="unified_search", params={"query": "CSV files"})

        # Get suggestions
        result = search(action="suggest", params={"partial_query": "genom"})

    For detailed parameter documentation, see individual action functions.
    """
    params = params or {}

    try:
        if action is None:
            return {
                "module": "search",
                "actions": [
                    "discover",
                    "unified_search",
                    "search_packages",
                    "search_objects",
                    "suggest",
                    "explain",
                ],
                "description": "Intelligent search operations via Quilt Catalog GraphQL with distinct Package and Object search types",
            }
        elif action == "discover":
            return search_discover()
        elif action == "search_packages":
            # Map frontend parameter names to function parameter names
            mapped_params = {}
            if "query" in params:
                mapped_params["query"] = params["query"]
            if "scope" in params:
                mapped_params["scope"] = params["scope"]
            if "target" in params:
                mapped_params["target"] = params["target"]
            # Map bucket parameter to target for bucket-scoped searches
            if "bucket" in params and not mapped_params.get("target"):
                mapped_params["target"] = params["bucket"]
            if "max_results" in params:
                mapped_params["limit"] = params["max_results"]
            if "limit" in params:
                mapped_params["limit"] = params["limit"]
            if "offset" in params:
                mapped_params["offset"] = params["offset"]
            if "page" in params:
                # Convert page number to offset (page 1 = offset 0, page 2 = offset limit, etc.)
                limit = mapped_params.get("limit", 100)
                mapped_params["offset"] = (params["page"] - 1) * limit
            if "include_metadata" in params:
                mapped_params["include_metadata"] = params["include_metadata"]
            if "explain_query" in params:
                mapped_params["explain_query"] = params["explain_query"]
            if "filters" in params:
                mapped_params["filters"] = params["filters"]

            # Apply navigation context for smart defaults
            if _context:
                # Auto-detect scope and target if not specified
                if not mapped_params.get("scope"):
                    context_scope, context_target = get_context_scope_and_target(_context)
                    mapped_params["scope"] = context_scope
                    if context_target and not mapped_params.get("target"):
                        mapped_params["target"] = context_target

                # Add path prefix filter for directory-aware searches
                if is_prefix_context(_context):
                    path_prefix = get_context_path_prefix(_context)
                    if path_prefix:
                        filters = mapped_params.get("filters", {})
                        filters["path_prefix"] = path_prefix
                        mapped_params["filters"] = filters

            return await search_packages(**mapped_params)
        elif action == "search_objects":
            # Map frontend parameter names to function parameter names
            mapped_params = {}
            if "query" in params:
                mapped_params["query"] = params["query"]
            if "scope" in params:
                mapped_params["scope"] = params["scope"]
            if "target" in params:
                mapped_params["target"] = params["target"]
            # Map bucket parameter to target for bucket-scoped searches
            if "bucket" in params and not mapped_params.get("target"):
                mapped_params["target"] = params["bucket"]
            if "max_results" in params:
                mapped_params["limit"] = params["max_results"]
            if "limit" in params:
                mapped_params["limit"] = params["limit"]
            if "offset" in params:
                mapped_params["offset"] = params["offset"]
            if "page" in params:
                # Convert page number to offset (page 1 = offset 0, page 2 = offset limit, etc.)
                limit = mapped_params.get("limit", 100)
                mapped_params["offset"] = (params["page"] - 1) * limit
            if "include_metadata" in params:
                mapped_params["include_metadata"] = params["include_metadata"]
            if "explain_query" in params:
                mapped_params["explain_query"] = params["explain_query"]
            if "filters" in params:
                mapped_params["filters"] = params["filters"]

            # Apply navigation context for smart defaults
            if _context:
                # Auto-detect scope and target if not specified
                if not mapped_params.get("scope"):
                    context_scope, context_target = get_context_scope_and_target(_context)
                    mapped_params["scope"] = context_scope
                    if context_target and not mapped_params.get("target"):
                        mapped_params["target"] = context_target

                # Add path prefix filter for directory-aware searches
                if is_prefix_context(_context):
                    path_prefix = get_context_path_prefix(_context)
                    if path_prefix:
                        filters = mapped_params.get("filters", {})
                        filters["path_prefix"] = path_prefix
                        mapped_params["filters"] = filters

            return await search_objects(**mapped_params)
        elif action == "unified_search":
            # Map frontend parameter names to function parameter names
            mapped_params = {}
            if "query" in params:
                mapped_params["query"] = params["query"]
            if "scope" in params:
                mapped_params["scope"] = params["scope"]
            if "target" in params:
                mapped_params["target"] = params["target"]
            # Map bucket parameter to target for bucket-scoped searches
            if "bucket" in params and not mapped_params.get("target"):
                mapped_params["target"] = params["bucket"]
            if "search_type" in params:
                mapped_params["search_type"] = params["search_type"]
            if "max_results" in params:
                mapped_params["limit"] = params["max_results"]
            if "limit" in params:
                mapped_params["limit"] = params["limit"]
            if "offset" in params:
                mapped_params["offset"] = params["offset"]
            if "page" in params:
                # Convert page number to offset (page 1 = offset 0, page 2 = offset limit, etc.)
                limit = mapped_params.get("limit", 100)
                mapped_params["offset"] = (params["page"] - 1) * limit
            if "include_metadata" in params:
                mapped_params["include_metadata"] = params["include_metadata"]
            if "include_content_preview" in params:
                mapped_params["include_content_preview"] = params["include_content_preview"]
            if "explain_query" in params:
                mapped_params["explain_query"] = params["explain_query"]
            if "filters" in params:
                mapped_params["filters"] = params["filters"]
            if "count_only" in params:
                mapped_params["count_only"] = params["count_only"]

            # Lightweight intent detection when caller does not specify a search type explicitly
            if "search_type" not in mapped_params:
                query_text = str(mapped_params.get("query") or "").lower()
                file_keywords = (" file", " files", "object", "objects", "readme", "how many files", "how many objects")
                package_keywords = ("package", "packages", "dataset", "datasets", "collection", "collections")
                if any(keyword in query_text for keyword in file_keywords):
                    mapped_params["search_type"] = "objects"
                elif any(keyword in query_text for keyword in package_keywords):
                    mapped_params["search_type"] = "packages"

            # Apply navigation context for smart defaults
            if _context:
                # Auto-detect scope and target if not specified
                if mapped_params.get("scope") == "auto" or not mapped_params.get("scope"):
                    context_scope, context_target = get_context_scope_and_target(_context)
                    mapped_params["scope"] = context_scope
                    if context_target and not mapped_params.get("target"):
                        mapped_params["target"] = context_target

                # Add path prefix filter for directory-aware searches
                if is_prefix_context(_context):
                    path_prefix = get_context_path_prefix(_context)
                    if path_prefix:
                        filters = mapped_params.get("filters", {})
                        filters["path_prefix"] = path_prefix
                        mapped_params["filters"] = filters

            return await unified_search(**mapped_params)
        elif action == "suggest":
            return search_suggest(**params)
        elif action == "explain":
            # Extract query parameter
            if "query" not in params:
                return format_error_response("Parameter 'query' is required for explain action")
            return search_explain(query=params["query"])
        else:
            return format_error_response(f"Unknown search action: {action}")

    except Exception as exc:
        logger.exception(f"Error executing search action '{action}': {exc}")
        return format_error_response(f"Failed to execute search action '{action}': {str(exc)}")

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
    limit: int = 20,
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
    limit: int = 20,
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
        limit: Maximum number of results to return (default: 20)
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
        return await _unified_search(
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




async def search(action: str | None = None, params: Optional[Dict[str, Any]] = None, _context: Optional[NavigationContext] = None) -> Dict[str, Any]:
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
                limit = mapped_params.get("limit", 20)
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
                limit = mapped_params.get("limit", 20)
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
                limit = mapped_params.get("limit", 20)
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
        else:
            return format_error_response(f"Unknown search action: {action}")
    
    except Exception as exc:
        logger.exception(f"Error executing search action '{action}': {exc}")
        return format_error_response(f"Failed to execute search action '{action}': {str(exc)}")

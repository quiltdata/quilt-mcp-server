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


def unified_search(
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
        query: Natural language search query (e.g., "CSV files", "genomics data", "files larger than 100MB")
        scope: Search scope - "global" (all), "catalog" (current catalog), "package" (specific package), "bucket" (specific bucket)
        target: Specific target when scope is narrow (package name like "user/dataset" or bucket like "s3://my-bucket")
        backends: Preferred backends - ["auto"] (intelligent selection), ["elasticsearch"], ["graphql"], ["s3"], or combinations
        limit: Maximum number of results to return (default: 50)
        include_metadata: Include rich metadata in results (default: True)
        include_content_preview: Include content previews for files (default: False)
        explain_query: Include query execution explanation and backend selection reasoning (default: False)
        filters: Additional filters as dict - e.g., {"file_extensions": ["csv"], "size_gt": "100MB", "date_after": "2023-01-01"}

    Returns:
        Unified search results with metadata, explanations, and suggestions

    Examples:
        unified_search("CSV files in genomics packages")
        unified_search("packages created last month", scope="catalog")
        unified_search("README files", scope="package", target="user/dataset")
        unified_search("files larger than 100MB", filters={"size_gt": "100MB"})
        unified_search("*.csv", scope="bucket", target="s3://quilt-example")
    """
    try:
        # Force GraphQL backend regardless of caller input
        backends = ["graphql"]

        # Handle async execution properly for MCP tools
        # IMPORTANT: Don't use ThreadPoolExecutor - it breaks ContextVar propagation
        # The request context (including JWT token) won't be available in the new thread
        try:
            # Try to get the current event loop
            loop = asyncio.get_running_loop()
            # We're in an async context, create a task in the current loop
            # This preserves the ContextVar from the request middleware
            task = asyncio.create_task(
                _unified_search(
                    query=query,
                    scope=scope,
                    target=target,
                    backends=backends,
                    limit=limit,
                    include_metadata=include_metadata,
                    include_content_preview=include_content_preview,
                    explain_query=explain_query,
                    filters=filters,
                    count_only=count_only,
                )
            )
            # Wait for the task to complete synchronously
            return loop.run_until_complete(task)
        except RuntimeError:
            # No event loop running, we can use asyncio.run directly
            return asyncio.run(
                _unified_search(
                    query=query,
                    scope=scope,
                    target=target,
                    backends=backends,
                    limit=limit,
                    include_metadata=include_metadata,
                    include_content_preview=include_content_preview,
                    explain_query=explain_query,
                    filters=filters,
                    count_only=count_only,
                )
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




def search(action: str | None = None, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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
                    "suggest",
                ],
                "description": "Intelligent search operations via Quilt Catalog GraphQL",
            }
        elif action == "discover":
            return search_discover()
        elif action == "unified_search":
            # Map frontend parameter names to function parameter names
            mapped_params = {}
            if "query" in params:
                mapped_params["query"] = params["query"]
            if "scope" in params:
                mapped_params["scope"] = params["scope"]
            if "target" in params:
                mapped_params["target"] = params["target"]
            if "max_results" in params:
                mapped_params["limit"] = params["max_results"]
            if "limit" in params:
                mapped_params["limit"] = params["limit"]
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
            return unified_search(**mapped_params)
        elif action == "suggest":
            return search_suggest(**params)
        else:
            return format_error_response(f"Unknown search action: {action}")
    
    except Exception as exc:
        logger.exception(f"Error executing search action '{action}': {exc}")
        return format_error_response(f"Failed to execute search action '{action}': {str(exc)}")

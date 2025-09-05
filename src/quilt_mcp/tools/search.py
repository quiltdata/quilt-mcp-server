"""Search tools for Quilt MCP Server.

This module exposes the unified search functionality as MCP tools.
"""

import asyncio
from typing import Dict, List, Any, Optional

from ..search.tools.unified_search import unified_search as _unified_search
from ..search.tools.search_suggest import search_suggest as _search_suggest
from ..search.tools.search_explain import search_explain as _search_explain


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
        # Set default backends if None
        if backends is None:
            backends = ["auto"]

        # Handle async execution properly for MCP tools
        try:
            # Try to get the current event loop
            asyncio.get_running_loop()
            # We're in an async context, need to handle this carefully
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
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
                    ),
                )
                return future.result(timeout=30)
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
                "backends": ["auto", "elasticsearch", "graphql", "s3"],
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


def search_explain(query: str, scope: str = "global", target: str = "") -> Dict[str, Any]:
    """
    Explain how a search query would be processed and executed.

    Args:
        query: Search query to explain
        scope: Search scope
        target: Target for scoped searches

    Returns:
        Detailed explanation of query processing and backend selection
    """
    try:
        return _search_explain(query=query)
    except (RuntimeError, ValueError) as e:
        return {
            "success": False,
            "error": f"Search explanation failed: {e}",
            "query": query,
        }

"""Unified search architecture for Quilt MCP Server.

This package provides intelligent, context-aware search capabilities
across Quilt catalogs, packages, and S3 buckets using multiple backends.
"""

from .tools.unified_search import unified_search
from .tools.search_suggest import search_suggest
from .tools.search_explain import search_explain

__all__ = ["unified_search", "search_suggest", "search_explain"]

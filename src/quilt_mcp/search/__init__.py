"""Unified search architecture for Quilt MCP Server.

This package provides intelligent, context-aware search capabilities
across Quilt catalogs, packages, and S3 buckets using GraphQL backend.
"""

from .tools.unified_search import unified_search
from .tools.search_suggest import search_suggest

__all__ = ["unified_search", "search_suggest"]

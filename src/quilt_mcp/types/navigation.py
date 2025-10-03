"""Navigation context types and helpers for MCP tool integration.

This module provides types and utilities for integrating MCP tools with
Qurator's native navigation system.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class RouteParams:
    """Route parameters for navigation context."""
    bucket: Optional[str] = None
    path: Optional[str] = None
    version: Optional[str] = None
    mode: Optional[str] = None


@dataclass
class Route:
    """Route information for navigation context."""
    name: str
    params: Optional[RouteParams] = None


@dataclass
class BucketInfo:
    """Bucket information from stack context."""
    name: str
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None


@dataclass
class StackInfo:
    """Stack information containing available buckets."""
    buckets: List[BucketInfo]


@dataclass
class NavigationContext:
    """Navigation context passed to MCP tools."""
    route: Route
    stack_info: Optional[StackInfo] = None


def get_context_bucket(context: Optional[NavigationContext]) -> Optional[str]:
    """Extract bucket from navigation context."""
    if not context or not context.route.params:
        return None
    return context.route.params.bucket


def get_context_path(context: Optional[NavigationContext]) -> Optional[str]:
    """Extract path from navigation context."""
    if not context or not context.route.params:
        return None
    return context.route.params.path


def get_context_version(context: Optional[NavigationContext]) -> Optional[str]:
    """Extract version from navigation context."""
    if not context or not context.route.params:
        return None
    return context.route.params.version


def is_bucket_context(context: Optional[NavigationContext]) -> bool:
    """Check if we're in a bucket context."""
    if not context:
        return False
    return context.route.name in ["bucket.overview", "bucket.prefix", "bucket.object"]


def is_object_context(context: Optional[NavigationContext]) -> bool:
    """Check if we're viewing a specific object."""
    if not context:
        return False
    return context.route.name == "bucket.object"


def is_prefix_context(context: Optional[NavigationContext]) -> bool:
    """Check if we're viewing a directory/prefix."""
    if not context:
        return False
    return context.route.name == "bucket.prefix"


def get_context_scope_and_target(context: Optional[NavigationContext]) -> tuple[str, str]:
    """Get scope and target from navigation context.
    
    Returns:
        Tuple of (scope, target) where scope is one of:
        - "global" for home/search pages
        - "bucket" for bucket-specific pages
        - "package" for package-specific pages (future)
    """
    if not context:
        return "global", ""
    
    if context.route.name in ["bucket.overview", "bucket.prefix", "bucket.object"]:
        bucket = get_context_bucket(context)
        return "bucket", bucket or ""
    
    if context.route.name in ["home", "search"]:
        return "global", ""
    
    # Default to global scope
    return "global", ""


def get_context_path_prefix(context: Optional[NavigationContext]) -> Optional[str]:
    """Get path prefix from navigation context for directory-aware searches."""
    if not context:
        return None
    
    if context.route.name == "bucket.prefix":
        return get_context_path(context)
    
    if context.route.name == "bucket.object":
        path = get_context_path(context)
        if path and "/" in path:
            # Get directory from file path
            return "/".join(path.split("/")[:-1]) + "/"
    
    return None


def suggest_package_name_from_context(context: Optional[NavigationContext]) -> Optional[str]:
    """Suggest a package name based on navigation context."""
    if not context:
        return None
    
    bucket = get_context_bucket(context)
    if not bucket:
        return None
    
    if context.route.name == "bucket.prefix":
        path = get_context_path(context)
        if path:
            # Use the last directory name as package name
            dir_name = path.rstrip("/").split("/")[-1]
            return f"{bucket}/{dir_name}"
    
    if context.route.name == "bucket.object":
        path = get_context_path(context)
        if path:
            # Use the file name (without extension) as package name
            file_name = path.split("/")[-1]
            if "." in file_name:
                file_name = file_name.rsplit(".", 1)[0]
            return f"{bucket}/{file_name}"
    
    # Default to bucket name
    return bucket


def get_available_buckets(context: Optional[NavigationContext]) -> List[str]:
    """Get list of available buckets from stack context."""
    if not context or not context.stack_info:
        return []
    
    return [bucket.name for bucket in context.stack_info.buckets]


def is_current_object(context: Optional[NavigationContext], bucket: str, key: str) -> bool:
    """Check if the given bucket/key matches the current navigation context."""
    if not context or not is_object_context(context):
        return False
    
    context_bucket = get_context_bucket(context)
    context_path = get_context_path(context)
    
    return context_bucket == bucket and context_path == key

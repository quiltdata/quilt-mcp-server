"""Stack bucket discovery for cross-bucket search."""

import logging
from typing import List, Set, Optional

logger = logging.getLogger(__name__)


def get_stack_buckets() -> List[str]:
    """Get all buckets in the current Quilt stack.

    Returns:
        List of bucket names that are part of the current stack.
        Falls back to just the default bucket if stack discovery fails.
    """
    try:
        # Try GraphQL first (most reliable for enterprise)
        stack_buckets = _get_stack_buckets_via_graphql()
        if stack_buckets:
            logger.info(f"Found {len(stack_buckets)} buckets in stack via GraphQL")
            return list(stack_buckets)

        # Fallback to permission discovery
        stack_buckets = _get_stack_buckets_via_permissions()
        if stack_buckets:
            logger.info(f"Found {len(stack_buckets)} buckets in stack via permissions")
            return list(stack_buckets)

        # No fallback - return empty list if no buckets found
        logger.warning("No stack buckets found")
        return []

    except Exception as e:
        logger.error(f"Failed to discover stack buckets: {e}")
        return []


def _get_stack_buckets_via_graphql() -> Set[str]:
    """Get stack buckets using GraphQL bucketConfigs query."""
    try:
        # Use QuiltOps for backend-agnostic GraphQL queries
        from ..ops.factory import QuiltOpsFactory

        quilt_ops = QuiltOpsFactory.create()

        # Query for bucket configurations (this gets all buckets in the stack)
        query = "query { bucketConfigs { name title } }"

        result = quilt_ops.execute_graphql_query(query=query)

        # Extract bucket names from GraphQL response
        if "data" in result and "bucketConfigs" in result["data"]:
            bucket_names = {bucket["name"] for bucket in result["data"]["bucketConfigs"]}
            logger.debug(f"GraphQL discovered buckets: {list(bucket_names)}")
            return bucket_names
        else:
            logger.debug(f"GraphQL response missing expected data structure: {result}")
            return set()

    except Exception as e:
        logger.debug(f"GraphQL bucket discovery failed: {e}")
        return set()


def _get_stack_buckets_via_permissions() -> Set[str]:
    """Get stack buckets using AWS permission discovery."""
    try:
        from ..services.permission_discovery import AWSPermissionDiscovery

        discovery = AWSPermissionDiscovery()
        accessible_buckets = discovery.discover_accessible_buckets()

        # Return buckets that user has at least read access to
        bucket_names = {bucket.name for bucket in accessible_buckets if bucket.can_read or bucket.can_list}

        logger.debug(f"Permission discovery found buckets: {list(bucket_names)}")
        return bucket_names

    except Exception as e:
        logger.debug(f"Permission-based bucket discovery failed: {e}")
        return set()


def build_stack_search_indices(buckets: Optional[List[str]] = None, packages_only: bool = False) -> str:
    """Build Elasticsearch index pattern for searching across all stack buckets.

    Args:
        buckets: List of bucket names. If None, discovers stack buckets automatically.
        packages_only: If True, only include *_packages indices (not object indices).

    Returns:
        Comma-separated index pattern for Elasticsearch.
        - packages_only=False: "bucket1,bucket1_packages,bucket2,bucket2_packages"
        - packages_only=True:  "bucket1_packages,bucket2_packages"
    """
    if buckets is None:
        buckets = get_stack_buckets()

    if not buckets:
        logger.warning("No buckets found for stack search")
        return ""

    # Build index pattern based on packages_only flag
    indices = []
    for bucket in buckets:
        if packages_only:
            indices.append(f"{bucket}_packages")
        else:
            indices.extend([bucket, f"{bucket}_packages"])

    index_pattern = ",".join(indices)
    logger.debug(f"Built stack search index pattern: {index_pattern} (packages_only={packages_only})")
    return index_pattern


def stack_info() -> dict:
    """Get comprehensive information about the current Quilt stack.

    This tool shows all buckets that are part of your Quilt stack and
    confirms that cross-bucket search is properly configured.

    Returns:
        Dict with stack bucket information and search capabilities.
    """
    try:
        buckets = get_stack_buckets()
        index_pattern = build_stack_search_indices(buckets)

        # Test GraphQL availability
        graphql_buckets = _get_stack_buckets_via_graphql()
        permissions_buckets = _get_stack_buckets_via_permissions()

        discovery_method = "none"
        if graphql_buckets:
            discovery_method = "graphql"
        elif permissions_buckets:
            discovery_method = "permissions"

        return {
            "success": True,
            "stack_buckets": buckets,
            "bucket_count": len(buckets),
            "search_index_pattern": index_pattern,
            "cross_bucket_search_enabled": len(buckets) > 1,
            "discovery_method": discovery_method,
            "discovery_details": {
                "graphql_found": len(graphql_buckets),
                "permissions_found": len(permissions_buckets),
            },
            "search_capabilities": {
                "elasticsearch_indices": len(buckets) * 2,  # Each bucket has 2 indices
                "supports_cross_bucket": len(buckets) > 1,
                "fallback_configured": bool(buckets),
            },
            "message": f"Stack contains {len(buckets)} buckets with cross-bucket search {'enabled' if len(buckets) > 1 else 'not needed (single bucket)'}",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "stack_buckets": [],
            "bucket_count": 0,
            "message": "Failed to discover stack configuration",
        }

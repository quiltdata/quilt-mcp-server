"""Stack bucket discovery for cross-bucket search."""

import logging
from typing import List, Set, Optional
from urllib.parse import urljoin

from ..services.quilt_service import QuiltService

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

        # Final fallback to default bucket
        from ..constants import DEFAULT_REGISTRY

        if DEFAULT_REGISTRY:
            bucket_name = DEFAULT_REGISTRY.replace("s3://", "")
            logger.info(f"Falling back to default bucket: {bucket_name}")
            return [bucket_name]

        logger.warning("No stack buckets found and no default bucket configured")
        return []

    except Exception as e:
        logger.error(f"Failed to discover stack buckets: {e}")
        # Emergency fallback
        from ..constants import DEFAULT_REGISTRY

        if DEFAULT_REGISTRY:
            return [DEFAULT_REGISTRY.replace("s3://", "")]
        return []


def _get_stack_buckets_via_graphql() -> Set[str]:
    """Get stack buckets using GraphQL bucketConfigs query."""
    try:
        quilt_service = QuiltService()

        # Get the authenticated session from QuiltService
        if quilt_service.has_session_support():
            session = quilt_service.get_session()
            registry_url = quilt_service.get_registry_url()

            if not registry_url:
                logger.debug("No registry URL available for GraphQL query")
                return set()

            # Construct GraphQL endpoint URL
            graphql_url = urljoin(registry_url.rstrip("/") + "/", "graphql")
            logger.debug(f"Querying GraphQL endpoint: {graphql_url}")

            # Query for bucket configurations (this gets all buckets in the stack)
            query = {"query": "query { bucketConfigs { name title } }"}

            response = session.post(graphql_url, json=query)

            if response.status_code == 200:
                data = response.json()
                if "data" in data and "bucketConfigs" in data["data"]:
                    bucket_names = {bucket["name"] for bucket in data["data"]["bucketConfigs"]}
                    logger.debug(f"GraphQL discovered buckets: {list(bucket_names)}")
                    return bucket_names
                else:
                    logger.debug(f"GraphQL response missing expected data structure: {data}")
                    return set()
            else:
                logger.debug(f"GraphQL query failed with status {response.status_code}: {response.text}")
                return set()

    except Exception as e:
        logger.debug(f"GraphQL bucket discovery failed: {e}")
        return set()

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


def build_stack_search_indices(buckets: Optional[List[str]] = None) -> str:
    """Build Elasticsearch index pattern for searching across all stack buckets.

    Args:
        buckets: List of bucket names. If None, discovers stack buckets automatically.

    Returns:
        Comma-separated index pattern for Elasticsearch (e.g., "bucket1,bucket1_packages,bucket2,bucket2_packages")
    """
    if buckets is None:
        buckets = get_stack_buckets()

    if not buckets:
        logger.warning("No buckets found for stack search")
        return ""

    # Build index pattern: for each bucket, include both the main index and packages index
    indices = []
    for bucket in buckets:
        indices.extend([bucket, f"{bucket}_packages"])

    index_pattern = ",".join(indices)
    logger.debug(f"Built stack search index pattern: {index_pattern}")
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

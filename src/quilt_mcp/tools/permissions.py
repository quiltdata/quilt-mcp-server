"""AWS Permissions Discovery MCP Tools.

This module provides MCP tools for discovering AWS permissions and providing
intelligent bucket recommendations based on user's actual access levels.
"""

from typing import Dict, List, Any, Optional
import logging
from datetime import datetime, timezone

from ..services.permission_discovery import AWSPermissionDiscovery, PermissionLevel
from ..utils import format_error_response

logger = logging.getLogger(__name__)

# Global permission discovery instance
_permission_discovery = None


def _get_permission_discovery() -> AWSPermissionDiscovery:
    """Get or create the global permission discovery instance."""
    global _permission_discovery
    if _permission_discovery is None:
        _permission_discovery = AWSPermissionDiscovery()
    return _permission_discovery


def aws_permissions_discover(
    check_buckets: Optional[List[str]] = None,
    include_cross_account: bool = False,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """
    Discover AWS permissions for current user/role.

    Args:
        check_buckets: Specific buckets to check (optional)
        include_cross_account: Include cross-account accessible buckets
        force_refresh: Force refresh of cached permissions

    Returns:
        Comprehensive permission report with bucket access levels
    """
    try:
        discovery = _get_permission_discovery()

        if force_refresh:
            discovery.clear_cache()

        # Discover user identity
        identity = discovery.discover_user_identity()

        # Discover accessible buckets
        if check_buckets:
            # Check specific buckets
            bucket_permissions = []
            for bucket_name in check_buckets:
                try:
                    bucket_info = discovery.discover_bucket_permissions(bucket_name)
                    bucket_permissions.append(bucket_info._asdict())
                except Exception as e:
                    logger.warning(f"Failed to check bucket {bucket_name}: {e}")
                    bucket_permissions.append(
                        {
                            "name": bucket_name,
                            "permission_level": PermissionLevel.NO_ACCESS.value,
                            "error_message": str(e),
                        }
                    )
        else:
            # Discover all accessible buckets
            accessible_buckets = discovery.discover_accessible_buckets(include_cross_account)
            bucket_permissions = [bucket._asdict() for bucket in accessible_buckets]

        # Categorize buckets by permission level
        categorized_buckets = {
            "full_access": [],
            "read_write": [],
            "read_only": [],
            "list_only": [],
            "no_access": [],
        }

        for bucket in bucket_permissions:
            permission_level = bucket.get("permission_level")
            if isinstance(permission_level, PermissionLevel):
                permission_level = permission_level.value

            category = permission_level.replace("_", "_").lower()
            if category in categorized_buckets:
                categorized_buckets[category].append(bucket)

        # Generate recommendations
        recommendations = _generate_bucket_recommendations(bucket_permissions, identity)

        # Get cache statistics
        cache_stats = discovery.get_cache_stats()

        return {
            "success": True,
            "user_identity": identity._asdict(),
            "bucket_permissions": bucket_permissions,
            "categorized_buckets": categorized_buckets,
            "recommendations": recommendations,
            "cache_stats": cache_stats,
            "discovery_timestamp": datetime.now(timezone.utc).isoformat(),
            "total_buckets_checked": len(bucket_permissions),
        }

    except Exception as e:
        logger.error(f"Error discovering AWS permissions: {e}")
        return format_error_response(f"Failed to discover AWS permissions: {str(e)}")


def bucket_access_check(bucket_name: str, operations: List[str] = None) -> Dict[str, Any]:
    """
    Check specific access permissions for a bucket.

    Args:
        bucket_name: S3 bucket to check
        operations: List of operations to validate (default: ["read", "write", "list"])

    Returns:
        Detailed access report for the specified bucket
    """
    if operations is None:
        operations = ["read", "write", "list"]

    try:
        discovery = _get_permission_discovery()

        # Get comprehensive bucket info
        bucket_info = discovery.discover_bucket_permissions(bucket_name)

        # Test specific operations if requested
        operation_results = discovery.test_bucket_operations(bucket_name, operations)

        # Add helpful guidance for uncertain permissions
        guidance = []
        if bucket_info.permission_level == PermissionLevel.READ_ONLY:
            guidance.append(
                "This bucket appears to be read-only. Consider using a different bucket for package creation."
            )
        elif bucket_info.permission_level == PermissionLevel.LIST_ONLY:
            guidance.append(
                "Limited access detected. You can see bucket contents but may not be able to read or write files."
            )
        elif bucket_info.permission_level == PermissionLevel.NO_ACCESS:
            guidance.append("No access detected. Check your AWS permissions or verify the bucket name.")

        # Add quilt-specific guidance
        if bucket_info.can_write:
            guidance.append("✅ This bucket can be used for Quilt package creation.")
        else:
            guidance.append("❌ This bucket cannot be used for Quilt package creation (no write access).")

        return {
            "success": True,
            "bucket_name": bucket_name,
            "permission_level": bucket_info.permission_level.value,
            "access_summary": {
                "can_read": bucket_info.can_read,
                "can_write": bucket_info.can_write,
                "can_list": bucket_info.can_list,
            },
            "operation_tests": operation_results,
            "bucket_region": bucket_info.region,
            "last_checked": bucket_info.last_checked.isoformat(),
            "error_message": bucket_info.error_message,
            "guidance": guidance,
            "quilt_compatible": bucket_info.can_write,
            "recommended_for_packages": bucket_info.permission_level
            in [PermissionLevel.FULL_ACCESS, PermissionLevel.READ_WRITE],
        }

    except Exception as e:
        logger.error(f"Error checking bucket access for {bucket_name}: {e}")
        return format_error_response(f"Failed to check bucket access: {str(e)}")


def bucket_recommendations_get(
    source_bucket: Optional[str] = None,
    operation_type: str = "package_creation",
    user_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Get smart bucket recommendations based on permissions and context.

    Args:
        source_bucket: Source bucket for context (optional)
        operation_type: Type of operation needing bucket access
        user_context: Additional context (department, project, etc.)

    Returns:
        Categorized bucket recommendations with rationale
    """
    try:
        discovery = _get_permission_discovery()

        # Discover accessible buckets
        accessible_buckets = discovery.discover_accessible_buckets()

        # Filter for writable buckets
        writable_buckets = [
            bucket
            for bucket in accessible_buckets
            if bucket.can_write
            and bucket.permission_level in [PermissionLevel.FULL_ACCESS, PermissionLevel.READ_WRITE]
        ]

        # Generate recommendations
        recommendations = _generate_smart_recommendations(
            writable_buckets, source_bucket, operation_type, user_context
        )

        return {
            "success": True,
            "operation_type": operation_type,
            "source_bucket": source_bucket,
            "recommendations": recommendations,
            "total_writable_buckets": len(writable_buckets),
            "total_accessible_buckets": len(accessible_buckets),
            "recommendation_timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Error generating bucket recommendations: {e}")
        return format_error_response(f"Failed to generate recommendations: {str(e)}")


def _generate_bucket_recommendations(bucket_permissions: List[Dict[str, Any]], identity) -> Dict[str, List[str]]:
    """Generate general bucket recommendations based on permissions."""
    recommendations = {
        "package_creation": [],
        "data_storage": [],
        "temporary_storage": [],
    }

    for bucket in bucket_permissions:
        bucket_name = bucket["name"]
        permission_level = bucket.get("permission_level")

        if permission_level in ["full_access", "read_write"]:
            # Categorize based on naming patterns
            bucket_lower = bucket_name.lower()

            if any(pattern in bucket_lower for pattern in ["package", "registry", "quilt"]):
                recommendations["package_creation"].append(bucket_name)
            elif any(pattern in bucket_lower for pattern in ["data", "storage", "warehouse"]):
                recommendations["data_storage"].append(bucket_name)
            elif any(pattern in bucket_lower for pattern in ["temp", "tmp", "scratch", "work"]):
                recommendations["temporary_storage"].append(bucket_name)
            else:
                recommendations["data_storage"].append(bucket_name)

    return recommendations


def _generate_smart_recommendations(
    writable_buckets: List,
    source_bucket: Optional[str],
    operation_type: str,
    user_context: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Generate smart, context-aware bucket recommendations."""
    primary_recommendations = []
    alternative_options = []

    # Score buckets based on various factors
    scored_buckets = []

    for bucket in writable_buckets:
        score = 0
        rationale = []

        bucket_name = bucket.name.lower()

        # Scoring based on naming patterns
        if operation_type == "package_creation":
            if any(pattern in bucket_name for pattern in ["package", "registry", "quilt"]):
                score += 50
                rationale.append("Naming pattern suggests package storage")

            if source_bucket:
                source_lower = source_bucket.lower()
                # Look for related naming patterns
                if any(part in bucket_name for part in source_lower.split("-")):
                    score += 30
                    rationale.append("Related to source bucket naming pattern")

        # Scoring based on permission level
        if bucket.permission_level == PermissionLevel.FULL_ACCESS:
            score += 20
            rationale.append("Full administrative access")
        elif bucket.permission_level == PermissionLevel.READ_WRITE:
            score += 10
            rationale.append("Read and write access")

        # User context scoring
        if user_context:
            if "department" in user_context:
                dept = user_context["department"].lower()
                if dept in bucket_name:
                    score += 25
                    rationale.append(f"Matches {user_context['department']} department")

        scored_buckets.append({"bucket": bucket, "score": score, "rationale": rationale})

    # Sort by score and categorize
    scored_buckets.sort(key=lambda x: x["score"], reverse=True)

    for scored in scored_buckets[:3]:  # Top 3 as primary
        primary_recommendations.append(
            {
                "bucket_name": scored["bucket"].name,
                "permission_level": scored["bucket"].permission_level.value,
                "score": scored["score"],
                "rationale": scored["rationale"],
                "region": scored["bucket"].region,
            }
        )

    for scored in scored_buckets[3:]:  # Rest as alternatives
        alternative_options.append(
            {
                "bucket_name": scored["bucket"].name,
                "permission_level": scored["bucket"].permission_level.value,
                "rationale": scored["rationale"],
            }
        )

    return {
        "primary_recommendations": primary_recommendations,
        "alternative_options": alternative_options,
        "recommendation_criteria": {
            "operation_type": operation_type,
            "source_context": source_bucket,
            "user_context": user_context,
            "scoring_factors": [
                "naming_patterns",
                "permission_levels",
                "user_context_matching",
                "source_bucket_relationships",
            ],
        },
    }

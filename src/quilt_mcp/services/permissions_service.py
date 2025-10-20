"""Service layer for AWS permission discovery helpers.

These helpers wrap :mod:`quilt_mcp.services.permission_discovery` to provide
the high-level behaviours that were previously exposed via
``quilt_mcp.tools.permissions``. Resources and tests should depend on this
module instead of the legacy tool shim.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from quilt_mcp.services.permission_discovery import (
    AWSPermissionDiscovery,
    PermissionLevel,
)
from quilt_mcp.utils import format_error_response

logger = logging.getLogger(__name__)

_permission_discovery: Optional[AWSPermissionDiscovery] = None


def get_permission_discovery() -> AWSPermissionDiscovery:
    """Return the singleton :class:`AWSPermissionDiscovery` instance."""
    global _permission_discovery
    if _permission_discovery is None:
        _permission_discovery = AWSPermissionDiscovery()
    return _permission_discovery


def discover_permissions(
    check_buckets: Optional[List[str]] = None,
    include_cross_account: bool = False,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """Discover AWS permissions for the current principal."""
    try:
        discovery = get_permission_discovery()

        if force_refresh:
            discovery.clear_cache()

        identity = discovery.discover_user_identity()

        if check_buckets:
            bucket_permissions = []
            for bucket_name in check_buckets:
                try:
                    bucket_info = discovery.discover_bucket_permissions(bucket_name)
                    bucket_permissions.append(bucket_info._asdict())
                except Exception as exc:  # pragma: no cover - defensive logging
                    logger.warning("Failed to check bucket %s: %s", bucket_name, exc)
                    bucket_permissions.append(
                        {
                            "name": bucket_name,
                            "permission_level": PermissionLevel.NO_ACCESS.value,
                            "error_message": str(exc),
                        }
                    )
        else:
            accessible_buckets = discovery.discover_accessible_buckets(include_cross_account)
            bucket_permissions = [bucket._asdict() for bucket in accessible_buckets]

        categorized_buckets: Dict[str, List[Dict[str, Any]]] = {
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

            category = str(permission_level).lower()
            if category in categorized_buckets:
                categorized_buckets[category].append(bucket)

        recommendations = _generate_bucket_recommendations(bucket_permissions, identity)
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

    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Error discovering AWS permissions: %s", exc)
        return format_error_response(f"Failed to discover AWS permissions: {exc}")


def check_bucket_access(bucket_name: str, operations: Optional[List[str]] = None) -> Dict[str, Any]:
    """Check the caller's access to ``bucket_name``."""
    if operations is None:
        operations = ["read", "write", "list"]

    try:
        discovery = get_permission_discovery()

        bucket_info = discovery.discover_bucket_permissions(bucket_name)
        operation_results = discovery.test_bucket_operations(bucket_name, operations)

        guidance: List[str] = []
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
            in {PermissionLevel.FULL_ACCESS, PermissionLevel.READ_WRITE},
        }

    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Error checking bucket access for %s: %s", bucket_name, exc)
        return format_error_response(f"Failed to check bucket access: {exc}")


def bucket_recommendations_get(
    source_bucket: Optional[str] = None,
    operation_type: str = "package_creation",
    user_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Return context-aware bucket recommendations."""
    try:
        discovery = get_permission_discovery()
        accessible_buckets = discovery.discover_accessible_buckets()

        writable_buckets = [
            bucket
            for bucket in accessible_buckets
            if bucket.can_write
            and bucket.permission_level in (PermissionLevel.FULL_ACCESS, PermissionLevel.READ_WRITE)
        ]

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

    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Error generating bucket recommendations: %s", exc)
        return format_error_response(f"Failed to generate recommendations: {exc}")


def _generate_bucket_recommendations(bucket_permissions: List[Dict[str, Any]], identity) -> Dict[str, List[str]]:
    recommendations: Dict[str, List[str]] = {
        "package_creation": [],
        "data_storage": [],
        "temporary_storage": [],
    }

    for bucket in bucket_permissions:
        bucket_name = bucket["name"]
        permission_level = bucket.get("permission_level")

        if permission_level in ["full_access", "read_write"]:
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
    primary_recommendations: List[Dict[str, Any]] = []
    alternative_options: List[Dict[str, Any]] = []

    scored_buckets = []

    for bucket in writable_buckets:
        score = 0
        rationale: List[str] = []

        bucket_name = bucket.name.lower()

        if operation_type == "package_creation":
            if any(pattern in bucket_name for pattern in ["package", "registry", "quilt"]):
                score += 50
                rationale.append("Naming pattern suggests package storage")

            if source_bucket:
                source_lower = source_bucket.lower()
                if any(part in bucket_name for part in source_lower.split("-")):
                    score += 30
                    rationale.append("Related to source bucket naming pattern")

        if bucket.permission_level == PermissionLevel.FULL_ACCESS:
            score += 20
            rationale.append("Full administrative access")
        elif bucket.permission_level == PermissionLevel.READ_WRITE:
            score += 10
            rationale.append("Read and write access")

        if user_context and "department" in user_context:
            dept = user_context["department"].lower()
            if dept in bucket_name:
                score += 25
                rationale.append(f"Matches {user_context['department']} department")

        scored_buckets.append({"bucket": bucket, "score": score, "rationale": rationale})

    scored_buckets.sort(key=lambda item: item["score"], reverse=True)

    for scored in scored_buckets[:3]:
        primary_recommendations.append(
            {
                "bucket_name": scored["bucket"].name,
                "permission_level": scored["bucket"].permission_level.value,
                "score": scored["score"],
                "rationale": scored["rationale"],
                "region": scored["bucket"].region,
            }
        )

    for scored in scored_buckets[3:]:
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

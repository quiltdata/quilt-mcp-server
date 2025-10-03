"""
Permissions discovery and access checking via Quilt Catalog GraphQL API.

This module queries the Quilt Catalog to determine:
- User identity and role
- Accessible buckets
- Bucket permission levels

All operations use the catalog GraphQL API with the user's JWT token.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

from ..runtime import get_active_token
from ..utils import format_error_response, resolve_catalog_url
from ..clients import catalog as catalog_client

logger = logging.getLogger(__name__)


def permissions_discover(
    check_buckets: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Discover user permissions via Quilt Catalog GraphQL API.

    Args:
        check_buckets: Specific buckets to check (optional)

    Returns:
        Comprehensive permission report with bucket access levels
    """
    token = get_active_token()
    if not token:
        return format_error_response("Authorization token required for permissions discovery")

    catalog_url = resolve_catalog_url()
    if not catalog_url:
        return format_error_response("Catalog URL not configured")

    try:
        # Debug logging
        logger.info(f"Starting permissions discovery with token: {token[:20] if token else 'None'}...")
        logger.info(f"Catalog URL: {catalog_url}")

        # Query user identity
        me_query = """
            query Me {
                me {
                    name
                    email
                    isAdmin
                    role {
                        name
                    }
                    roles {
                        name
                    }
                }
            }
        """

        logger.info(f"Making GraphQL query to: {catalog_url}")
        me_data = catalog_client.catalog_graphql_query(
            registry_url=catalog_url,
            query=me_query,
            auth_token=token,
        )
        logger.info(f"GraphQL query successful, got user data: {bool(me_data.get('me'))}")

        user_data = me_data.get("me")
        if not user_data:
            return format_error_response("No user data returned from catalog")

        # Query accessible buckets with collaborators to get permission levels
        buckets_query = """
            query BucketConfigs {
                bucketConfigs {
                    name
                    title
                    description
                    browsable
                    lastIndexed
                    collaborators {
                        collaborator {
                            email
                            username
                        }
                        permissionLevel
                    }
                }
            }
        """

        buckets_data = catalog_client.catalog_graphql_query(
            registry_url=catalog_url,
            query=buckets_query,
            auth_token=token,
        )

        all_buckets = buckets_data.get("bucketConfigs", [])

        # Filter to specific buckets if requested
        if check_buckets:
            bucket_set = set(check_buckets)
            filtered_buckets = [b for b in all_buckets if b.get("name") in bucket_set]

            # Add any requested buckets that weren't found (no access)
            found_names = {b.get("name") for b in filtered_buckets}
            for bucket_name in check_buckets:
                if bucket_name not in found_names:
                    filtered_buckets.append(
                        {
                            "name": bucket_name,
                            "permission_level": "no_access",
                            "accessible": False,
                        }
                    )

            bucket_permissions = filtered_buckets
        else:
            bucket_permissions = all_buckets

        # Get user email for permission checking
        user_email = user_data.get("email")

        # Format bucket info with actual permission levels
        formatted_buckets = []
        for bucket in bucket_permissions:
            if bucket.get("accessible") is False:
                # Bucket not accessible
                formatted_buckets.append(
                    {
                        "name": bucket["name"],
                        "permission_level": "no_access",
                        "accessible": False,
                    }
                )
            else:
                # Determine actual permission level from collaborators
                permission_level = "read_access"  # Default
                collaborators = bucket.get("collaborators", [])

                for collab in collaborators:
                    collab_email = collab.get("collaborator", {}).get("email")
                    if collab_email == user_email:
                        level = collab.get("permissionLevel")
                        if level == "READ_WRITE":
                            permission_level = "write_access"
                        elif level == "READ":
                            permission_level = "read_access"
                        break

                formatted_buckets.append(
                    {
                        "name": bucket["name"],
                        "title": bucket.get("title", ""),
                        "description": bucket.get("description", ""),
                        "browsable": bucket.get("browsable", False),
                        "last_indexed": bucket.get("lastIndexed"),
                        "permission_level": permission_level,
                        "accessible": True,
                    }
                )

        # Categorize buckets by access
        categorized = {
            "accessible": [b for b in formatted_buckets if b.get("accessible")],
            "not_accessible": [b for b in formatted_buckets if not b.get("accessible")],
        }

        return {
            "success": True,
            "user_identity": {
                "name": user_data.get("name"),
                "email": user_data.get("email"),
                "is_admin": user_data.get("isAdmin", False),
                "role": user_data.get("role", {}).get("name"),
                "roles": [r.get("name") for r in user_data.get("roles", [])],
            },
            "bucket_permissions": formatted_buckets,
            "categorized_buckets": categorized,
            "discovery_timestamp": datetime.now(timezone.utc).isoformat(),
            "total_buckets_checked": len(formatted_buckets),
            "catalog_url": catalog_url,
        }

    except Exception as e:
        logger.exception("Error discovering permissions via catalog")
        return format_error_response(f"Failed to discover permissions: {str(e)}")


def bucket_access_check(bucket_name: str) -> Dict[str, Any]:
    """
    Check access permissions for a specific bucket via Quilt Catalog.

    Args:
        bucket_name: S3 bucket to check

    Returns:
        Access check results including permission level
    """
    if not bucket_name:
        return format_error_response("Bucket name is required")

    token = get_active_token()
    if not token:
        return format_error_response("Authorization token required for bucket access check")

    catalog_url = resolve_catalog_url()
    if not catalog_url:
        return format_error_response("Catalog URL not configured")

    try:
        # Query specific bucket config with collaborators to get permission level
        bucket_query = """
            query BucketConfig($name: String!) {
                bucketConfig(name: $name) {
                    name
                    title
                    description
                    browsable
                    lastIndexed
                    collaborators {
                        collaborator {
                            email
                            username
                        }
                        permissionLevel
                    }
                }
            }
        """

        bucket_data = catalog_client.catalog_graphql_query(
            registry_url=catalog_url,
            query=bucket_query,
            variables={"name": bucket_name},
            auth_token=token,
        )

        bucket_config = bucket_data.get("bucketConfig")

        if not bucket_config:
            return {
                "success": True,
                "bucket_name": bucket_name,
                "accessible": False,
                "permission_level": "no_access",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        # Determine actual permission level from collaborators and role information
        user_email = None
        try:
            # Get current user email from token context
            me_data = catalog_client.catalog_graphql_query(
                registry_url=catalog_url,
                query="query { me { email } }",
                auth_token=token,
            )
            user_email = me_data.get("me", {}).get("email")
        except Exception:
            pass  # If we can't get user email, we'll use default logic

        # Check collaborators for user's permission level
        permission_level = "read_access"  # Default
        collaborators = bucket_config.get("collaborators", [])

        # First try to get permission from explicit collaborators
        for collab in collaborators:
            collab_email = collab.get("collaborator", {}).get("email")
            if collab_email == user_email:
                level = collab.get("permissionLevel")
                if level == "READ_WRITE":
                    permission_level = "write_access"
                elif level == "READ":
                    permission_level = "read_access"
                break

        # If no explicit collaborator permission found, check if user has admin role
        # (Admin users typically have write access to all buckets)
        if permission_level == "read_access" and user_email:
            try:
                me_data = catalog_client.catalog_graphql_query(
                    registry_url=catalog_url,
                    query="query { me { isAdmin } }",
                    auth_token=token,
                )
                is_admin = me_data.get("me", {}).get("isAdmin", False)
                if is_admin:
                    permission_level = "write_access"
            except Exception:
                pass

        return {
            "success": True,
            "bucket_name": bucket_name,
            "title": bucket_config.get("title", ""),
            "description": bucket_config.get("description", ""),
            "browsable": bucket_config.get("browsable", False),
            "last_indexed": bucket_config.get("lastIndexed"),
            "accessible": True,
            "permission_level": permission_level,
            "user_email": user_email,
            "collaborators_count": len(collaborators),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.exception(f"Error checking bucket access for {bucket_name}")
        return format_error_response(f"Failed to check bucket access: {str(e)}")


def permissions_recommendations_get() -> Dict[str, Any]:
    """
    Get recommendations for improving permissions and access patterns.

    Returns:
        List of recommendations based on current permissions
    """
    # Get current permissions
    perms = permissions_discover()

    if not perms.get("success"):
        return perms

    recommendations = []

    user_identity = perms.get("user_identity", {})
    accessible_buckets = perms.get("categorized_buckets", {}).get("accessible", [])

    # Generate recommendations
    if user_identity.get("is_admin"):
        recommendations.append(
            {
                "category": "security",
                "priority": "info",
                "message": "You have admin privileges. Use them responsibly.",
            }
        )

    if len(accessible_buckets) == 0:
        recommendations.append(
            {
                "category": "access",
                "priority": "warning",
                "message": "No accessible buckets found. Contact your administrator if you need bucket access.",
            }
        )
    elif len(accessible_buckets) > 20:
        recommendations.append(
            {
                "category": "organization",
                "priority": "info",
                "message": f"You have access to {len(accessible_buckets)} buckets. Consider organizing them with favorites or tags.",
            }
        )

    return {
        "success": True,
        "recommendations": recommendations,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def permissions(action: Optional[str] = None, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Unified permissions module wrapper.

    Args:
        action: The permissions action to perform
        params: Action-specific parameters

    Returns:
        Action result or module info
    """
    if action is None:
        return {
            "module": "permissions",
            "actions": [
                "discover",
                "access_check",
                "check_bucket_access",  # Alias for access_check
                "recommendations_get",
            ],
            "description": "Discover user permissions and bucket access via Quilt Catalog",
        }

    params = params or {}

    try:
        if action == "discover":
            return permissions_discover(
                check_buckets=params.get("check_buckets"),
            )
        elif action == "access_check" or action == "check_bucket_access":
            # Support both 'bucket_name' and 'bucket' parameter names
            bucket_name = params.get("bucket_name") or params.get("bucket")
            return bucket_access_check(
                bucket_name=bucket_name,
            )
        elif action == "recommendations_get":
            return permissions_recommendations_get()
        else:
            return format_error_response(f"Unknown permissions action: {action}")

    except Exception as exc:
        logger.exception(f"Permissions action {action} failed")
        return format_error_response(f"Permissions action failed: {exc}")

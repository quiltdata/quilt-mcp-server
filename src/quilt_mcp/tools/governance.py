"""Stateless GraphQL-based governance tools for Quilt catalog admin operations.

These tools use the Quilt catalog GraphQL admin API to manage users, roles,
SSO configuration, and tabulator settings. All operations require admin privileges.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from ..utils import format_error_response

logger = logging.getLogger(__name__)

# Import GraphQL-based implementations
from .governance_impl import (
    admin_users_list,
    admin_user_get,
    admin_user_create,
    admin_user_delete,
    admin_user_set_email,
    admin_user_set_admin,
    admin_user_set_active,
)

from .governance_impl_part2 import (
    admin_roles_list,
    admin_role_get,
    admin_role_create,
    admin_role_delete,
    admin_sso_config_get,
    admin_sso_config_set,
    admin_tabulator_list,
    admin_tabulator_create,
    admin_tabulator_delete,
    admin_tabulator_open_query_get,
    admin_tabulator_open_query_set,
)
from .governance_impl_part3 import (
    admin_policies_list,
    admin_policy_get,
    admin_policy_create_managed,
    admin_policy_create_unmanaged,
    admin_policy_update_managed,
    admin_policy_update_unmanaged,
    admin_policy_delete,
)


async def admin(action: Optional[str] = None, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Quilt catalog administration and governance operations (ADMIN ONLY).
    
    Use this tool for administrative operations on Quilt catalogs including user management,
    role administration, SSO configuration, and tabulator table settings. All operations
    require administrative privileges on the Quilt catalog.
    
    **When to use this tool:**
    - Managing catalog users (list, create, modify, delete users)
    - Managing IAM roles and permissions
    - Configuring single sign-on (SSO) settings
    - Administering tabulator table configurations
    - Any operation requiring catalog admin privileges
    
    Available actions:
    - users_list: List all users in the catalog
    - user_get: Get detailed information about a specific user
    - user_create: Create a new catalog user
    - user_delete: Delete a user from the catalog
    - user_set_email: Update a user's email address
    - user_set_admin: Grant or revoke admin privileges for a user
    - user_set_active: Activate or deactivate a user account
    - roles_list: List all IAM roles configured in the catalog
    - role_get: Get details about a specific IAM role
    - role_create: Create a new IAM role
    - role_delete: Delete an IAM role
    - sso_config_get: Get current SSO configuration
    - sso_config_set: Update SSO configuration settings
    - policies_list: List all policies in the catalog
    - policy_get: Get details about a specific policy
    - policy_create_managed: Create a managed policy with bucket permissions
    - policy_create_unmanaged: Create an unmanaged policy with IAM ARN
    - policy_update_managed: Update a managed policy
    - policy_update_unmanaged: Update an unmanaged policy
    - policy_delete: Delete a policy
    - tabulator_list: List tabulator tables for a bucket
    - tabulator_create: Create a new tabulator table
    - tabulator_delete: Delete a tabulator table
    - tabulator_open_query_get: Get open query setting for a table
    - tabulator_open_query_set: Set open query setting for a table

    Args:
        action: The admin action to perform. If None, returns available actions.
        params: Action-specific parameters as a dictionary

    Returns:
        Action-specific response dictionary with success status and data/error

    Examples:
        # Discovery mode - list available actions
        result = admin()
        
        # List all catalog users (admin only)
        result = admin(action="users_list")
        
        # Get specific user details
        result = admin(action="user_get", params={"username": "john.doe"})
        
        # Create a new user
        result = admin(action="user_create", params={
            "username": "jane.doe",
            "email": "jane.doe@example.com"
        })
        
        # List IAM roles
        result = admin(action="roles_list")
        
        # Get SSO configuration
        result = admin(action="sso_config_get")
        
        # List tabulator tables for a bucket
        result = admin(action="tabulator_list", params={"bucket_name": "my-bucket"})

    For detailed parameter documentation, see individual action functions.
    """
    if action is None:
        return {
            "module": "admin",
            "actions": [
                "users_list",
                "user_get",
                "user_create",
                "user_delete",
                "user_set_email",
                "user_set_admin",
                "user_set_active",
                "roles_list",
                "role_get",
                "role_create",
                "role_delete",
                "policies_list",
                "policy_get",
                "policy_create_managed",
                "policy_create_unmanaged",
                "policy_update_managed",
                "policy_update_unmanaged",
                "policy_delete",
                "sso_config_get",
                "sso_config_set",
                "tabulator_list",
                "tabulator_create",
                "tabulator_delete",
                "tabulator_open_query_get",
                "tabulator_open_query_set",
            ],
        }

    params = params or {}
    dispatch_map = {
        "users_list": admin_users_list,
        "user_get": admin_user_get,
        "user_create": admin_user_create,
        "user_delete": admin_user_delete,
        "user_set_email": admin_user_set_email,
        "user_set_admin": admin_user_set_admin,
        "user_set_active": admin_user_set_active,
        "roles_list": admin_roles_list,
        "role_get": admin_role_get,
        "role_create": admin_role_create,
        "role_delete": admin_role_delete,
        "policies_list": admin_policies_list,
        "policy_get": admin_policy_get,
        "policy_create_managed": admin_policy_create_managed,
        "policy_create_unmanaged": admin_policy_create_unmanaged,
        "policy_update_managed": admin_policy_update_managed,
        "policy_update_unmanaged": admin_policy_update_unmanaged,
        "policy_delete": admin_policy_delete,
        "sso_config_get": admin_sso_config_get,
        "sso_config_set": admin_sso_config_set,
        "tabulator_list": admin_tabulator_list,
        "tabulator_create": admin_tabulator_create,
        "tabulator_delete": admin_tabulator_delete,
        "tabulator_open_query_get": admin_tabulator_open_query_get,
        "tabulator_open_query_set": admin_tabulator_open_query_set,
    }

    func = dispatch_map.get(action)
    if func is None:
        return format_error_response(f"Unknown governance action: {action}")

    try:
        if callable(func):
            # All governance functions are async, so await them
            return await func(**params)
        return format_error_response(f"Governance action not callable: {action}")
    except Exception as exc:
        logger.exception("Admin action %s failed", action)
        return format_error_response(f"Admin action failed: {exc}")


# Re-export all functions for direct import
__all__ = [
    "admin_users_list",
    "admin_user_get",
    "admin_user_create",
    "admin_user_delete",
    "admin_user_set_email",
    "admin_user_set_admin",
    "admin_user_set_active",
    "admin_roles_list",
    "admin_role_get",
    "admin_role_create",
    "admin_role_delete",
    "admin_sso_config_get",
    "admin_sso_config_set",
    "admin_tabulator_list",
    "admin_tabulator_create",
    "admin_tabulator_delete",
    "admin_tabulator_open_query_get",
    "admin_tabulator_open_query_set",
    "admin_policies_list",
    "admin_policy_get",
    "admin_policy_create_managed",
    "admin_policy_create_unmanaged",
    "admin_policy_update_managed",
    "admin_policy_update_unmanaged",
    "admin_policy_delete",
    "admin",  # Main wrapper function
    "governance",  # Deprecated alias for backwards compatibility
]

# Backwards compatibility alias
governance = admin

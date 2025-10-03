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


def governance(action: Optional[str] = None, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Governance and administration tool dispatcher.
    
    Args:
        action: The governance action to perform
        params: Parameters for the action
        
    Returns:
        Result dictionary with success status and data/error
    """
    if action is None:
        return {
            "module": "governance",
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
            # Check if function is async
            if getattr(func, "__code__", None) and func.__code__.co_flags & 0x80:
                import asyncio
                return asyncio.get_event_loop().run_until_complete(func(**params))
            return func(**params)
        return format_error_response(f"Governance action not callable: {action}")
    except Exception as exc:
        logger.exception("Governance action %s failed", action)
        return format_error_response(f"Governance action failed: {exc}")


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
    "governance",
]

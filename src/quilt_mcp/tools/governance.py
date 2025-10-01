"""Stateless stubs for Quilt governance tools.

These tools previously relied on quilt3 admin APIs. Until stateless catalog
admin endpoints are available, we surface clear error messages while still
validating basic input and token/catalog configuration.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..runtime import get_active_token
from ..utils import format_error_response, resolve_catalog_url

logger = logging.getLogger(__name__)


def _admin_unavailable(message: Optional[str] = None) -> Dict[str, Any]:
    """Common response helper for admin operations."""

    token = get_active_token()
    catalog_url = resolve_catalog_url()

    if not token:
        return format_error_response("Authorization token required for admin operations")

    if not catalog_url:
        return format_error_response("Catalog URL not configured for admin operations")

    return format_error_response(message or "Admin APIs are not yet available in the stateless backend")


async def admin_users_list() -> Dict[str, Any]:
    return _admin_unavailable()


async def admin_user_get(name: str) -> Dict[str, Any]:
    if not name:
        return format_error_response("Username cannot be empty")
    return _admin_unavailable()


async def admin_user_create(
    name: str,
    email: str,
    role: str,
    extra_roles: Optional[List[str]] = None,
) -> Dict[str, Any]:
    if not name:
        return format_error_response("Username cannot be empty")
    if not email:
        return format_error_response("Email cannot be empty")
    if "@" not in email or "." not in email:
        return format_error_response("Invalid email format")
    if not role:
        return format_error_response("Role cannot be empty")
    return _admin_unavailable()


async def admin_user_delete(name: str) -> Dict[str, Any]:
    if not name:
        return format_error_response("Username cannot be empty")
    return _admin_unavailable()


async def admin_user_set_email(name: str, email: str) -> Dict[str, Any]:
    if not name:
        return format_error_response("Username cannot be empty")
    if not email:
        return format_error_response("Email cannot be empty")
    if "@" not in email or "." not in email:
        return format_error_response("Invalid email format")
    return _admin_unavailable()


async def admin_user_set_admin(name: str, admin: bool) -> Dict[str, Any]:
    if not name:
        return format_error_response("Username cannot be empty")
    return _admin_unavailable()


async def admin_user_set_active(name: str, active: bool) -> Dict[str, Any]:
    if not name:
        return format_error_response("Username cannot be empty")
    return _admin_unavailable()


async def admin_roles_list() -> Dict[str, Any]:
    return _admin_unavailable()


async def admin_role_get(name: str) -> Dict[str, Any]:
    if not name:
        return format_error_response("Role name cannot be empty")
    return _admin_unavailable()


async def admin_role_create(name: str, description: str) -> Dict[str, Any]:
    if not name:
        return format_error_response("Role name cannot be empty")
    return _admin_unavailable()


async def admin_role_delete(name: str) -> Dict[str, Any]:
    if not name:
        return format_error_response("Role name cannot be empty")
    return _admin_unavailable()


async def admin_sso_config_get() -> Dict[str, Any]:
    return _admin_unavailable()


async def admin_sso_config_set(config: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(config, dict) or not config:
        return format_error_response("SSO configuration must be a non-empty dictionary")
    return _admin_unavailable()


async def admin_tabulator_list(bucket_name: str) -> Dict[str, Any]:
    if not bucket_name:
        return format_error_response("Bucket name cannot be empty")
    return _admin_unavailable()


async def admin_tabulator_create(
    bucket_name: str,
    table_name: str,
    config_yaml: str,
) -> Dict[str, Any]:
    if not bucket_name:
        return format_error_response("Bucket name cannot be empty")
    if not table_name:
        return format_error_response("Table name cannot be empty")
    if not config_yaml:
        return format_error_response("Tabulator configuration cannot be empty")
    return _admin_unavailable()


async def admin_tabulator_delete(bucket_name: str, table_name: str) -> Dict[str, Any]:
    if not bucket_name:
        return format_error_response("Bucket name cannot be empty")
    if not table_name:
        return format_error_response("Table name cannot be empty")
    return _admin_unavailable()

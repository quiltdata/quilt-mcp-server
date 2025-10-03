"""Governance implementation part 2: Roles, SSO, and Tabulator."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

from ..clients.catalog import catalog_graphql_query
from ..runtime import get_active_token
from ..utils import format_error_response, resolve_catalog_url

logger = logging.getLogger(__name__)


def _require_admin_auth() -> tuple[str, str]:
    """Validate and return token and catalog URL for admin operations."""
    token = get_active_token()
    if not token:
        raise ValueError("Authorization token required for admin operations")

    catalog_url = resolve_catalog_url()
    if not catalog_url:
        raise ValueError("Catalog URL not configured for admin operations")

    return token, catalog_url


# Role Management Functions


async def admin_roles_list() -> Dict[str, Any]:
    """List all roles in the catalog (admin only)."""
    try:
        token, catalog_url = _require_admin_auth()
    except ValueError as e:
        return format_error_response(str(e))

    query = """
    query AdminRolesList {
      roles {
        ... on ManagedRole {
          id
          name
          arn
          policies {
            id
            title
          }
          permissions {
            bucket { name }
            level
          }
        }
        ... on UnmanagedRole {
          id
          name
          arn
        }
      }
    }
    """

    try:
        result = catalog_graphql_query(
            registry_url=catalog_url,
            query=query,
            auth_token=token,
        )

        roles = result.get("roles", [])
        return {
            "success": True,
            "roles": roles,
            "count": len(roles),
        }
    except Exception as e:
        logger.exception("Failed to list roles")
        return format_error_response(f"Failed to list roles: {e}")


async def admin_role_get(role_id: str) -> Dict[str, Any]:
    """Get details for a specific role by ID (admin only).

    Note: The GraphQL schema uses role IDs, not names.
    """
    if not role_id:
        return format_error_response("Role ID cannot be empty")

    try:
        token, catalog_url = _require_admin_auth()
    except ValueError as e:
        return format_error_response(str(e))

    query = """
    query AdminRoleGet($id: ID!) {
      role(id: $id) {
        ... on ManagedRole {
          id
          name
          arn
          policies {
            id
            title
            arn
          }
          permissions {
            bucket { name }
            level
          }
        }
        ... on UnmanagedRole {
          id
          name
          arn
        }
      }
    }
    """

    try:
        result = catalog_graphql_query(
            registry_url=catalog_url,
            query=query,
            variables={"id": role_id},
            auth_token=token,
        )

        role = result.get("role")
        if not role:
            return format_error_response(f"Role '{role_id}' not found")

        return {
            "success": True,
            "role": role,
        }
    except Exception as e:
        logger.exception("Failed to get role")
        return format_error_response(f"Failed to get role: {e}")


async def admin_role_create(name: str, description: str) -> Dict[str, Any]:
    """Create a new role (admin only).

    Note: This is a simplified stub. The actual GraphQL schema requires
    complex inputs (ManagedRoleInput or UnmanagedRoleInput) including
    policies and ARNs. This function signature needs updating.

    Args:
        name: Role name
        description: Role description (currently unused due to schema complexity)
    """
    if not name:
        return format_error_response("Role name cannot be empty")

    # Note: description argument is ignored because the GraphQL schema requires
    # complex role inputs that include policies, ARNs, etc.
    return format_error_response(
        "Role creation requires complex inputs (policies, ARNs). "
        "Use the Quilt catalog UI or contact support for role management."
    )


async def admin_role_delete(role_id: str) -> Dict[str, Any]:
    """Delete a role by ID (admin only).

    Note: The GraphQL schema uses role IDs, not names.
    """
    if not role_id:
        return format_error_response("Role ID cannot be empty")

    try:
        token, catalog_url = _require_admin_auth()
    except ValueError as e:
        return format_error_response(str(e))

    mutation = """
    mutation AdminRoleDelete($id: ID!) {
      roleDelete(id: $id) {
        ... on Ok { _ }
        ... on InvalidInput {
          errors { name message }
        }
        ... on OperationError {
          message
        }
      }
    }
    """

    try:
        result = catalog_graphql_query(
            registry_url=catalog_url,
            query=mutation,
            variables={"id": role_id},
            auth_token=token,
        )

        delete_result = result.get("roleDelete", {})

        if "_" in delete_result:
            return {
                "success": True,
                "message": f"Role '{role_id}' deleted successfully",
            }
        elif "errors" in delete_result:
            errors = delete_result["errors"]
            error_msgs = [f"{err.get('name', 'Error')}: {err.get('message', '')}" for err in errors]
            return format_error_response("Invalid input: " + "; ".join(error_msgs))
        elif "message" in delete_result:
            return format_error_response(f"Operation error: {delete_result['message']}")
        else:
            return format_error_response(f"Unexpected response: {delete_result}")

    except Exception as e:
        logger.exception("Failed to delete role")
        return format_error_response(f"Failed to delete role: {e}")


# SSO Configuration Functions


async def admin_sso_config_get() -> Dict[str, Any]:
    """Get SSO configuration (admin only)."""
    try:
        token, catalog_url = _require_admin_auth()
    except ValueError as e:
        return format_error_response(str(e))

    query = """
    query AdminSsoConfigGet {
      admin {
        ssoConfig {
          text
          timestamp
          uploader {
            name
            email
          }
        }
      }
    }
    """

    try:
        result = catalog_graphql_query(
            registry_url=catalog_url,
            query=query,
            auth_token=token,
        )

        sso_config = result.get("admin", {}).get("ssoConfig")

        return {
            "success": True,
            "sso_config": sso_config,  # Can be null if not configured
        }
    except Exception as e:
        logger.exception("Failed to get SSO config")
        return format_error_response(f"Failed to get SSO config: {e}")


async def admin_sso_config_set(config: Dict[str, Any]) -> Dict[str, Any]:
    """Set SSO configuration (admin only).

    Note: The GraphQL schema expects a String (JSON), not a Dict.
    """
    if not isinstance(config, dict) or not config:
        return format_error_response("SSO configuration must be a non-empty dictionary")

    try:
        token, catalog_url = _require_admin_auth()
    except ValueError as e:
        return format_error_response(str(e))

    # Convert dict to JSON string
    try:
        config_str = json.dumps(config)
    except (TypeError, ValueError) as e:
        return format_error_response(f"Invalid SSO configuration format: {e}")

    mutation = """
    mutation AdminSsoConfigSet($config: String) {
      admin {
        setSsoConfig(config: $config) {
          ... on SsoConfig {
            text
            timestamp
            uploader {
              name
              email
            }
          }
          ... on InvalidInput {
            errors { name message }
          }
          ... on OperationError {
            message
          }
        }
      }
    }
    """

    try:
        result = catalog_graphql_query(
            registry_url=catalog_url,
            query=mutation,
            variables={"config": config_str},
            auth_token=token,
        )

        set_result = result.get("admin", {}).get("setSsoConfig", {})

        if "text" in set_result and "timestamp" in set_result:
            return {
                "success": True,
                "sso_config": set_result,
            }
        elif "errors" in set_result:
            errors = set_result["errors"]
            error_msgs = [f"{err.get('name', 'Error')}: {err.get('message', '')}" for err in errors]
            return format_error_response("Invalid input: " + "; ".join(error_msgs))
        elif "message" in set_result:
            return format_error_response(f"Operation error: {set_result['message']}")
        else:
            return format_error_response(f"Unexpected response: {set_result}")

    except Exception as e:
        logger.exception("Failed to set SSO config")
        return format_error_response(f"Failed to set SSO config: {e}")


# Tabulator Functions


async def admin_tabulator_list(bucket_name: str) -> Dict[str, Any]:
    """List tabulator tables for a bucket (admin only).

    Note: This is not a direct admin query. It queries bucket config.
    """
    if not bucket_name:
        return format_error_response("Bucket name cannot be empty")

    try:
        token, catalog_url = _require_admin_auth()
    except ValueError as e:
        return format_error_response(str(e))

    query = """
    query AdminTabulatorList($bucketName: String!) {
      bucketConfig(name: $bucketName) {
        name
        tabulatorTables {
          name
          config
        }
      }
    }
    """

    try:
        result = catalog_graphql_query(
            registry_url=catalog_url,
            query=query,
            variables={"bucketName": bucket_name},
            auth_token=token,
        )

        bucket_config = result.get("bucketConfig")
        if not bucket_config:
            return format_error_response(f"Bucket '{bucket_name}' not found")

        tables = bucket_config.get("tabulatorTables", [])

        return {
            "success": True,
            "bucket": bucket_name,
            "tables": tables,
            "count": len(tables),
        }
    except Exception as e:
        logger.exception("Failed to list tabulator tables")
        return format_error_response(f"Failed to list tabulator tables: {e}")


async def admin_tabulator_create(
    bucket_name: str,
    table_name: str,
    config_yaml: str,
) -> Dict[str, Any]:
    """Create or update a tabulator table (admin only)."""
    if not bucket_name:
        return format_error_response("Bucket name cannot be empty")
    if not table_name:
        return format_error_response("Table name cannot be empty")
    if not config_yaml:
        return format_error_response("Tabulator configuration cannot be empty")

    try:
        token, catalog_url = _require_admin_auth()
    except ValueError as e:
        return format_error_response(str(e))

    mutation = """
    mutation AdminTabulatorCreate($bucketName: String!, $tableName: String!, $config: String) {
      admin {
        bucketSetTabulatorTable(bucketName: $bucketName, tableName: $tableName, config: $config) {
          ... on BucketConfig {
            name
            tabulatorTables {
              name
              config
            }
          }
          ... on InvalidInput {
            errors { name message }
          }
          ... on OperationError {
            message
          }
        }
      }
    }
    """

    try:
        result = catalog_graphql_query(
            registry_url=catalog_url,
            query=mutation,
            variables={
                "bucketName": bucket_name,
                "tableName": table_name,
                "config": config_yaml,
            },
            auth_token=token,
        )

        set_result = result.get("admin", {}).get("bucketSetTabulatorTable", {})

        if "name" in set_result and "tabulatorTables" in set_result:
            return {
                "success": True,
                "bucket": set_result["name"],
                "tables": set_result["tabulatorTables"],
            }
        elif "errors" in set_result:
            errors = set_result["errors"]
            error_msgs = [f"{err.get('name', 'Error')}: {err.get('message', '')}" for err in errors]
            return format_error_response("Invalid input: " + "; ".join(error_msgs))
        elif "message" in set_result:
            return format_error_response(f"Operation error: {set_result['message']}")
        else:
            return format_error_response(f"Unexpected response: {set_result}")

    except Exception as e:
        logger.exception("Failed to create tabulator table")
        return format_error_response(f"Failed to create tabulator table: {e}")


async def admin_tabulator_delete(bucket_name: str, table_name: str) -> Dict[str, Any]:
    """Delete a tabulator table (admin only).

    Note: Delete is done by setting config to null.
    """
    if not bucket_name:
        return format_error_response("Bucket name cannot be empty")
    if not table_name:
        return format_error_response("Table name cannot be empty")

    try:
        token, catalog_url = _require_admin_auth()
    except ValueError as e:
        return format_error_response(str(e))

    mutation = """
    mutation AdminTabulatorDelete($bucketName: String!, $tableName: String!) {
      admin {
        bucketSetTabulatorTable(bucketName: $bucketName, tableName: $tableName, config: null) {
          ... on BucketConfig {
            name
            tabulatorTables {
              name
              config
            }
          }
          ... on InvalidInput {
            errors { name message }
          }
          ... on OperationError {
            message
          }
        }
      }
    }
    """

    try:
        result = catalog_graphql_query(
            registry_url=catalog_url,
            query=mutation,
            variables={
                "bucketName": bucket_name,
                "tableName": table_name,
            },
            auth_token=token,
        )

        delete_result = result.get("admin", {}).get("bucketSetTabulatorTable", {})

        if "name" in delete_result:
            return {
                "success": True,
                "message": f"Tabulator table '{table_name}' deleted from bucket '{bucket_name}'",
                "bucket": delete_result["name"],
            }
        elif "errors" in delete_result:
            errors = delete_result["errors"]
            error_msgs = [f"{err.get('name', 'Error')}: {err.get('message', '')}" for err in errors]
            return format_error_response("Invalid input: " + "; ".join(error_msgs))
        elif "message" in delete_result:
            return format_error_response(f"Operation error: {delete_result['message']}")
        else:
            return format_error_response(f"Unexpected response: {delete_result}")

    except Exception as e:
        logger.exception("Failed to delete tabulator table")
        return format_error_response(f"Failed to delete tabulator table: {e}")


async def admin_tabulator_open_query_get() -> Dict[str, Any]:
    """Get tabulator open query status (admin only)."""
    try:
        token, catalog_url = _require_admin_auth()
    except ValueError as e:
        return format_error_response(str(e))

    query = """
    query AdminTabulatorOpenQueryGet {
      admin {
        tabulatorOpenQuery
      }
    }
    """

    try:
        result = catalog_graphql_query(
            registry_url=catalog_url,
            query=query,
            auth_token=token,
        )

        open_query = result.get("admin", {}).get("tabulatorOpenQuery")

        return {
            "success": True,
            "open_query_enabled": open_query,
        }
    except Exception as e:
        logger.exception("Failed to get tabulator open query status")
        return format_error_response(f"Failed to get tabulator open query status: {e}")


async def admin_tabulator_open_query_set(enabled: bool) -> Dict[str, Any]:
    """Set tabulator open query status (admin only)."""
    if not isinstance(enabled, bool):
        return format_error_response("enabled must be a boolean value")

    try:
        token, catalog_url = _require_admin_auth()
    except ValueError as e:
        return format_error_response(str(e))

    mutation = """
    mutation AdminTabulatorOpenQuerySet($enabled: Boolean!) {
      admin {
        setTabulatorOpenQuery(enabled: $enabled) {
          tabulatorOpenQuery
        }
      }
    }
    """

    try:
        result = catalog_graphql_query(
            registry_url=catalog_url,
            query=mutation,
            variables={"enabled": enabled},
            auth_token=token,
        )

        set_result = result.get("admin", {}).get("setTabulatorOpenQuery", {})

        if "tabulatorOpenQuery" in set_result:
            return {
                "success": True,
                "open_query_enabled": set_result["tabulatorOpenQuery"],
            }
        else:
            return format_error_response(f"Unexpected response: {set_result}")

    except Exception as e:
        logger.exception("Failed to set tabulator open query status")
        return format_error_response(f"Failed to set tabulator open query status: {e}")

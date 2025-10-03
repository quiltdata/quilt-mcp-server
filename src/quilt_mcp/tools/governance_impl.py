"""GraphQL-based implementation of governance tools."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

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


def _handle_graphql_union_result(result: Dict[str, Any], expected_type: str) -> Dict[str, Any]:
    """Handle GraphQL union response types (Success | InvalidInput | OperationError)."""
    if expected_type in result:
        return {"success": True, "data": result[expected_type]}
    
    # Check for InvalidInput
    if "errors" in result and isinstance(result["errors"], list):
        error_msgs = [f"{err.get('name', 'Error')}: {err.get('message', '')}" 
                      for err in result["errors"]]
        return format_error_response("Invalid input: " + "; ".join(error_msgs))
    
    # Check for OperationError
    if "message" in result:
        return format_error_response(f"Operation error: {result['message']}")
    
    # Unknown format
    return format_error_response(f"Unexpected response format: {result}")


# User Management Functions

async def admin_users_list() -> Dict[str, Any]:
    """List all users in the catalog (admin only)."""
    try:
        token, catalog_url = _require_admin_auth()
    except ValueError as e:
        return format_error_response(str(e))
    
    query = """
    query AdminUsersList {
      admin {
        user {
          list {
            name
            email
            dateJoined
            lastLogin
            isActive
            isAdmin
            isSsoOnly
            isService
            role {
              ... on ManagedRole { name arn }
              ... on UnmanagedRole { name arn }
            }
            extraRoles {
              ... on ManagedRole { name arn }
              ... on UnmanagedRole { name arn }
            }
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
        
        users = result.get("admin", {}).get("user", {}).get("list", [])
        return {
            "success": True,
            "users": users,
            "count": len(users),
        }
    except Exception as e:
        logger.exception("Failed to list users")
        return format_error_response(f"Failed to list users: {e}")


async def admin_user_get(name: str) -> Dict[str, Any]:
    """Get details for a specific user (admin only)."""
    if not name:
        return format_error_response("Username cannot be empty")
    
    try:
        token, catalog_url = _require_admin_auth()
    except ValueError as e:
        return format_error_response(str(e))
    
    query = """
    query AdminUserGet($name: String!) {
      admin {
        user {
          get(name: $name) {
            name
            email
            dateJoined
            lastLogin
            isActive
            isAdmin
            isSsoOnly
            isService
            role {
              ... on ManagedRole { name arn }
              ... on UnmanagedRole { name arn }
            }
            extraRoles {
              ... on ManagedRole { name arn }
              ... on UnmanagedRole { name arn }
            }
            isRoleAssignmentDisabled
            isAdminAssignmentDisabled
          }
        }
      }
    }
    """
    
    try:
        result = catalog_graphql_query(
            registry_url=catalog_url,
            query=query,
            variables={"name": name},
            auth_token=token,
        )
        
        user = result.get("admin", {}).get("user", {}).get("get")
        if not user:
            return format_error_response(f"User '{name}' not found")
        
        return {
            "success": True,
            "user": user,
        }
    except Exception as e:
        logger.exception("Failed to get user")
        return format_error_response(f"Failed to get user: {e}")


async def admin_user_create(
    name: str,
    email: str,
    role: str,
    extra_roles: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Create a new user (admin only)."""
    if not name:
        return format_error_response("Username cannot be empty")
    if not email:
        return format_error_response("Email cannot be empty")
    if "@" not in email or "." not in email:
        return format_error_response("Invalid email format")
    if not role:
        return format_error_response("Role cannot be empty")
    
    try:
        token, catalog_url = _require_admin_auth()
    except ValueError as e:
        return format_error_response(str(e))
    
    mutation = """
    mutation AdminUserCreate($input: UserInput!) {
      admin {
        user {
          create(input: $input) {
            ... on User {
              name
              email
              isActive
              isAdmin
              role {
                ... on ManagedRole { name }
                ... on UnmanagedRole { name }
              }
            }
            ... on InvalidInput {
              errors {
                name
                message
                path
              }
            }
            ... on OperationError {
              message
              name
            }
          }
        }
      }
    }
    """
    
    user_input = {
        "name": name,
        "email": email,
        "role": role,
        "extraRoles": extra_roles or [],
    }
    
    try:
        result = catalog_graphql_query(
            registry_url=catalog_url,
            query=mutation,
            variables={"input": user_input},
            auth_token=token,
        )
        
        create_result = result.get("admin", {}).get("user", {}).get("create", {})
        
        # Handle union result
        if "name" in create_result and "email" in create_result:
            return {
                "success": True,
                "user": create_result,
            }
        elif "errors" in create_result:
            errors = create_result["errors"]
            error_msgs = [f"{err.get('name', 'Error')}: {err.get('message', '')}" 
                          for err in errors]
            return format_error_response("Invalid input: " + "; ".join(error_msgs))
        elif "message" in create_result:
            return format_error_response(f"Operation error: {create_result['message']}")
        else:
            return format_error_response(f"Unexpected response: {create_result}")
            
    except Exception as e:
        logger.exception("Failed to create user")
        return format_error_response(f"Failed to create user: {e}")


async def admin_user_delete(name: str) -> Dict[str, Any]:
    """Delete a user (admin only)."""
    if not name:
        return format_error_response("Username cannot be empty")
    
    try:
        token, catalog_url = _require_admin_auth()
    except ValueError as e:
        return format_error_response(str(e))
    
    mutation = """
    mutation AdminUserDelete($name: String!) {
      admin {
        user {
          mutate(name: $name) {
            delete {
              ... on Ok {
                _
              }
              ... on InvalidInput {
                errors {
                  name
                  message
                }
              }
              ... on OperationError {
                message
                name
              }
            }
          }
        }
      }
    }
    """
    
    try:
        result = catalog_graphql_query(
            registry_url=catalog_url,
            query=mutation,
            variables={"name": name},
            auth_token=token,
        )
        
        delete_result = result.get("admin", {}).get("user", {}).get("mutate", {}).get("delete", {})
        
        # Handle union result
        if "_" in delete_result:
            return {
                "success": True,
                "message": f"User '{name}' deleted successfully",
            }
        elif "errors" in delete_result:
            errors = delete_result["errors"]
            error_msgs = [f"{err.get('name', 'Error')}: {err.get('message', '')}" 
                          for err in errors]
            return format_error_response("Invalid input: " + "; ".join(error_msgs))
        elif "message" in delete_result:
            return format_error_response(f"Operation error: {delete_result['message']}")
        else:
            return format_error_response(f"Unexpected response: {delete_result}")
            
    except Exception as e:
        logger.exception("Failed to delete user")
        return format_error_response(f"Failed to delete user: {e}")


async def admin_user_set_email(name: str, email: str) -> Dict[str, Any]:
    """Update user's email address (admin only)."""
    if not name:
        return format_error_response("Username cannot be empty")
    if not email:
        return format_error_response("Email cannot be empty")
    if "@" not in email or "." not in email:
        return format_error_response("Invalid email format")
    
    try:
        token, catalog_url = _require_admin_auth()
    except ValueError as e:
        return format_error_response(str(e))
    
    mutation = """
    mutation AdminUserSetEmail($name: String!, $email: String!) {
      admin {
        user {
          mutate(name: $name) {
            setEmail(email: $email) {
              ... on User {
                name
                email
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
      }
    }
    """
    
    try:
        result = catalog_graphql_query(
            registry_url=catalog_url,
            query=mutation,
            variables={"name": name, "email": email},
            auth_token=token,
        )
        
        update_result = result.get("admin", {}).get("user", {}).get("mutate", {}).get("setEmail", {})
        
        if "name" in update_result and "email" in update_result:
            return {
                "success": True,
                "user": update_result,
            }
        elif "errors" in update_result:
            errors = update_result["errors"]
            error_msgs = [f"{err.get('name', 'Error')}: {err.get('message', '')}" 
                          for err in errors]
            return format_error_response("Invalid input: " + "; ".join(error_msgs))
        elif "message" in update_result:
            return format_error_response(f"Operation error: {update_result['message']}")
        else:
            return format_error_response(f"Unexpected response: {update_result}")
            
    except Exception as e:
        logger.exception("Failed to set user email")
        return format_error_response(f"Failed to set user email: {e}")


async def admin_user_set_admin(name: str, admin: bool) -> Dict[str, Any]:
    """Set user's admin status (admin only)."""
    if not name:
        return format_error_response("Username cannot be empty")
    
    try:
        token, catalog_url = _require_admin_auth()
    except ValueError as e:
        return format_error_response(str(e))
    
    mutation = """
    mutation AdminUserSetAdmin($name: String!, $admin: Boolean!) {
      admin {
        user {
          mutate(name: $name) {
            setAdmin(admin: $admin) {
              ... on User {
                name
                isAdmin
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
      }
    }
    """
    
    try:
        result = catalog_graphql_query(
            registry_url=catalog_url,
            query=mutation,
            variables={"name": name, "admin": admin},
            auth_token=token,
        )
        
        update_result = result.get("admin", {}).get("user", {}).get("mutate", {}).get("setAdmin", {})
        
        if "name" in update_result and "isAdmin" in update_result:
            return {
                "success": True,
                "user": update_result,
            }
        elif "errors" in update_result:
            errors = update_result["errors"]
            error_msgs = [f"{err.get('name', 'Error')}: {err.get('message', '')}" 
                          for err in errors]
            return format_error_response("Invalid input: " + "; ".join(error_msgs))
        elif "message" in update_result:
            return format_error_response(f"Operation error: {update_result['message']}")
        else:
            return format_error_response(f"Unexpected response: {update_result}")
            
    except Exception as e:
        logger.exception("Failed to set user admin status")
        return format_error_response(f"Failed to set user admin status: {e}")


async def admin_user_set_active(name: str, active: bool) -> Dict[str, Any]:
    """Set user's active status (admin only)."""
    if not name:
        return format_error_response("Username cannot be empty")
    
    try:
        token, catalog_url = _require_admin_auth()
    except ValueError as e:
        return format_error_response(str(e))
    
    mutation = """
    mutation AdminUserSetActive($name: String!, $active: Boolean!) {
      admin {
        user {
          mutate(name: $name) {
            setActive(active: $active) {
              ... on User {
                name
                isActive
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
      }
    }
    """
    
    try:
        result = catalog_graphql_query(
            registry_url=catalog_url,
            query=mutation,
            variables={"name": name, "active": active},
            auth_token=token,
        )
        
        update_result = result.get("admin", {}).get("user", {}).get("mutate", {}).get("setActive", {})
        
        if "name" in update_result and "isActive" in update_result:
            return {
                "success": True,
                "user": update_result,
            }
        elif "errors" in update_result:
            errors = update_result["errors"]
            error_msgs = [f"{err.get('name', 'Error')}: {err.get('message', '')}" 
                          for err in errors]
            return format_error_response("Invalid input: " + "; ".join(error_msgs))
        elif "message" in update_result:
            return format_error_response(f"Operation error: {update_result['message']}")
        else:
            return format_error_response(f"Unexpected response: {update_result}")
            
    except Exception as e:
        logger.exception("Failed to set user active status")
        return format_error_response(f"Failed to set user active status: {e}")


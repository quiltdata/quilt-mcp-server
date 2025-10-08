"""GraphQL-based policy management implementation for the admin tool."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from ..clients.catalog import catalog_graphql_query
from ..utils import format_error_response
from .governance_impl_part2 import _require_admin_auth

logger = logging.getLogger(__name__)

VALID_PERMISSION_LEVELS = {"READ", "READ_WRITE"}
ARN_PATTERN = re.compile(r"^arn:aws:iam::\d{12}:policy/.+$")


def _build_permissions_input(permissions: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    converted: List[Dict[str, str]] = []
    for permission in permissions:
        bucket_name = (permission.get("bucket_name") or permission.get("bucket") or "").strip()
        level = (permission.get("level") or "").strip().upper()
        if not bucket_name:
            raise ValueError("Each permission must include a bucket_name value")
        if level not in VALID_PERMISSION_LEVELS:
            raise ValueError("Permission level must be READ or READ_WRITE")
        # GraphQL schema uses "bucket", not "bucketName"
        converted.append({"bucket": bucket_name, "level": level})
    if not converted:
        raise ValueError("Managed policies require at least one permission entry")
    return converted


def _handle_policy_mutation_result(payload: Dict[str, Any]) -> Dict[str, Any]:
    typename = payload.get("__typename")
    if typename in (None, "Policy"):
        return {
            "success": True,
            "policy": {k: v for k, v in payload.items() if k != "__typename"},
        }
    if typename == "InvalidInput":
        errors = payload.get("errors") or []
        message = "; ".join(err.get("message", "Invalid input") for err in errors) or "Invalid input"
        return format_error_response(message)
    if typename == "OperationError":
        message = payload.get("message") or "Policy operation failed"
        return format_error_response(message)
    return format_error_response(f"Policy operation failed with result '{typename}'")


def _handle_policy_delete_result(payload: Dict[str, Any]) -> Dict[str, Any]:
    typename = payload.get("__typename")
    if typename in (None, "Ok"):
        return {"success": True}
    if typename == "InvalidInput":
        errors = payload.get("errors") or []
        message = "; ".join(err.get("message", "Invalid input") for err in errors) or "Invalid input"
        return format_error_response(message)
    if typename == "OperationError":
        message = payload.get("message") or "Policy delete failed"
        return format_error_response(message)
    return format_error_response(f"policy_delete returned unexpected result '{typename}'")


def _fetch_policy(token: str, catalog_url: str, policy_id: str) -> Dict[str, Any]:
    query = """
    query AdminPolicyGet($policyId: ID!) {
      policy(id: $policyId) {
        id
        name
        arn
        title
        permissions {
          bucket { name }
          level
        }
      }
    }
    """
    result = catalog_graphql_query(
        registry_url=catalog_url,
        query=query,
        variables={"policyId": policy_id},
        auth_token=token,
    )
    policy = result.get("policy")
    if not policy:
        raise ValueError(f"Policy '{policy_id}' not found")
    return policy


def _convert_existing_permissions(permissions: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    converted: List[Dict[str, str]] = []
    for permission in permissions or []:
        bucket = permission.get("bucket") or {}
        bucket_name = (bucket.get("name") or "").strip()
        level = (permission.get("level") or "").strip().upper()
        if bucket_name and level in VALID_PERMISSION_LEVELS:
            converted.append({"bucketName": bucket_name, "level": level})
    return converted


async def admin_policies_list() -> Dict[str, Any]:
    try:
        token, catalog_url = _require_admin_auth()
    except ValueError as exc:
        return format_error_response(str(exc))

    query = """
    query AdminPoliciesList {
      policies {
        id
        name
        arn
        title
        permissions {
          bucket { name }
          level
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
        policies = result.get("policies", [])
        return {
            "success": True,
            "policies": policies,
            "count": len(policies),
        }
    except Exception as exc:
        logger.exception("Failed to list policies")
        return format_error_response(f"Failed to list policies: {exc}")


async def admin_policy_get(policy_id: str) -> Dict[str, Any]:
    if not policy_id or not policy_id.strip():
        return format_error_response("Policy ID cannot be empty")

    try:
        token, catalog_url = _require_admin_auth()
    except ValueError as exc:
        return format_error_response(str(exc))

    try:
        policy = _fetch_policy(token, catalog_url, policy_id.strip())
        return {"success": True, "policy": policy}
    except ValueError as exc:
        return format_error_response(str(exc))
    except Exception as exc:
        logger.exception("Failed to get policy details")
        return format_error_response(f"Failed to get policy: {exc}")


async def admin_policy_create_managed(
    title: str,
    permissions: Optional[List[Dict[str, Any]]] = None,
    roles: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Create a managed policy with bucket permissions.
    
    Args:
        title: Policy title (required by GraphQL schema)
        permissions: List of bucket permissions (optional, defaults to empty)
        roles: List of role IDs to assign this policy to (optional, defaults to empty)
    """
    if not title or not title.strip():
        return format_error_response("Policy title cannot be empty")

    try:
        permissions_input = _build_permissions_input(permissions or [])
    except ValueError as exc:
        return format_error_response(str(exc))

    try:
        token, catalog_url = _require_admin_auth()
    except ValueError as exc:
        return format_error_response(str(exc))

    # GraphQL schema requires: title, permissions, roles (all required!)
    input_payload: Dict[str, Any] = {
        "title": title.strip(),
        "permissions": permissions_input,
        "roles": roles or [],  # Empty array if not provided
    }

    mutation = """
    mutation PolicyCreateManaged($input: ManagedPolicyInput!) {
      policyCreateManaged(input: $input) {
        __typename
        ... on Policy {
          id
          arn
          title
          managed
          permissions {
            bucket { name }
            level
          }
        }
        ... on InvalidInput {
          __typename
          errors { message path }
        }
        ... on OperationError {
          __typename
          message
        }
      }
    }
    """
    try:
        result = catalog_graphql_query(
            registry_url=catalog_url,
            query=mutation,
            variables={"input": input_payload},
            auth_token=token,
        )
    except Exception as exc:
        logger.exception("Failed to execute managed policy creation")
        return format_error_response(f"Failed to create managed policy: {exc}")

    payload = result.get("policyCreateManaged")
    if not isinstance(payload, dict):
        return format_error_response("Unexpected response from policyCreateManaged mutation")
    return _handle_policy_mutation_result(payload)


async def admin_policy_create_unmanaged(
    name: str,
    arn: str,
    title: Optional[str] = None,
) -> Dict[str, Any]:
    if not name or not name.strip():
        return format_error_response("Policy name cannot be empty")
    if not arn or not arn.strip():
        return format_error_response("Policy ARN cannot be empty")
    if not ARN_PATTERN.match(arn.strip()):
        return format_error_response("Policy ARN must match pattern arn:aws:iam::<account>:policy/<name>")

    try:
        token, catalog_url = _require_admin_auth()
    except ValueError as exc:
        return format_error_response(str(exc))

    input_payload: Dict[str, Any] = {
        "name": name.strip(),
        "arn": arn.strip(),
    }
    if title:
        input_payload["title"] = title

    mutation = """
    mutation PolicyCreateUnmanaged($input: UnmanagedPolicyInput!) {
      policyCreateUnmanaged(input: $input) {
        __typename
        ... on Policy {
          id
          name
          arn
          title
        }
        ... on InvalidInput {
          __typename
          errors { message path }
        }
        ... on OperationError {
          __typename
          message
          name
        }
      }
    }
    """
    try:
        result = catalog_graphql_query(
            registry_url=catalog_url,
            query=mutation,
            variables={"input": input_payload},
            auth_token=token,
        )
    except Exception as exc:
        logger.exception("Failed to execute unmanaged policy creation")
        return format_error_response(f"Failed to create unmanaged policy: {exc}")

    payload = result.get("policyCreateUnmanaged")
    if not isinstance(payload, dict):
        return format_error_response("Unexpected response from policyCreateUnmanaged mutation")
    return _handle_policy_mutation_result(payload)


async def admin_policy_update_managed(
    policy_id: str,
    name: Optional[str] = None,
    permissions: Optional[List[Dict[str, Any]]] = None,
    title: Optional[str] = None,
) -> Dict[str, Any]:
    policy_id = (policy_id or "").strip()
    if not policy_id:
        return format_error_response("Policy ID cannot be empty")

    if name is None and permissions is None and title is None:
        return format_error_response("Provide at least one field to update")

    try:
        token, catalog_url = _require_admin_auth()
    except ValueError as exc:
        return format_error_response(str(exc))

    try:
        existing_policy = _fetch_policy(token, catalog_url, policy_id)
    except ValueError as exc:
        return format_error_response(str(exc))
    except Exception as exc:
        logger.exception("Failed to fetch existing policy")
        return format_error_response(f"Failed to fetch existing policy: {exc}")

    policy_name = name.strip() if name is not None else existing_policy.get("name")
    if not policy_name:
        return format_error_response("Policy name cannot be empty")

    if permissions is not None:
        try:
            permissions_input = _build_permissions_input(permissions)
        except ValueError as exc:
            return format_error_response(str(exc))
    else:
        permissions_input = _convert_existing_permissions(existing_policy.get("permissions", []))
        if not permissions_input:
            return format_error_response("Existing policy does not contain permissions to reuse; provide permissions")

    input_payload: Dict[str, Any] = {"name": policy_name, "permissions": permissions_input}
    final_title = title if title is not None else existing_policy.get("title")
    if final_title:
        input_payload["title"] = final_title

    mutation = """
    mutation PolicyUpdateManaged($id: ID!, $input: ManagedPolicyInput!) {
      policyUpdateManaged(id: $id, input: $input) {
        __typename
        ... on Policy {
          id
          name
          arn
          title
          permissions {
            bucket { name }
            level
          }
        }
        ... on InvalidInput {
          __typename
          errors { message path }
        }
        ... on OperationError {
          __typename
          message
          name
        }
      }
    }
    """
    try:
        result = catalog_graphql_query(
            registry_url=catalog_url,
            query=mutation,
            variables={"id": policy_id, "input": input_payload},
            auth_token=token,
        )
    except Exception as exc:
        logger.exception("Failed to execute managed policy update")
        return format_error_response(f"Failed to update managed policy: {exc}")

    payload = result.get("policyUpdateManaged")
    if not isinstance(payload, dict):
        return format_error_response("Unexpected response from policyUpdateManaged mutation")
    return _handle_policy_mutation_result(payload)


async def admin_policy_update_unmanaged(
    policy_id: str,
    name: Optional[str] = None,
    arn: Optional[str] = None,
    title: Optional[str] = None,
) -> Dict[str, Any]:
    policy_id = (policy_id or "").strip()
    if not policy_id:
        return format_error_response("Policy ID cannot be empty")

    if name is None and arn is None and title is None:
        return format_error_response("Provide at least one field to update")

    try:
        token, catalog_url = _require_admin_auth()
    except ValueError as exc:
        return format_error_response(str(exc))

    try:
        existing_policy = _fetch_policy(token, catalog_url, policy_id)
    except ValueError as exc:
        return format_error_response(str(exc))
    except Exception as exc:
        logger.exception("Failed to fetch existing policy for unmanaged update")
        return format_error_response(f"Failed to fetch existing policy: {exc}")

    policy_name = name.strip() if name is not None else existing_policy.get("name")
    policy_arn = arn.strip() if arn is not None else existing_policy.get("arn")

    if not policy_name:
        return format_error_response("Policy name cannot be empty")
    if not policy_arn:
        return format_error_response("Policy ARN cannot be empty")
    if not ARN_PATTERN.match(policy_arn):
        return format_error_response("Policy ARN must match pattern arn:aws:iam::<account>:policy/<name>")

    input_payload: Dict[str, Any] = {"name": policy_name, "arn": policy_arn}
    final_title = title if title is not None else existing_policy.get("title")
    if final_title:
        input_payload["title"] = final_title

    mutation = """
    mutation PolicyUpdateUnmanaged($id: ID!, $input: UnmanagedPolicyInput!) {
      policyUpdateUnmanaged(id: $id, input: $input) {
        __typename
        ... on Policy {
          id
          name
          arn
          title
        }
        ... on InvalidInput {
          __typename
          errors { message path }
        }
        ... on OperationError {
          __typename
          message
          name
        }
      }
    }
    """
    try:
        result = catalog_graphql_query(
            registry_url=catalog_url,
            query=mutation,
            variables={"id": policy_id, "input": input_payload},
            auth_token=token,
        )
    except Exception as exc:
        logger.exception("Failed to execute unmanaged policy update")
        return format_error_response(f"Failed to update unmanaged policy: {exc}")

    payload = result.get("policyUpdateUnmanaged")
    if not isinstance(payload, dict):
        return format_error_response("Unexpected response from policyUpdateUnmanaged mutation")
    return _handle_policy_mutation_result(payload)


async def admin_policy_delete(policy_id: str) -> Dict[str, Any]:
    policy_id = (policy_id or "").strip()
    if not policy_id:
        return format_error_response("Policy ID cannot be empty")

    try:
        token, catalog_url = _require_admin_auth()
    except ValueError as exc:
        return format_error_response(str(exc))

    mutation = """
    mutation PolicyDelete($policyId: ID!) {
      policyDelete(id: $policyId) {
        __typename
        ... on Ok { __typename }
        ... on InvalidInput {
          __typename
          errors { message path }
        }
        ... on OperationError {
          __typename
          message
          name
        }
      }
    }
    """
    try:
        result = catalog_graphql_query(
            registry_url=catalog_url,
            query=mutation,
            variables={"policyId": policy_id},
            auth_token=token,
        )
    except Exception as exc:
        logger.exception("Failed to execute policy delete mutation")
        return format_error_response(f"Failed to delete policy: {exc}")

    payload = result.get("policyDelete")
    if not isinstance(payload, dict):
        return format_error_response("Unexpected response from policyDelete mutation")
    return _handle_policy_delete_result(payload)

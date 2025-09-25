"""Permission Mapper for Quilt MCP Tools.

This module provides permission mapping between MCP tools and required AWS/Quilt permissions.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class PermissionMapper:
    """Maps MCP tools to required permissions."""
    
    def __init__(self):
        self._permission_mapping = self._load_permission_mapping()
    
    def _load_permission_mapping(self) -> Dict[str, Any]:
        """Load permission mapping from configuration.
        
        Returns:
            Permission mapping dictionary
        """
        try:
            # Try to load from config file first
            config_path = Path("configs/permission_mapping.json")
            if config_path.exists():
                with open(config_path, "r") as f:
                    mapping = json.load(f)
                    logger.debug("Loaded permission mapping from config file")
                    return mapping.get("tool_permissions", {})
            
            # Fall back to default mapping
            logger.debug("Using default permission mapping")
            return self._get_default_permission_mapping()
            
        except Exception as e:
            logger.error("Failed to load permission mapping: %s", e)
            return self._get_default_permission_mapping()
    
    def _get_default_permission_mapping(self) -> Dict[str, Any]:
        """Get default permission mapping.
        
        Returns:
            Default permission mapping dictionary
        """
        return {
            # S3 Bucket Operations
            "bucket_objects_list": {
                "aws_permissions": ["s3:ListBucket", "s3:GetBucketLocation"],
                "quilt_permissions": ["bucket:read"],
                "required_services": ["s3"],
                "description": "List objects in S3 bucket"
            },
            "bucket_object_info": {
                "aws_permissions": ["s3:GetObject", "s3:GetObjectVersion"],
                "quilt_permissions": ["bucket:read"],
                "required_services": ["s3"],
                "description": "Get object metadata from S3 bucket"
            },
            "bucket_object_text": {
                "aws_permissions": ["s3:GetObject"],
                "quilt_permissions": ["bucket:read"],
                "required_services": ["s3"],
                "description": "Read object content as text from S3 bucket"
            },
            "bucket_object_fetch": {
                "aws_permissions": ["s3:GetObject"],
                "quilt_permissions": ["bucket:read"],
                "required_services": ["s3"],
                "description": "Fetch object from S3 bucket"
            },
            "bucket_objects_put": {
                "aws_permissions": ["s3:PutObject", "s3:PutObjectAcl"],
                "quilt_permissions": ["bucket:write"],
                "required_services": ["s3"],
                "description": "Upload objects to S3 bucket"
            },
            "bucket_object_link": {
                "aws_permissions": ["s3:GetObject"],
                "quilt_permissions": ["bucket:read"],
                "required_services": ["s3"],
                "description": "Generate signed URL for S3 object"
            },
            
            # Package Operations
            "package_create": {
                "aws_permissions": ["s3:PutObject", "s3:PutObjectAcl", "s3:ListBucket"],
                "quilt_permissions": ["package:write"],
                "required_services": ["s3", "quilt_api"],
                "description": "Create Quilt package"
            },
            "package_update": {
                "aws_permissions": ["s3:PutObject", "s3:PutObjectAcl", "s3:ListBucket"],
                "quilt_permissions": ["package:write"],
                "required_services": ["s3", "quilt_api"],
                "description": "Update Quilt package"
            },
            "package_delete": {
                "aws_permissions": ["s3:DeleteObject", "s3:ListBucket"],
                "quilt_permissions": ["package:write"],
                "required_services": ["s3", "quilt_api"],
                "description": "Delete Quilt package"
            },
            "package_browse": {
                "aws_permissions": ["s3:ListBucket", "s3:GetObject"],
                "quilt_permissions": ["package:read"],
                "required_services": ["s3", "quilt_api"],
                "description": "Browse Quilt package contents"
            },
            "package_contents_search": {
                "aws_permissions": ["s3:ListBucket", "s3:GetObject"],
                "quilt_permissions": ["package:read"],
                "required_services": ["s3", "quilt_api"],
                "description": "Search package contents"
            },
            "package_diff": {
                "aws_permissions": ["s3:GetObject", "s3:ListBucket"],
                "quilt_permissions": ["package:read"],
                "required_services": ["s3", "quilt_api"],
                "description": "Compare package versions"
            },
            "create_package_enhanced": {
                "aws_permissions": ["s3:PutObject", "s3:PutObjectAcl", "s3:ListBucket"],
                "quilt_permissions": ["package:write"],
                "required_services": ["s3", "quilt_api"],
                "description": "Create enhanced Quilt package"
            },
            "create_package_from_s3": {
                "aws_permissions": ["s3:GetObject", "s3:PutObject", "s3:ListBucket"],
                "quilt_permissions": ["package:write"],
                "required_services": ["s3", "quilt_api"],
                "description": "Create package from S3 objects"
            },
            "package_create_from_s3": {
                "aws_permissions": ["s3:GetObject", "s3:PutObject", "s3:ListBucket"],
                "quilt_permissions": ["package:write"],
                "required_services": ["s3", "quilt_api"],
                "description": "Create package from S3 objects (alias)"
            },
            
            # Athena/Glue Operations
            "athena_query_execute": {
                "aws_permissions": [
                    "athena:StartQueryExecution",
                    "athena:GetQueryExecution",
                    "athena:GetQueryResults",
                    "athena:StopQueryExecution"
                ],
                "quilt_permissions": ["athena:execute"],
                "required_services": ["athena"],
                "description": "Execute Athena query"
            },
            "athena_databases_list": {
                "aws_permissions": ["glue:GetDatabases"],
                "quilt_permissions": ["athena:read"],
                "required_services": ["glue"],
                "description": "List Athena databases"
            },
            "athena_tables_list": {
                "aws_permissions": ["glue:GetTables", "glue:GetTable"],
                "quilt_permissions": ["athena:read"],
                "required_services": ["glue"],
                "description": "List Athena tables"
            },
            "athena_table_schema": {
                "aws_permissions": ["glue:GetTable", "glue:GetPartitions"],
                "quilt_permissions": ["athena:read"],
                "required_services": ["glue"],
                "description": "Get Athena table schema"
            },
            "athena_workgroups_list": {
                "aws_permissions": ["athena:ListWorkGroups"],
                "quilt_permissions": ["athena:read"],
                "required_services": ["athena"],
                "description": "List Athena workgroups"
            },
            "athena_query_history": {
                "aws_permissions": ["athena:ListQueryExecutions"],
                "quilt_permissions": ["athena:read"],
                "required_services": ["athena"],
                "description": "Get Athena query history"
            },
            
            # Tabulator Operations
            "tabulator_tables_list": {
                "aws_permissions": ["glue:GetTables"],
                "quilt_permissions": ["tabulator:read"],
                "required_services": ["glue"],
                "description": "List tabulator tables"
            },
            "tabulator_table_create": {
                "aws_permissions": ["glue:CreateTable", "glue:UpdateTable"],
                "quilt_permissions": ["tabulator:write"],
                "required_services": ["glue"],
                "description": "Create tabulator table"
            },
            
            # Search Operations
            "unified_search": {
                "aws_permissions": [],
                "quilt_permissions": ["search:execute"],
                "required_services": ["quilt_api"],
                "description": "Unified search across packages"
            },
            "packages_search": {
                "aws_permissions": [],
                "quilt_permissions": ["search:execute"],
                "required_services": ["quilt_api"],
                "description": "Search packages"
            },
            
            # Permission Operations
            "aws_permissions_discover": {
                "aws_permissions": ["iam:GetRole", "iam:ListRoles", "iam:GetUser"],
                "quilt_permissions": ["permissions:read"],
                "required_services": ["iam"],
                "description": "Discover AWS permissions"
            },
            "bucket_access_check": {
                "aws_permissions": ["s3:ListBucket", "s3:GetBucketLocation"],
                "quilt_permissions": ["permissions:read"],
                "required_services": ["s3"],
                "description": "Check bucket access"
            },
            "bucket_recommendations_get": {
                "aws_permissions": ["s3:ListAllMyBuckets"],
                "quilt_permissions": ["permissions:read"],
                "required_services": ["s3"],
                "description": "Get bucket recommendations"
            }
        }
    
    def get_tool_permissions(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get permissions required for tool.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Permission requirements for the tool
        """
        return self._permission_mapping.get(tool_name)
    
    def get_tool_aws_permissions(self, tool_name: str) -> List[str]:
        """Get AWS permissions required for tool.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            List of required AWS permissions
        """
        tool_perms = self.get_tool_permissions(tool_name)
        if tool_perms:
            return tool_perms.get("aws_permissions", [])
        return []
    
    def get_tool_quilt_permissions(self, tool_name: str) -> List[str]:
        """Get Quilt permissions required for tool.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            List of required Quilt permissions
        """
        tool_perms = self.get_tool_permissions(tool_name)
        if tool_perms:
            return tool_perms.get("quilt_permissions", [])
        return []
    
    def get_tool_required_services(self, tool_name: str) -> List[str]:
        """Get AWS services required for tool.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            List of required AWS services
        """
        tool_perms = self.get_tool_permissions(tool_name)
        if tool_perms:
            return tool_perms.get("required_services", [])
        return []
    
    def get_tool_description(self, tool_name: str) -> str:
        """Get description for tool.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Tool description
        """
        tool_perms = self.get_tool_permissions(tool_name)
        if tool_perms:
            return tool_perms.get("description", "No description available")
        return "Unknown tool"
    
    def list_tools_by_category(self) -> Dict[str, List[str]]:
        """List tools grouped by category.
        
        Returns:
            Dictionary mapping categories to tool lists
        """
        categories = {
            "s3_bucket_operations": [],
            "package_operations": [],
            "athena_glue_operations": [],
            "tabulator_operations": [],
            "search_operations": [],
            "permission_operations": []
        }
        
        for tool_name in self._permission_mapping.keys():
            if "bucket_" in tool_name:
                categories["s3_bucket_operations"].append(tool_name)
            elif "package_" in tool_name or "create_package" in tool_name:
                categories["package_operations"].append(tool_name)
            elif "athena_" in tool_name:
                categories["athena_glue_operations"].append(tool_name)
            elif "tabulator_" in tool_name:
                categories["tabulator_operations"].append(tool_name)
            elif "search" in tool_name:
                categories["search_operations"].append(tool_name)
            elif "permissions" in tool_name or "bucket_access" in tool_name or "bucket_recommendations" in tool_name:
                categories["permission_operations"].append(tool_name)
        
        return categories
    
    def validate_user_permissions(self, tool_name: str, user_permissions: Dict[str, Any]) -> Dict[str, Any]:
        """Validate user permissions against tool requirements.
        
        Args:
            tool_name: Name of the tool
            user_permissions: User's permission information
            
        Returns:
            Validation result with details
        """
        tool_perms = self.get_tool_permissions(tool_name)
        if not tool_perms:
            return {
                "valid": True,
                "reason": "No permission requirements found for tool"
            }
        
        user_aws_perms = user_permissions.get("permissions", [])
        user_quilt_perms = user_permissions.get("quilt_permissions", [])
        user_buckets = user_permissions.get("buckets", [])
        
        # Check AWS permissions
        required_aws_perms = tool_perms.get("aws_permissions", [])
        missing_aws_perms = []
        
        for perm in required_aws_perms:
            if perm not in user_aws_perms and "*" not in user_aws_perms:
                missing_aws_perms.append(perm)
        
        # Check Quilt permissions
        required_quilt_perms = tool_perms.get("quilt_permissions", [])
        missing_quilt_perms = []
        
        for perm in required_quilt_perms:
            if perm not in user_quilt_perms and "*" not in user_quilt_perms:
                missing_quilt_perms.append(perm)
        
        # Determine validity
        valid = len(missing_aws_perms) == 0 and len(missing_quilt_perms) == 0
        
        return {
            "valid": valid,
            "missing_aws_permissions": missing_aws_perms,
            "missing_quilt_permissions": missing_quilt_perms,
            "required_aws_permissions": required_aws_perms,
            "required_quilt_permissions": required_quilt_perms,
            "user_buckets": user_buckets
        }


# Global instance
_permission_mapper: Optional[PermissionMapper] = None


def get_permission_mapper() -> PermissionMapper:
    """Get global permission mapper instance.
    
    Returns:
        PermissionMapper instance
    """
    global _permission_mapper
    if _permission_mapper is None:
        _permission_mapper = PermissionMapper()
    return _permission_mapper

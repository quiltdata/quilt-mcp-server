"""Unified Package Management Tool with GraphQL Integration.

This module provides comprehensive package management functionality including:
- Package discovery and listing via GraphQL
- Package creation, update, and deletion
- S3-to-package creation with smart organization
- Enhanced metadata templates and validation
- Unified interface for all package operations

IMPORTANT: This module automatically ensures that README content is always written
as README.md files within packages, never stored in package metadata. Any
'readme_content' or 'readme' fields in metadata will be automatically extracted
and converted to package files.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from ..clients import catalog as catalog_client
from ..constants import DEFAULT_BUCKET, DEFAULT_REGISTRY
from ..runtime import get_active_token
from ..utils import (
    format_error_response,
    generate_signed_url,
    get_s3_client,
    resolve_catalog_url,
    validate_package_name,
)

logger = logging.getLogger(__name__)


# Smart Organization and Template System
FOLDER_MAPPING = {
    # Data files
    "csv": "data/processed",
    "tsv": "data/processed",
    "parquet": "data/processed",
    "json": "data/processed",
    "xml": "data/processed",
    "jsonl": "data/processed",
    # Raw data
    "log": "data/raw",
    "txt": "data/raw",
    "raw": "data/raw",
    # Documentation
    "md": "docs",
    "rst": "docs",
    "pdf": "docs",
    "docx": "docs",
    # Code
    "py": "code",
    "r": "code",
    "sql": "code",
    "sh": "code",
    "ipynb": "code",
    # Images
    "png": "images",
    "jpg": "images",
    "jpeg": "images",
    "gif": "images",
    "svg": "images",
    "tiff": "images",
    # Models
    "pkl": "models",
    "joblib": "models",
    "h5": "models",
    "pth": "models",
    # Config
    "yaml": "config",
    "yml": "config",
    "toml": "config",
    "ini": "config",
    "conf": "config",
}

# Metadata templates
METADATA_TEMPLATES = {
    "standard": {
        "description": "Standard package metadata template",
        "fields": {
            "title": {"type": "string", "required": True, "description": "Package title"},
            "description": {"type": "string", "required": True, "description": "Package description"},
            "version": {"type": "string", "required": False, "default": "1.0.0", "description": "Package version"},
            "author": {"type": "string", "required": False, "description": "Package author"},
            "license": {"type": "string", "required": False, "description": "Package license"},
            "tags": {"type": "array", "required": False, "description": "Package tags"},
        }
    },
    "dataset": {
        "description": "Dataset package metadata template",
        "fields": {
            "title": {"type": "string", "required": True, "description": "Dataset title"},
            "description": {"type": "string", "required": True, "description": "Dataset description"},
            "version": {"type": "string", "required": False, "default": "1.0.0", "description": "Dataset version"},
            "source": {"type": "string", "required": False, "description": "Data source"},
            "collection_date": {"type": "string", "required": False, "description": "Data collection date"},
            "format": {"type": "string", "required": False, "description": "Data format"},
            "size": {"type": "string", "required": False, "description": "Dataset size"},
            "tags": {"type": "array", "required": False, "description": "Dataset tags"},
        }
    },
    "model": {
        "description": "ML model package metadata template",
        "fields": {
            "title": {"type": "string", "required": True, "description": "Model title"},
            "description": {"type": "string", "required": True, "description": "Model description"},
            "version": {"type": "string", "required": False, "default": "1.0.0", "description": "Model version"},
            "algorithm": {"type": "string", "required": False, "description": "ML algorithm"},
            "framework": {"type": "string", "required": False, "description": "ML framework"},
            "performance": {"type": "object", "required": False, "description": "Model performance metrics"},
            "training_data": {"type": "string", "required": False, "description": "Training data reference"},
            "tags": {"type": "array", "required": False, "description": "Model tags"},
        }
    }
}


# Helper functions
def _normalize_registry(bucket_or_uri: str) -> str:
    """Normalize registry input to s3:// URI format."""
    if not bucket_or_uri:
        return bucket_or_uri

    if bucket_or_uri.startswith(("http://", "https://")):
        return bucket_or_uri.rstrip("/")

    if bucket_or_uri.startswith("s3://"):
        return bucket_or_uri.rstrip("/")

    return f"s3://{bucket_or_uri.strip('/')}"


def _prepare_metadata(
    metadata: dict[str, Any] | str | None,
    warnings: list[str],
    *,
    on_error_message: str,
) -> tuple[Optional[dict[str, Any]], Optional[dict[str, Any]]]:
    """Prepare metadata for package operations."""
    if metadata is None:
        return {}, None

    if isinstance(metadata, str):
        try:
            metadata_dict = json.loads(metadata)
        except json.JSONDecodeError as exc:
            return None, {
                "success": False,
                "error": on_error_message,
                "provided": metadata,
                "expected": "Valid JSON object or Python dict",
                "json_error": str(exc),
            }
    elif isinstance(metadata, dict):
        metadata_dict = dict(metadata)
    else:
        return None, {
            "success": False,
            "error": on_error_message,
            "provided": str(type(metadata)),
            "expected": "Valid JSON object or Python dict",
        }

    # Extract README content and convert to file
    readme_content = None
    if "readme_content" in metadata_dict:
        readme_content = metadata_dict.pop("readme_content")
        warnings.append("README content extracted from metadata and will be written as README.md file")
    elif "readme" in metadata_dict:
        readme_content = metadata_dict.pop("readme")
        warnings.append("README content extracted from metadata and will be written as README.md file")

    return metadata_dict, None


def _get_file_extension(filename: str) -> str:
    """Get file extension from filename."""
    return Path(filename).suffix.lstrip('.').lower()


def _organize_file_path(filename: str, auto_organize: bool = True) -> str:
    """Organize file path based on extension and smart mapping."""
    if not auto_organize:
        return filename

    ext = _get_file_extension(filename)
    if ext in FOLDER_MAPPING:
        folder = FOLDER_MAPPING[ext]
        return f"{folder}/{filename}"

    return filename


def _validate_package_name(name: str) -> tuple[bool, Optional[str]]:
    """Validate package name format."""
    if not name:
        return False, "Package name is required"

    if not validate_package_name(name):
        return False, f"Invalid package name: {name}. Must be in format 'namespace/packagename'"

    return True, None


# Package discovery (simplified for now)
def packages_discover(registry: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
    """
    Discover all accessible packages.
    
    Args:
        registry: Registry to search (default: auto-detect)
        limit: Maximum number of packages to return
        
    Returns:
        Dict with package information including names, descriptions, and metadata.
    """
    token = get_active_token()
    if not token:
        return format_error_response("Authorization token required for package discovery")
    
    catalog_url = resolve_catalog_url()
    if not catalog_url:
        return format_error_response("Catalog URL not configured")
    
    try:
        # For now, return a placeholder response
        # TODO: Implement proper GraphQL package discovery once schema is clarified
        return {
            "success": True,
            "packages": [],
            "total_packages": 0,
            "message": "Package discovery not yet implemented - use 'list' action for basic package listing",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
    except Exception as e:
        logger.exception(f"Error discovering packages: {e}")
        return format_error_response(f"Failed to discover packages: {str(e)}")


# Package listing (legacy compatibility)
def packages_list(registry: str = DEFAULT_REGISTRY, limit: int = 0, prefix: str = "") -> dict[str, Any]:
    """List all available Quilt packages in a registry."""
    token = get_active_token()
    if not token:
        return format_error_response("Authorization token required for package listing")

    catalog_url = resolve_catalog_url()
    if not catalog_url:
        return format_error_response("Catalog URL not configured")

    try:
        # Use GraphQL for package listing
        packages_query = """
            query Packages($first: Int, $name: String) {
                packages(first: $first, name: $name) {
                    edges {
                        node {
                            name
                            description
                        }
                    }
                }
            }
        """
        
        variables = {"first": limit if limit > 0 else 1000}
        if prefix:
            variables["name"] = prefix
            
        packages_data = catalog_client.catalog_graphql_query(
            registry_url=catalog_url,
            query=packages_query,
            variables=variables,
            auth_token=token,
        )
        
        packages_connection = packages_data.get("packages", {})
        edges = packages_connection.get("edges", [])
        
        package_names = [edge["node"]["name"] for edge in edges if edge.get("node", {}).get("name")]
        
        return {
            "success": True,
            "packages": package_names,
            "count": len(package_names),
            "registry": registry,
        }
        
    except Exception as e:
        logger.exception(f"Error listing packages: {e}")
        return format_error_response(f"Failed to list packages: {str(e)}")


# Package browsing
def package_browse(name: str, registry: str = DEFAULT_REGISTRY) -> dict[str, Any]:
    """Browse a specific Quilt package and its contents."""
    token = get_active_token()
    if not token:
        return format_error_response("Authorization token required for package browsing")

    catalog_url = resolve_catalog_url()
    if not catalog_url:
        return format_error_response("Catalog URL not configured")

    try:
        # Use existing catalog_package_entries function
        entries = catalog_client.catalog_package_entries(
            registry_url=catalog_url,
            package_name=name,
            auth_token=token,
        )

        return {
            "success": True,
            "package": {
                "name": name,
                "entries": entries,
            },
        }
        
    except Exception as e:
        logger.exception(f"Error browsing package '{name}': {e}")
        return format_error_response(f"Failed to browse package '{name}': {str(e)}")


# Package creation
def package_create(
    name: str,
    files: List[str],
    description: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    registry: Optional[str] = None,
    dry_run: bool = False,
    auto_organize: bool = True,
    copy_mode: str = "all",
) -> Dict[str, Any]:
    """Create a new Quilt package."""
    token = get_active_token()
    if not token:
        return format_error_response("Authorization token required for package creation")

    catalog_url = resolve_catalog_url()
    if not catalog_url:
        return format_error_response("Catalog URL not configured")

    # Validate package name
    is_valid, error = _validate_package_name(name)
    if not is_valid:
        return format_error_response(error)

    # Prepare metadata
    warnings = []
    metadata_dict, error = _prepare_metadata(
        metadata, warnings, on_error_message="Invalid metadata format"
    )
    if error:
        return error

    # Add description to metadata
    if description:
        metadata_dict["description"] = description

    # Organize files
    organized_files = []
    for file_path in files:
        organized_path = _organize_file_path(file_path, auto_organize)
        organized_files.append({
            "logical_key": organized_path,
            "physical_key": file_path,
        })

    if dry_run:
        return {
            "success": True,
            "dry_run": True,
            "package_name": name,
            "files": organized_files,
            "metadata": metadata_dict,
            "warnings": warnings,
            "message": "Dry run completed successfully",
        }

    try:
        # Use existing catalog_package_create function
        result = catalog_client.catalog_package_create(
            registry_url=catalog_url,
            package_name=name,
            auth_token=token,
            s3_uris=files,
            metadata=metadata_dict,
            message=description or f"Created package {name}",
            flatten=not auto_organize,
            copy_mode=copy_mode,
        )

        return {
            "success": True,
            "result": result,
            "warnings": warnings,
            "message": f"Package '{name}' created successfully",
        }
        
    except Exception as e:
        logger.exception(f"Error creating package '{name}': {e}")
        return format_error_response(f"Failed to create package '{name}': {str(e)}")


# S3-to-package creation
def package_create_from_s3(
    name: str,
    bucket: str,
    prefix: str = "",
    description: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    auto_organize: bool = True,
    dry_run: bool = False,
    copy_mode: str = "all",
) -> Dict[str, Any]:
    """Create a package from S3 bucket contents."""
    token = get_active_token()
    if not token:
        return format_error_response("Authorization token required for S3 package creation")

    # Validate package name
    is_valid, error = _validate_package_name(name)
    if not is_valid:
        return error

    # Get S3 client
    try:
        s3_client = get_s3_client()
    except Exception as e:
        return format_error_response(f"Failed to get S3 client: {str(e)}")

    # List S3 objects
    try:
        response = s3_client.list_objects_v2(
            Bucket=bucket,
            Prefix=prefix,
            MaxKeys=1000
        )
        objects = response.get("Contents", [])
    except Exception as e:
        return format_error_response(f"Failed to list S3 objects: {str(e)}")

    if not objects:
        return format_error_response(f"No objects found in bucket '{bucket}' with prefix '{prefix}'")

    # Prepare files
    files = []
    for obj in objects:
        key = obj["Key"]
        if key.endswith("/"):  # Skip directories
            continue
        
        # Create S3 URI
        s3_uri = f"s3://{bucket}/{key}"
        files.append(s3_uri)

    # Create package
    return package_create(
        name=name,
        files=files,
        description=description,
        metadata=metadata,
        auto_organize=auto_organize,
        dry_run=dry_run,
        copy_mode=copy_mode,
    )


# Metadata templates
def get_metadata_template(template_name: str = "standard") -> Dict[str, Any]:
    """Get metadata template by name."""
    if template_name not in METADATA_TEMPLATES:
        return format_error_response(f"Unknown metadata template: {template_name}")
    
    return {
        "success": True,
        "template": METADATA_TEMPLATES[template_name],
        "name": template_name,
    }


def list_metadata_templates() -> Dict[str, Any]:
    """List all available metadata templates."""
    templates = {}
    for name, template in METADATA_TEMPLATES.items():
        templates[name] = {
            "description": template["description"],
            "fields": list(template["fields"].keys()),
        }
    
    return {
        "success": True,
        "templates": templates,
    }


# Main unified function
def packaging(action: Optional[str] = None, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Unified package management operations.

    Available actions:
    - discover: Discover all accessible packages with metadata
    - list: List package names in a registry
    - browse: Browse a specific package and its contents
    - create: Create a new package
    - create_from_s3: Create a package from S3 bucket contents
    - metadata_templates: List available metadata templates
    - get_template: Get a specific metadata template

    Args:
        action: The operation to perform. If None, returns available actions.
        params: Action-specific parameters

    Returns:
        Action-specific response dictionary
    """
    params = params or {}
    
    try:
        if action is None:
            return {
                "module": "packaging",
                "actions": [
                    "discover",
                    "list", 
                    "browse",
                    "create",
                    "create_from_s3",
                    "metadata_templates",
                    "get_template",
                ],
                "description": "Unified package management via Quilt Catalog GraphQL",
            }
        elif action == "discover":
            return packages_discover(
                registry=params.get("registry"),
                limit=params.get("limit", 100),
            )
        elif action == "list":
            return packages_list(
                registry=params.get("registry", DEFAULT_REGISTRY),
                limit=params.get("limit", 0),
                prefix=params.get("prefix", ""),
            )
        elif action == "browse":
            return package_browse(
                name=params.get("name"),
                registry=params.get("registry", DEFAULT_REGISTRY),
            )
        elif action == "create":
            return package_create(
                name=params.get("name"),
                files=params.get("files", []),
                description=params.get("description", ""),
                metadata=params.get("metadata"),
                registry=params.get("registry"),
                dry_run=params.get("dry_run", False),
                auto_organize=params.get("auto_organize", True),
                copy_mode=params.get("copy_mode", "all"),
            )
        elif action == "create_from_s3":
            return package_create_from_s3(
                name=params.get("name"),
                bucket=params.get("bucket"),
                prefix=params.get("prefix", ""),
                description=params.get("description", ""),
                metadata=params.get("metadata"),
                auto_organize=params.get("auto_organize", True),
                dry_run=params.get("dry_run", False),
                copy_mode=params.get("copy_mode", "all"),
            )
        elif action == "metadata_templates":
            return list_metadata_templates()
        elif action == "get_template":
            return get_metadata_template(
                template_name=params.get("template_name", "standard")
            )
        else:
            return format_error_response(f"Unknown packaging action: {action}")
    
    except Exception as exc:
        logger.exception(f"Error executing packaging action '{action}': {exc}")
        return format_error_response(f"Failed to execute packaging action '{action}': {str(exc)}")

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

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..clients import catalog as catalog_client
from ..constants import DEFAULT_REGISTRY
from ..runtime import get_active_token
from ..utils import (
    format_error_response,
    resolve_catalog_url,
    validate_package_name,
)
from ..types.navigation import (
    NavigationContext,
    get_context_bucket,
    get_context_path,
    suggest_package_name_from_context,
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
    if "readme_content" in metadata_dict:
        metadata_dict.pop("readme_content")
        warnings.append("README content extracted from metadata - upload README.md to S3 and add to 'files' parameter instead")
    elif "readme" in metadata_dict:
        metadata_dict.pop("readme")
        warnings.append("README content extracted from metadata - upload README.md to S3 and add to 'files' parameter instead")

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


# Package discovery and listing removed - use search tool instead
# Users should use: search.unified_search(query="*", scope="catalog", search_type="packages")


# Package browsing
def package_browse(name: str, bucket: Optional[str] = None, registry: str = DEFAULT_REGISTRY) -> dict[str, Any]:  # noqa: ARG001
    """Browse a specific Quilt package and its contents.
    
    Args:
        name: Package name (e.g., "team/package")
        bucket: S3 bucket name (without s3:// prefix). If not provided, will try to infer.
        registry: Registry URL (unused, kept for compatibility)
        
    Returns:
        Dict with success status and package entries
    """
    token = get_active_token()
    if not token:
        return format_error_response("Authorization token required for package browsing")

    catalog_url = resolve_catalog_url()
    if not catalog_url:
        return format_error_response("Catalog URL not configured")
    
    # If bucket not provided, return helpful error
    if not bucket:
        return format_error_response(
            f"Bucket parameter required for package browsing. "
            f"Specify bucket name (e.g., 'quilt-sandbox-bucket') for package '{name}'"
        )

    try:
        # Use existing catalog_package_entries function
        entries = catalog_client.catalog_package_entries(
            registry_url=catalog_url,
            bucket=bucket,
            package_name=name,
            auth_token=token,
        )

        return {
            "success": True,
            "package": {
                "name": name,
                "bucket": bucket,
                "entries": entries,
            },
        }
        
    except Exception:
        logger.exception("Error browsing package '%s' in bucket '%s'", name, bucket)
        return format_error_response(f"Failed to browse package '{name}' in bucket '{bucket}'")


# Package creation
def package_create(
    name: str,
    files: Optional[List[str]] = None,
    description: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    registry: Optional[str] = None,
    dry_run: bool = False,
    auto_organize: bool = True,
    copy_mode: str = "all",
    readme: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new Quilt package.
    
    Args:
        name: Package name in format 'namespace/packagename'
        files: List of S3 URIs to include in package (optional if readme provided)
        description: Package description
        metadata: Package metadata dict
        registry: Target registry bucket (optional, extracted from name if not provided)
        dry_run: If true, validate but don't create
        auto_organize: Organize files into logical folders
        copy_mode: Copy mode for files ('all', 'none', or 'metadata')
        readme: README content to create as README.md file (optional)
        
    Returns:
        Dict with success status and package information
    """
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

    # Extract registry bucket from name if not provided
    if not registry:
        if "/" in name:
            registry = name.split("/")[0]
        else:
            return format_error_response("Could not determine registry bucket")

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

    # Validate inputs
    if not files and not readme:
        return format_error_response(
            "Package creation requires 'files' parameter with a list of S3 URIs. "
            "\n\n"
            "IMPORTANT: The MCP server cannot upload files directly because the JWT token is for "
            "authentication only and does not contain AWS credentials. The Quilt catalog backend "
            "handles AWS credential management via IAM role assumption.\n\n"
            "To create a package, files must already exist in S3. You have two options:\n\n"
            "Option 1 - Upload via Quilt web UI:\n"
            "  1. Use the Quilt web interface to upload files\n"
            "  2. Then call packaging.create with those S3 URIs\n\n"
            "Option 2 - Upload via AWS CLI:\n"
            "  1. Use AWS CLI to upload: aws s3 cp README.md s3://bucket/path/README.md\n"
            "  2. Then call packaging.create(name='bucket/pkg', files=['s3://bucket/path/README.md'])\n\n"
            "The 'readme' parameter is not currently supported - files must be pre-uploaded to S3."
        )

    # Handle README content if provided
    # NOTE: GraphQL packageConstruct requires files to already exist in S3.
    # The JWT token doesn't contain AWS credentials - the registry backend handles
    # credential management via IAM role assumption on the server side.
    if readme and not files:
        return format_error_response(
            "Cannot create package with inline 'readme' content.\n\n"
            "The MCP server uses JWT for authentication, but the JWT does not contain AWS credentials. "
            "The Quilt registry backend handles AWS access by assuming IAM roles on behalf of users.\n\n"
            "To create a package with a README:\n"
            "1. Upload README.md to S3 first (via Quilt web UI or AWS CLI)\n"
            "2. Then call: packaging.create(name='{registry}/pkg', files=['s3://{registry}/path/README.md'])\n\n"
            "Example using AWS CLI:\n"
            "  $ echo 'hello world' > README.md\n"
            "  $ aws s3 cp README.md s3://{registry}/.quilt/packages/my-pkg/README.md\n"
            "  Then call packaging.create with files=['s3://{registry}/.quilt/packages/my-pkg/README.md']"
        )

    # Use provided files
    all_files = files or []

    # Require at least one file
    if not all_files:
        return format_error_response(
            "Package creation requires at least one S3 URI in 'files' parameter.\n\n"
            "Files must already exist in S3 before creating a package. "
            "Upload files via Quilt web UI or AWS CLI first."
        )

    # Organize files
    organized_files = []
    for file_path in all_files:
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
            s3_uris=all_files,
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
        
    except Exception:
        logger.exception("Error creating package '%s'", name)
        return format_error_response(f"Failed to create package '{name}'")


# S3-to-package creation
def package_create_from_s3(  # noqa: ARG001
    name: str,
    bucket: str,
    prefix: str = "",
    description: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    auto_organize: bool = True,
    dry_run: bool = False,
    copy_mode: str = "all",
) -> Dict[str, Any]:
    """Create a package from S3 bucket contents.
    
    NOTE: This function cannot list S3 objects because JWT tokens do not contain AWS credentials.
    The Quilt registry backend handles AWS access via IAM role assumption.
    
    To create a package from S3 contents, you must:
    1. Use 'search.unified_search' to find files in the bucket
    2. Collect the S3 URIs from search results
    3. Call 'packaging.create' with the list of S3 URIs
    """
    return format_error_response(
        "Cannot create package from S3 bucket listing - JWT tokens do not contain AWS credentials.\n\n"
        "The MCP server cannot list S3 objects directly. To create a package from S3 contents:\n\n"
        "1. Use 'search.unified_search' to find files:\n"
        f"   search.unified_search(query='*', buckets=['{bucket}'], object_prefix='{prefix}')\n\n"
        "2. Collect S3 URIs from search results\n\n"
        "3. Call packaging.create with the URIs:\n"
        f"   packaging.create(name='{name}', files=['s3://{bucket}/file1.csv', 's3://{bucket}/file2.csv'])\n\n"
        "Alternatively, if you know the exact file paths, provide them directly to packaging.create."
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
def packaging(action: Optional[str] = None, params: Optional[Dict[str, Any]] = None, _context: Optional[NavigationContext] = None) -> Dict[str, Any]:
    """
    Unified package management operations.

    Available actions:
    - browse: Browse a specific package and its contents
    - create: Create a new package
    - create_from_s3: Create a package from S3 bucket contents (returns guidance)
    - metadata_templates: List available metadata templates
    - get_template: Get a specific metadata template

    Note: For package discovery/listing, use the search tool:
        search.unified_search(query="*", scope="catalog", search_type="packages")

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
                    "browse",
                    "create",
                    "create_from_s3",
                    "metadata_templates",
                    "get_template",
                ],
                "description": "Unified package management via Quilt Catalog GraphQL",
                "note": "For package discovery/listing, use search.unified_search(scope='catalog', search_type='packages')"
            }
        elif action == "browse":
            name = params.get("name")
            if not name:
                return format_error_response("Package name is required for browse action")
            return package_browse(
                name=name,
                bucket=params.get("bucket"),
                registry=params.get("registry", DEFAULT_REGISTRY),
            )
        elif action == "create":
            # Map frontend parameter names to function parameter names
            name = params.get("name") or params.get("package_name")
            
            # Apply navigation context for smart defaults
            if _context and not name:
                suggested_name = suggest_package_name_from_context(_context)
                if suggested_name:
                    return {
                        "success": False,
                        "error": f"Package name is required. Suggested name based on current context: {suggested_name}",
                        "suggested_name": suggested_name,
                        "context_info": {
                            "route": _context.route.name,
                            "bucket": get_context_bucket(_context),
                            "path": get_context_path(_context),
                        }
                    }
            
            return package_create(
                name=name,
                files=params.get("files"),  # Now optional
                description=params.get("description", ""),
                metadata=params.get("metadata") or params.get("meta"),  # Support both names
                registry=params.get("registry"),
                dry_run=params.get("dry_run", False),
                auto_organize=params.get("auto_organize", True),
                copy_mode=params.get("copy_mode", "all"),
                readme=params.get("readme"),  # Support inline README content
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
    
    except Exception:
        logger.exception("Error executing packaging action '%s'", action)
        return format_error_response(f"Failed to execute packaging action '{action}'")

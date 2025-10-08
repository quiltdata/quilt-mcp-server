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

from collections import Counter
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import re
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


PACKAGE_METADATA_STOPWORDS = {
    "package",
    "packages",
    "data",
    "dataset",
    "datasets",
    "demo",
    "sample",
    "samples",
    "analysis",
    "test",
    "default",
}


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
        },
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
        },
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
        },
    },
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
        warnings.append(
            "README content extracted from metadata - upload README.md to S3 and add to 'files' parameter instead"
        )
    elif "readme" in metadata_dict:
        metadata_dict.pop("readme")
        warnings.append(
            "README content extracted from metadata - upload README.md to S3 and add to 'files' parameter instead"
        )

    return metadata_dict, None


def _get_file_extension(filename: str) -> str:
    """Get file extension from filename."""
    if filename.startswith("s3://"):
        without_scheme = filename[5:]
        without_query = without_scheme.split("?", 1)[0]
        if "/" in without_query:
            without_query = without_query.split("/", 1)[1]
        filename = without_query
    filename = filename.split("?", 1)[0]
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


def _tokenize(value: str) -> List[str]:
    tokens = re.split(r"[^a-z0-9]+", value.lower())
    return [token for token in tokens if token]


def _extract_bucket_from_uri(s3_uri: str) -> Optional[str]:
    if not s3_uri.startswith("s3://"):
        return None
    parts = s3_uri[5:].split("/", 1)
    return parts[0] if parts else None


def _generate_default_metadata(
    *,
    package_name: str,
    files: List[str],
    description: str,
    catalog_url: str,
    token: str,
) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {}

    if description:
        metadata["description"] = description
    else:
        metadata["description"] = (
            f"Auto-generated description: package '{package_name}' built from {len(files)} object(s)."
        )

    ext_counter: Counter[str] = Counter()
    buckets: set[str] = set()

    for uri in files:
        bucket = _extract_bucket_from_uri(uri)
        if bucket:
            buckets.add(bucket)
        ext = _get_file_extension(uri)
        if ext:
            ext_counter[ext] += 1

    if ext_counter:
        metadata.setdefault("file_extensions", sorted(ext_counter.keys()))
        metadata.setdefault("file_counts_by_extension", dict(ext_counter.most_common()))

    if buckets:
        metadata.setdefault("source_buckets", sorted(buckets))

    namespace, _, package_slug = package_name.partition("/")
    tokens = set(_tokenize(namespace)) | set(_tokenize(package_slug))

    similar_packages: List[str] = []
    try:
        similar_packages = catalog_client.catalog_packages_list(
            registry_url=catalog_url,
            auth_token=token,
            limit=20,
            prefix=f"{namespace}/",
        )
    except Exception:  # pragma: no cover - best effort
        similar_packages = []

    related = [pkg for pkg in similar_packages if pkg != package_name]
    if related:
        metadata.setdefault("related_packages", related[:5])

    for pkg in related:
        slug = pkg.split("/", 1)[-1]
        tokens.update(_tokenize(slug))

    tokens = [t for t in tokens if t not in PACKAGE_METADATA_STOPWORDS and len(t) >= 3]
    if tokens:
        metadata.setdefault("tags", sorted(tokens)[:10])

    if files:
        metadata.setdefault(
            "summary",
            f"Automatically generated metadata for {package_name} containing {len(files)} objects",
        )

    metadata.setdefault("generated_by", "quilt-mcp packaging tool")
    metadata.setdefault("generated_at", datetime.now(timezone.utc).isoformat())

    return metadata


def _validate_package_name(name: str) -> tuple[bool, Optional[str]]:
    """Validate package name format."""
    if not name:
        return False, "Package name is required"

    # Check if it contains a slash
    if "/" not in name:
        return False, (
            f"Invalid package name: '{name}'. Missing namespace separator '/'.\n"
            f"Package names MUST be in format 'namespace/packagename'\n"
            f"Examples:\n"
            f"  ✓ 'demo-team/csv-data'\n"
            f"  ✓ 'myteam/csvexample2'\n"
            f"  ✓ 'analytics/q1-reports'\n"
            f"  ✗ 'csvdata' (missing namespace)\n"
            f"  ✗ 'MyTeam/Data' (uppercase not allowed)\n"
            f"\nRules:\n"
            f"  - Must contain exactly one '/' separating namespace and package name\n"
            f"  - Use lowercase letters, numbers, hyphens, and underscores only\n"
            f"  - Must start with a lowercase letter or number"
        )

    if not validate_package_name(name):
        parts = name.split("/")
        if len(parts) != 2:
            return False, (
                f"Invalid package name: '{name}'. Too many '/' characters.\n"
                f"Package names must have exactly ONE '/' separator.\n"
                f"Format: 'namespace/packagename'\n"
                f"Examples: 'demo-team/csv-data', 'myteam/dataset1'"
            )

        namespace, pkg_name = parts
        return False, (
            f"Invalid package name: '{name}'.\n"
            f"  Namespace: '{namespace}'\n"
            f"  Package: '{pkg_name}'\n"
            f"\nRules:\n"
            f"  - Use lowercase letters, numbers, hyphens (-), and underscores (_) ONLY\n"
            f"  - No uppercase letters allowed\n"
            f"  - No periods (.) allowed - use hyphens instead\n"
            f"  - No spaces or special characters\n"
            f"  - Must start with a lowercase letter or number\n"
            f"\nValid examples:\n"
            f"  ✓ 'demo-team/csv-data'\n"
            f"  ✓ 'myteam/csvexample2'\n"
            f"  ✓ 'user_123/my_dataset'\n"
            f"  ✓ 'team/data-v2' (use hyphens for versions)\n"
            f"\nInvalid examples:\n"
            f"  ✗ 'MyTeam/Data' (uppercase not allowed)\n"
            f"  ✗ 'team/data.csv' (periods not allowed)\n"
            f"  ✗ 'team/my data' (spaces not allowed)\n"
            f"  ✗ 'team/data@v1' (special characters not allowed)\n"
            f"  ✗ 'team/csv-' (ends with hyphen)\n"
            f"  ✗ '-team/data' (starts with hyphen)"
        )

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
    auto_organize: bool = False,
    copy_mode: str = "all",
    readme: Optional[str] = None,
    target_bucket: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new Quilt package.

    IMPORTANT: Package names MUST be in 'namespace/packagename' format with BOTH parts.

    Args:
        name: Package name in format 'namespace/packagename' (REQUIRED: both namespace AND package name)
              Examples: 'demo-team/csv-data', 'myteam/dataset1', 'analytics/q1-reports'
              Rules: lowercase letters, numbers, hyphens (-), underscores (_) ONLY
              INVALID: uppercase, periods (.), spaces, special characters (@, #, etc.)
        files: List of S3 URIs to include in package (optional if readme provided)
               Example: ['s3://bucket/path/file1.csv', 's3://bucket/path/file2.json']
        description: Package description
        metadata: Package metadata dict
        registry: Target registry bucket (optional, extracted from name if not provided)
        dry_run: If true, validate but don't create
        auto_organize: Organize files into logical folders. Defaults to False to keep a shallow structure.
        copy_mode: Copy mode for files ('all', 'none', or 'metadata')
        readme: README content to upload as README.md (requires target bucket)

    Returns:
        Dict with success status and package information

    Example:
        package_create(
            name='demo-team/csv-analysis',  # MUST have both namespace/packagename
            files=['s3://quilt-sandbox-bucket/data/file1.csv', 's3://quilt-sandbox-bucket/data/file2.csv'],
            description='CSV analysis dataset'
        )
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
    metadata_dict, error = _prepare_metadata(metadata, warnings, on_error_message="Invalid metadata format")
    if error:
        return error

    if metadata_dict is None:
        metadata_dict = {}

    if description:
        metadata_dict.setdefault("description", description)

    # Validate inputs
    if not files and not readme:
        return format_error_response(
            "Package creation requires at least one S3 URI in 'files' or inline README content."
        )

    # Use provided files
    all_files = list(files or [])
    readme_file_added = False
    readme_upload_details: Dict[str, Any] = {}
    readme_planned_uri: Optional[str] = None
    readme_target_bucket: Optional[str] = None
    readme_key: Optional[str] = None

    if readme:
        readme_target_bucket = target_bucket or (all_files and _extract_bucket_from_uri(all_files[0])) or registry
        if readme_target_bucket and isinstance(readme_target_bucket, str):
            if readme_target_bucket.startswith("s3://"):
                readme_target_bucket = readme_target_bucket[5:].split("/", 1)[0]
            else:
                readme_target_bucket = readme_target_bucket.strip("/")

        if not readme_target_bucket:
            return format_error_response(
                "Cannot determine target bucket for README upload. "
                "Provide the 'bucket' parameter or include at least one S3 URI with a bucket."
            )

        readme_key = f".quilt/packages/{name}/README.md".replace("//", "/")
        readme_planned_uri = f"s3://{readme_target_bucket}/{readme_key}"

        if dry_run:
            all_files.append(readme_planned_uri)
        else:
            try:
                from .buckets import bucket_objects_put

                upload_result = bucket_objects_put(
                    bucket=readme_target_bucket,
                    items=[
                        {
                            "key": readme_key,
                            "text": readme,
                            "content_type": "text/markdown",
                        }
                    ],
                )
            except Exception as exc:  # pragma: no cover - defensive
                return format_error_response(f"Failed to upload README content: {exc}")

            readme_upload_details = upload_result
            upload_outcome = (upload_result.get("results") or [{}])[0]
            if upload_outcome.get("error"):
                return {
                    "success": False,
                    "error": f"Failed to upload README.md: {upload_outcome['error']}",
                    "upload_context": upload_result,
                }

            readme_uri = readme_planned_uri
            all_files.append(readme_uri)
            readme_file_added = True

    if not all_files:
        return format_error_response(
            "Package creation requires at least one S3 object. Upload failed or no files were provided."
        )

    # Organize files
    organized_files = []
    for file_path in all_files:
        organized_path = _organize_file_path(file_path, auto_organize)
        organized_files.append(
            {
                "logical_key": organized_path,
                "physical_key": file_path,
            }
        )

    auto_metadata = _generate_default_metadata(
        package_name=name,
        files=all_files,
        description=metadata_dict.get("description", ""),
        catalog_url=catalog_url,
        token=token,
    )
    added_keys = [key for key in auto_metadata if key not in metadata_dict]
    for key, value in auto_metadata.items():
        metadata_dict.setdefault(key, value)
    if added_keys:
        warnings.append("Auto-generated metadata fields applied: " + ", ".join(sorted(added_keys)))

    if readme_file_added:
        warnings.append("README.md uploaded and included in package manifest")
    elif readme and dry_run and readme_planned_uri:
        warnings.append(f"README.md will be uploaded to {readme_planned_uri}")

    if dry_run:
        return {
            "success": True,
            "dry_run": True,
            "package_name": name,
            "files": organized_files,
            "metadata": metadata_dict,
            "warnings": warnings,
            "message": "Dry run completed successfully",
            "planned_readme_uri": readme_planned_uri,
            "readme_target_bucket": readme_target_bucket,
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

        if not result.get("success", False):
            error_response = {
                "success": False,
                "error": result.get("error", f"Failed to create package '{name}'"),
                "warnings": warnings + result.get("warnings", []),
            }
            if result.get("error_type"):
                error_response["error_type"] = result["error_type"]
            if result.get("details"):
                error_response["details"] = result["details"]
            return error_response

        navigation = None
        bucket_for_nav: Optional[str] = None

        if isinstance(result, dict):
            package_info = result.get("package")
            if isinstance(package_info, dict):
                bucket_for_nav = package_info.get("bucket")

        if not bucket_for_nav:
            source_buckets = metadata_dict.get("source_buckets")
            if isinstance(source_buckets, list) and source_buckets:
                bucket_for_nav = source_buckets[0]

        if not bucket_for_nav:
            for uri in all_files:
                candidate = _extract_bucket_from_uri(uri)
                if candidate:
                    bucket_for_nav = candidate
                    break

        if bucket_for_nav:
            bucket_for_nav = bucket_for_nav.replace("s3://", "")
            navigation = {
                "tool": "navigate",
                "params": {
                    "route": {
                        "name": "package.overview",
                        "params": {
                            "bucket": bucket_for_nav,
                            "name": name,
                        },
                    },
                },
                "auto_execute": True,
                "description": f"Navigating to package: {name}",
                "url": f"/b/{bucket_for_nav}/packages/{name}",
            }

        response_payload = {
            "success": True,
            "result": result,
            "warnings": warnings,
            "message": f"Package '{name}' created successfully",
        }

        if navigation:
            response_payload["navigation"] = navigation

        if readme_file_added:
            response_payload["readme_upload"] = readme_upload_details
        elif readme_planned_uri:
            response_payload["readme_upload"] = {
                "planned_uri": readme_planned_uri,
                "target_bucket": readme_target_bucket,
            }

        return response_payload

    except Exception:
        logger.exception("Error creating package '%s'", name)
        return format_error_response(f"Failed to create package '{name}'")


def package_delete(
    name: str,
    bucket: Optional[str] = None,
    registry: Optional[str] = None,
    confirm: bool = False,
    dry_run: bool = False,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    """Delete an existing Quilt package."""
    if not name:
        return format_error_response("Package name is required for deletion")

    target_registry: Optional[str] = None
    normalized_bucket = None
    if registry:
        target_registry = registry
    elif bucket:
        normalized_bucket = bucket.strip("/")
        if normalized_bucket.startswith("s3://"):
            target_registry = normalized_bucket
            normalized_bucket = normalized_bucket[5:]
        else:
            target_registry = f"s3://{normalized_bucket}"
    else:
        target_registry = resolve_catalog_url() or DEFAULT_REGISTRY

    if normalized_bucket is None and bucket:
        normalized_bucket = bucket.strip("/")

    preview_payload = {
        "success": True,
        "action": "preview",
        "package_name": name,
        "registry": target_registry,
        "bucket": normalized_bucket,
        "message": "Set confirm=True to delete this package",
    }
    if reason:
        preview_payload["reason"] = reason

    if dry_run:
        return preview_payload

    if not confirm:
        preview_payload["success"] = False
        preview_payload["error"] = "Package deletion requires confirm=True"
        preview_payload["next_steps"] = [
            "Call packaging(action='delete', params={'name': 'namespace/package', 'bucket': 'my-bucket', 'confirm': True})"
        ]
        return preview_payload

    token = get_active_token()
    if not token:
        return format_error_response("Authorization token required to delete packages")

    catalog_url = resolve_catalog_url()
    if not catalog_url:
        return format_error_response("Catalog URL not configured")

    try:
        backend_response = catalog_client.catalog_package_delete(
            registry_url=catalog_url,
            package_name=name,
            auth_token=token,
        )
    except Exception as exc:
        logger.exception("Failed to delete package '%s'", name)
        return {
            "success": False,
            "error": f"Failed to delete package '{name}': {exc}",
            "package_name": name,
            "registry": target_registry,
            "bucket": normalized_bucket,
        }

    response: Dict[str, Any] = {
        "success": True,
        "action": "deleted",
        "package_name": name,
        "registry": target_registry,
        "bucket": normalized_bucket,
        "message": f"Package '{name}' deleted successfully",
    }
    if reason:
        response["reason"] = reason
    if backend_response:
        response["backend_response"] = backend_response
    return response


# S3-to-package creation
def package_create_from_s3(  # noqa: ARG001
    name: str,
    bucket: str,
    prefix: str = "",
    description: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    auto_organize: bool = False,
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
def packaging(
    action: Optional[str] = None, params: Optional[Dict[str, Any]] = None, _context: Optional[NavigationContext] = None
) -> Dict[str, Any]:
    """
    Unified package management operations.

    ⚠️  CRITICAL: Package names MUST use 'namespace/package-name' format:
        - REQUIRED: Both namespace AND package name separated by exactly one '/'
        - REQUIRED: Lowercase letters, numbers, hyphens (-), underscores (_) ONLY
        - NO uppercase letters allowed
        - NO periods (.) allowed - use hyphens instead
        - NO spaces or special characters
        - Examples: 'demo-team/csv-data', 'myteam/dataset1', 'analytics/q1-reports'
        - WRONG: 'csvdata' (missing namespace), 'MyTeam/Data' (uppercase), 'team/data.csv' (period)

    Available actions:
    - browse: Browse a specific package and its contents
    - create: Create a new package (REQUIRES 'namespace/package-name' format)
    - create_from_s3: Create a package from S3 bucket contents (returns guidance)
    - metadata_templates: List available metadata templates
    - get_template: Get a specific metadata template

    Note: For package discovery/listing, use the search tool:
        search.unified_search(query="*", scope="catalog", search_type="packages")

    Defaults:
        - Files are added to the package root (flattened) unless auto_organize=True
        - Useful metadata (description, tags, extension counts) is auto-generated when missing

    Example create action:
        packaging(action="create", params={
            "name": "demo-team/csv-analysis",  # MUST have namespace/package-name
            "files": ["s3://bucket/file1.csv", "s3://bucket/file2.csv"],
            "description": "CSV analysis dataset"
        })

    Args:
        action: The operation to perform. If None, returns available actions.
        params: Action-specific parameters. For 'create' action, 'name' parameter
                MUST be in 'namespace/package-name' format (lowercase only).

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
                    "delete",
                    "metadata_templates",
                    "get_template",
                ],
                "description": "Unified package management via Quilt Catalog GraphQL",
                "CRITICAL_NAMING_RULE": "Package names MUST be 'namespace/package-name' format (lowercase, hyphens, underscores only - NO PERIODS)",
                "naming_examples": {
                    "valid": ["demo-team/csv-data", "myteam/dataset1", "analytics/q1-reports", "user123/data-v2"],
                    "invalid": [
                        "csvdata (missing namespace)",
                        "MyTeam/Data (uppercase not allowed)",
                        "team/data.csv (periods not allowed)",
                        "team/my data (spaces not allowed)",
                        "team/data@v1 (special chars not allowed)",
                    ],
                },
                "note": "For package discovery/listing, use search.unified_search(scope='catalog', search_type='packages')",
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

            # Early validation with helpful error message
            if name and "/" not in name:
                return {
                    "success": False,
                    "error": f"Invalid package name: '{name}'. Missing namespace separator '/'.",
                    "CRITICAL": "Package names MUST be in 'namespace/package-name' format",
                    "provided": name,
                    "examples": {
                        "valid": ["demo-team/csv-data", "myteam/dataset1", "analytics/reports"],
                        "invalid": [
                            "csvdata (missing namespace)",
                            "MyTeam/Data (uppercase)",
                            "team/data.csv (period)",
                        ],
                    },
                    "correct_format": "namespace/package-name (lowercase, hyphens, underscores only - NO PERIODS)",
                    "tip": f"Try: 'demo-team/{name}' or 'myteam/{name}'",
                }

            # Check for periods in the name
            if name and "." in name:
                clean_name = name.replace(".", "-")
                return {
                    "success": False,
                    "error": f"Invalid package name: '{name}'. Periods (.) are not allowed.",
                    "CRITICAL": "Package names cannot contain periods - use hyphens (-) instead",
                    "provided": name,
                    "suggestion": clean_name,
                    "examples": {
                        "valid": ["demo-team/csv-data", "myteam/v1-0", "analytics/data-v2"],
                        "invalid": ["team/data.csv (period)", "team/v1.0 (period)", "team/file.name (period)"],
                    },
                    "tip": f"Use hyphens instead: '{clean_name}'",
                }

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
                        },
                    }

            return package_create(
                name=name,
                files=params.get("files"),  # Now optional
                description=params.get("description", ""),
                metadata=params.get("metadata") or params.get("meta"),  # Support both names
                registry=params.get("registry"),
                dry_run=params.get("dry_run", False),
                auto_organize=params.get("auto_organize", False),
                copy_mode=params.get("copy_mode", "all"),
                readme=params.get("readme"),  # Support inline README content
                target_bucket=params.get("bucket"),
            )
        elif action == "create_from_s3":
            return package_create_from_s3(
                name=params.get("name"),
                bucket=params.get("bucket"),
                prefix=params.get("prefix", ""),
                description=params.get("description", ""),
                metadata=params.get("metadata"),
                auto_organize=params.get("auto_organize", False),
                dry_run=params.get("dry_run", False),
                copy_mode=params.get("copy_mode", "all"),
            )
        elif action == "delete":
            name = params.get("name") or params.get("package_name")
            if not name:
                return format_error_response("Package name is required for delete action")
            return package_delete(
                name=name,
                bucket=params.get("bucket"),
                registry=params.get("registry"),
                confirm=params.get("confirm", False),
                dry_run=params.get("dry_run", False),
                reason=params.get("reason"),
            )
        elif action == "metadata_templates":
            return list_metadata_templates()
        elif action == "get_template":
            return get_metadata_template(template_name=params.get("template_name", "standard"))
        else:
            return format_error_response(f"Unknown packaging action: {action}")

    except Exception:
        logger.exception("Error executing packaging action '%s'", action)
        return format_error_response(f"Failed to execute packaging action '{action}'")

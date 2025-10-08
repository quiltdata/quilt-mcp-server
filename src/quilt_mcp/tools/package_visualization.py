"""Package visualization enrichment tools.

This module analyses package contents and ensures that Quilt packages include
README documentation, quilt_summarize.json entries, and dashboard-friendly
visualizations following Quilt documentation standards.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..clients import catalog as catalog_client
from ..runtime import get_active_token
from ..types.navigation import NavigationContext, get_context_bucket
from ..utils import format_error_response, resolve_catalog_url
from .buckets import bucket_objects_put
from .quilt_summary import create_quilt_summary_files
from .s3_package import _generate_readme_content, _organize_file_structure

logger = logging.getLogger(__name__)


def _load_package_revision_metadata(registry_url: str, bucket: str, package_name: str, token: str) -> Dict[str, Any]:
    """Fetch package metadata and latest revision details."""
    query = """
    query PackageVisualizationMetadata($bucket: String!, $name: String!) {
      package(bucket: $bucket, name: $name) {
        name
        metadata
        latest: revision(hashOrTag: "latest") {
          hash
          metadata
          userMeta
        }
      }
    }
    """

    data = catalog_client.catalog_graphql_query(
        registry_url=registry_url,
        query=query,
        variables={"bucket": bucket, "name": package_name},
        auth_token=token,
    )

    package_info = data.get("package") if isinstance(data, dict) else {}
    latest_revision = package_info.get("latest") or {}

    revision_metadata = latest_revision.get("metadata") or {}
    package_metadata = package_info.get("metadata") or {}

    quilt_metadata = {}
    quilt_metadata.update(package_metadata if isinstance(package_metadata, dict) else {})
    quilt_metadata.update(revision_metadata if isinstance(revision_metadata, dict) else {})

    return {
        "quilt": quilt_metadata,
        "revision_hash": latest_revision.get("hash"),
    }


def _build_structure_from_entries(entries: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Convert package entries into the structure expected by summary helpers."""
    objects = []
    for entry in entries:
        logical_key = entry.get("logicalKey") or entry.get("logical_key") or ""
        if not logical_key:
            continue
        objects.append(
            {
                "Key": logical_key,
                "Size": entry.get("size") or entry.get("Size") or 0,
            }
        )

    # Reuse existing organizer to provide consistent folder/extension grouping
    return _organize_file_structure(objects, auto_organize=True)


def _detect_dashboard_assets(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Identify HTML dashboards that should surface in quilt_summarize.json."""
    dashboards: List[Dict[str, Any]] = []

    for entry in entries:
        logical_key = entry.get("logicalKey") or ""
        ext = Path(logical_key).suffix.lower()
        if ext in {".html", ".htm"}:
            title = Path(logical_key).stem.replace("_", " ").title()
            dashboards.append(
                {
                    "title": title,
                    "type": "web",
                    "description": "Embedded HTML report included in the package.",
                    "path": logical_key,
                }
            )
    return dashboards


def _detect_visualizable_tables(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Detect tabular assets that should expose quick visualizations."""
    visualizations: List[Dict[str, Any]] = []

    table_exts = {".csv", ".tsv", ".parquet", ".json"}
    for entry in entries:
        logical_key = entry.get("logicalKey") or ""
        ext = Path(logical_key).suffix.lower()
        if ext in table_exts:
            title = Path(logical_key).name
            viz_type = "table"
            if ext in {".parquet"}:
                viz_type = "dataset"
            visualizations.append(
                {
                    "title": f"Preview: {title}",
                    "type": viz_type,
                    "path": logical_key,
                    "description": "Automatically detected tabular dataset.",
                }
            )
    return visualizations


def _needs_readme(entries: List[Dict[str, Any]]) -> bool:
    """Determine whether README.md is missing."""
    for entry in entries:
        logical_key = entry.get("logicalKey", "").lower()
        if logical_key.endswith("readme.md"):
            return False
    return True


def _build_source_info(bucket: str, package_name: str) -> Dict[str, Any]:
    """Create source info payload for summary helpers."""
    namespace = package_name.split("/")[0] if "/" in package_name else "unknown"
    return {
        "type": "package_revision",
        "bucket": bucket,
        "prefix": f".quilt/packages/{namespace}",
        "source_description": f"Package stored in {bucket}",
    }


async def package_visualization(
    action: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
    _context: Optional[NavigationContext] = None,
) -> Dict[str, Any]:
    """Package visualization tool dispatcher."""
    if action is None:
        return {
            "module": "package_visualization",
            "actions": [
                "enrich",
            ],
            "description": "Generate README, quilt_summarize.json, and visualization dashboards for existing packages.",
        }

    params = dict(params or {})

    if action != "enrich":
        return format_error_response(f"Unknown package_visualization action: {action}")

    package_name = params.get("package_name") or params.get("name")
    if not package_name:
        return format_error_response("package_name is required")

    bucket = params.get("bucket") or get_context_bucket(_context)
    if not bucket:
        return format_error_response("bucket parameter is required to enrich package visualizations")

    token = get_active_token()
    if not token:
        return format_error_response("Authorization token required")

    catalog_url = resolve_catalog_url()
    if not catalog_url:
        return format_error_response("Catalog URL not configured")

    registry_url = catalog_url
    bucket_stripped = bucket.replace("s3://", "")

    try:
        entries = catalog_client.catalog_package_entries(
            registry_url=registry_url,
            bucket=bucket_stripped,
            package_name=package_name,
            auth_token=token,
        )
    except Exception as exc:
        logger.exception("Failed to fetch package entries")
        return format_error_response(f"Failed to fetch package entries: {exc}")

    if not entries:
        return format_error_response(f"No package entries found for {package_name} in bucket {bucket_stripped}")

    metadata_info = _load_package_revision_metadata(registry_url, bucket_stripped, package_name, token)
    package_metadata = {"quilt": metadata_info.get("quilt", {})}

    organized_structure = _build_structure_from_entries(entries)

    total_size = sum(entry.get("size", 0) for entry in entries)
    source_info = _build_source_info(bucket_stripped, package_name)

    readme_exists = not _needs_readme(entries)
    if readme_exists:
        readme_content = "Existing README retained."
    else:
        description = package_metadata["quilt"].get("description", "")
        readme_content = _generate_readme_content(
            package_name=package_name,
            description=description,
            organized_structure=organized_structure,
            total_size=total_size,
            source_info=source_info,
            metadata_template=params.get("metadata_template", "standard"),
        )

    summary_result = create_quilt_summary_files(
        package_name=package_name,
        package_metadata=package_metadata,
        organized_structure=organized_structure,
        readme_content=readme_content,
        source_info=source_info,
        metadata_template=params.get("metadata_template", "standard"),
    )

    if not summary_result.get("success"):
        return format_error_response(summary_result.get("error", "Failed to generate summary files"))

    summary_package = summary_result["summary_package"]
    summary_json = summary_package.get("quilt_summarize.json", {})

    dashboards = _detect_dashboard_assets(entries)
    table_visualizations = _detect_visualizable_tables(entries)

    if dashboards:
        summary_json.setdefault("visualization_dashboards", [])
        summary_json["visualization_dashboards"].extend(dashboards)

    if table_visualizations:
        summary_json.setdefault("quick_visualizations", [])
        summary_json["quick_visualizations"].extend(table_visualizations)

    summary_package["quilt_summarize.json"] = summary_json

    uploads = []
    new_resources: List[str] = []

    summary_key = f".quilt/packages/{package_name}/quilt_summarize.json"
    uploads.append(
        {
            "key": summary_key,
            "text": json.dumps(summary_json, indent=2),
            "content_type": "application/json",
        }
    )
    new_resources.append(f"s3://{bucket_stripped}/{summary_key}")

    readme_generated = False
    if not readme_exists:
        readme_key = f".quilt/packages/{package_name}/README.md"
        uploads.append(
            {
                "key": readme_key,
                "text": readme_content,
                "content_type": "text/markdown",
            }
        )
        new_resources.append(f"s3://{bucket_stripped}/{readme_key}")
        readme_generated = True

    upload_result = bucket_objects_put(bucket_stripped, uploads)
    if not upload_result.get("success"):
        return upload_result

    try:
        update_response = catalog_client.catalog_package_update(
            registry_url=registry_url,
            package_name=package_name,
            auth_token=token,
            s3_uris=new_resources,
            metadata=None,
            message=f"Added visualization metadata for {package_name}",
            copy_mode="all",
            flatten=True,
        )
    except Exception as exc:
        logger.exception("Failed to update package with visualization assets")
        return format_error_response(f"Failed to update package with visualization assets: {exc}")

    return {
        "success": True,
        "package_name": package_name,
        "bucket": bucket_stripped,
        "readme_created": readme_generated,
        "summary_key": summary_key,
        "dashboards_added": dashboards,
        "table_visualizations": table_visualizations,
        "upload_result": upload_result,
        "package_update": update_response,
        "message": "Package visualization assets generated successfully.",
        "next_steps": [
            f"Open the package in the catalog to view dashboards for '{package_name}'.",
            "Review quilt_summarize.json to customize dashboards if needed.",
        ],
    }


__all__ = ["package_visualization"]

"""Quilt Package Summary and Visualization Generator.

This module automatically generates quilt_summarize.json files and visualizations
for all Quilt packages, following the official Quilt documentation standards.
"""

from typing import Optional, Dict, Any
from typing import List, Tuple
import json
import logging
import io
import base64
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict

from quilt_mcp.visualization.multi_format import MultiFormatVisualizationGenerator

logger = logging.getLogger(__name__)

# Color schemes for visualizations
COLOR_SCHEMES = {
    "default": ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"],
    "genomics": ["#2E8B57", "#20B2AA", "#48D1CC", "#00CED1", "#40E0D0"],
    "ml": ["#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7"],
    "research": ["#6C5CE7", "#A29BFE", "#FD79A8", "#FDCB6E", "#E17055"],
    "analytics": ["#00B894", "#00CEC9", "#74B9FF", "#FDCB6E", "#E17055"],
}

MULTI_FORMAT_GENERATOR = MultiFormatVisualizationGenerator()

_MATPLOTLIB_CONFIGURED = False
_MATPLOTLIB_PYLOT = None
_NUMPY_LIB = None


def _ensure_matplotlib():
    """Lazily import matplotlib so environments without it can still use multi-format flows."""
    global _MATPLOTLIB_CONFIGURED, _MATPLOTLIB_PYLOT  # pylint: disable=global-statement

    if _MATPLOTLIB_PYLOT is not None:
        return _MATPLOTLIB_PYLOT

    import matplotlib  # type: ignore import-error

    if not _MATPLOTLIB_CONFIGURED:
        matplotlib.use("Agg")
        _MATPLOTLIB_CONFIGURED = True

    import matplotlib.pyplot as plt  # type: ignore import-error

    _MATPLOTLIB_PYLOT = plt
    return _MATPLOTLIB_PYLOT


def _ensure_numpy():
    """Lazy import for numpy to keep legacy visualizations optional."""
    global _NUMPY_LIB  # pylint: disable=global-statement

    if _NUMPY_LIB is None:
        import numpy as np  # type: ignore import-error

        _NUMPY_LIB = np

    return _NUMPY_LIB


def generate_quilt_summarize_json(
    package_name: str,
    package_metadata: Dict[str, Any],
    organized_structure: Dict[str, List[Dict[str, Any]]],
    readme_content: str,
    source_info: Dict[str, Any],
    metadata_template: str = "standard",
) -> Dict[str, Any]:
    """
    Generate a comprehensive quilt_summarize.json file following Quilt standards.

    This file provides a machine-readable summary of the package contents,
    structure, and metadata for automated processing and discovery.

    Args:
        package_name: Package name in namespace/name format
        package_metadata: Full package metadata dictionary
        organized_structure: Organized file structure by folders
        readme_content: Generated README.md content
        source_info: Information about the data source
        metadata_template: Template used for metadata generation

    Returns:
        Complete quilt_summarize.json content as dictionary
    """
    try:
        # Calculate comprehensive statistics
        total_files = sum(len(files) for files in organized_structure.values())
        total_size = sum(sum(obj.get("Size", 0) for obj in files) for files in organized_structure.values())

        # Extract file types and sizes
        file_types = defaultdict(int)
        file_sizes = defaultdict(int)
        folder_stats = {}

        for folder, files in organized_structure.items():
            folder_files = len(files)
            folder_size = sum(obj.get("Size", 0) for obj in files)
            folder_stats[folder or "root"] = {
                "file_count": folder_files,
                "total_size_bytes": folder_size,
                "total_size_mb": round(folder_size / (1024 * 1024), 2),
            }

            for obj in files:
                ext = Path(obj["Key"]).suffix.lower().lstrip(".")
                if ext:
                    file_types[ext] += 1
                    file_sizes[ext] += obj.get("Size", 0)

        # Build the summary structure
        summary = {
            "package_info": {
                "name": package_name,
                "namespace": (package_name.split("/")[0] if "/" in package_name else "unknown"),
                "package_name": (package_name.split("/")[-1] if "/" in package_name else package_name),
                "version": package_metadata.get("quilt", {}).get("package_version", "1.0.0"),
                "created_by": package_metadata.get("quilt", {}).get("created_by", "quilt-mcp-server"),
                "creation_date": package_metadata.get("quilt", {}).get(
                    "creation_date", datetime.now(timezone.utc).isoformat()
                ),
                "metadata_template": metadata_template,
                "description": package_metadata.get("quilt", {}).get(
                    "description", "Data package created via Quilt MCP Server"
                ),
            },
            "data_summary": {
                "total_files": total_files,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "total_size_gb": round(total_size / (1024 * 1024 * 1024), 3),
                "file_types": dict(file_types),
                "file_type_distribution": {
                    ext: {
                        "count": count,
                        "total_size_bytes": file_sizes[ext],
                        "total_size_mb": round(file_sizes[ext] / (1024 * 1024), 2),
                    }
                    for ext, count in file_types.items()
                },
            },
            "structure": {
                "folders": folder_stats,
                "organization_type": (
                    "smart_hierarchy" if any(folder for folder in organized_structure.keys()) else "flat"
                ),
                "auto_organized": True,
            },
            "source": {
                "type": source_info.get("type", "s3_bucket"),
                "bucket": source_info.get("bucket", "unknown"),
                "prefix": source_info.get("prefix", ""),
                "source_description": source_info.get("source_description", "Data sourced from S3 bucket"),
            },
            "documentation": {
                "readme_generated": bool(readme_content),
                "readme_length": len(readme_content) if readme_content else 0,
                "metadata_complete": bool(package_metadata.get("quilt")),
                "visualizations_generated": True,
            },
            "quilt_metadata": package_metadata.get("quilt", {}),
            "access": {
                "browse_command": f"Use search.unified_search with scope='package' and target='{package_name}'",
                "catalog_url": f"https://open.quiltdata.com/b/{source_info.get('bucket', 'unknown')}/packages/{package_name}",
                "api_access": True,
                "cli_access": True,
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "generator": "quilt-mcp-server",
            "generator_version": "1.0.0",
        }

        return summary

    except Exception as e:
        logger.error(f"Failed to generate quilt_summarize.json: {e}")
        return {
            "error": f"Failed to generate summary: {str(e)}",
            "package_name": package_name,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


def generate_package_visualizations(
    package_name: str,
    organized_structure: Dict[str, List[Dict[str, Any]]],
    file_types: Dict[str, Any],
    metadata_template: str = "standard",
    package_metadata: Optional[Dict[str, Any]] = None,
    **_extra: Any,
) -> Dict[str, Any]:
    """
    Generate comprehensive visualizations for the package.

    Creates multiple visualization types:
    - File type distribution pie chart
    - Folder structure treemap
    - File size distribution histogram
    - Package overview dashboard

    Args:
        package_name: Package name for title generation (e.g., "user/dataset")
        organized_structure: Organized file structure by folder.
            REQUIRED FORMAT: Dict[folder_name, List[file_dict]]
            Example: {
                "data": [
                    {"Key": "file1.csv", "Size": 1024},
                    {"Key": "file2.json", "Size": 512}
                ],
                "docs": [{"Key": "README.md", "Size": 256}]
            }
            Each file_dict MUST have "Key" (or "key") and "Size" (or "size") fields.
        file_types: File type counts. Can be:
            - Dict[str, int]: {"csv": 5, "json": 3}
            - Dict[str, dict]: {"csv": {"count": 5}}
            - {} (empty): Will auto-derive from organized_structure
        metadata_template: Template for color scheme (default, genomics, ml, research, analytics)
        package_metadata: Optional package metadata (reserved for future use)
        **_extra: Future-proof parameter for accepting additional kwargs

    Returns:
        Dictionary with:
        - success: bool
        - count: int (number of visualizations generated)
        - types: List[str] (visualization types)
        - visualizations: Dict (visualization data)
        - metadata: Dict (generation metadata)
        - visualization_dashboards: List (widget-based dashboard configs)

    Example:
        result = generate_package_visualizations(
            package_name="user/dataset",
            organized_structure={
                "data": [
                    {"Key": "data.csv", "Size": 1024},
                    {"Key": "results.json", "Size": 512}
                ]
            },
            file_types={"csv": 1, "json": 1}
        )
    """
    try:
        # Validate organized_structure format
        if not isinstance(organized_structure, dict):
            return {
                "success": False,
                "error": f"organized_structure must be a dict, got {type(organized_structure).__name__}",
                "visualizations": {},
                "count": 0,
            }
        
        # Check that all values are lists
        for folder_name, files in (organized_structure or {}).items():
            if not isinstance(files, list):
                return {
                    "success": False,
                    "error": f"organized_structure['{folder_name}'] must be a list, got {type(files).__name__}. "
                            f"Expected format: {{'folder': [{{'Key': 'file.csv', 'Size': 1024}}]}}",
                    "visualizations": {},
                    "count": 0,
                }
        
        # Normalize incoming file_types to simple counts
        normalized_file_types: Dict[str, int] = {}
        for ext, info in (file_types or {}).items():
            if isinstance(info, dict):
                count = info.get("count") or info.get("total")
                if count is not None:
                    normalized_file_types[ext] = int(count)
            else:
                normalized_file_types[ext] = int(info)

        # Derive file type counts from structure if not provided
        if not normalized_file_types:
            for files in (organized_structure or {}).values():
                for obj in files or []:
                    logical_key = (
                        obj.get("logicalKey")
                        or obj.get("LogicalKey")
                        or obj.get("Key")
                        or obj.get("key")
                        or ""
                    )
                    ext = Path(str(logical_key)).suffix.lstrip(".").lower() or "unknown"
                    normalized_file_types[ext] = normalized_file_types.get(ext, 0) + 1

        total_files = sum(len(files or []) for files in (organized_structure or {}).values())
        total_bytes = sum(
            (entry.get("Size") or entry.get("size") or 0)
            for files in (organized_structure or {}).values()
            for entry in (files or [])
        )
        total_size_mb = total_bytes / (1024 * 1024) if total_bytes else 0

        try:
            plt = _ensure_matplotlib()
        except Exception as exc:  # pragma: no cover - depends on optional dependency
            logger.error("Matplotlib unavailable for legacy visualizations: %s", exc)
            return {
                "success": False,
                "error": f"Matplotlib is required for legacy visualizations: {exc}",
                "visualizations": {},
                "count": 0,
            }

        try:
            np = _ensure_numpy()
        except Exception as exc:  # pragma: no cover - depends on optional dependency
            logger.error("NumPy unavailable for legacy visualizations: %s", exc)
            return {
                "success": False,
                "error": f"NumPy is required for legacy visualizations: {exc}",
                "visualizations": {},
                "count": 0,
            }

        visualizations = {}

        # 1. File Type Distribution Pie Chart
        if normalized_file_types and len(normalized_file_types) > 1:
            fig, ax = plt.subplots(figsize=(10, 8))
            colors = COLOR_SCHEMES.get(metadata_template, COLOR_SCHEMES["default"])

            # Sort by count for better visualization
            sorted_types = sorted(normalized_file_types.items(), key=lambda x: x[1], reverse=True)
            labels = [f"{ext} ({count})" for ext, count in sorted_types]
            sizes = [count for _, count in sorted_types]

            wedges, texts, autotexts = ax.pie(
                sizes,
                labels=labels,
                autopct="%1.1f%%",
                colors=colors[: len(sizes)],
                startangle=90,
            )
            ax.set_title(
                f"File Type Distribution - {package_name}",
                fontsize=16,
                fontweight="bold",
            )

            # Save to base64 string
            img_buffer = io.BytesIO()
            plt.savefig(img_buffer, format="png", dpi=150, bbox_inches="tight")
            img_buffer.seek(0)
            img_base64 = base64.b64encode(img_buffer.getvalue()).decode()
            plt.close()

            visualizations["file_type_distribution"] = {
                "type": "pie_chart",
                "title": "File Type Distribution",
                "description": "Distribution of files by file extension",
                "data": {
                    "labels": [ext for ext, _ in sorted_types],
                    "values": sizes,
                    "percentages": [round(count / sum(sizes) * 100, 1) for count in sizes],
                },
                "image_base64": img_base64,
                "mime_type": "image/png",
            }

        # 2. Folder Structure Visualization
        if organized_structure:
            fig, ax = plt.subplots(figsize=(12, 8))

            folders = list(organized_structure.keys())
            file_counts = [len(organized_structure.get(folder, []) or []) for folder in folders]

            # Use horizontal bar chart for folder structure
            y_pos = np.arange(len(folders))
            colors = COLOR_SCHEMES.get(metadata_template, COLOR_SCHEMES["default"])

            bars = ax.barh(y_pos, file_counts, color=colors[: len(folders)])
            ax.set_yticks(y_pos)
            ax.set_yticklabels([f"{folder}/" if folder else "root/" for folder in folders])
            ax.set_xlabel("Number of Files")
            ax.set_title(
                f"File Distribution by Folder - {package_name}",
                fontsize=16,
                fontweight="bold",
            )

            # Add value labels on bars
            for i, bar in enumerate(bars):
                width = bar.get_width()
                ax.text(
                    width + 0.1,
                    bar.get_y() + bar.get_height() / 2,
                    str(int(width)),
                    ha="left",
                    va="center",
                )

            plt.tight_layout()

            # Save to base64 string
            img_buffer = io.BytesIO()
            plt.savefig(img_buffer, format="png", dpi=150, bbox_inches="tight")
            img_buffer.seek(0)
            img_base64 = base64.b64encode(img_buffer.getvalue()).decode()
            plt.close()

            visualizations["folder_structure"] = {
                "type": "horizontal_bar_chart",
                "title": "File Distribution by Folder",
                "description": "Number of files in each organized folder",
                "data": {
                    "folders": [f"{folder}/" if folder else "root/" for folder in folders],
                    "file_counts": file_counts,
                },
                "image_base64": img_base64,
                "mime_type": "image/png",
            }

        # 3. File Size Distribution (if we have size data)
        all_sizes = []
        for files in organized_structure.values():
            for obj in files:
                size = obj.get("Size") or obj.get("size") or 0
                if size > 0:
                    all_sizes.append(size)

        if all_sizes and len(all_sizes) > 5:
            fig, ax = plt.subplots(figsize=(10, 6))

            # Convert to MB for better readability
            sizes_mb = [size / (1024 * 1024) for size in all_sizes]

            ax.hist(
                sizes_mb,
                bins=min(20, len(sizes_mb) // 2),
                alpha=0.7,
                color=COLOR_SCHEMES.get(metadata_template, COLOR_SCHEMES["default"])[0],
            )
            ax.set_xlabel("File Size (MB)")
            ax.set_ylabel("Number of Files")
            ax.set_title(
                f"File Size Distribution - {package_name}",
                fontsize=16,
                fontweight="bold",
            )

            # Add statistics
            mean_size = np.mean(sizes_mb)
            median_size = np.median(sizes_mb)
            ax.axvline(
                mean_size,
                color="red",
                linestyle="--",
                label=f"Mean: {mean_size:.1f} MB",
            )
            ax.axvline(
                median_size,
                color="orange",
                linestyle="--",
                label=f"Median: {median_size:.1f} MB",
            )
            ax.legend()

            plt.tight_layout()

            # Save to base64 string
            img_buffer = io.BytesIO()
            plt.savefig(img_buffer, format="png", dpi=150, bbox_inches="tight")
            img_buffer.seek(0)
            img_base64 = base64.b64encode(img_buffer.getvalue()).decode()
            plt.close()

            visualizations["file_size_distribution"] = {
                "type": "histogram",
                "title": "File Size Distribution",
                "description": "Distribution of file sizes in MB",
                "data": {
                    "sizes_mb": sizes_mb,
                    "statistics": {
                        "mean_mb": round(mean_size, 2),
                        "median_mb": round(median_size, 2),
                        "min_mb": round(min(sizes_mb), 2),
                        "max_mb": round(max(sizes_mb), 2),
                    },
                },
                "image_base64": img_base64,
                "mime_type": "image/png",
            }

        # 4. Package Overview Dashboard
        if visualizations:
            # Create a summary visualization combining key metrics
            fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
            fig.suptitle(
                f"Package Overview Dashboard - {package_name}",
                fontsize=20,
                fontweight="bold",
            )

            # Top left: File count by folder
            if "folder_structure" in visualizations:
                folders = visualizations["folder_structure"]["data"]["folders"]
                counts = visualizations["folder_structure"]["data"]["file_counts"]
                ax1.bar(
                    range(len(folders)),
                    counts,
                    color=COLOR_SCHEMES.get(metadata_template, COLOR_SCHEMES["default"]),
                )
                ax1.set_title("Files per Folder")
                ax1.set_xticks(range(len(folders)))
                ax1.set_xticklabels([f.split("/")[0] for f in folders], rotation=45)
                ax1.set_ylabel("File Count")

            # Top right: File type distribution
            if "file_type_distribution" in visualizations:
                labels = visualizations["file_type_distribution"]["data"]["labels"]
                values = visualizations["file_type_distribution"]["data"]["values"]
                ax2.pie(
                    values,
                    labels=labels,
                    autopct="%1.1f%%",
                    colors=COLOR_SCHEMES.get(metadata_template, COLOR_SCHEMES["default"]),
                )
                ax2.set_title("File Types")

            # Bottom left: File size distribution
            if "file_size_distribution" in visualizations:
                sizes = visualizations["file_size_distribution"]["data"]["sizes_mb"]
                ax3.hist(
                    sizes,
                    bins=min(15, len(sizes) // 3),
                    alpha=0.7,
                    color=COLOR_SCHEMES.get(metadata_template, COLOR_SCHEMES["default"])[0],
                )
                ax3.set_title("File Sizes")
                ax3.set_xlabel("Size (MB)")
                ax3.set_ylabel("Count")

            # Bottom right: Summary statistics
            ax4.axis("off")
            total_files = sum(len(files or []) for files in organized_structure.values())
            total_size_mb = sum(
                sum((obj.get("Size") or obj.get("size") or 0) for obj in (files or []))
                for files in organized_structure.values()
            ) / (
                1024 * 1024
            )

            summary_text = f"""
Package Summary

Total Files: {total_files}
Total Size: {total_size_mb:.1f} MB
Folders: {len(organized_structure)}
File Types: {len(normalized_file_types)}

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}
Template: {metadata_template}
            """
            ax4.text(
                0.1,
                0.5,
                summary_text,
                transform=ax4.transAxes,
                fontsize=12,
                verticalalignment="center",
                fontfamily="monospace",
            )

            plt.tight_layout()

            # Save dashboard to base64 string
            img_buffer = io.BytesIO()
            plt.savefig(img_buffer, format="png", dpi=150, bbox_inches="tight")
            img_buffer.seek(0)
            img_base64 = base64.b64encode(img_buffer.getvalue()).decode()
            plt.close()

            visualizations["package_dashboard"] = {
                "type": "dashboard",
                "title": "Package Overview Dashboard",
                "description": "Comprehensive overview of package contents and structure",
                "data": {
                    "total_files": total_files,
                    "total_size_mb": round(total_size_mb, 2),
                    "folder_count": len(organized_structure),
                    "file_type_count": len(normalized_file_types),
                },
                "image_base64": img_base64,
                "mime_type": "image/png",
            }

        return {
            "success": True,
            "visualizations": visualizations,
            "count": len(visualizations),
            "types": list(visualizations.keys()),
            "metadata": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "template_used": metadata_template,
                "color_scheme": COLOR_SCHEMES.get(metadata_template, COLOR_SCHEMES["default"]),
            },
            "visualization_dashboards": [
                {
                    "id": "package-overview",
                    "title": f"Package Overview - {package_name}",
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "widgets": [
                        {
                            "type": "stats",
                            "title": "Summary",
                            "stats": [
                                {"label": "Total Files", "value": total_files},
                                {"label": "Total Size (MB)", "value": round(total_size_mb, 2)},
                                {"label": "File Types", "value": len(normalized_file_types)},
                            ],
                        },
                        {
                            "type": "chart",
                            "chart": "pie",
                            "title": "File Type Distribution",
                            "data": visualizations.get("file_type_distribution", {}).get("data", {}),
                        },
                        {
                            "type": "chart",
                            "chart": "bar",
                            "title": "Folder Distribution",
                            "data": visualizations.get("folder_structure", {}).get("data", {}),
                        },
                    ],
                }
            ],
        }

    except Exception as e:
        logger.error(f"Failed to generate visualizations: {e}")
        return {
            "success": False,
            "error": f"Failed to generate visualizations: {str(e)}",
            "visualizations": {},
            "count": 0,
        }


def generate_multi_format_visualizations(
    package_name: str,
    organized_structure: Dict[str, List[Dict[str, Any]]],
    file_types: Dict[str, Any],
    metadata_template: str = "standard",
    viz_preferences: Optional[Dict[str, Any]] = None,
    **_extra: Any,
) -> Dict[str, Any]:
    """
    Generate multi-format visualizations using the intelligent selector.

    Args:
        package_name: Package identifier in namespace/name format.
        organized_structure: Organized file structure by folder.
        file_types: File type counts or descriptors.
        metadata_template: Template name used for color schemes (reserved).
        viz_preferences: Optional preferences (e.g. Perspective plugin selection).

    Returns:
        Visualization payload containing Quilt-ready configs and metadata.
    """
    try:
        result = MULTI_FORMAT_GENERATOR.generate(
            package_name=package_name,
            organized_structure=organized_structure,
            file_types=file_types,
            metadata_template=metadata_template,
            viz_preferences=viz_preferences,
        )
        result.setdefault("metadata", {})["metadata_template"] = metadata_template
        return result
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Failed to generate multi-format visualizations: %s", exc)
        return {
            "success": False,
            "error": f"Failed to generate multi-format visualizations: {exc}",
            "count": 0,
            "visualizations": {},
            "quilt_summarize_entries": [],
            "files": {},
            "metadata": {"package_name": package_name, "metadata_template": metadata_template},
        }


def create_quilt_summary_files(
    package_name: str,
    package_metadata: Dict[str, Any],
    organized_structure: Dict[str, List[Dict[str, Any]]],
    readme_content: str,
    source_info: Dict[str, Any],
    metadata_template: str = "standard",
) -> Dict[str, Any]:
    """
    Create all Quilt summary files for a package.

    Generates:
    - quilt_summarize.json: Machine-readable package summary
    - README.md: Human-readable documentation
    - Visualizations: Charts and graphs for package overview

    Args:
        package_name: Package name in namespace/name format
        package_metadata: Full package metadata
        organized_structure: Organized file structure
        readme_content: README.md content
        source_info: Data source information
        metadata_template: Metadata template used

    Returns:
        Dictionary with all generated files and content
    """
    try:
        # Generate quilt_summarize.json
        summary_json = generate_quilt_summarize_json(
            package_name=package_name,
            package_metadata=package_metadata,
            organized_structure=organized_structure,
            readme_content=readme_content,
            source_info=source_info,
            metadata_template=metadata_template,
        )

        # Extract file types for visualization
        file_types = {}
        for files in organized_structure.values():
            for obj in files:
                ext = Path(obj["Key"]).suffix.lower().lstrip(".")
                if ext:
                    file_types[ext] = file_types.get(ext, 0) + 1

        # Generate visualizations (multi-format + legacy PNG dashboards)
        multi_format_visualizations = generate_multi_format_visualizations(
            package_name=package_name,
            organized_structure=organized_structure,
            file_types=file_types,
            metadata_template=metadata_template,
        )
        legacy_visualizations = generate_package_visualizations(
            package_name=package_name,
            organized_structure=organized_structure,
            file_types=file_types,
            metadata_template=metadata_template,
        )

        # Create the complete summary package
        summary_package = {
            "quilt_summarize.json": summary_json,
            "README.md": readme_content,
            "visualizations": {
                "multi_format": multi_format_visualizations,
                "legacy": legacy_visualizations,
            },
            "quilt_summarize_entries": multi_format_visualizations.get("quilt_summarize_entries", []),
            "visualization_files": multi_format_visualizations.get("files", {}),
            "generation_info": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "generator": "quilt-mcp-server",
                "version": "1.0.0",
                "template_used": metadata_template,
                "files_generated": [
                    "quilt_summarize.json",
                    "README.md",
                    "visualizations",
                ],
            },
        }

        return {
            "success": True,
            "summary_package": summary_package,
            "files_generated": {
                "quilt_summarize.json": bool(summary_json),
                "README.md": bool(readme_content),
                "visualizations": multi_format_visualizations.get("success", False),
            },
            "visualization_count": multi_format_visualizations.get("count", 0),
            "next_steps": [
                "Add these files to your Quilt package",
                "Use quilt_summarize.json for automated processing",
                "Include visualizations in package documentation",
            ],
        }

    except Exception as e:
        logger.error(f"Failed to create Quilt summary files: {e}")
        return {
            "success": False,
            "error": f"Failed to create summary files: {str(e)}",
            "summary_package": {},
            "files_generated": {},
        }


def quilt_summary(action: str | None = None, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Quilt package summary and visualization generation with multi-format support.

    VISUALIZATION FORMAT SELECTION GUIDE:
    =====================================

    The tool intelligently selects the optimal visualization format based on your data:

    1. **IGV (Integrative Genomics Viewer)** - For genomic data
       - File types: .bam, .vcf, .bed, .gff, .gtf, .bigwig, .bw
       - Use for: Genome tracks, variant visualization, alignment viewing
       - Output: JSON config with track definitions

    2. **Perspective** - For large tabular data requiring exploration
       - File types: .csv, .tsv, .xlsx, .xls, .parquet, .jsonl
       - Use for: Interactive data grids, pivot tables, data analysis
       - Features: Filter, sort, group, aggregate, multiple view types
       - Handles: Up to 6MB compressed data

    3. **Vega-Lite** - For statistical and analytical charts
       - Best for: Statistical analysis, publication-quality charts
       - Chart types: Box plots, histograms, scatter (with regression), faceted plots
       - Use when: Need data binning, aggregation, or statistical transforms
       - Output: Declarative JSON specification

    4. **ECharts** - For interactive, animated charts
       - Best for: Interactive dashboards, hierarchical data, mobile
       - Chart types: Pie, tree, treemap, sunburst, graph, gauge, sankey
       - Use when: Need rich interactivity, animations, or custom styling
       - Output: ECharts option JSON

    5. **Voila** - For interactive Jupyter notebooks
       - Use for: Custom Python-driven dashboards
       - Features: Full Jupyter kernel, ipywidgets, live computation
       - Note: Requires separate notebook file in package

    AUTOMATIC SELECTION LOGIC:
    =========================

    File Extension → Format:
    - .bam, .vcf, .bed, .gff → IGV
    - .csv, .parquet (>100 rows) → Perspective
    - .csv (statistical analysis) → Vega-Lite
    - Hierarchical .json → ECharts
    - .ipynb → Voila

    Visualization Type → Format:
    - Bar chart → ECharts (for interactivity) or Vega-Lite (for simplicity)
    - Scatter plot → Vega-Lite (statistical features)
    - Pie chart → ECharts (better animations)
    - Box plot → Vega-Lite (native support)
    - Treemap/Sunburst → ECharts (only option)
    - Data grid → Perspective (only option)
    - Genome tracks → IGV (only option)

    Available actions:
    - create_files: Create all summary files (README, quilt_summarize.json, visualizations)
    - generate_viz: Generate visualizations (legacy, matplotlib PNGs)
    - generate_multi_viz: Generate multi-format visualizations (recommended)
    - generate_json: Generate quilt_summarize.json

    Examples:

    # Generate multi-format visualizations automatically
    result = quilt_summary(
        action="generate_multi_viz",
        params={
            "package_name": "genomics/study",
            "organized_structure": {
                "data": [
                    {"Key": "alignments.bam", "Size": 1024000},
                    {"Key": "variants.vcf", "Size": 512000},
                    {"Key": "results.csv", "Size": 8192}
                ]
            },
            "file_types": {"bam": 1, "vcf": 1, "csv": 1}
        }
    )

    # Result includes:
    # - IGV config for BAM/VCF files
    # - Perspective grid for CSV
    # - quilt_summarize.json entries
    # - Visualization files ready to add to the package
    """
    actions = {
        "create_files": create_quilt_summary_files,
        "generate_viz": generate_package_visualizations,
        "generate_multi_viz": generate_multi_format_visualizations,
        "generate_json": generate_quilt_summarize_json,
    }

    # Discovery mode
    if action is None:
        return {
            "success": True,
            "module": "quilt_summary",
            "actions": list(actions.keys()),
            "usage": "Call with action='<action_name>' to execute",
        }

    # Validate action
    if action not in actions:
        available = ", ".join(sorted(actions.keys()))
        return {
            "success": False,
            "error": f"Unknown action '{action}' for module 'quilt_summary'. Available actions: {available}",
        }

    # Dispatch
    try:
        func = actions[action]
        params = params or {}
        return func(**params)
    except TypeError as e:
        import inspect

        sig = inspect.signature(func)
        expected_params = list(sig.parameters.keys())
        return {
            "success": False,
            "error": f"Invalid parameters for action '{action}'. Expected: {expected_params}. Error: {str(e)}",
        }
    except Exception as e:
        if isinstance(e, dict) and not e.get("success"):
            return e
        return {
            "success": False,
            "error": f"Error executing action '{action}': {str(e)}",
        }

"""Package metadata and README generation helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def generate_readme_content(
    package_name: str,
    description: str,
    organized_structure: dict[str, list[dict[str, Any]]],
    total_size: int,
    source_info: dict[str, str],
    metadata_template: str,
) -> str:
    """Generate README.md content for S3-ingested packages."""
    total_files = sum(len(files) for files in organized_structure.values())
    total_size_mb = total_size / (1024 * 1024)

    file_types = set()
    for files in organized_structure.values():
        for file_info in files:
            ext = Path(file_info["Key"]).suffix.lower().lstrip(".")
            if ext:
                file_types.add(ext)

    readme_content = f"""# {package_name}

## Overview
{description or f"This package contains data sourced from {source_info.get('source_description', 'S3 bucket')}."}

## Contents

This package is organized into the following structure:

"""

    for folder, files in organized_structure.items():
        if folder:
            readme_content += f"### `{folder}/` ({len(files)} files)\n"
            if folder == "data/processed":
                readme_content += "Cleaned and processed data files ready for analysis.\n\n"
            elif folder == "data/raw":
                readme_content += "Original source data in raw format.\n\n"
            elif folder == "docs":
                readme_content += "Documentation, schemas, and supplementary materials.\n\n"
            elif folder == "metadata":
                readme_content += "Configuration files and package metadata.\n\n"
            else:
                readme_content += f"Files organized in {folder}.\n\n"

    readme_content += """## File Summary

| Folder | File Count | Primary Types |
|--------|------------|---------------|
"""

    for folder, files in organized_structure.items():
        if files:
            folder_types = set()
            for file_info in files[:5]:
                ext = Path(file_info["Key"]).suffix.lower().lstrip(".")
                if ext:
                    folder_types.add(ext)
            readme_content += f"| `{folder or 'root'}/` | {len(files)} | {', '.join(sorted(folder_types))} |\n"

    readme_content += f"""
## Usage

```python
# Browse the package using Quilt
# pkg = Package.browse("{package_name}")

# Access specific data files
"""

    for folder, files in organized_structure.items():
        if files and folder:
            sample_file = files[0]["Key"]
            logical_path = f"{folder}/{Path(sample_file).name}"
            readme_content += f"""
# Access files in {folder}/
data = pkg["{logical_path}"]()
"""

    readme_content += """```

## Package Metadata

"""

    readme_content += f"""- **Created**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC
- **Source**: {source_info.get('bucket', 'Unknown')}
- **Total Size**: {total_size_mb:.1f} MB
- **File Count**: {total_files}
- **File Types**: {', '.join(sorted(file_types))}
- **Organization**: Smart folder structure applied
"""

    if metadata_template == "ml":
        readme_content += """
## ML Model Information

This package appears to contain machine learning related data. Key considerations:

- **Training Data**: Located in `data/processed/`
- **Models**: Check for model files in appropriate folders
- **Documentation**: Review `docs/` for model specifications and methodology
"""
    elif metadata_template == "analytics":
        readme_content += """
## Analytics Information

This package contains analytics data. Key features:

- **Processed Data**: Analysis-ready data in `data/processed/`
- **Reports**: Documentation and analysis reports in `docs/`
- **Metrics**: Configuration and metadata in `metadata/`
"""

    readme_content += """
## Data Quality

- ✅ Files organized into logical structure
- ✅ Comprehensive metadata included
- ✅ Source attribution maintained
- ✅ Documentation generated

## Support

For questions about this package, refer to the metadata or contact the package maintainer.
"""
    return readme_content


def generate_package_metadata(
    package_name: str,
    source_info: dict[str, Any],
    organized_structure: dict[str, list[dict[str, Any]]],
    metadata_template: str,
    user_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate metadata for S3-ingested packages."""
    total_objects = sum(len(files) for files in organized_structure.values())
    total_size = sum(sum(obj.get("Size", 0) for obj in files) for files in organized_structure.values())

    file_types = set()
    for files in organized_structure.values():
        for obj in files:
            ext = Path(obj["Key"]).suffix.lower().lstrip(".")
            if ext:
                file_types.add(ext)

    metadata: dict[str, Any] = {
        "quilt": {
            "created_by": "mcp-s3-package-tool-enhanced",
            "creation_date": datetime.now(timezone.utc).isoformat() + "Z",
            "package_version": "1.0.0",
            "source": {
                "type": "s3_bucket",
                "bucket": source_info.get("bucket"),
                "prefix": source_info.get("prefix", ""),
                "total_objects": total_objects,
                "total_size_bytes": total_size,
            },
            "organization": {
                "structure_type": "logical_hierarchy",
                "auto_organized": True,
                "folder_mapping": {
                    folder: f"Contains {len(files)} files" for folder, files in organized_structure.items() if files
                },
            },
            "data_profile": {
                "file_types": sorted(list(file_types)),
                "total_files": total_objects,
                "size_mb": round(total_size / (1024 * 1024), 2),
            },
        }
    }

    if metadata_template == "ml":
        metadata["ml"] = {"type": "machine_learning", "data_stage": "processed", "model_ready": True}
    elif metadata_template == "analytics":
        metadata["analytics"] = {
            "type": "business_analytics",
            "analysis_ready": True,
            "report_generated": True,
        }

    if user_metadata:
        metadata["user_metadata"] = user_metadata

    return metadata

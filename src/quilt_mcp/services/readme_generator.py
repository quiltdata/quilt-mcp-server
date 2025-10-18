"""README and quilt_summarize.json generation for packages.

This module provides functions to automatically generate README.md and quilt_summarize.json
files for Quilt packages based on package metadata, files, and user-provided information.

Per user requirements:
- README contents should be added as actual files in the package (not package metadata)
- Every package should include a quilt_summarize.json file containing at least the README
  and, if relevant, a visualization
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional


def generate_package_readme(
    package_name: str,
    s3_uris: List[str],
    metadata: Optional[Dict[str, Any]] = None,
    registry: Optional[str] = None,
    organized_structure: Optional[Dict[str, List[Dict[str, Any]]]] = None,
) -> str:
    """Generate a comprehensive README.md for a package.

    Args:
        package_name: Name of the package (namespace/name format)
        s3_uris: List of S3 URIs included in the package
        metadata: Package metadata dictionary
        registry: Target registry URL
        organized_structure: Organized file structure (if using smart organization)

    Returns:
        README content as markdown string
    """
    metadata = metadata or {}
    description = metadata.get("description", "")

    # Extract namespace and name
    parts = package_name.split("/", 1)
    namespace = parts[0] if len(parts) > 1 else ""
    name = parts[1] if len(parts) > 1 else package_name

    readme_parts = []

    # Header
    readme_parts.append(f"# {package_name}")
    readme_parts.append("")

    # Description
    if description:
        readme_parts.append("## Overview")
        readme_parts.append("")
        readme_parts.append(description)
        readme_parts.append("")

    # Package Information
    readme_parts.append("## Package Information")
    readme_parts.append("")
    readme_parts.append(f"- **Package Name:** `{package_name}`")
    if namespace:
        readme_parts.append(f"- **Namespace:** `{namespace}`")
    if registry:
        readme_parts.append(f"- **Registry:** `{registry}`")

    # Add other metadata fields
    metadata_fields = {
        "version": "Version",
        "license": "License",
        "author": "Author",
        "contact": "Contact",
        "homepage": "Homepage",
        "doi": "DOI",
    }

    for key, label in metadata_fields.items():
        if key in metadata and metadata[key]:
            readme_parts.append(f"- **{label}:** {metadata[key]}")

    readme_parts.append("")

    # File Contents
    readme_parts.append("## Contents")
    readme_parts.append("")

    if organized_structure:
        # Use organized structure if available
        total_files = sum(len(objects) for objects in organized_structure.values())
        readme_parts.append(f"This package contains {total_files} file(s) organized into folders:")
        readme_parts.append("")

        for folder, objects in sorted(organized_structure.items()):
            folder_name = folder if folder else "root"
            readme_parts.append(f"### {folder_name}/")
            readme_parts.append("")
            readme_parts.append(f"- {len(objects)} file(s)")
            readme_parts.append("")
    else:
        # Simple file listing
        readme_parts.append(f"This package contains {len(s3_uris)} file(s):")
        readme_parts.append("")

        # List first few files
        display_limit = 10
        for i, uri in enumerate(s3_uris[:display_limit]):
            # Extract filename from S3 URI
            filename = uri.split("/")[-1]
            readme_parts.append(f"- `{filename}`")

        if len(s3_uris) > display_limit:
            readme_parts.append(f"- ... and {len(s3_uris) - display_limit} more files")
        readme_parts.append("")

    # Usage Examples
    readme_parts.append("## Usage")
    readme_parts.append("")
    readme_parts.append("### Installation")
    readme_parts.append("")
    readme_parts.append("```bash")
    readme_parts.append("pip install quilt3")
    readme_parts.append("```")
    readme_parts.append("")

    readme_parts.append("### Loading the Package")
    readme_parts.append("")
    readme_parts.append("```python")
    readme_parts.append("import quilt3 as q3")
    readme_parts.append("")
    readme_parts.append("# Browse the package")
    if registry:
        readme_parts.append(f"pkg = q3.Package.browse('{package_name}', registry='{registry}')")
    else:
        readme_parts.append(f"pkg = q3.Package.browse('{package_name}')")
    readme_parts.append("")
    readme_parts.append("# List package contents")
    readme_parts.append("for key in pkg:")
    readme_parts.append("    print(f'{key}: {pkg[key]}')")
    readme_parts.append("```")
    readme_parts.append("")

    # Additional metadata sections
    if "tags" in metadata and metadata["tags"]:
        readme_parts.append("## Tags")
        readme_parts.append("")
        for tag in metadata["tags"]:
            readme_parts.append(f"- {tag}")
        readme_parts.append("")

    # Citation
    if "doi" in metadata or "citation" in metadata:
        readme_parts.append("## Citation")
        readme_parts.append("")
        if "citation" in metadata:
            readme_parts.append(metadata["citation"])
            readme_parts.append("")
        elif "doi" in metadata:
            readme_parts.append(f"DOI: {metadata['doi']}")
            readme_parts.append("")

    # Footer
    readme_parts.append("---")
    readme_parts.append("")
    readme_parts.append(f"*Package created: {datetime.now().strftime('%Y-%m-%d')}*")
    readme_parts.append("")
    readme_parts.append("Generated automatically by Quilt MCP Server")

    return "\n".join(readme_parts)


def generate_quilt_summarize(
    package_name: str,
    readme_content: str,
    metadata: Optional[Dict[str, Any]] = None,
    registry: Optional[str] = None,
    s3_uris: Optional[List[str]] = None,
) -> str:
    """Generate a quilt_summarize.json file for a package.

    This follows the Quilt summarization schema and includes:
    - Package summary
    - Full README content
    - Package metadata
    - Optional visualizations (images array)

    Args:
        package_name: Name of the package
        readme_content: Full README.md content
        metadata: Package metadata dictionary
        registry: Target registry URL
        s3_uris: List of S3 URIs in the package (for file count)

    Returns:
        quilt_summarize.json content as JSON string
    """
    metadata = metadata or {}

    # Extract summary from description or generate one
    description = metadata.get("description", "")
    summary = description[:200] + "..." if len(description) > 200 else description

    if not summary:
        summary = f"Quilt package: {package_name}"

    summary_data = {
        "type": "package",
        "summary": summary,
        "readme": readme_content,
        "metadata": {
            "package_name": package_name,
            "created": datetime.now().isoformat(),
            "registry": registry or "default",
            "file_count": len(s3_uris) if s3_uris else 0,
        },
        "images": [],  # Placeholder for future visualization support
    }

    # Add user-provided metadata
    if metadata:
        # Copy relevant metadata fields
        for key in ["version", "license", "author", "tags", "doi", "homepage"]:
            if key in metadata:
                summary_data["metadata"][key] = metadata[key]

        # Add all other metadata fields
        for key, value in metadata.items():
            if key not in summary_data["metadata"] and key not in ["description"]:
                summary_data["metadata"][key] = value

    return json.dumps(summary_data, indent=2, ensure_ascii=False)

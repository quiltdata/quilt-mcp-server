"""Package structure validation utilities."""

from typing import Dict, List, Any, Tuple
import re
from pathlib import Path


RECOMMENDED_FOLDERS = {
    "data/processed": "Cleaned and processed data files",
    "data/raw": "Original source data",
    "data/media": "Images, videos, and media files",
    "docs": "Documentation and analysis",
    "docs/schemas": "Data schemas and specifications",
    "metadata": "Configuration and package metadata",
}

DISCOURAGED_PATTERNS = ["temp", "tmp", "backup", "old", "test", "_test", "cache"]


def validate_package_structure(
    organized_structure: Dict[str, List[Dict[str, Any]]],
) -> Tuple[bool, List[str], List[str]]:
    """
    Validate package structure against Quilt best practices.

    Args:
        organized_structure: Dictionary mapping folders to file lists

    Returns:
        Tuple of (is_valid, warnings, recommendations)
    """
    warnings = []
    recommendations = []
    is_valid = True

    # Check for empty structure
    if not organized_structure or all(not files for files in organized_structure.values()):
        warnings.append("Package structure is empty")
        is_valid = False
        return is_valid, warnings, recommendations

    # Validate folder names
    for folder in organized_structure.keys():
        if folder:  # Skip root folder
            folder_warnings, folder_recs = validate_folder_structure(folder)
            warnings.extend(folder_warnings)
            recommendations.extend(folder_recs)

    # Check for recommended structure
    has_data_folder = any(folder.startswith("data/") for folder in organized_structure.keys())
    if not has_data_folder:
        recommendations.append("Consider organizing data files into 'data/' subfolder structure")

    has_docs = any(folder.startswith("docs") for folder in organized_structure.keys())
    if not has_docs and len(organized_structure) > 1:
        recommendations.append("Consider adding a 'docs/' folder for documentation")

    # Check for README
    readme_found = False
    for folder, files in organized_structure.items():
        for file_info in files:
            if "readme" in Path(file_info["Key"]).name.lower():
                readme_found = True
                break

    if not readme_found:
        recommendations.append("Consider adding a README.md file for package documentation")

    # Check file distribution
    total_files = sum(len(files) for files in organized_structure.values())
    if total_files > 100:
        max_files_in_folder = max(len(files) for files in organized_structure.values())
        if max_files_in_folder > 50:
            warnings.append(
                f"Large number of files ({max_files_in_folder}) in single folder - consider further organization"
            )

    return is_valid, warnings, recommendations


def validate_folder_structure(folder_path: str) -> Tuple[List[str], List[str]]:
    """
    Validate individual folder structure.

    Args:
        folder_path: Path of the folder to validate

    Returns:
        Tuple of (warnings, recommendations)
    """
    warnings = []
    recommendations = []

    # Check for discouraged patterns
    folder_lower = folder_path.lower()
    for pattern in DISCOURAGED_PATTERNS:
        if pattern in folder_lower:
            warnings.append(f"Folder '{folder_path}' contains discouraged pattern '{pattern}'")

    # Check folder depth
    parts = folder_path.split("/")
    if len(parts) > 4:
        warnings.append(f"Folder '{folder_path}' has deep nesting ({len(parts)} levels) - consider flattening")

    # Check for special characters
    if re.search(r"[^a-zA-Z0-9/_-]", folder_path):
        warnings.append(
            f"Folder '{folder_path}' contains special characters - use only alphanumeric, dash, and underscore"
        )

    # Suggest improvements
    if folder_path not in RECOMMENDED_FOLDERS:
        # Find closest recommended folder
        for recommended in RECOMMENDED_FOLDERS:
            if any(part in folder_lower for part in recommended.split("/")):
                recommendations.append(f"Consider using recommended folder '{recommended}' instead of '{folder_path}'")
                break

    return warnings, recommendations


def suggest_folder_organization(file_objects: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """
    Suggest optimal folder organization for a list of files.

    Args:
        file_objects: List of file objects with 'Key' field

    Returns:
        Dictionary mapping suggested folders to file keys
    """
    suggestions = {}

    for obj in file_objects:
        key = obj["Key"]
        file_path = Path(key)
        file_ext = file_path.suffix.lower().lstrip(".")
        file_name = file_path.name.lower()

        # Determine suggested folder
        suggested_folder = "data/misc"  # default

        # Data files
        if file_ext in ["csv", "parquet", "json", "tsv", "jsonl"]:
            suggested_folder = "data/processed"
        elif file_ext in ["log", "txt", "raw"]:
            suggested_folder = "data/raw"
        elif file_ext in ["png", "jpg", "jpeg", "mp4", "avi", "gif"]:
            suggested_folder = "data/media"

        # Documentation
        elif file_ext in ["md", "rst", "pdf", "docx"] or "readme" in file_name:
            suggested_folder = "docs"
        elif "schema" in file_name or file_ext == "schema":
            suggested_folder = "docs/schemas"

        # Configuration
        elif file_ext in ["yml", "yaml", "toml", "ini", "conf"] or "config" in file_name:
            suggested_folder = "metadata"

        if suggested_folder not in suggestions:
            suggestions[suggested_folder] = []
        suggestions[suggested_folder].append(key)

    return suggestions


def validate_file_naming(file_path: str) -> Tuple[bool, List[str]]:
    """
    Validate file naming conventions.

    Args:
        file_path: Path of the file to validate

    Returns:
        Tuple of (is_valid, warnings)
    """
    warnings = []
    is_valid = True

    file_name = Path(file_path).name

    # Check for spaces in filename
    if " " in file_name:
        warnings.append(f"File '{file_name}' contains spaces - consider using underscores or hyphens")
        is_valid = False

    # Check for special characters
    if re.search(r"[^a-zA-Z0-9._-]", file_name):
        warnings.append(f"File '{file_name}' contains special characters")
        is_valid = False

    # Check for very long names
    if len(file_name) > 100:
        warnings.append(f"File '{file_name}' has very long name ({len(file_name)} chars)")

    # Check for common anti-patterns
    if file_name.startswith("."):
        warnings.append(f"Hidden file '{file_name}' - consider if this should be included in package")

    return is_valid, warnings

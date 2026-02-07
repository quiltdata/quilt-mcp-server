"""Metadata validation utilities for Quilt packages."""

from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime, timezone
import re


REQUIRED_QUILT_FIELDS = [
    "quilt.created_by",
    "quilt.creation_date",
    "quilt.source.type",
    "quilt.source.bucket",
]

RECOMMENDED_FIELDS = [
    "quilt.package_version",
    "quilt.data_profile.file_types",
    "quilt.data_profile.total_files",
    "user_metadata.description",
    "user_metadata.tags",
]


def validate_metadata_compliance(metadata: Dict[str, Any]) -> Tuple[bool, List[str], List[str]]:
    """
    Validate metadata against Quilt compliance standards.

    Args:
        metadata: Package metadata dictionary

    Returns:
        Tuple of (is_compliant, errors, warnings)
    """
    errors = []
    warnings = []
    is_compliant = True

    # Check required fields
    for field_path in REQUIRED_QUILT_FIELDS:
        if not _get_nested_value(metadata, field_path):
            errors.append(f"Missing required field: {field_path}")
            is_compliant = False

    # Check recommended fields
    for field_path in RECOMMENDED_FIELDS:
        if not _get_nested_value(metadata, field_path):
            warnings.append(f"Missing recommended field: {field_path}")

    # Validate specific field formats
    creation_date = _get_nested_value(metadata, "quilt.creation_date")
    if creation_date:
        if not _validate_iso_date(creation_date):
            errors.append("Invalid creation_date format - should be ISO 8601")
            is_compliant = False

    # Validate source type
    source_type = _get_nested_value(metadata, "quilt.source.type")
    if source_type and source_type not in [
        "s3_bucket",
        "local_files",
        "database",
        "api",
    ]:
        warnings.append(f"Unusual source type: {source_type}")

    # Check for empty or invalid values
    total_files = _get_nested_value(metadata, "quilt.data_profile.total_files")
    if total_files is not None and (not isinstance(total_files, int) or total_files <= 0):
        errors.append("total_files must be a positive integer")
        is_compliant = False

    return is_compliant, errors, warnings


def validate_quilt_metadata(metadata: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate core Quilt metadata structure.

    Args:
        metadata: Metadata dictionary to validate

    Returns:
        Tuple of (is_valid, issues)
    """
    issues = []
    is_valid = True

    # Check top-level structure
    if "quilt" not in metadata:
        issues.append("Missing 'quilt' top-level section")
        is_valid = False
        return is_valid, issues

    quilt_meta = metadata["quilt"]

    # Validate creation metadata
    if "created_by" not in quilt_meta:
        issues.append("Missing 'created_by' field")
        is_valid = False

    if "creation_date" not in quilt_meta:
        issues.append("Missing 'creation_date' field")
        is_valid = False
    elif not _validate_iso_date(quilt_meta["creation_date"]):
        issues.append("Invalid 'creation_date' format")
        is_valid = False

    # Validate source information
    if "source" not in quilt_meta:
        issues.append("Missing 'source' section")
        is_valid = False
    else:
        source = quilt_meta["source"]
        if "type" not in source:
            issues.append("Missing source 'type'")
            is_valid = False

        if source.get("type") == "s3_bucket" and "bucket" not in source:
            issues.append("Missing source 'bucket' for S3 source type")
            is_valid = False

    # Validate data profile if present
    if "data_profile" in quilt_meta:
        profile = quilt_meta["data_profile"]

        if "total_files" in profile and not isinstance(profile["total_files"], int):
            issues.append("'total_files' must be an integer")
            is_valid = False

        if "file_types" in profile and not isinstance(profile["file_types"], list):
            issues.append("'file_types' must be a list")
            is_valid = False

    return is_valid, issues


def validate_user_metadata(metadata: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate user-provided metadata.

    Args:
        metadata: User metadata dictionary

    Returns:
        Tuple of (is_valid, recommendations)
    """
    recommendations = []
    is_valid = True

    if not metadata:
        recommendations.append("Consider adding user metadata with description and tags")
        return is_valid, recommendations

    # Check for description
    if "description" not in metadata:
        recommendations.append("Consider adding a description field")
    elif len(metadata["description"]) < 10:
        recommendations.append("Description is very short - consider adding more detail")

    # Check for tags
    if "tags" not in metadata:
        recommendations.append("Consider adding tags for better discoverability")
    elif not isinstance(metadata["tags"], list):
        recommendations.append("Tags should be a list of strings")
    elif len(metadata["tags"]) == 0:
        recommendations.append("Tags list is empty - consider adding relevant tags")

    # Check for contact information
    if "contact" not in metadata and "author" not in metadata:
        recommendations.append("Consider adding contact or author information")

    # Validate tag format
    if "tags" in metadata and isinstance(metadata["tags"], list):
        for tag in metadata["tags"]:
            if not isinstance(tag, str):
                recommendations.append("All tags should be strings")
                break
            elif len(tag) < 2:
                recommendations.append(f"Tag '{tag}' is very short")

    return is_valid, recommendations


def enhance_metadata_quality(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enhance metadata with quality improvements.

    Args:
        metadata: Original metadata dictionary

    Returns:
        Enhanced metadata dictionary
    """
    enhanced = metadata.copy()

    # Ensure quilt section exists
    if "quilt" not in enhanced:
        enhanced["quilt"] = {}

    # Add quality indicators
    enhancement_timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    enhanced["quilt"]["metadata_quality"] = {
        "version": "1.0",
        "enhanced_by": "mcp-metadata-validator",
        "enhancement_date": enhancement_timestamp,
    }

    # Add missing recommended fields with defaults
    if "package_version" not in enhanced["quilt"]:
        enhanced["quilt"]["package_version"] = "1.0.0"

    # Normalize file types
    if "data_profile" in enhanced["quilt"] and "file_types" in enhanced["quilt"]["data_profile"]:
        file_types = enhanced["quilt"]["data_profile"]["file_types"]
        if isinstance(file_types, list):
            # Remove duplicates and sort
            enhanced["quilt"]["data_profile"]["file_types"] = sorted(list(set(file_types)))

    return enhanced


def _get_nested_value(data: Dict[str, Any], path: str) -> Optional[Any]:
    """Get value from nested dictionary using dot notation."""
    keys = path.split(".")
    current = data

    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return None

    return current


def _validate_iso_date(date_string: str) -> bool:
    """Validate ISO 8601 date format."""
    if not isinstance(date_string, str):
        return False

    try:
        # Try parsing ISO format
        datetime.fromisoformat(date_string.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def suggest_metadata_improvements(metadata: Dict[str, Any]) -> List[str]:
    """
    Suggest improvements for metadata quality.

    Args:
        metadata: Current metadata dictionary

    Returns:
        List of improvement suggestions
    """
    suggestions = []

    # Check completeness
    is_compliant, errors, warnings = validate_metadata_compliance(metadata)

    if errors:
        suggestions.extend([f"Fix error: {error}" for error in errors])

    if warnings:
        suggestions.extend([f"Consider: {warning}" for warning in warnings])

    # Check user metadata quality
    user_meta = metadata.get("user_metadata", {})
    is_valid, user_recommendations = validate_user_metadata(user_meta)
    suggestions.extend(user_recommendations)

    # Check for searchability
    if not any(field in metadata for field in ["user_metadata.tags", "user_metadata.keywords"]):
        suggestions.append("Add tags or keywords to improve package discoverability")

    return suggestions

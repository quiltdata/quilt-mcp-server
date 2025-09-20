"""Package naming validation and suggestion utilities."""

import re
from datetime import datetime, timezone
from typing import List, Tuple, Optional, Dict, Any


# Package naming patterns
VALID_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9\-_]*[a-zA-Z0-9])?$")
NAMESPACE_SUGGESTIONS = {
    "ml": ["ai", "models", "training", "neural", "tensorflow", "pytorch"],
    "analytics": ["reports", "metrics", "dashboard", "bi", "insights"],
    "data": ["dataset", "warehouse", "lake", "raw", "processed"],
    "research": ["experiment", "study", "analysis", "paper"],
    "finance": ["trading", "risk", "portfolio", "market"],
    "health": ["medical", "clinical", "genomic", "pharma"],
    "geo": ["maps", "spatial", "location", "gis"],
    "text": ["nlp", "corpus", "language", "documents"],
}


def validate_package_naming(package_name: str) -> Tuple[bool, List[str], List[str]]:
    """
    Validate package naming according to Quilt conventions.

    Args:
        package_name: Package name in namespace/name format

    Returns:
        Tuple of (is_valid, errors, suggestions)
    """
    errors = []
    suggestions = []
    is_valid = True

    # Check basic format
    if not package_name or "/" not in package_name:
        errors.append("Package name must be in 'namespace/name' format")
        is_valid = False
        return is_valid, errors, suggestions

    parts = package_name.split("/")
    if len(parts) != 2:
        errors.append("Package name must have exactly one '/' separator")
        is_valid = False
        return is_valid, errors, suggestions

    namespace, name = parts

    # Validate namespace
    namespace_valid, namespace_errors, namespace_suggestions = _validate_name_component(namespace, "namespace")
    if not namespace_valid:
        is_valid = False
        errors.extend(namespace_errors)
    suggestions.extend(namespace_suggestions)

    # Validate package name
    name_valid, name_errors, name_suggestions = _validate_name_component(name, "package name")
    if not name_valid:
        is_valid = False
        errors.extend(name_errors)
    suggestions.extend(name_suggestions)

    # Check for naming best practices
    if is_valid:
        practice_suggestions = _check_naming_practices(namespace, name)
        suggestions.extend(practice_suggestions)

    return is_valid, errors, suggestions


def suggest_package_name(
    source_bucket: str,
    source_prefix: str = "",
    description: str = "",
    suggested_namespace: Optional[str] = None,
) -> List[str]:
    """
    Suggest package names based on source information.

    Args:
        source_bucket: Source S3 bucket name
        source_prefix: Source S3 prefix
        description: Package description
        suggested_namespace: Preferred namespace

    Returns:
        List of suggested package names
    """
    suggestions = []

    # Extract potential namespace from bucket/prefix
    if not suggested_namespace:
        suggested_namespace = _extract_namespace_from_source(source_bucket, source_prefix)

    # Extract potential package name from source
    potential_names = _extract_package_names_from_source(source_bucket, source_prefix, description)

    # Generate combinations
    for name in potential_names:
        clean_namespace = _clean_name_component(suggested_namespace)
        clean_name = _clean_name_component(name)

        if clean_namespace and clean_name:
            suggestions.append(f"{clean_namespace}/{clean_name}")

    # Add some generic suggestions if no good ones found
    if not suggestions:
        clean_namespace = _clean_name_component(suggested_namespace or "data")
        timestamp_suffix = _generate_timestamp_suffix()
        suggestions.extend(
            [
                f"{clean_namespace}/dataset-{timestamp_suffix}",
                f"{clean_namespace}/package-{timestamp_suffix}",
                f"{clean_namespace}/data-{timestamp_suffix}",
            ]
        )

    return suggestions[:5]  # Return top 5 suggestions


def _validate_name_component(component: str, component_type: str) -> Tuple[bool, List[str], List[str]]:
    """Validate individual name component (namespace or package name)."""
    errors = []
    suggestions = []
    is_valid = True

    if not component:
        errors.append(f"{component_type} cannot be empty")
        is_valid = False
        return is_valid, errors, suggestions

    # Check length
    if len(component) < 2:
        errors.append(f"{component_type} must be at least 2 characters long")
        is_valid = False
    elif len(component) > 50:
        errors.append(f"{component_type} must be 50 characters or less")
        is_valid = False

    # Check pattern
    if not VALID_NAME_PATTERN.match(component):
        errors.append(
            f"{component_type} contains invalid characters. Use only letters, numbers, hyphens, and underscores"
        )
        is_valid = False

    # Check for anti-patterns
    if component.startswith("-") or component.startswith("_"):
        errors.append(f"{component_type} cannot start with dash or underscore")
        is_valid = False

    if component.endswith("-") or component.endswith("_"):
        errors.append(f"{component_type} cannot end with dash or underscore")
        is_valid = False

    # Check for discouraged patterns
    discouraged_patterns = ["test", "temp", "tmp", "old", "backup", "copy"]
    component_lower = component.lower()
    for pattern in discouraged_patterns:
        if pattern in component_lower:
            suggestions.append(f"Consider avoiding '{pattern}' in {component_type}")

    return is_valid, errors, suggestions


def _check_naming_practices(namespace: str, name: str) -> List[str]:
    """Check naming against best practices."""
    suggestions = []

    # Check for descriptive names
    if len(name) < 5:
        suggestions.append("Consider using a more descriptive package name")

    # Check for version in name (discouraged)
    if re.search(r"v\d+|version|ver\d+", name.lower()):
        suggestions.append("Avoid version numbers in package name - use Quilt's versioning instead")

    # Check for date in name (sometimes discouraged)
    if re.search(r"\d{4}[-_]\d{2}[-_]\d{2}|\d{8}", name):
        suggestions.append("Consider whether date in name is necessary - packages are automatically timestamped")

    # Suggest namespace improvements
    namespace_suggestions = _suggest_namespace_improvements(namespace)
    suggestions.extend(namespace_suggestions)

    return suggestions


def _suggest_namespace_improvements(namespace: str) -> List[str]:
    """Suggest namespace improvements based on common patterns."""
    suggestions = []

    namespace_lower = namespace.lower()

    # Check if namespace could be more specific
    if namespace_lower in ["data", "dataset", "package"]:
        suggestions.append("Consider using a more specific namespace (e.g., 'analytics', 'ml', 'finance')")

    # Suggest better namespaces based on content
    for suggested_ns, keywords in NAMESPACE_SUGGESTIONS.items():
        if any(keyword in namespace_lower for keyword in keywords):
            if namespace_lower != suggested_ns:
                suggestions.append(f"Consider using '{suggested_ns}' namespace for this type of data")
            break

    return suggestions


def _extract_namespace_from_source(bucket: str, prefix: str) -> str:
    """Extract potential namespace from source bucket and prefix."""
    # Try to extract from bucket name
    bucket_parts = bucket.lower().replace("-", "_").split("_")

    # Look for recognizable patterns
    for part in bucket_parts:
        for namespace, keywords in NAMESPACE_SUGGESTIONS.items():
            if part in keywords or part == namespace:
                return namespace

    # Try prefix
    if prefix:
        prefix_parts = prefix.lower().replace("/", "_").replace("-", "_").split("_")
        for part in prefix_parts:
            for namespace, keywords in NAMESPACE_SUGGESTIONS.items():
                if part in keywords or part == namespace:
                    return namespace

    # Default fallback
    return "data"


def _extract_package_names_from_source(bucket: str, prefix: str, description: str) -> List[str]:
    """Extract potential package names from source information."""
    candidates = []

    # From bucket name
    bucket_clean = bucket.lower().replace("-", "_")
    bucket_parts = [part for part in bucket_clean.split("_") if len(part) > 2]
    candidates.extend(bucket_parts[-2:])  # Take last 2 meaningful parts

    # From prefix
    if prefix:
        prefix_parts = [part for part in prefix.replace("/", "_").replace("-", "_").split("_") if len(part) > 2]
        candidates.extend(prefix_parts[-2:])

    # From description
    if description:
        desc_words = re.findall(r"\b\w{3,}\b", description.lower())
        candidates.extend(desc_words[:3])

    # Clean and deduplicate
    cleaned_candidates = []
    for candidate in candidates:
        cleaned = _clean_name_component(candidate)
        if cleaned and cleaned not in cleaned_candidates:
            cleaned_candidates.append(cleaned)

    return cleaned_candidates[:5]


def _clean_name_component(component: str) -> str:
    """Clean a component to make it a valid name."""
    if not component:
        return ""

    # Convert to lowercase and replace invalid characters
    cleaned = re.sub(r"[^a-zA-Z0-9\-_]", "-", component.lower())

    # Remove multiple consecutive separators
    cleaned = re.sub(r"[-_]+", "-", cleaned)

    # Remove leading/trailing separators
    cleaned = cleaned.strip("-_")

    # Ensure it meets minimum requirements
    if len(cleaned) < 2:
        return ""

    if not VALID_NAME_PATTERN.match(cleaned):
        return ""

    return cleaned


def _generate_timestamp_suffix() -> str:
    """Generate a timestamp suffix for generic names."""
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def validate_and_suggest_name(
    package_name: str,
    source_bucket: str,
    source_prefix: str = "",
    description: str = "",
) -> Dict[str, Any]:
    """
    Comprehensive package name validation and suggestions.

    Args:
        package_name: Proposed package name
        source_bucket: Source S3 bucket
        source_prefix: Source S3 prefix
        description: Package description

    Returns:
        Dictionary with validation results and suggestions
    """
    # Validate current name
    is_valid, errors, suggestions = validate_package_naming(package_name)

    # Generate alternative suggestions
    alternatives = suggest_package_name(source_bucket, source_prefix, description)

    return {
        "is_valid": is_valid,
        "errors": errors,
        "suggestions": suggestions,
        "alternatives": alternatives,
        "recommended": alternatives[0] if alternatives else None,
    }

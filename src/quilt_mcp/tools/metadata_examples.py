"""Metadata Examples and Usage Guidance.

This module provides the metadata_template_create tool for simplified
metadata creation using templates.

Note: show_metadata_examples and fix_metadata_validation_issues have been
moved to resources/metadata.py as they are now resources, not tools.
"""

from typing import Dict, Any
from .metadata_templates import metadata_template_get


def metadata_template_create(
    template_name: str = "standard",
    description: str = "",
    custom_fields: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """Create metadata using a template with custom fields - simplified interface.

    Args:
        template_name: Template to use ('standard', 'genomics', 'ml', 'research', 'analytics')
        description: Package description (added to metadata)
        custom_fields: Additional fields to merge with template

    Returns:
        Complete metadata dictionary ready for package creation

    Examples:
        Basic usage:
        metadata = metadata_template_create("genomics", "Human genome study", {"organism": "human"})

        Then use in package creation:
        create_package("genomics/study1", ["s3://bucket/data.vcf"], metadata=metadata)
    """
    try:
        # Get base template
        metadata = metadata_template_get(template_name, custom_fields or {})

        # Add description if provided
        if description:
            metadata["description"] = description

        return {
            "success": True,
            "metadata": metadata,
            "template_used": template_name,
            "field_count": len(metadata),
            "usage_tip": "Use this metadata in create_package() or create_package()",
            "example_usage": f'create_package("team/package", ["s3://bucket/file.csv"], metadata={str(metadata)})',
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to create metadata from template: {str(e)}",
            "template_requested": template_name,
            "suggested_actions": [
                "Try: list_metadata_templates() to see available templates",
                "Use 'standard' template as fallback",
                "Check custom_fields format",
            ],
        }

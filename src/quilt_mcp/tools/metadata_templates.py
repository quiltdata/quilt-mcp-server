"""Metadata templates for common package types.

This module provides pre-defined metadata templates for common data package
types, making it easy for users to create properly structured metadata.
"""

from typing import Optional, Dict, Any
from typing import Dict, Any, List
from datetime import datetime, timezone


METADATA_TEMPLATES = {
    "standard": {
        "description": "Standard data package",
        "created_by": "quilt-mcp-server",
        "creation_date": datetime.now(timezone.utc).isoformat(),
        "package_type": "data",
        "version": "1.0.0",
    },
    "genomics": {
        "description": "Genomics data package",
        "created_by": "quilt-mcp-server",
        "creation_date": datetime.now(timezone.utc).isoformat(),
        "package_type": "genomics",
        "data_type": "genomics",
        "organism": "unknown",
        "genome_build": "unknown",
        "sequencing_platform": "unknown",
        "analysis_type": "unknown",
        "version": "1.0.0",
    },
    "ml": {
        "description": "Machine learning dataset",
        "created_by": "quilt-mcp-server",
        "creation_date": datetime.now(timezone.utc).isoformat(),
        "package_type": "ml_dataset",
        "data_type": "machine_learning",
        "dataset_stage": "processed",
        "model_ready": True,
        "features_count": "unknown",
        "target_variable": "unknown",
        "version": "1.0.0",
    },
    "research": {
        "description": "Research data package",
        "created_by": "quilt-mcp-server",
        "creation_date": datetime.now(timezone.utc).isoformat(),
        "package_type": "research",
        "data_type": "research",
        "study_type": "unknown",
        "research_domain": "unknown",
        "publication_status": "unpublished",
        "version": "1.0.0",
    },
    "analytics": {
        "description": "Business analytics data package",
        "created_by": "quilt-mcp-server",
        "creation_date": datetime.now(timezone.utc).isoformat(),
        "package_type": "analytics",
        "data_type": "business_analytics",
        "analysis_period": "unknown",
        "business_unit": "unknown",
        "metrics_included": [],
        "version": "1.0.0",
    },
}


def get_metadata_template(template_name: str, custom_fields: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Get a metadata template with optional custom fields.

    Args:
        template_name: Name of the template ('standard', 'genomics', 'ml', 'research', 'analytics')
        custom_fields: Optional custom fields to merge with template

    Returns:
        Metadata dictionary with template fields and custom fields
    """
    if template_name not in METADATA_TEMPLATES:
        template_name = "standard"

    # Start with template
    metadata = METADATA_TEMPLATES[template_name].copy()

    # Update creation date to current time
    metadata["creation_date"] = datetime.now(timezone.utc).isoformat()

    # Merge custom fields
    if custom_fields:
        metadata.update(custom_fields)

    return metadata


def list_metadata_templates() -> Dict[str, Any]:
    """
    List available metadata templates with descriptions.

    Returns:
        Dictionary with template information and usage examples
    """
    templates_info = {}

    for template_name, template_data in METADATA_TEMPLATES.items():
        templates_info[template_name] = {
            "description": template_data.get("description", ""),
            "package_type": template_data.get("package_type", ""),
            "data_type": template_data.get("data_type", ""),
            "fields": list(template_data.keys()),
            "example_usage": f'get_metadata_template("{template_name}", {{"custom_field": "value"}})',
        }

    return {
        "available_templates": templates_info,
        "usage_examples": [
            'metadata = get_metadata_template("genomics", {"organism": "human", "genome_build": "GRCh38"})',
            'metadata = get_metadata_template("ml", {"features_count": 150, "target_variable": "price"})',
            'metadata = get_metadata_template("research", {"study_type": "clinical_trial"})',
        ],
        "custom_template_tip": "You can also pass any custom metadata dict directly to package creation functions",
    }


def validate_metadata_structure(metadata: Dict[str, Any], template_name: str = None) -> Dict[str, Any]:
    """
    Validate metadata structure and provide suggestions.

    Args:
        metadata: Metadata dictionary to validate
        template_name: Optional template name to validate against

    Returns:
        Validation result with suggestions for improvement
    """
    issues = []
    suggestions = []

    # Basic validation
    if not isinstance(metadata, dict):
        return {
            "valid": False,
            "error": "Metadata must be a dictionary/JSON object",
            "provided_type": type(metadata).__name__,
            "fix": "Pass a dictionary like {'description': 'My dataset'}",
        }

    # Check for recommended fields
    recommended_fields = ["description", "created_by", "version"]
    missing_recommended = [field for field in recommended_fields if field not in metadata]

    if missing_recommended:
        suggestions.extend([f"Consider adding '{field}' field" for field in missing_recommended])

    # Check for common issues
    if "description" in metadata and len(metadata["description"]) < 10:
        suggestions.append("Description is very short - consider adding more detail")

    # Template-specific validation
    if template_name and template_name in METADATA_TEMPLATES:
        template = METADATA_TEMPLATES[template_name]
        template_fields = set(template.keys())
        provided_fields = set(metadata.keys())

        missing_template_fields = template_fields - provided_fields
        if missing_template_fields:
            suggestions.extend([f"Template '{template_name}' suggests adding: {', '.join(missing_template_fields)}"])

    return {
        "valid": True,
        "issues": issues,
        "suggestions": suggestions,
        "field_count": len(metadata),
        "recommended_additions": missing_recommended if missing_recommended else None,
    }


def metadata_templates(action: str | None = None, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Metadata templates and validation utilities.
    
    Available actions:
    - get_template: Get a metadata template with optional custom fields
    - list_templates: List available metadata templates with descriptions
    - validate: Validate metadata structure and provide suggestions
    
    Args:
        action: The operation to perform. If None, returns available actions.
        **kwargs: Action-specific parameters
    
    Returns:
        Action-specific response dictionary
    
    Examples:
        # Discovery mode
        result = metadata_templates()
        
        # Get template
        result = metadata_templates(action="get_template", template_name="standard")
        
        # Validate metadata
        result = metadata_templates(action="validate", metadata={"description": "test"})
    
    For detailed parameter documentation, see individual action functions.
    """
    actions = {
        "get_template": get_metadata_template,
        "list_templates": list_metadata_templates,
        "validate": validate_metadata_structure,
    }
    
    # Discovery mode
    if action is None:
        return {
            "success": True,
            "module": "metadata_templates",
            "actions": list(actions.keys()),
            "usage": "Call with action='<action_name>' to execute",
        }
    
    # Validate action
    if action not in actions:
        available = ", ".join(sorted(actions.keys()))
        return {
            "success": False,
            "error": f"Unknown action '{action}' for module 'metadata_templates'. Available actions: {available}",
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

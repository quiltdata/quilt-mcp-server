"""Metadata helpers used by MCP resources and higher-level workflows.

This module centralizes the read-only metadata helpers that previously lived
under ``quilt_mcp.tools.metadata_templates`` and
``quilt_mcp.tools.metadata_examples`` so resources can consume them directly
without routing through the tools shim.  Other call sites (e.g. enhanced
package management) can import from here as well without creating circular
dependencies.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _current_timestamp() -> str:
    """Return an ISO-8601 timestamp for template fields."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Metadata templates
# ---------------------------------------------------------------------------

METADATA_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "standard": {
        "description": "Standard data package",
        "created_by": "quilt-mcp-server",
        "creation_date": _current_timestamp(),
        "package_type": "data",
        "version": "1.0.0",
    },
    "genomics": {
        "description": "Genomics data package",
        "created_by": "quilt-mcp-server",
        "creation_date": _current_timestamp(),
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
        "creation_date": _current_timestamp(),
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
        "creation_date": _current_timestamp(),
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
        "creation_date": _current_timestamp(),
        "package_type": "analytics",
        "data_type": "business_analytics",
        "analysis_period": "unknown",
        "business_unit": "unknown",
        "metrics_included": [],
        "version": "1.0.0",
    },
}


def get_metadata_template(template_name: str, custom_fields: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Return a metadata template merged with optional custom fields."""
    template_key = template_name if template_name in METADATA_TEMPLATES else "standard"
    metadata = METADATA_TEMPLATES[template_key].copy()
    metadata["creation_date"] = _current_timestamp()

    if custom_fields:
        metadata.update(custom_fields)

    return metadata


def list_metadata_templates() -> Dict[str, Any]:
    """List the available metadata templates and usage examples."""
    templates_info: Dict[str, Dict[str, Any]] = {}

    for name, template in METADATA_TEMPLATES.items():
        templates_info[name] = {
            "description": template.get("description", ""),
            "package_type": template.get("package_type", ""),
            "data_type": template.get("data_type", ""),
            "fields": list(template.keys()),
            "example_usage": f'get_metadata_template("{name}", {{"custom_field": "value"}})',
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


def validate_metadata_structure(metadata: Dict[str, Any], template_name: Optional[str] = None) -> Dict[str, Any]:
    """Validate a metadata dictionary and surface improvement suggestions."""
    if not isinstance(metadata, dict):
        return {
            "valid": False,
            "error": "Metadata must be a dictionary/JSON object",
            "provided_type": type(metadata).__name__,
            "fix": "Pass a dictionary like {'description': 'My dataset'}",
        }

    issues: List[str] = []
    suggestions: List[str] = []

    recommended_fields = ["description", "created_by", "version"]
    missing_recommended = [field for field in recommended_fields if field not in metadata]
    if missing_recommended:
        suggestions.extend([f"Consider adding '{field}' field" for field in missing_recommended])

    if "description" in metadata and isinstance(metadata["description"], str) and len(metadata["description"]) < 10:
        suggestions.append("Description is very short - consider adding more detail")

    if template_name and template_name in METADATA_TEMPLATES:
        template = METADATA_TEMPLATES[template_name]
        template_fields = set(template.keys())
        provided_fields = set(metadata.keys())

        missing_template_fields = template_fields - provided_fields
        if missing_template_fields:
            suggestions.extend([f"Template '{template_name}' suggests adding: {', '.join(missing_template_fields)}"])

        extra_fields = provided_fields - template_fields
        if extra_fields:
            suggestions.extend([f"Extra fields not in '{template_name}' template: {', '.join(extra_fields)}"])

    is_valid = not issues

    return {
        "valid": is_valid,
        "issues": issues,
        "suggestions": suggestions,
        "checked_template": template_name,
    }


# ---------------------------------------------------------------------------
# Metadata examples and troubleshooting
# ---------------------------------------------------------------------------


def show_metadata_examples() -> Dict[str, Any]:
    """Return comprehensive metadata usage examples and troubleshooting tips."""
    return {
        "metadata_usage_guide": {
            "overview": "Metadata can be passed as either a dictionary object or JSON string",
            "recommended_approach": "Use metadata templates for consistent structure",
            "working_examples": {
                "basic_dict": {
                    "description": "Pass metadata as a Python dictionary",
                    "example": '{"description": "My dataset", "version": "1.0", "tags": ["research"]}',
                    "usage": 'package_create("team/data", ["s3://bucket/file.csv"], metadata={"description": "My dataset"})',
                },
                "json_string": {
                    "description": "Pass metadata as a JSON string (automatically parsed)",
                    "example": '\'{"description": "My dataset", "version": "1.0", "tags": ["research"]}\'',
                    "usage": 'package_create("team/data", ["s3://bucket/file.csv"], metadata=\'{"description": "My dataset"}\')',
                },
                "template_based": {
                    "description": "Use metadata templates (recommended)",
                    "example": "Uses pre-configured templates for common domains",
                    "usage": 'create_package_enhanced("genomics/study", ["s3://bucket/data.vcf"], metadata_template="genomics")',
                },
                "template_with_custom": {
                    "description": "Combine templates with custom fields",
                    "example": "Template provides structure, custom fields add specifics",
                    "usage": 'create_package_enhanced("ml/training", files, metadata_template="ml", metadata={"model_type": "regression"})',
                },
            },
            "common_patterns": {
                "research_data": {
                    "template": "research",
                    "custom_fields": {
                        "study_type": "clinical_trial",
                        "participants": 150,
                        "duration_months": 12,
                        "primary_endpoint": "efficacy",
                    },
                    "usage": 'create_package_enhanced("research/trial-2024", files, metadata_template="research", metadata={"study_type": "clinical_trial"})',
                },
                "genomics_data": {
                    "template": "genomics",
                    "custom_fields": {
                        "organism": "human",
                        "genome_build": "GRCh38",
                        "sequencing_platform": "Illumina",
                        "read_length": 150,
                        "coverage": "30x",
                    },
                    "usage": 'create_package_enhanced("genomics/wgs-study", files, metadata_template="genomics", metadata={"organism": "human"})',
                },
                "ml_dataset": {
                    "template": "ml",
                    "custom_fields": {
                        "features_count": 42,
                        "target_variable": "price",
                        "dataset_stage": "cleaned",
                        "model_ready": True,
                        "split_ratios": {"train": 0.7, "val": 0.15, "test": 0.15},
                    },
                    "usage": 'create_package_enhanced("ml/housing-prices", files, metadata_template="ml", metadata={"target_variable": "price"})',
                },
                "business_analytics": {
                    "template": "analytics",
                    "custom_fields": {
                        "analysis_period": "Q1-2024",
                        "business_unit": "sales",
                        "metrics_included": ["revenue", "conversion", "retention"],
                        "dashboard_ready": True,
                    },
                    "usage": 'create_package_enhanced("analytics/q1-sales", files, metadata_template="analytics", metadata={"analysis_period": "Q1-2024"})',
                },
            },
        },
        "troubleshooting": {
            "validation_errors": {
                "json_format_error": {
                    "error": "Invalid metadata JSON format",
                    "cause": "Malformed JSON string",
                    "fix": "Ensure proper JSON formatting with quotes around keys",
                    "example_fix": 'Change {"description": My dataset} to {"description": "My dataset"}',
                },
                "schema_validation_error": {
                    "error": "not valid under any of the given schemas",
                    "cause": "Parameter type mismatch in FastMCP validation",
                    "fix": "Use dictionary object instead of JSON string for direct calls",
                    "example_fix": 'Use metadata={"key": "value"} instead of metadata=\'{"key": "value"}\'',
                },
                "type_error": {
                    "error": "Invalid metadata type",
                    "cause": "Metadata is not a dict or JSON string",
                    "fix": "Pass metadata as dictionary or JSON string only",
                    "example_fix": 'Use {"description": "value"} not description="value"',
                },
            },
            "permission_errors": {
                "access_denied": {
                    "error": "AccessDenied when calling PutObject",
                    "cause": "Insufficient S3 write permissions",
                    "fix": "Check bucket permissions and try alternative bucket",
                    "tools_to_try": [
                        "test_permissions()",
                        "bucket_recommendations_get()",
                    ],
                }
            },
        },
        "best_practices": [
            "Use metadata templates for consistent structure across packages",
            "Include description, version, and tags in all packages",
            "Use semantic versioning (1.0.0, 1.1.0, 2.0.0) for versions",
            "Add contact/author information for collaborative projects",
            "Include data quality indicators (raw, cleaned, validated)",
            "Use standardized tag vocabularies within your organization",
            "Document data sources and processing steps in metadata",
        ],
        "quick_reference": {
            "available_templates": [
                "standard",
                "genomics",
                "ml",
                "research",
                "analytics",
            ],
            "required_fields": ["description"],
            "recommended_fields": ["version", "created_by", "tags"],
            "common_custom_fields": [
                "source",
                "quality",
                "contact",
                "project",
                "department",
            ],
        },
    }


def create_metadata_from_template(
    template_name: str = "standard",
    description: str = "",
    custom_fields: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create metadata content by combining a template with optional overrides."""
    try:
        metadata = get_metadata_template(template_name, custom_fields or {})
        if description:
            metadata["description"] = description

        return {
            "success": True,
            "metadata": metadata,
            "template_used": template_name,
            "field_count": len(metadata),
            "usage_tip": "Use this metadata in package_create() or create_package_enhanced()",
            "example_usage": f'package_create("team/package", ["s3://bucket/file.csv"], metadata={str(metadata)})',
        }

    except Exception as exc:
        return {
            "success": False,
            "error": f"Failed to create metadata from template: {exc}",
            "template_requested": template_name,
            "suggested_actions": [
                "Try: list_metadata_templates() to see available templates",
                "Use 'standard' template as fallback",
                "Check custom_fields format",
            ],
        }


def fix_metadata_validation_issues() -> Dict[str, Any]:
    """Provide troubleshooting tips for common metadata validation issues."""
    return {
        "common_issues_and_fixes": {
            "schema_validation_error": {
                "error_message": "not valid under any of the given schemas",
                "root_cause": "FastMCP parameter validation expects specific types",
                "solution": "Use dictionary objects instead of JSON strings for direct tool calls",
                "working_examples": [
                    'metadata={"description": "My dataset", "version": "1.0"}',
                    'metadata={"tags": ["research", "2024"], "author": "scientist"}',
                ],
                "avoid": [
                    'metadata=\'{"description": "My dataset"}\'  # JSON string may fail validation',
                    'metadata="description=My dataset"  # Not JSON format',
                ],
            },
            "json_format_error": {
                "error_message": "Invalid metadata JSON format",
                "root_cause": "Malformed JSON string",
                "solution": "Use proper JSON formatting with quotes around all keys and string values",
                "working_examples": [
                    '\'{"description": "My dataset", "version": "1.0"}\'',
                    '\'{"tags": ["tag1", "tag2"], "count": 42}\'',
                ],
                "common_mistakes": [
                    '{description: "value"}  # Missing quotes around key',
                    '{"description": My dataset}  # Missing quotes around value',
                    "{'description': 'value'}  # Use double quotes, not single",
                ],
            },
            "type_validation_error": {
                "error_message": "Invalid metadata type",
                "root_cause": "Metadata is neither dict nor JSON string",
                "solution": "Pass metadata as dictionary object or valid JSON string only",
                "working_examples": [
                    '{"description": "value", "tags": ["tag1"]}  # Dictionary object',
                    '\'{"description": "value", "tags": ["tag1"]}\'  # JSON string',
                ],
                "avoid": [
                    'description="value"  # Individual parameters not supported',
                    "None  # Use {} for empty metadata instead",
                ],
            },
        },
        "step_by_step_fix": [
            "1. Choose your approach: dictionary object (recommended) or JSON string",
            "2. If using JSON string, validate format with online JSON validator",
            "3. If using dictionary, ensure all keys are strings and values are JSON-serializable",
            "4. Test with simple metadata first: {'description': 'test'}",
            "5. Gradually add more fields once basic metadata works",
            "6. Use metadata templates for complex structures",
        ],
        "testing_approach": [
            "Start simple: metadata={'description': 'test package'}",
            "Verify it works with package_create()",
            "Add one field at a time to identify problematic fields",
            "Use dry_run=True to test without creating actual packages",
            "Use validate_metadata_structure() to check format before creation",
        ],
        "recommended_workflow": [
            "1. Use create_package_enhanced() as primary tool (best error handling)",
            "2. Start with metadata templates: metadata_template='standard'",
            "3. Add custom fields via metadata parameter",
            "4. Use dry_run=True to preview before creation",
            "5. Validate with package_validate() after creation",
        ],
    }

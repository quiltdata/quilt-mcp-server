"""Metadata Examples and Usage Guidance.

This module provides comprehensive examples and guidance for using metadata
with Quilt packages, addressing common user confusion and validation issues.
"""

from typing import Dict, Any, List
from .metadata_templates import get_metadata_template, list_metadata_templates


def show_metadata_examples() -> Dict[str, Any]:
    """
    Show comprehensive metadata usage examples with working patterns.

    Returns:
        Dict with examples, patterns, and troubleshooting guidance
    """
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
    custom_fields: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """
    Create metadata using a template with custom fields - simplified interface.

    Args:
        template_name: Template to use ('standard', 'genomics', 'ml', 'research', 'analytics')
        description: Package description (added to metadata)
        custom_fields: Additional fields to merge with template

    Returns:
        Complete metadata dictionary ready for package creation

    Examples:
        Basic usage:
        metadata = create_metadata_from_template("genomics", "Human genome study", {"organism": "human"})

        Then use in package creation:
        package_create("genomics/study1", ["s3://bucket/data.vcf"], metadata=metadata)
    """
    try:
        # Get base template
        metadata = get_metadata_template(template_name, custom_fields or {})

        # Add description if provided
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


def fix_metadata_validation_issues() -> Dict[str, Any]:
    """
    Provide specific guidance for fixing metadata validation issues.

    Returns:
        Comprehensive troubleshooting guide for metadata problems
    """
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

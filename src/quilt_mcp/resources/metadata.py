"""Metadata MCP Resources.

This module implements MCP resources for metadata-related functions like
template discovery, examples, and troubleshooting guides.
"""

from typing import Dict, Any, List
from .base import MCPResource


def show_metadata_examples() -> Dict[str, Any]:
    """Show comprehensive metadata usage examples with working patterns.

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
                    "usage": 'create_package("team/data", ["s3://bucket/file.csv"], metadata={"description": "My dataset"})',
                },
                "json_string": {
                    "description": "Pass metadata as a JSON string (automatically parsed)",
                    "example": '\'{"description": "My dataset", "version": "1.0", "tags": ["research"]}\'',
                    "usage": 'create_package("team/data", ["s3://bucket/file.csv"], metadata=\'{"description": "My dataset"}\')',
                },
                "template_based": {
                    "description": "Use metadata templates (recommended)",
                    "example": "Uses pre-configured templates for common domains",
                    "usage": 'create_package("genomics/study", ["s3://bucket/data.vcf"], metadata_template="genomics")',
                },
                "template_with_custom": {
                    "description": "Combine templates with custom fields",
                    "example": "Template provides structure, custom fields add specifics",
                    "usage": 'create_package("ml/training", files, metadata_template="ml", metadata={"model_type": "regression"})',
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
                    "usage": 'create_package("research/trial-2024", files, metadata_template="research", metadata={"study_type": "clinical_trial"})',
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
                    "usage": 'create_package("genomics/wgs-study", files, metadata_template="genomics", metadata={"organism": "human"})',
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
                    "usage": 'create_package("ml/housing-prices", files, metadata_template="ml", metadata={"target_variable": "price"})',
                },
                "business_analytics": {
                    "template": "analytics",
                    "custom_fields": {
                        "analysis_period": "Q1-2024",
                        "business_unit": "sales",
                        "metrics_included": ["revenue", "conversion", "retention"],
                        "dashboard_ready": True,
                    },
                    "usage": 'create_package("analytics/q1-sales", files, metadata_template="analytics", metadata={"analysis_period": "Q1-2024"})',
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


def fix_metadata_validation_issues() -> Dict[str, Any]:
    """Provide specific guidance for fixing metadata validation issues.

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
            "Verify it works with create_package()",
            "Add one field at a time to identify problematic fields",
            "Use dry_run=True to test without creating actual packages",
            "Use validate_metadata_structure() to check format before creation",
        ],
        "recommended_workflow": [
            "1. Use create_package() as primary tool (best error handling)",
            "2. Start with metadata templates: metadata_template='standard'",
            "3. Add custom fields via metadata parameter",
            "4. Use dry_run=True to preview before creation",
            "5. Validate with package_validate() after creation",
        ],
    }


class MetadataTemplatesResource(MCPResource):
    """MCP resource for metadata templates listing."""

    def __init__(self):
        """Initialize MetadataTemplatesResource."""
        super().__init__("metadata://templates")

    async def list_items(self, **params) -> Dict[str, Any]:
        """List metadata templates.

        Returns:
            Metadata templates data in original format
        """
        # Import here to avoid circular imports and maintain compatibility
        from ..tools.metadata_templates import list_metadata_templates

        # Call the original sync function
        return list_metadata_templates()

    def _extract_items(self, raw_data: Dict[str, Any]) -> List[Any]:
        """Extract templates list from metadata templates data."""
        available_templates = raw_data.get("available_templates", {})

        # Convert template dict to list of items
        items = []
        for template_name, template_info in available_templates.items():
            item = template_info.copy()
            item["name"] = template_name
            items.append(item)

        return items

    def _extract_metadata(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract metadata from metadata templates data."""
        metadata = super()._extract_metadata(raw_data)

        # Add metadata template-specific metadata
        if "usage_examples" in raw_data:
            metadata["usage_examples"] = raw_data["usage_examples"]
        if "custom_template_tip" in raw_data:
            metadata["custom_template_tip"] = raw_data["custom_template_tip"]

        return metadata


class MetadataExamplesResource(MCPResource):
    """Static MCP resource for metadata usage examples and patterns."""

    def __init__(self):
        """Initialize MetadataExamplesResource."""
        super().__init__("metadata://examples")

    async def list_items(self, **params) -> Dict[str, Any]:
        """Get comprehensive metadata usage examples.

        Returns:
            Metadata examples and patterns in original format
        """
        return show_metadata_examples()

    def _extract_items(self, raw_data: Dict[str, Any]) -> List[Any]:
        """Extract examples as list items."""
        items = []

        # Extract working examples
        metadata_usage = raw_data.get("metadata_usage_guide", {})
        working_examples = metadata_usage.get("working_examples", {})
        for example_name, example_data in working_examples.items():
            items.append({"name": example_name, "type": "working_example", **example_data})

        # Extract common patterns
        common_patterns = metadata_usage.get("common_patterns", {})
        for pattern_name, pattern_data in common_patterns.items():
            items.append({"name": pattern_name, "type": "common_pattern", **pattern_data})

        return items

    def _extract_metadata(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract metadata from examples data."""
        metadata = super()._extract_metadata(raw_data)

        # Add examples-specific metadata
        if "best_practices" in raw_data:
            metadata["best_practices"] = raw_data["best_practices"]
        if "quick_reference" in raw_data:
            metadata["quick_reference"] = raw_data["quick_reference"]
        if "troubleshooting" in raw_data:
            metadata["troubleshooting"] = raw_data["troubleshooting"]

        return metadata


class MetadataTroubleshootingResource(MCPResource):
    """Static MCP resource for metadata validation troubleshooting."""

    def __init__(self):
        """Initialize MetadataTroubleshootingResource."""
        super().__init__("metadata://troubleshooting")

    async def list_items(self, **params) -> Dict[str, Any]:
        """Get metadata validation troubleshooting guide.

        Returns:
            Troubleshooting guidance in original format
        """
        return fix_metadata_validation_issues()

    def _extract_items(self, raw_data: Dict[str, Any]) -> List[Any]:
        """Extract troubleshooting issues as list items."""
        items = []

        # Extract common issues
        common_issues = raw_data.get("common_issues_and_fixes", {})
        for issue_name, issue_data in common_issues.items():
            items.append({"name": issue_name, "type": "issue_fix", **issue_data})

        return items

    def _extract_metadata(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract metadata from troubleshooting data."""
        metadata = super()._extract_metadata(raw_data)

        # Add troubleshooting-specific metadata
        if "step_by_step_fix" in raw_data:
            metadata["step_by_step_fix"] = raw_data["step_by_step_fix"]
        if "testing_approach" in raw_data:
            metadata["testing_approach"] = raw_data["testing_approach"]
        if "recommended_workflow" in raw_data:
            metadata["recommended_workflow"] = raw_data["recommended_workflow"]

        return metadata

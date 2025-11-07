"""Pydantic models for MCP tool input parameters.

This module defines rigorous type models for tool inputs,
ensuring MCP generates useful input schemas and provides
proper validation for tool parameters.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, Optional

from pydantic import BaseModel, Field, conint, constr, field_validator


# ============================================================================
# S3/Bucket Input Models
# ============================================================================


class BucketObjectsListParams(BaseModel):
    """Parameters for bucket_objects_list tool."""

    bucket: Annotated[
        str,
        Field(
            description="S3 bucket name or s3:// URI",
            examples=["my-bucket", "s3://my-bucket"],
        ),
    ]
    prefix: Annotated[
        str,
        Field(
            default="",
            description="Filter objects by prefix (e.g., 'data/' to list only objects in data folder)",
            examples=["", "data/", "experiments/2024/"],
        ),
    ]
    max_keys: Annotated[
        int,
        Field(
            default=100,
            ge=1,
            le=1000,
            description="Maximum number of objects to return (1-1000)",
        ),
    ]
    continuation_token: Annotated[
        str,
        Field(
            default="",
            description="Token for paginating through large result sets (from previous response)",
        ),
    ]
    include_signed_urls: Annotated[
        bool,
        Field(
            default=True,
            description="Include presigned download URLs for each object",
        ),
    ]


class BucketObjectInfoParams(BaseModel):
    """Parameters for bucket_object_info tool."""

    s3_uri: Annotated[
        str,
        Field(
            description="Full S3 URI to the object, optionally with versionId query parameter",
            examples=[
                "s3://bucket-name/path/to/object",
                "s3://bucket-name/path/to/object?versionId=abc123",
            ],
            pattern=r"^s3://[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]/.+",
        ),
    ]


class BucketObjectFetchParams(BaseModel):
    """Parameters for bucket_object_fetch tool."""

    s3_uri: Annotated[
        str,
        Field(
            description="Full S3 URI to the object",
            examples=["s3://bucket-name/path/to/file"],
            pattern=r"^s3://[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]/.+",
        ),
    ]
    max_bytes: Annotated[
        int,
        Field(
            default=65536,
            ge=1,
            le=10485760,  # 10MB
            description="Maximum bytes to read (1 byte to 10MB)",
        ),
    ]
    base64_encode: Annotated[
        bool,
        Field(
            default=True,
            description="Return binary data as base64 (true) or attempt text decoding (false)",
        ),
    ]


class BucketObjectLinkParams(BaseModel):
    """Parameters for bucket_object_link tool."""

    s3_uri: Annotated[
        str,
        Field(
            description="Full S3 URI to the object",
            examples=["s3://bucket-name/path/to/file"],
            pattern=r"^s3://[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]/.+",
        ),
    ]
    expiration: Annotated[
        int,
        Field(
            default=3600,
            ge=1,
            le=604800,  # 7 days
            description="URL expiration time in seconds (1 second to 7 days)",
        ),
    ]


class BucketObjectTextParams(BaseModel):
    """Parameters for bucket_object_text tool."""

    s3_uri: Annotated[
        str,
        Field(
            description="Full S3 URI to the object",
            examples=["s3://bucket-name/path/to/file.txt"],
            pattern=r"^s3://[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]/.+",
        ),
    ]
    max_bytes: Annotated[
        int,
        Field(
            default=65536,
            ge=1,
            le=10485760,  # 10MB
            description="Maximum bytes to read (1 byte to 10MB)",
        ),
    ]
    encoding: Annotated[
        str,
        Field(
            default="utf-8",
            description="Text encoding to use for decoding",
            examples=["utf-8", "latin-1", "ascii"],
        ),
    ]


class BucketObjectsPutParams(BaseModel):
    """Parameters for uploading multiple objects to S3.

    Items are provided as a list of dicts with the following structure:
    - key (required): S3 key (path) for the object
    - text OR data (required): Text content or base64-encoded binary content (not both)
    - content_type (optional): MIME type, defaults to "application/octet-stream"
    - encoding (optional): Text encoding (e.g., 'utf-8') when uploading text
    - metadata (optional): Custom metadata key-value pairs

    Simple example:
    items=[{"key": "file.txt", "text": "Hello World"}]
    """

    bucket: Annotated[
        str,
        Field(
            description="S3 bucket name or s3:// URI",
            examples=["my-bucket", "s3://my-bucket"],
        ),
    ]
    items: Annotated[
        list[dict[str, Any]],
        Field(
            description=(
                "List of objects to upload. Each item is a dict with:\n"
                "- key (str, required): S3 key (path) for the object\n"
                "- text (str, optional): Text content to upload (use this OR data, not both)\n"
                "- data (str, optional): Base64-encoded binary content (use this OR text, not both)\n"
                "- content_type (str, optional): MIME type, defaults to 'application/octet-stream'\n"
                "- encoding (str, optional): Text encoding (e.g., 'utf-8') when uploading text\n"
                "- metadata (dict[str, str], optional): Custom metadata key-value pairs"
            ),
            min_length=1,
            examples=[
                # Minimal example
                [{"key": "hello.txt", "text": "Hello World"}],
                # With content type
                [
                    {
                        "key": "data.csv",
                        "text": "col1,col2\n1,2",
                        "content_type": "text/csv",
                    }
                ],
                # Binary data
                [
                    {
                        "key": "image.png",
                        "data": "iVBORw0KGgo...",
                        "content_type": "image/png",
                    }
                ],
                # With metadata
                [
                    {
                        "key": "report.txt",
                        "text": "Report content",
                        "content_type": "text/plain",
                        "encoding": "utf-8",
                        "metadata": {"author": "system", "version": "1.0"},
                    }
                ],
            ],
        ),
    ]

    @field_validator("items")
    @classmethod
    def validate_items(cls, v: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Validate items structure with enhanced error messages."""
        if not isinstance(v, list):
            raise ValueError("items must be a list")

        for idx, item in enumerate(v):
            if not isinstance(item, dict):
                raise ValueError(f"Item at index {idx} must be a dict, got {type(item).__name__}")

            # Validate required key field
            if "key" not in item or not item["key"]:
                error_lines = [
                    f"Invalid item at index {idx}: Missing required 'key' field",
                    "",
                    "Each item must have:",
                    "  - 'key' (required): S3 key/path for the object",
                    "  - 'text' OR 'data' (required): Content to upload",
                    "",
                    "Example:",
                    '  {"key": "file.txt", "text": "Hello World"}',
                ]
                raise ValueError("\n".join(error_lines))

            # Validate exactly one of text or data is present
            has_text = "text" in item and item["text"] is not None
            has_data = "data" in item and item["data"] is not None

            if not has_text and not has_data:
                raise ValueError(
                    f"Item at index {idx}: Must provide either 'text' or 'data' field\n"
                    f"Provided keys: {list(item.keys())}"
                )

            if has_text and has_data:
                raise ValueError(
                    f"Item at index {idx}: Cannot provide both 'text' and 'data' fields\n"
                    "Use only one: 'text' for strings, 'data' for base64-encoded binary"
                )

        return v


# ============================================================================
# Package Input Models
# ============================================================================


class PackageBrowseParams(BaseModel):
    """Parameters for package_browse tool."""

    package_name: Annotated[
        str,
        Field(
            description="Name of the package in namespace/name format",
            examples=["username/dataset", "team/analysis-results"],
            pattern=r"^[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+$",
        ),
    ]
    registry: Annotated[
        str,
        Field(
            default="s3://quilt-ernest-staging",
            description="Quilt registry S3 URI",
            examples=["s3://my-bucket", "s3://quilt-example"],
        ),
    ]
    recursive: Annotated[
        bool,
        Field(
            default=True,
            description="Show full file tree (true) or just top-level entries (false)",
        ),
    ]
    include_file_info: Annotated[
        bool,
        Field(
            default=True,
            description="Include file sizes, types, and modification dates",
        ),
    ]
    max_depth: Annotated[
        int,
        Field(
            default=0,
            ge=0,
            description="Maximum directory depth to show (0 for unlimited)",
        ),
    ]
    top: Annotated[
        int,
        Field(
            default=0,
            ge=0,
            description="Limit number of entries returned (0 for unlimited)",
        ),
    ]
    include_signed_urls: Annotated[
        bool,
        Field(
            default=True,
            description="Include presigned download URLs for S3 objects",
        ),
    ]


class PackageCreateParams(BaseModel):
    """Parameters for package_create tool."""

    package_name: Annotated[
        str,
        Field(
            description="Name for the new package in namespace/name format",
            examples=["username/dataset", "team/analysis-results"],
            pattern=r"^[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+$",
        ),
    ]
    s3_uris: Annotated[
        list[str],
        Field(
            description="List of S3 URIs to include in the package",
            examples=[["s3://bucket/file1.csv", "s3://bucket/file2.json"]],
            min_length=1,
        ),
    ]
    registry: Annotated[
        str,
        Field(
            default="s3://quilt-ernest-staging",
            description="Target Quilt registry S3 URI",
        ),
    ]
    metadata: Annotated[
        Optional[dict[str, Any]],
        Field(
            default=None,
            description="Optional metadata to attach to the package (JSON object)",
            examples=[{"description": "My dataset", "version": "1.0"}],
        ),
    ]
    message: Annotated[
        str,
        Field(
            default="Created via package_create tool",
            description="Commit message for package creation",
        ),
    ]
    flatten: Annotated[
        bool,
        Field(
            default=True,
            description="Use only filenames as logical paths (true) instead of full S3 keys (false)",
        ),
    ]
    copy_mode: Annotated[
        Literal["all", "same_bucket", "none"],
        Field(
            default="all",
            description="Copy policy for the underlying data: 'all' (copy everything), 'same_bucket' (copy only if different bucket), 'none' (reference only)",
        ),
    ]


class PackageUpdateParams(BaseModel):
    """Parameters for package_update tool."""

    package_name: Annotated[
        str,
        Field(
            description="Name of the existing package to update in namespace/name format",
            examples=["username/dataset", "team/analysis-results"],
            pattern=r"^[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+$",
        ),
    ]
    s3_uris: Annotated[
        list[str],
        Field(
            description="List of S3 URIs to add to the package",
            examples=[["s3://bucket/newfile.csv", "s3://bucket/updated.json"]],
            min_length=1,
        ),
    ]
    registry: Annotated[
        str,
        Field(
            default="s3://quilt-ernest-staging",
            description="Target Quilt registry S3 URI",
        ),
    ]
    metadata: Annotated[
        Optional[dict[str, Any]],
        Field(
            default=None,
            description="Optional metadata to merge with existing package metadata",
            examples=[{"updated": "true", "version": "2.0"}],
        ),
    ]
    message: Annotated[
        str,
        Field(
            default="Added objects via package_update tool",
            description="Commit message for package update",
        ),
    ]
    flatten: Annotated[
        bool,
        Field(
            default=True,
            description="Use only filenames as logical paths (true) instead of full S3 keys (false)",
        ),
    ]
    copy_mode: Annotated[
        Literal["all", "same_bucket", "none"],
        Field(
            default="all",
            description="Copy policy for the source objects: 'all' (copy everything), 'same_bucket' (copy only if different bucket), 'none' (reference only)",
        ),
    ]


class PackageDeleteParams(BaseModel):
    """Parameters for package_delete tool."""

    package_name: Annotated[
        str,
        Field(
            description="Name of the package to delete in namespace/name format",
            examples=["username/dataset", "team/old-analysis"],
            pattern=r"^[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+$",
        ),
    ]
    registry: Annotated[
        str,
        Field(
            default="s3://quilt-ernest-staging",
            description="Quilt registry S3 URI where the package resides",
        ),
    ]


class PackagesListParams(BaseModel):
    """Parameters for packages_list tool."""

    registry: Annotated[
        str,
        Field(
            default="s3://quilt-ernest-staging",
            description="Quilt registry S3 URI to list packages from",
        ),
    ]
    limit: Annotated[
        int,
        Field(
            default=0,
            ge=0,
            description="Maximum number of packages to return, 0 for unlimited",
        ),
    ]
    prefix: Annotated[
        str,
        Field(
            default="",
            description="Filter packages by name prefix",
            examples=["", "team/", "user/analysis-"],
        ),
    ]


class PackageDiffParams(BaseModel):
    """Parameters for package_diff tool."""

    package1_name: Annotated[
        str,
        Field(
            description="Name of the first package in namespace/name format",
            examples=["username/dataset", "team/analysis-v1"],
            pattern=r"^[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+$",
        ),
    ]
    package2_name: Annotated[
        str,
        Field(
            description="Name of the second package in namespace/name format",
            examples=["username/dataset", "team/analysis-v2"],
            pattern=r"^[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+$",
        ),
    ]
    registry: Annotated[
        str,
        Field(
            default="s3://quilt-ernest-staging",
            description="Quilt registry S3 URI",
        ),
    ]
    package1_hash: Annotated[
        str,
        Field(
            default="",
            description="Optional specific hash for first package (empty string for latest)",
        ),
    ]
    package2_hash: Annotated[
        str,
        Field(
            default="",
            description="Optional specific hash for second package (empty string for latest)",
        ),
    ]


class PackageCreateFromS3Params(BaseModel):
    """Parameters for creating a Quilt package from S3 bucket contents.

    Basic usage requires only source_bucket and package_name.
    All other parameters have sensible defaults.
    """

    # === REQUIRED: Core Parameters ===
    source_bucket: Annotated[
        str,
        Field(
            description="S3 bucket name containing source data (without s3:// prefix)",
            examples=["my-data-bucket", "research-data"],
            json_schema_extra={"importance": "required"},
        ),
    ]
    package_name: Annotated[
        str,
        Field(
            description="Name for the new package in namespace/name format",
            examples=["username/dataset", "team/research-data"],
            pattern=r"^[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+$",
            json_schema_extra={"importance": "required"},
        ),
    ]

    # === COMMON: Frequently Used Options ===
    source_prefix: Annotated[
        str,
        Field(
            default="",
            description="Optional prefix to filter source objects (e.g., 'data/' to include only data folder)",
            examples=["", "data/2024/", "experiments/"],
            json_schema_extra={"importance": "common"},
        ),
    ]
    description: Annotated[
        str,
        Field(
            default="",
            description="Human-readable description of the package contents",
            json_schema_extra={"importance": "common"},
        ),
    ]

    # === ADVANCED: Fine-tuning Options ===
    target_registry: Annotated[
        Optional[str],
        Field(
            default=None,
            description="[ADVANCED] Target Quilt registry (auto-suggested if not provided)",
            json_schema_extra={"importance": "advanced"},
        ),
    ]
    include_patterns: Annotated[
        Optional[list[str]],
        Field(
            default=None,
            description="[ADVANCED] File patterns to include (glob style, e.g., ['*.csv', '*.json'])",
            examples=[["*.csv", "*.json"], ["data/*.parquet"]],
            json_schema_extra={"importance": "advanced"},
        ),
    ]
    exclude_patterns: Annotated[
        Optional[list[str]],
        Field(
            default=None,
            description="[ADVANCED] File patterns to exclude (glob style, e.g., ['*.tmp', '*.log'])",
            examples=[["*.tmp", "*.log"], ["temp/*"]],
            json_schema_extra={"importance": "advanced"},
        ),
    ]
    metadata_template: Annotated[
        Literal["standard", "ml", "analytics"],
        Field(
            default="standard",
            description="[ADVANCED] Metadata template to use for package organization",
            json_schema_extra={"importance": "advanced"},
        ),
    ]
    copy_mode: Annotated[
        Literal["all", "same_bucket", "none"],
        Field(
            default="all",
            description="[ADVANCED] Copy policy: 'all' (copy everything), 'same_bucket' (copy only if different bucket), 'none' (reference only)",
            json_schema_extra={"importance": "advanced"},
        ),
    ]

    # === INTERNAL: Developer/Testing Flags ===
    auto_organize: Annotated[
        bool,
        Field(
            default=True,
            description="[INTERNAL] Enable smart folder organization (keep True for best results)",
            json_schema_extra={"importance": "internal"},
        ),
    ]
    generate_readme: Annotated[
        bool,
        Field(
            default=True,
            description="[INTERNAL] Generate comprehensive README.md (keep True for best results)",
            json_schema_extra={"importance": "internal"},
        ),
    ]
    confirm_structure: Annotated[
        bool,
        Field(
            default=True,
            description="[INTERNAL] Require user confirmation of structure (set False for automation)",
            json_schema_extra={"importance": "internal"},
        ),
    ]
    dry_run: Annotated[
        bool,
        Field(
            default=False,
            description="[INTERNAL] Preview structure without creating package (for testing)",
            json_schema_extra={"importance": "internal"},
        ),
    ]
    force: Annotated[
        bool,
        Field(
            default=False,
            description="[INTERNAL] Skip confirmation prompts (useful for automated ingestion)",
            json_schema_extra={"importance": "internal"},
        ),
    ]
    metadata: Annotated[
        Optional[dict[str, Any]],
        Field(
            default=None,
            description="[INTERNAL] Additional user-provided metadata (rarely needed)",
            json_schema_extra={"importance": "internal"},
        ),
    ]

    model_config = {
        "json_schema_extra": {
            "examples": [
                # Minimal example (most common)
                {
                    "source_bucket": "my-data-bucket",
                    "package_name": "team/dataset",
                },
                # With description
                {
                    "source_bucket": "research-data",
                    "package_name": "team/experiment-results",
                    "description": "Results from Q1 2024 experiments",
                },
                # With filtering
                {
                    "source_bucket": "my-data-bucket",
                    "package_name": "team/csv-data",
                    "source_prefix": "data/",
                    "include_patterns": ["*.csv"],
                },
            ]
        }
    }


# ============================================================================
# Catalog Input Models
# ============================================================================


class CatalogUrlParams(BaseModel):
    """Parameters for catalog_url tool."""

    registry: Annotated[
        str,
        Field(
            description="Target registry as S3 URI or bare bucket name",
            examples=["s3://my-bucket", "my-bucket"],
        ),
    ]
    package_name: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Optional package name in namespace/name format for direct package view",
            examples=["team/dataset", "user/analysis"],
        ),
    ]
    path: Annotated[
        str,
        Field(
            default="",
            description="Optional path inside the bucket or package for deep links",
            examples=["data/metrics.csv", "reports/"],
        ),
    ]
    catalog_host: Annotated[
        str,
        Field(
            default="",
            description="Optional override for catalog host (auto-detected if not provided)",
            examples=["catalog.example.com", "https://catalog.example.com"],
        ),
    ]


class CatalogUriParams(BaseModel):
    """Parameters for catalog_uri tool."""

    registry: Annotated[
        str,
        Field(
            description="Registry backing the URI as S3 URI or bucket name",
            examples=["s3://my-bucket", "my-bucket"],
        ),
    ]
    package_name: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Optional package name in namespace/name format",
        ),
    ]
    path: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Optional path fragment to include in the URI",
        ),
    ]
    top_hash: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Optional immutable package hash to lock the reference",
        ),
    ]
    tag: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Optional human-friendly tag (ignored when top_hash is provided)",
        ),
    ]
    catalog_host: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Optional catalog hostname hint to embed in the fragment",
        ),
    ]


# ============================================================================
# Data Visualization Input Models
# ============================================================================


class DataVisualizationParams(BaseModel):
    """Parameters for creating data visualizations from tabular data.

    Basic usage requires data, plot_type, x_column, and y_column.
    All other parameters have sensible defaults for quick visualization.
    """

    # === REQUIRED: Core Parameters ===
    data: Annotated[
        dict[str, list] | list[dict[str, str | int | float]] | str,
        Field(
            description="Source data as dict of columns, list of row dicts, CSV/TSV string, or S3 URI",
            examples=[
                {"gene": ["BRCA1", "TP53"], "expression": [42.5, 38.1]},
                [{"gene": "BRCA1", "expression": 42.5}, {"gene": "TP53", "expression": 38.1}],
                "gene,expression\nBRCA1,42.5\nTP53,38.1",
                "s3://bucket/data.csv",
            ],
            json_schema_extra={"importance": "required"},
        ),
    ]
    plot_type: Annotated[
        Literal["boxplot", "scatter", "line", "bar"],
        Field(
            description="Visualization type to generate",
            json_schema_extra={"importance": "required"},
        ),
    ]
    x_column: Annotated[
        str,
        Field(
            description="Column name for x-axis (category or numeric depending on plot type)",
            examples=["gene", "sample_id", "timestamp"],
            json_schema_extra={"importance": "required"},
        ),
    ]
    y_column: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Column name for y-axis (required for all plot types)",
            examples=["expression", "value", "count"],
            json_schema_extra={"importance": "required"},
        ),
    ]

    # === COMMON: Frequently Used Options ===
    group_column: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Optional column for grouping/coloring (scatter/line/bar)",
            examples=["condition", "treatment", "category"],
            json_schema_extra={"importance": "common"},
        ),
    ]
    title: Annotated[
        str,
        Field(
            default="",
            description="Chart title (auto-generated if empty)",
            json_schema_extra={"importance": "common"},
        ),
    ]

    # === ADVANCED: Fine-tuning Options ===
    xlabel: Annotated[
        str,
        Field(
            default="",
            description="[ADVANCED] X-axis label (defaults to x_column name if empty)",
            json_schema_extra={"importance": "advanced"},
        ),
    ]
    ylabel: Annotated[
        str,
        Field(
            default="",
            description="[ADVANCED] Y-axis label (defaults to y_column name if empty)",
            json_schema_extra={"importance": "advanced"},
        ),
    ]
    color_scheme: Annotated[
        Literal["genomics", "ml", "research", "analytics", "default"],
        Field(
            default="genomics",
            description="[ADVANCED] Color palette to use for the visualization",
            json_schema_extra={"importance": "advanced"},
        ),
    ]
    template: Annotated[
        str,
        Field(
            default="research",
            description="[ADVANCED] Metadata template label for quilt_summarize.json",
            json_schema_extra={"importance": "advanced"},
        ),
    ]
    output_format: Annotated[
        Literal["echarts"],
        Field(
            default="echarts",
            description="[ADVANCED] Visualization engine (currently only 'echarts' is supported)",
            json_schema_extra={"importance": "advanced"},
        ),
    ]

    model_config = {
        "json_schema_extra": {
            "examples": [
                # Minimal example (most common)
                {
                    "data": {"gene": ["BRCA1", "TP53"], "expression": [42.5, 38.1]},
                    "plot_type": "boxplot",
                    "x_column": "gene",
                    "y_column": "expression",
                },
                # With grouping
                {
                    "data": "s3://bucket/experiment.csv",
                    "plot_type": "scatter",
                    "x_column": "time",
                    "y_column": "measurement",
                    "group_column": "condition",
                    "title": "Experimental Results Over Time",
                },
                # Full customization
                {
                    "data": [
                        {"gene": "BRCA1", "expression": 42.5, "condition": "control"},
                        {"gene": "BRCA1", "expression": 45.2, "condition": "treated"},
                    ],
                    "plot_type": "bar",
                    "x_column": "gene",
                    "y_column": "expression",
                    "group_column": "condition",
                    "title": "Gene Expression Comparison",
                    "xlabel": "Gene Name",
                    "ylabel": "Expression Level",
                    "color_scheme": "ml",
                },
            ]
        }
    }


# ============================================================================
# Workflow Input Models
# ============================================================================


class WorkflowCreateParams(BaseModel):
    """Parameters for workflow_create tool."""

    workflow_id: Annotated[
        str,
        Field(
            description="Unique identifier for the workflow",
            examples=["wf-123", "data-pipeline-001"],
        ),
    ]
    name: Annotated[
        str,
        Field(
            description="Human-readable name for the workflow",
            examples=["Data Processing Pipeline", "Analysis Workflow"],
        ),
    ]
    description: Annotated[
        str,
        Field(
            default="",
            description="Optional description of the workflow purpose",
        ),
    ]
    metadata: Annotated[
        Optional[dict[str, str | int | float | bool]],
        Field(
            default=None,
            description="Optional metadata dictionary for the workflow",
        ),
    ]


class WorkflowAddStepParams(BaseModel):
    """Parameters for workflow_add_step tool."""

    workflow_id: Annotated[
        str,
        Field(
            description="ID of the workflow to add step to",
        ),
    ]
    step_id: Annotated[
        str,
        Field(
            description="Unique identifier for this step",
            examples=["step-1", "upload-data", "process-files"],
        ),
    ]
    description: Annotated[
        str,
        Field(
            description="Description of what this step does",
            examples=["Upload raw data files", "Process uploaded files"],
        ),
    ]
    step_type: Annotated[
        str,
        Field(
            default="manual",
            description="Type of step (manual, automated, validation, etc.)",
        ),
    ]
    dependencies: Annotated[
        Optional[list[str]],
        Field(
            default=None,
            description="List of step IDs that must complete before this step",
            examples=[["step-0", "step-1"]],
        ),
    ]
    metadata: Annotated[
        Optional[dict[str, str | int | float | bool]],
        Field(
            default=None,
            description="Optional step-specific metadata",
        ),
    ]


class WorkflowUpdateStepParams(BaseModel):
    """Parameters for workflow_update_step tool."""

    workflow_id: Annotated[
        str,
        Field(
            description="ID of the workflow containing the step",
        ),
    ]
    step_id: Annotated[
        str,
        Field(
            description="ID of the step to update",
        ),
    ]
    status: Annotated[
        Literal["pending", "in_progress", "completed", "failed", "skipped"],
        Field(
            description="New status for the step",
        ),
    ]
    result: Annotated[
        Optional[dict],
        Field(
            default=None,
            description="Optional result data from step execution",
        ),
    ]
    error_message: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Optional error message if step failed",
        ),
    ]


class WorkflowGetStatusParams(BaseModel):
    """Parameters for workflow_get_status tool."""

    workflow_id: Annotated[
        str,
        Field(
            description="ID of the workflow to get status for",
            examples=["wf-123", "analysis-workflow-456"],
        ),
    ]


class WorkflowListAllParams(BaseModel):
    """Parameters for workflow_list_all tool."""

    # No parameters needed for list_all - but we keep the class for consistency
    pass


class WorkflowTemplateApplyParams(BaseModel):
    """Parameters for workflow_template_apply tool."""

    template_name: Annotated[
        Literal[
            "cross-package-aggregation",
            "environment-promotion",
            "longitudinal-analysis",
            "data-validation",
        ],
        Field(
            description="Name of the template to apply",
        ),
    ]
    workflow_id: Annotated[
        str,
        Field(
            description="ID for the new workflow to create from template",
            examples=["wf-aggregation-123", "wf-promotion-456"],
        ),
    ]
    params: Annotated[
        dict[str, str | int | list | dict],
        Field(
            description="Parameters to customize the template (varies by template type)",
            examples=[
                {
                    "source_packages": ["team/data1", "team/data2"],
                    "target_package": "team/aggregated",
                }
            ],
        ),
    ]

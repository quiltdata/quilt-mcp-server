"""Pydantic models for MCP tool input parameters.

This module defines rigorous type models for tool inputs,
ensuring MCP generates useful input schemas and provides
proper validation for tool parameters.
"""

from __future__ import annotations

from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field, conint, constr


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


class BucketObjectsPutItem(BaseModel):
    """A single item to upload to S3."""

    key: Annotated[
        str,
        Field(
            description="S3 key (path) for the object",
            examples=["data/results.csv", "reports/summary.txt"],
        ),
    ]
    text: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Text content to upload (use this OR data, not both)",
        ),
    ]
    data: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Base64-encoded binary content to upload (use this OR text, not both)",
        ),
    ]
    content_type: Annotated[
        str,
        Field(
            default="application/octet-stream",
            description="MIME type of the content",
            examples=["text/csv", "application/json", "image/png"],
        ),
    ]
    encoding: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Text encoding (e.g., 'utf-8') when uploading text",
        ),
    ]
    metadata: Annotated[
        Optional[dict[str, str]],
        Field(
            default=None,
            description="Custom metadata key-value pairs to attach to the object",
        ),
    ]


class BucketObjectsPutParams(BaseModel):
    """Parameters for bucket_objects_put tool."""

    bucket: Annotated[
        str,
        Field(
            description="S3 bucket name or s3:// URI",
            examples=["my-bucket", "s3://my-bucket"],
        ),
    ]
    items: Annotated[
        list[BucketObjectsPutItem],
        Field(
            description="List of objects to upload, each with key and content",
            min_length=1,
        ),
    ]


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
        Optional[dict[str, str | int | float | bool]],
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
        Optional[str],
        Field(
            default=None,
            description="Optional path inside the bucket or package for deep links",
            examples=["data/metrics.csv", "reports/"],
        ),
    ]
    catalog_host: Annotated[
        Optional[str],
        Field(
            default=None,
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
# Athena Query Input Models
# ============================================================================


class AthenaQueryExecuteParams(BaseModel):
    """Parameters for athena_query_execute tool."""

    query: Annotated[
        str,
        Field(
            description="SQL query to execute (use double quotes for identifiers, not backticks)",
            examples=[
                'SELECT * FROM "my-table" LIMIT 10',
                "SELECT COUNT(*) FROM dataset WHERE status = 'READY'",
            ],
        ),
    ]
    database_name: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Default database for query context (auto-discovered if not provided)",
        ),
    ]
    workgroup_name: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Athena workgroup to use (auto-discovered if not provided)",
        ),
    ]
    data_catalog_name: Annotated[
        str,
        Field(
            default="AwsDataCatalog",
            description="Data catalog to use",
        ),
    ]
    max_results: Annotated[
        int,
        Field(
            default=1000,
            ge=1,
            le=10000,
            description="Maximum number of results to return (1-10000)",
        ),
    ]
    output_format: Annotated[
        Literal["json", "csv", "parquet", "table"],
        Field(
            default="json",
            description="Output format for results",
        ),
    ]
    use_quilt_auth: Annotated[
        bool,
        Field(
            default=True,
            description="Use Quilt assumed role credentials if available",
        ),
    ]


class AthenaQueryValidateParams(BaseModel):
    """Parameters for athena_query_validate tool."""

    query: Annotated[
        str,
        Field(
            description="SQL query to validate (without executing)",
            examples=['SELECT * FROM "my-table"'],
        ),
    ]


# ============================================================================
# Data Visualization Input Models
# ============================================================================


class DataVisualizationParams(BaseModel):
    """Parameters for create_data_visualization tool."""

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
        ),
    ]
    plot_type: Annotated[
        Literal["boxplot", "scatter", "line", "bar"],
        Field(
            description="Visualization type to generate",
        ),
    ]
    x_column: Annotated[
        str,
        Field(
            description="Column name for x-axis (category or numeric depending on plot type)",
            examples=["gene", "sample_id", "timestamp"],
        ),
    ]
    y_column: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Column name for y-axis (required for all plot types)",
            examples=["expression", "value", "count"],
        ),
    ]
    group_column: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Optional column for grouping/coloring (scatter/line/bar)",
            examples=["condition", "treatment", "category"],
        ),
    ]
    title: Annotated[
        str,
        Field(
            default="",
            description="Chart title (auto-generated if empty)",
        ),
    ]
    xlabel: Annotated[
        str,
        Field(
            default="",
            description="X-axis label (defaults to x_column name if empty)",
        ),
    ]
    ylabel: Annotated[
        str,
        Field(
            default="",
            description="Y-axis label (defaults to y_column name if empty)",
        ),
    ]
    color_scheme: Annotated[
        Literal["genomics", "ml", "research", "analytics", "default"],
        Field(
            default="genomics",
            description="Color palette to use for the visualization",
        ),
    ]
    template: Annotated[
        str,
        Field(
            default="research",
            description="Metadata template label for quilt_summarize.json",
        ),
    ]
    output_format: Annotated[
        Literal["echarts"],
        Field(
            default="echarts",
            description="Visualization engine (currently only 'echarts' is supported)",
        ),
    ]


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

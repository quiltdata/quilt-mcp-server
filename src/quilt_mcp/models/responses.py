"""Pydantic models for MCP tool responses.

This module defines rigorous type models for tool return values,
replacing generic Dict[str, Any] with structured, validated responses.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ============================================================================
# Base Response Models
# ============================================================================


class SuccessResponse(BaseModel):
    """Base model for successful operations."""

    success: Literal[True] = True


class ErrorResponse(BaseModel):
    """Base model for error responses."""

    success: Literal[False] = False
    error: str
    cause: Optional[str] = None
    possible_fixes: Optional[list[str]] = None
    suggested_actions: Optional[list[str]] = None


# ============================================================================
# Catalog Tool Responses
# ============================================================================


class CatalogUrlSuccess(SuccessResponse):
    """Response from catalog_url when successful."""

    status: Literal["success"] = "success"
    catalog_url: str
    view_type: Literal["package", "bucket"]
    bucket: str
    package_name: Optional[str] = None
    path: Optional[str] = None
    catalog_host: Optional[str] = None


class CatalogUrlError(BaseModel):
    """Response from catalog_url when failed."""

    status: Literal["error"] = "error"
    error: str


class CatalogUriSuccess(SuccessResponse):
    """Response from catalog_uri when successful."""

    status: Literal["success"] = "success"
    quilt_plus_uri: str
    bucket: str
    package_name: Optional[str] = None
    path: Optional[str] = None
    top_hash: Optional[str] = None
    tag: Optional[str] = None
    catalog_host: Optional[str] = None


class CatalogUriError(BaseModel):
    """Response from catalog_uri when failed."""

    status: Literal["error"] = "error"
    error: str


# ============================================================================
# S3/Bucket Tool Responses
# ============================================================================


class S3Object(BaseModel):
    """Metadata for a single S3 object."""

    key: str
    s3_uri: str
    size: int
    last_modified: str  # ISO datetime string
    etag: str
    storage_class: Optional[str] = None
    signed_url: Optional[str] = None
    signed_url_expiry: Optional[int] = None


class BucketObjectsListSuccess(SuccessResponse):
    """Response from bucket_objects_list when successful."""

    bucket: str
    prefix: str = ""
    objects: list[S3Object]
    count: int
    is_truncated: bool = False
    next_continuation_token: Optional[str] = None
    auth_type: Optional[str] = None


class BucketObjectsListError(BaseModel):
    """Response from bucket_objects_list when failed."""

    error: str
    bucket: str
    prefix: Optional[str] = None


class ObjectMetadata(BaseModel):
    """Detailed metadata for a single S3 object."""

    bucket: str
    key: str
    s3_uri: str
    size: int
    content_type: Optional[str] = None
    last_modified: str  # ISO datetime string
    etag: str
    version_id: Optional[str] = None
    metadata: dict[str, str] = Field(default_factory=dict)
    storage_class: Optional[str] = None


class BucketObjectInfoSuccess(SuccessResponse):
    """Response from bucket_object_info when successful."""

    object: ObjectMetadata
    auth_type: Optional[str] = None


class BucketObjectInfoError(BaseModel):
    """Response from bucket_object_info when failed."""

    error: str
    bucket: Optional[str] = None
    key: Optional[str] = None


class PresignedUrlResponse(SuccessResponse):
    """Response from bucket_object_link with presigned URL."""

    bucket: str
    key: str
    s3_uri: str
    signed_url: str
    expiration_seconds: int
    expires_at: str  # ISO datetime string
    auth_type: Optional[str] = None


class BucketObjectTextSuccess(SuccessResponse):
    """Response from bucket_object_text when successful."""

    bucket: str
    key: str
    s3_uri: str
    text: str
    encoding: str
    bytes_read: int
    truncated: bool
    auth_type: Optional[str] = None


class BucketObjectTextError(BaseModel):
    """Response from bucket_object_text when failed."""

    error: str
    bucket: Optional[str] = None
    key: Optional[str] = None


class BucketObjectFetchSuccess(SuccessResponse):
    """Response from bucket_object_fetch when successful."""

    bucket: str
    key: str
    s3_uri: str
    data: str  # Base64-encoded or text depending on base64_encode param
    content_type: Optional[str] = None
    bytes_read: int
    truncated: bool
    is_base64: bool
    auth_type: Optional[str] = None


class BucketObjectFetchError(BaseModel):
    """Response from bucket_object_fetch when failed."""

    error: str
    bucket: Optional[str] = None
    key: Optional[str] = None


class UploadResult(BaseModel):
    """Result of uploading a single object."""

    key: str
    etag: Optional[str] = None
    size: Optional[int] = None
    content_type: Optional[str] = None
    error: Optional[str] = None


class BucketObjectsPutSuccess(SuccessResponse):
    """Response from bucket_objects_put when successful."""

    bucket: str
    requested: int
    uploaded: int
    failed: int
    results: list[UploadResult]
    auth_type: Optional[str] = None


class BucketObjectsPutError(BaseModel):
    """Response from bucket_objects_put when failed."""

    error: str
    bucket: str


# ============================================================================
# Package Tool Responses
# ============================================================================


class PackageFileEntry(BaseModel):
    """A single file entry in a package."""

    logical_key: str
    physical_key: str
    size: int
    hash: Optional[str] = None
    meta: Optional[dict[str, str]] = None


class PackageMetadata(BaseModel):
    """Package metadata."""

    user_meta: dict[str, str] = Field(default_factory=dict)
    version: Optional[str] = None
    message: Optional[str] = None


class PackageBrowseSuccess(SuccessResponse):
    """Response from package_browse when successful."""

    package_name: str
    registry: str
    top_hash: str
    entries: list[PackageFileEntry]
    metadata: PackageMetadata
    total_size: int
    file_count: int


class PackageCreateSuccess(SuccessResponse):
    """Response from package_create when successful."""

    package_name: str
    registry: str
    top_hash: str
    message: str
    files_added: int
    total_size: int
    catalog_url: Optional[str] = None


class PackageCreateError(ErrorResponse):
    """Response from package_create when failed."""

    provided_type: Optional[str] = None
    expected: Optional[str] = None
    examples: Optional[list[str]] = None
    tip: Optional[str] = None
    json_error: Optional[str] = None


# ============================================================================
# Athena Query Responses
# ============================================================================


class QueryExecutionMetadata(BaseModel):
    """Metadata about query execution."""

    query_execution_id: str
    state: str
    state_change_reason: Optional[str] = None
    data_scanned_bytes: Optional[int] = None
    execution_time_ms: Optional[int] = None
    workgroup: Optional[str] = None
    database: Optional[str] = None


class AthenaQuerySuccess(SuccessResponse):
    """Response from athena_query_execute when successful."""

    query: str
    columns: list[str]
    data: list[dict[str, str]]  # Row data with string values
    formatted_data: list[dict[str, str | int | float | bool | None]]  # Typed row data
    row_count: int
    execution: QueryExecutionMetadata
    output_format: Literal["json", "csv", "parquet", "table"]


class AthenaQueryError(ErrorResponse):
    """Response from athena_query_execute when failed."""

    query: Optional[str] = None
    state: Optional[str] = None
    state_change_reason: Optional[str] = None


class AthenaQueryValidationSuccess(SuccessResponse):
    """Response from athena_query_validate when query is valid."""

    query: str
    valid: Literal[True] = True
    suggestions: list[str] = Field(default_factory=list)


class AthenaQueryValidationError(ErrorResponse):
    """Response from athena_query_validate when query is invalid."""

    query: str
    valid: Literal[False] = False
    syntax_errors: list[str]


# ============================================================================
# Data Visualization Responses
# ============================================================================


class VisualizationFile(BaseModel):
    """A file to be uploaded for visualization."""

    key: str
    text: str
    content_type: str


class VisualizationConfig(BaseModel):
    """ECharts visualization configuration."""

    type: Literal["boxplot", "scatter", "line", "bar"]
    option: dict  # ECharts option object
    filename: str


class DataVisualizationSuccess(SuccessResponse):
    """Response from create_data_visualization when successful."""

    visualization_config: VisualizationConfig
    data_file: VisualizationFile
    quilt_summarize: VisualizationFile
    files_to_upload: list[VisualizationFile]
    metadata: dict[str, str | int | float]


class DataVisualizationError(ErrorResponse):
    """Response from create_data_visualization when failed."""

    plot_type: Optional[str] = None
    x_column: Optional[str] = None
    y_column: Optional[str] = None


# ============================================================================
# Workflow Orchestration Responses
# ============================================================================


class WorkflowStep(BaseModel):
    """A step in a workflow."""

    step_id: str
    description: str
    status: Literal["pending", "in_progress", "completed", "failed", "skipped"]
    step_type: str = "manual"
    dependencies: list[str] = Field(default_factory=list)
    result: Optional[dict] = None
    error_message: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class WorkflowCreateSuccess(SuccessResponse):
    """Response from workflow_create."""

    workflow_id: str
    name: str
    description: str
    status: Literal["created"] = "created"
    steps: list[WorkflowStep] = Field(default_factory=list)
    created_at: str


class WorkflowStepUpdateSuccess(SuccessResponse):
    """Response from workflow_update_step."""

    workflow_id: str
    step_id: str
    old_status: str
    new_status: str
    updated_at: str


# ============================================================================
# Type Aliases for Union Types
# ============================================================================

# Catalog responses
CatalogUrlResponse = CatalogUrlSuccess | CatalogUrlError
CatalogUriResponse = CatalogUriSuccess | CatalogUriError

# Bucket responses
BucketObjectsListResponse = BucketObjectsListSuccess | BucketObjectsListError
BucketObjectInfoResponse = BucketObjectInfoSuccess | BucketObjectInfoError
BucketObjectTextResponse = BucketObjectTextSuccess | BucketObjectTextError
BucketObjectFetchResponse = BucketObjectFetchSuccess | BucketObjectFetchError
BucketObjectsPutResponse = BucketObjectsPutSuccess | BucketObjectsPutError

# Package responses
PackageBrowseResponse = PackageBrowseSuccess | ErrorResponse
PackageCreateResponse = PackageCreateSuccess | PackageCreateError

# Athena responses
AthenaQueryResponse = AthenaQuerySuccess | AthenaQueryError
AthenaQueryValidationResponse = AthenaQueryValidationSuccess | AthenaQueryValidationError

# Visualization responses
DataVisualizationResponse = DataVisualizationSuccess | DataVisualizationError

# Workflow responses
WorkflowCreateResponse = WorkflowCreateSuccess | ErrorResponse
WorkflowStepUpdateResponse = WorkflowStepUpdateSuccess | ErrorResponse

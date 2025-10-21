"""Pydantic models for MCP tool responses.

This module defines rigorous type models for tool return values,
replacing generic Dict[str, Any] with structured, validated responses.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class DictAccessibleModel(BaseModel):
    """Base model that supports dict-like access for backward compatibility."""

    def __getitem__(self, key: str) -> Any:
        """Allow dict-like access to model fields."""
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        """Support dict.get() method."""
        try:
            return getattr(self, key)
        except AttributeError:
            return default

    def __contains__(self, key: str) -> bool:
        """Support 'key in model' checks."""
        return hasattr(self, key)


# ============================================================================
# Base Response Models
# ============================================================================


class SuccessResponse(DictAccessibleModel):
    """Base model for successful operations."""

    success: Literal[True] = True


class ErrorResponse(DictAccessibleModel):
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


class CatalogUrlError(ErrorResponse):
    """Response from catalog_url when failed."""

    pass  # Inherits error field from ErrorResponse


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


class CatalogUriError(ErrorResponse):
    """Response from catalog_uri when failed."""

    pass  # Inherits error field from ErrorResponse


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


class PackageSummary(BaseModel):
    """Summary statistics for a package."""

    total_size: int
    total_size_human: str
    file_types: list[str]
    total_files: int
    total_directories: int


class PackageBrowseSuccess(SuccessResponse):
    """Response from package_browse when successful."""

    package_name: str
    registry: str
    total_entries: int
    summary: PackageSummary
    view_type: Literal["recursive", "flat"]
    file_tree: Optional[dict] = None  # Recursive tree structure
    entries: list[dict]  # List of entry data with logical_key, physical_key, size, etc.
    metadata: Optional[dict] = None  # Package metadata if available


class PackageCreateSuccess(SuccessResponse):
    """Response from package_create when successful."""

    package_name: str
    registry: str
    top_hash: str
    message: str
    files_added: int
    total_size: int = 0  # Default to 0 if not calculated
    package_url: Optional[str] = None  # Catalog URL for viewing the package
    files: list[dict[str, str]] = Field(default_factory=list)  # List of file entries
    warnings: list[str] = Field(default_factory=list)  # Any warnings during creation
    auth_type: Optional[str] = None  # Authentication type used


class PackageCreateError(ErrorResponse):
    """Response from package_create when failed."""

    package_name: Optional[str] = None
    registry: Optional[str] = None
    provided_type: Optional[str] = None
    expected: Optional[str] = None
    examples: Optional[list[str]] = None
    tip: Optional[str] = None
    json_error: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)


class PackageUpdateSuccess(SuccessResponse):
    """Response from package_update when successful."""

    status: Literal["success"] = "success"
    action: Literal["updated"] = "updated"
    package_name: str
    registry: str
    top_hash: str
    files_added: int  # Number of files added
    package_url: Optional[str] = None  # Catalog URL for viewing the package
    files: list[dict[str, str]] = Field(default_factory=list)  # List of {"logical_path": str, "source": str}
    warnings: list[str] = Field(default_factory=list)
    message: str
    auth_type: Optional[str] = None


class PackageUpdateError(ErrorResponse):
    """Response from package_update when failed."""

    package_name: Optional[str] = None
    registry: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)


class PackageDeleteSuccess(SuccessResponse):
    """Response from package_delete when successful."""

    status: Literal["success"] = "success"
    action: Literal["deleted"] = "deleted"
    package_name: str
    registry: str
    message: str
    auth_type: Optional[str] = None


class PackageDeleteError(ErrorResponse):
    """Response from package_delete when failed."""

    package_name: Optional[str] = None
    registry: Optional[str] = None


class PackagesListSuccess(SuccessResponse):
    """Response from packages_list when successful."""

    packages: list[str]
    count: int = Field(description="Number of packages returned")
    registry: Optional[str] = None
    prefix_filter: Optional[str] = None


class PackagesListError(ErrorResponse):
    """Response from packages_list when failed."""

    registry: Optional[str] = None


class PackageDiffSuccess(SuccessResponse):
    """Response from package_diff when successful."""

    package1: str
    package2: str
    package1_hash: str
    package2_hash: str
    registry: str
    diff: dict  # Quilt3's diff result


class PackageDiffError(ErrorResponse):
    """Response from package_diff when failed."""

    package1: Optional[str] = None
    package2: Optional[str] = None


class FolderInfo(BaseModel):
    """Information about an organized folder."""

    file_count: int
    sample_files: list[str] = Field(max_length=3)


class PackageCreateFromS3Success(SuccessResponse):
    """Response from package_create_from_s3 when successful."""

    action: Literal["created", "preview"]
    package_name: str
    registry: str
    structure: dict  # folders_created, files_organized, readme_generated
    metadata_info: dict  # package_size_mb, file_types, organization_applied
    confirmation: dict  # bucket_suggested, structure_preview, etc.
    package_hash: Optional[str] = None
    created_at: Optional[str] = None
    summary_files: Optional[dict] = None
    readme_preview: Optional[str] = None
    metadata_preview: Optional[dict] = None
    message: Optional[str] = None


class PackageCreateFromS3Error(ErrorResponse):
    """Response from package_create_from_s3 when failed."""

    bucket: Optional[str] = None
    package_name: Optional[str] = None
    registry: Optional[str] = None
    provided: Optional[str] = None
    expected: Optional[str] = None
    example: Optional[str] = None
    tip: Optional[str] = None
    fix: Optional[str] = None
    debug_info: Optional[dict] = None


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


class DatabaseInfo(BaseModel):
    """Information about an Athena/Glue database."""

    name: str
    description: str = ""
    location_uri: str = ""
    create_time: Optional[str] = None
    parameters: dict[str, str] = Field(default_factory=dict)


class AthenaDatabasesListSuccess(SuccessResponse):
    """Response from athena_databases_list when successful."""

    databases: list[DatabaseInfo]
    data_catalog_name: str
    count: int


class TableInfo(BaseModel):
    """Information about an Athena/Glue table."""

    name: str
    database_name: str
    description: str = ""
    owner: str = ""
    create_time: Optional[str] = None
    update_time: Optional[str] = None
    table_type: str = ""
    storage_descriptor: dict = Field(default_factory=dict)
    partition_keys: list[dict] = Field(default_factory=list)
    parameters: dict[str, str] = Field(default_factory=dict)


class AthenaTablesListSuccess(SuccessResponse):
    """Response from athena_tables_list when successful."""

    tables: list[TableInfo]
    database_name: str
    data_catalog_name: str
    count: int


class ColumnInfo(BaseModel):
    """Information about a table column."""

    name: str
    type: str
    comment: str = ""
    parameters: dict[str, str] = Field(default_factory=dict)


class PartitionInfo(BaseModel):
    """Information about a table partition."""

    name: str
    type: str
    comment: str = ""


class TableSchemaInfo(BaseModel):
    """Detailed schema information for a table."""

    table_name: str
    database_name: str
    data_catalog_name: str
    columns: list[ColumnInfo]
    partitions: list[PartitionInfo] = Field(default_factory=list)
    table_type: str = ""
    description: str = ""
    owner: str = ""
    create_time: Optional[str] = None
    update_time: Optional[str] = None
    storage_descriptor: dict = Field(default_factory=dict)
    parameters: dict[str, str] = Field(default_factory=dict)


class AthenaTableSchemaSuccess(SuccessResponse):
    """Response from athena_table_schema when successful."""

    success: Literal[True] = True
    table_name: str
    database_name: str
    data_catalog_name: str
    columns: list[ColumnInfo]
    partitions: list[PartitionInfo]
    table_type: str = ""
    description: str = ""
    owner: str = ""
    create_time: Optional[str] = None
    update_time: Optional[str] = None
    storage_descriptor: dict = Field(default_factory=dict)
    parameters: dict[str, str] = Field(default_factory=dict)


class WorkgroupInfo(BaseModel):
    """Information about an Athena workgroup."""

    name: str
    description: str = ""
    creation_time: Optional[datetime] = None
    output_location: Optional[str] = None
    enforce_workgroup_config: bool = False


class AthenaWorkgroupsListSuccess(SuccessResponse):
    """Response from athena_workgroups_list when successful."""

    workgroups: list[WorkgroupInfo]
    region: str
    count: int


class QueryHistoryEntry(BaseModel):
    """A single query execution from history."""

    query_execution_id: str
    query: str
    status: str
    submission_time: Optional[str] = None
    completion_time: Optional[str] = None
    execution_time_ms: Optional[int] = None
    data_scanned_bytes: Optional[int] = None
    result_location: Optional[str] = None
    work_group: Optional[str] = None
    database: Optional[str] = None
    error_message: Optional[str] = None


class AthenaQueryHistorySuccess(SuccessResponse):
    """Response from athena_query_history when successful."""

    query_history: list[QueryHistoryEntry]
    count: int
    filters: dict[str, str | int | None]


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

    type: Literal["echarts"]  # Visualization engine type
    option: dict  # ECharts option object
    filename: str


class DataVisualizationSuccess(SuccessResponse):
    """Response from create_data_visualization when successful."""

    visualization_config: VisualizationConfig
    data_file: VisualizationFile
    quilt_summarize: VisualizationFile
    files_to_upload: list[VisualizationFile]
    metadata: dict  # Contains plot_type, statistics (dict), data_points, visualization_engine, columns_used (list)


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


class WorkflowAddStepSuccess(SuccessResponse):
    """Response from workflow_add_step."""

    workflow_id: str
    step_id: str
    step: WorkflowStep
    workflow_summary: dict[str, int | str]
    message: str


class WorkflowProgress(DictAccessibleModel):
    """Progress information for a workflow."""

    total_steps: int
    completed_steps: int
    failed_steps: int
    in_progress_steps: int
    pending_steps: int
    percentage: float


class WorkflowGetStatusSuccess(SuccessResponse):
    """Response from workflow_get_status."""

    workflow: dict  # Full workflow data
    progress: WorkflowProgress
    next_available_steps: list[str]
    can_proceed: bool
    recent_activity: list[dict]
    recommendations: list[str]


class WorkflowSummary(BaseModel):
    """Summary of a single workflow."""

    id: str
    name: str
    status: Literal["created", "in_progress", "completed", "failed", "cancelled"]
    progress: dict[str, int | float]
    created_at: str
    updated_at: str


class WorkflowListAllSuccess(SuccessResponse):
    """Response from workflow_list_all."""

    workflows: list[WorkflowSummary]
    total_workflows: int
    active_workflows: int
    completed_workflows: int


class WorkflowTemplateApplySuccess(SuccessResponse):
    """Response from workflow_template_apply."""

    workflow_id: str
    template_applied: str
    workflow: dict  # Full workflow data with template steps
    message: str
    next_steps: list[str]


# ============================================================================
# Error Recovery Responses
# ============================================================================


class HealthCheckSuccess(SuccessResponse):
    """Response from health_check_with_recovery."""

    overall_health: Literal["healthy", "degraded", "unhealthy"]
    health_results: dict[str, Any]  # Batch operation results
    recovery_recommendations: list[str]
    timestamp: str
    next_steps: list[str]


# ============================================================================
# Quilt Summary Responses
# ============================================================================


class QuiltSummarizeJson(SuccessResponse):
    """Response from generate_quilt_summarize_json - the complete summary structure."""

    package_info: dict[str, Any]  # name, namespace, version, etc.
    data_summary: dict[str, Any]  # total_files, file_types, sizes
    structure: dict[str, Any]  # folders, organization_type
    source: dict[str, Any]  # type, bucket, prefix
    documentation: dict[str, Any]  # readme_generated, metadata_complete
    quilt_metadata: dict[str, Any]  # User-provided metadata
    access: dict[str, Any]  # browse_command, catalog_url
    generated_at: str
    generator: str
    generator_version: str


class QuiltSummarizeJsonError(ErrorResponse):
    """Error response from generate_quilt_summarize_json."""

    package_name: str
    generated_at: str


class PackageVisualizationsSuccess(SuccessResponse):
    """Response from generate_package_visualizations."""

    visualizations: dict[str, Any]  # Keyed by viz type (file_type_distribution, etc.)
    count: int
    types: list[str]
    metadata: dict[str, Any]
    visualization_dashboards: list[dict[str, Any]]


class PackageVisualizationsError(ErrorResponse):
    """Error response from generate_package_visualizations."""

    visualizations: dict[str, Any] = {}
    count: int = 0


class QuiltSummaryFilesSuccess(SuccessResponse):
    """Response from create_quilt_summary_files."""

    summary_package: dict[str, Any]  # Contains quilt_summarize.json, README.md, visualizations
    files_generated: dict[str, bool]  # Which files were successfully created
    visualization_count: int
    next_steps: list[str]


class QuiltSummaryFilesError(ErrorResponse):
    """Error response from create_quilt_summary_files."""

    summary_package: dict[str, Any] = {}
    files_generated: dict[str, bool] = {}


# ============================================================================
# Search Responses
# ============================================================================


class SearchExplainSuccess(SuccessResponse):
    """Response from search_explain."""

    query: str
    explanation: dict[str, Any]  # Contains backend selection, query parsing, execution plan
    backends_selected: list[str]
    query_complexity: str
    estimated_results: Optional[int] = None


class SearchExplainError(ErrorResponse):
    """Error response from search_explain."""

    query: str


class SearchGraphQLSuccess(SuccessResponse):
    """Response from search_graphql."""

    data: Optional[dict[str, Any]] = None
    errors: Optional[list[dict[str, Any]]] = None


class SearchGraphQLError(ErrorResponse):
    """Error response from search_graphql."""

    pass


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
PackageUpdateResponse = PackageUpdateSuccess | PackageUpdateError
PackageDeleteResponse = PackageDeleteSuccess | PackageDeleteError
PackagesListResponse = PackagesListSuccess | PackagesListError
PackageDiffResponse = PackageDiffSuccess | PackageDiffError
PackageCreateFromS3Response = PackageCreateFromS3Success | PackageCreateFromS3Error

# Athena responses
AthenaQueryResponse = AthenaQuerySuccess | AthenaQueryError
AthenaQueryValidationResponse = AthenaQueryValidationSuccess | AthenaQueryValidationError
AthenaDatabasesListResponse = AthenaDatabasesListSuccess | ErrorResponse
AthenaTablesListResponse = AthenaTablesListSuccess | ErrorResponse
AthenaTableSchemaResponse = AthenaTableSchemaSuccess | ErrorResponse
AthenaWorkgroupsListResponse = AthenaWorkgroupsListSuccess | ErrorResponse
AthenaQueryHistoryResponse = AthenaQueryHistorySuccess | ErrorResponse

# Visualization responses
DataVisualizationResponse = DataVisualizationSuccess | DataVisualizationError

# Workflow responses
WorkflowCreateResponse = WorkflowCreateSuccess | ErrorResponse
WorkflowStepUpdateResponse = WorkflowStepUpdateSuccess | ErrorResponse
WorkflowAddStepResponse = WorkflowAddStepSuccess | ErrorResponse
WorkflowGetStatusResponse = WorkflowGetStatusSuccess | ErrorResponse
WorkflowListAllResponse = WorkflowListAllSuccess | ErrorResponse
WorkflowTemplateApplyResponse = WorkflowTemplateApplySuccess | ErrorResponse

# Search responses
SearchExplainResponse = SearchExplainSuccess | SearchExplainError
SearchGraphQLResponse = SearchGraphQLSuccess | SearchGraphQLError

# Quilt summary responses
QuiltSummarizeJsonResponse = QuiltSummarizeJson | QuiltSummarizeJsonError
PackageVisualizationsResponse = PackageVisualizationsSuccess | PackageVisualizationsError
QuiltSummaryFilesResponse = QuiltSummaryFilesSuccess | QuiltSummaryFilesError

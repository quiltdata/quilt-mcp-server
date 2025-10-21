"""Pydantic models for structured, type-safe MCP tool inputs and responses."""

from .inputs import (
    # Athena input models
    AthenaQueryExecuteParams,
    AthenaQueryValidateParams,
    # Bucket input models
    BucketObjectFetchParams,
    BucketObjectInfoParams,
    BucketObjectLinkParams,
    BucketObjectsPutItem,
    BucketObjectsPutParams,
    BucketObjectsListParams,
    # Catalog input models
    CatalogUriParams,
    CatalogUrlParams,
    # Data visualization input models
    DataVisualizationParams,
    # Package input models
    PackageBrowseParams,
    PackageCreateParams,
    # Workflow input models
    WorkflowAddStepParams,
    WorkflowCreateParams,
    WorkflowUpdateStepParams,
)
from .responses import (
    # Base responses
    ErrorResponse,
    SuccessResponse,
    # Catalog responses
    CatalogUriError,
    CatalogUriResponse,
    CatalogUriSuccess,
    CatalogUrlError,
    CatalogUrlResponse,
    CatalogUrlSuccess,
    # Bucket responses
    BucketObjectInfoError,
    BucketObjectInfoResponse,
    BucketObjectInfoSuccess,
    BucketObjectsListError,
    BucketObjectsListResponse,
    BucketObjectsListSuccess,
    ObjectMetadata,
    PresignedUrlResponse,
    S3Object,
    # Package responses
    PackageBrowseResponse,
    PackageBrowseSuccess,
    PackageCreateError,
    PackageCreateResponse,
    PackageCreateSuccess,
    PackageFileEntry,
    PackageMetadata,
    # Athena responses
    AthenaQueryError,
    AthenaQueryResponse,
    AthenaQuerySuccess,
    AthenaQueryValidationError,
    AthenaQueryValidationResponse,
    AthenaQueryValidationSuccess,
    QueryExecutionMetadata,
    # Visualization responses
    DataVisualizationError,
    DataVisualizationResponse,
    DataVisualizationSuccess,
    VisualizationConfig,
    VisualizationFile,
    # Workflow responses
    WorkflowCreateResponse,
    WorkflowCreateSuccess,
    WorkflowStep,
    WorkflowStepUpdateResponse,
    WorkflowStepUpdateSuccess,
)

__all__ = [
    # Input models - Athena
    "AthenaQueryExecuteParams",
    "AthenaQueryValidateParams",
    # Input models - Bucket
    "BucketObjectFetchParams",
    "BucketObjectInfoParams",
    "BucketObjectLinkParams",
    "BucketObjectsPutItem",
    "BucketObjectsPutParams",
    "BucketObjectsListParams",
    # Input models - Catalog
    "CatalogUriParams",
    "CatalogUrlParams",
    # Input models - Data visualization
    "DataVisualizationParams",
    # Input models - Package
    "PackageBrowseParams",
    "PackageCreateParams",
    # Input models - Workflow
    "WorkflowAddStepParams",
    "WorkflowCreateParams",
    "WorkflowUpdateStepParams",
    # Response models - Base
    "ErrorResponse",
    "SuccessResponse",
    # Catalog
    "CatalogUriError",
    "CatalogUriResponse",
    "CatalogUriSuccess",
    "CatalogUrlError",
    "CatalogUrlResponse",
    "CatalogUrlSuccess",
    # Bucket
    "BucketObjectInfoError",
    "BucketObjectInfoResponse",
    "BucketObjectInfoSuccess",
    "BucketObjectsListError",
    "BucketObjectsListResponse",
    "BucketObjectsListSuccess",
    "ObjectMetadata",
    "PresignedUrlResponse",
    "S3Object",
    # Package
    "PackageBrowseResponse",
    "PackageBrowseSuccess",
    "PackageCreateError",
    "PackageCreateResponse",
    "PackageCreateSuccess",
    "PackageFileEntry",
    "PackageMetadata",
    # Athena
    "AthenaQueryError",
    "AthenaQueryResponse",
    "AthenaQuerySuccess",
    "AthenaQueryValidationError",
    "AthenaQueryValidationResponse",
    "AthenaQueryValidationSuccess",
    "QueryExecutionMetadata",
    # Visualization
    "DataVisualizationError",
    "DataVisualizationResponse",
    "DataVisualizationSuccess",
    "VisualizationConfig",
    "VisualizationFile",
    # Workflow
    "WorkflowCreateResponse",
    "WorkflowCreateSuccess",
    "WorkflowStep",
    "WorkflowStepUpdateResponse",
    "WorkflowStepUpdateSuccess",
]

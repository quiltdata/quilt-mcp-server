"""Catalog_Config domain object for backend-agnostic catalog configuration representation.

This module defines the Catalog_Config dataclass that represents Quilt catalog
configuration information in a way that's independent of the underlying backend 
(quilt3 library or Platform GraphQL).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Catalog_Config:
    """Backend-agnostic catalog configuration information.

    This dataclass represents catalog configuration consistently across different backends,
    allowing MCP tools to work with Quilt catalog concepts rather than backend-specific types.

    Attributes:
        region: AWS region where the catalog is deployed
        api_gateway_endpoint: API Gateway endpoint URL for the catalog
        analytics_bucket: S3 bucket name used for analytics data
        stack_prefix: CloudFormation stack prefix (derived from analytics bucket)
        tabulator_data_catalog: Athena data catalog name for tabulator operations
    """

    region: str
    api_gateway_endpoint: str
    analytics_bucket: str
    stack_prefix: str
    tabulator_data_catalog: str

    def __post_init__(self) -> None:
        """Validate required fields after initialization."""
        # Validate region field
        if self.region is None:
            raise TypeError("region field is required and cannot be None")
        if not isinstance(self.region, str):
            raise TypeError("region field must be a string")
        if self.region == "":
            raise ValueError("region field cannot be empty")

        # Validate api_gateway_endpoint field
        if self.api_gateway_endpoint is None:
            raise TypeError("api_gateway_endpoint field is required and cannot be None")
        if not isinstance(self.api_gateway_endpoint, str):
            raise TypeError("api_gateway_endpoint field must be a string")
        if self.api_gateway_endpoint == "":
            raise ValueError("api_gateway_endpoint field cannot be empty")

        # Validate analytics_bucket field
        if self.analytics_bucket is None:
            raise TypeError("analytics_bucket field is required and cannot be None")
        if not isinstance(self.analytics_bucket, str):
            raise TypeError("analytics_bucket field must be a string")
        if self.analytics_bucket == "":
            raise ValueError("analytics_bucket field cannot be empty")

        # Validate stack_prefix field
        if self.stack_prefix is None:
            raise TypeError("stack_prefix field is required and cannot be None")
        if not isinstance(self.stack_prefix, str):
            raise TypeError("stack_prefix field must be a string")
        if self.stack_prefix == "":
            raise ValueError("stack_prefix field cannot be empty")

        # Validate tabulator_data_catalog field
        if self.tabulator_data_catalog is None:
            raise TypeError("tabulator_data_catalog field is required and cannot be None")
        if not isinstance(self.tabulator_data_catalog, str):
            raise TypeError("tabulator_data_catalog field must be a string")
        if self.tabulator_data_catalog == "":
            raise ValueError("tabulator_data_catalog field cannot be empty")

    def __hash__(self) -> int:
        """Custom hash implementation for the frozen dataclass."""
        return hash((
            self.region,
            self.api_gateway_endpoint,
            self.analytics_bucket,
            self.stack_prefix,
            self.tabulator_data_catalog
        ))

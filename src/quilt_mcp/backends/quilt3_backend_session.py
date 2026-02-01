"""
Quilt3_Backend session, configuration, and AWS operations mixin.

This module provides session management, catalog configuration, GraphQL queries,
and AWS boto3 client access for the Quilt3_Backend implementation.

This mixin uses self.quilt3, self.requests, and self.boto3 which are provided by Quilt3_Backend_Base.
"""

import logging
from typing import List, Dict, Any, Optional, TYPE_CHECKING

from quilt_mcp.ops.exceptions import AuthenticationError, BackendError, ValidationError, NotFoundError
from quilt_mcp.domain.auth_status import Auth_Status
from quilt_mcp.domain.catalog_config import Catalog_Config

if TYPE_CHECKING:
    from types import ModuleType

logger = logging.getLogger(__name__)


class Quilt3_Backend_Session:
    """Mixin for session, configuration, and AWS operations."""

    # Type hints for attributes provided by Quilt3_Backend_Base
    if TYPE_CHECKING:
        quilt3: "ModuleType"
        requests: "ModuleType"
        boto3: "ModuleType"

    def get_auth_status(self) -> Auth_Status:
        """Get current authentication status.

        Returns:
            Auth_Status object with authentication details

        Raises:
            BackendError: If auth status retrieval fails
        """
        try:
            logger.debug("Getting authentication status")

            # Get logged-in URL from quilt3
            logged_in_url: Optional[str] = None
            try:
                if hasattr(self.quilt3, 'logged_in'):
                    logged_in_url = self.quilt3.logged_in()
            except Exception as e:
                logger.debug(f"Failed to get logged_in URL: {e}")
                logged_in_url = None

            # Determine authentication status
            is_authenticated = bool(logged_in_url)

            # Extract catalog name from URL if authenticated
            catalog_name: Optional[str] = None
            if is_authenticated and logged_in_url:
                from quilt_mcp.utils import get_dns_name_from_url

                catalog_name = get_dns_name_from_url(logged_in_url)

            # Get registry URL if authenticated
            registry_url: Optional[str] = None
            if is_authenticated and logged_in_url:
                try:
                    catalog_config = self.get_catalog_config(logged_in_url)
                    registry_url = catalog_config.registry_url
                except Exception as e:
                    logger.debug(f"Failed to get registry URL: {e}")
                    registry_url = None

            auth_status = Auth_Status(
                is_authenticated=is_authenticated,
                logged_in_url=logged_in_url,
                catalog_name=catalog_name,
                registry_url=registry_url,
            )

            logger.debug(f"Auth status: authenticated={is_authenticated}, catalog={catalog_name}")
            return auth_status

        except Exception as e:
            logger.error(f"Auth status retrieval failed: {str(e)}")
            raise BackendError(f"Failed to get authentication status: {str(e)}")

    def get_catalog_config(self, catalog_url: str) -> Catalog_Config:
        """Get catalog configuration from the specified catalog URL.

        Retrieves the catalog configuration by fetching config.json from the catalog URL
        and transforming it into a Catalog_Config domain object.

        Args:
            catalog_url: URL of the catalog (e.g., 'https://example.quiltdata.com')

        Returns:
            Catalog_Config object with configuration details

        Raises:
            AuthenticationError: When authentication credentials are invalid or missing
            BackendError: When the backend operation fails or catalog is unreachable
            ValidationError: When catalog_url parameter is invalid
            NotFoundError: When catalog configuration is not found
        """
        try:
            logger.debug(f"Getting catalog config for: {catalog_url}")

            # Validate catalog URL
            if not catalog_url or not isinstance(catalog_url, str):
                raise ValidationError("Invalid catalog URL: must be a non-empty string")

            # Use quilt3 session to fetch config.json
            if not hasattr(self.quilt3, 'session') or not hasattr(self.quilt3.session, 'get_session'):
                raise AuthenticationError("quilt3 session not available - user may not be authenticated")

            session = self.quilt3.session.get_session()
            if session is None:
                raise AuthenticationError("No active quilt3 session - please run 'quilt3 login'")

            # Normalize URL and fetch config.json
            from quilt_mcp.utils import normalize_url

            normalized_url = normalize_url(catalog_url)
            config_url = f"{normalized_url}/config.json"

            logger.debug(f"Fetching config from: {config_url}")
            response = session.get(config_url, timeout=10)
            response.raise_for_status()

            full_config = response.json()
            logger.debug("Successfully fetched catalog configuration")

            # Transform to Catalog_Config domain object
            catalog_config = self._transform_catalog_config(full_config)

            logger.debug(f"Successfully retrieved catalog config for: {catalog_url}")
            return catalog_config

        except ValidationError:
            raise
        except AuthenticationError:
            raise
        except Exception as e:
            # Handle HTTP errors
            if hasattr(e, 'response') and e.response is not None:
                if e.response.status_code == 404:
                    raise NotFoundError(f"Catalog configuration not found at {catalog_url}")
                elif e.response.status_code == 403:
                    raise AuthenticationError(f"Access denied to catalog configuration at {catalog_url}")
                else:
                    raise BackendError(f"HTTP error fetching catalog config: {e}")
            # Handle network errors
            elif "Network" in str(e) or "Connection" in str(e):
                raise BackendError(f"Network error fetching catalog config: {e}")
            else:
                logger.error(f"Catalog config retrieval failed: {str(e)}")
                raise BackendError(f"Quilt3 backend get_catalog_config failed: {str(e)}")

    def configure_catalog(self, catalog_url: str) -> None:
        """Configure the default catalog URL for subsequent operations.

        Sets the default catalog URL using quilt3.config() which persists the configuration
        for future operations.

        Args:
            catalog_url: URL of the catalog to configure as default

        Raises:
            AuthenticationError: When authentication credentials are invalid
            BackendError: When the backend operation fails
            ValidationError: When catalog_url parameter is invalid
        """
        try:
            logger.debug(f"Configuring catalog: {catalog_url}")

            # Validate catalog URL
            if not catalog_url or not isinstance(catalog_url, str):
                raise ValidationError("Invalid catalog URL: must be a non-empty string")

            # Use quilt3.config to set the catalog URL
            self.quilt3.config(catalog_url)

            logger.debug(f"Successfully configured catalog: {catalog_url}")

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Catalog configuration failed: {str(e)}")
            raise BackendError(f"Quilt3 backend configure_catalog failed: {str(e)}")

    def _transform_catalog_config(self, config_data: Dict[str, Any]) -> Catalog_Config:
        """Transform raw catalog configuration to Catalog_Config domain object.

        Args:
            config_data: Raw configuration dictionary from config.json

        Returns:
            Catalog_Config domain object

        Raises:
            BackendError: If transformation fails
        """
        try:
            logger.debug("Transforming catalog configuration")

            # Extract required fields with validation
            region = config_data.get("region", "")
            if not region:
                raise BackendError("Missing required field 'region' in catalog configuration")

            api_gateway_endpoint = config_data.get("apiGatewayEndpoint", "")
            if not api_gateway_endpoint:
                raise BackendError("Missing required field 'apiGatewayEndpoint' in catalog configuration")

            registry_url = config_data.get("registryUrl", "")
            if not registry_url:
                raise BackendError("Missing required field 'registryUrl' in catalog configuration")

            analytics_bucket = config_data.get("analyticsBucket", "")
            if not analytics_bucket:
                raise BackendError("Missing required field 'analyticsBucket' in catalog configuration")

            # Derive stack prefix from analytics bucket name
            # Example: "quilt-staging-analyticsbucket-10ort3e91tnoa" -> "quilt-staging"
            stack_prefix = ""
            analytics_bucket_lower = analytics_bucket.lower()
            if "-analyticsbucket" in analytics_bucket_lower:
                # Find the position in the original string (case-sensitive)
                analyticsbucket_pos = analytics_bucket_lower.find("-analyticsbucket")
                stack_prefix = analytics_bucket[:analyticsbucket_pos]
            else:
                # Fallback: use the full bucket name if no analyticsbucket suffix
                # or first part before dash if there are dashes
                if "-" in analytics_bucket:
                    stack_prefix = analytics_bucket.split("-")[0]
                else:
                    stack_prefix = analytics_bucket

            # Derive tabulator data catalog name from stack prefix
            # Example: "quilt-staging" -> "quilt-quilt-staging-tabulator"
            tabulator_data_catalog = f"quilt-{stack_prefix}-tabulator"

            catalog_config = Catalog_Config(
                region=region,
                api_gateway_endpoint=api_gateway_endpoint,
                registry_url=registry_url,
                analytics_bucket=analytics_bucket,
                stack_prefix=stack_prefix,
                tabulator_data_catalog=tabulator_data_catalog,
            )

            logger.debug("Successfully transformed catalog configuration")
            return catalog_config

        except BackendError:
            raise
        except Exception as e:
            logger.error(f"Catalog config transformation failed: {str(e)}")
            raise BackendError(f"Catalog configuration transformation failed: {str(e)}")

    def get_registry_url(self) -> Optional[str]:
        """Get the current default registry URL.

        Retrieves the currently configured default registry URL from the quilt3 session.
        This URL is typically set through catalog configuration or authentication.

        Returns:
            Registry API URL (HTTPS) for GraphQL queries (e.g., "https://example-registry.quiltdata.com") or None if not configured

        Raises:
            BackendError: When the backend operation fails to retrieve registry URL
        """
        try:
            logger.debug("Getting registry URL from quilt3 session")

            # Check if quilt3.session.get_registry_url method exists
            if hasattr(self.quilt3.session, "get_registry_url"):
                registry_url = self.quilt3.session.get_registry_url()
                logger.debug(f"Retrieved registry URL: {registry_url}")
                return str(registry_url) if registry_url is not None else None
            else:
                logger.debug("quilt3.session.get_registry_url method not available")
                return None

        except Exception as e:
            logger.error(f"Registry URL retrieval failed: {str(e)}")
            raise BackendError(f"Quilt3 backend get_registry_url failed: {str(e)}")

    def execute_graphql_query(
        self,
        query: str,
        variables: Optional[Dict] = None,
        registry: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute a GraphQL query against the catalog.

        Executes a GraphQL query against the catalog API using the authenticated
        quilt3 session. This provides access to catalog data and operations through
        the GraphQL interface.

        Args:
            query: GraphQL query string to execute
            variables: Optional dictionary of query variables
            registry: Target registry URL (uses default if None)

        Returns:
            Dict[str, Any]: Dictionary containing the GraphQL response data

        Raises:
            AuthenticationError: When authentication credentials are invalid or missing
            BackendError: When the GraphQL query execution fails
            ValidationError: When query syntax is invalid or variables are malformed
        """
        try:
            logger.debug("Executing GraphQL query against catalog")

            # Get authenticated session
            session = self.quilt3.session.get_session()

            # Get GraphQL endpoint
            if registry:
                # Legacy: registry parameter provided as S3 URL
                api_url = self._get_graphql_endpoint(registry)
            else:
                # Modern: get registry URL from catalog config
                logged_in_url = self.quilt3.logged_in()
                if not logged_in_url:
                    raise AuthenticationError("Not authenticated - no catalog configured")

                catalog_config = self.get_catalog_config(logged_in_url)
                # Construct GraphQL endpoint from catalog's registry URL
                from quilt_mcp.utils import graphql_endpoint

                api_url = graphql_endpoint(catalog_config.registry_url)

            # Prepare request payload
            payload: Dict[str, Any] = {"query": query}
            if variables:
                payload["variables"] = variables  # Variables is Dict[str, Any]  # type: ignore[assignment]

            # Execute GraphQL query
            response = session.post(api_url, json=payload)
            response.raise_for_status()

            logger.debug("GraphQL query executed successfully")
            result: Dict[str, Any] = response.json()
            return result

        except self.requests.HTTPError as e:
            if hasattr(e, 'response') and e.response and e.response.status_code == 403:
                logger.error("GraphQL query authorization failed")
                raise AuthenticationError("GraphQL query not authorized")
            else:
                error_text = e.response.text if hasattr(e, 'response') and e.response else str(e)
                logger.error(f"GraphQL query HTTP error: {error_text}")
                raise BackendError(f"GraphQL query failed: {error_text}")
        except AuthenticationError:
            raise
        except Exception as e:
            logger.error(f"GraphQL query execution error: {str(e)}")
            raise BackendError(f"GraphQL execution error: {str(e)}")

    def get_boto3_client(
        self,
        service_name: str,
        region: Optional[str] = None,
    ) -> Any:
        """Get authenticated boto3 client for AWS services.

        Creates and returns a boto3 client for the specified AWS service,
        configured with the appropriate authentication credentials from the
        quilt3 session. This provides backend-agnostic access to AWS services
        needed for Quilt operations.

        Args:
            service_name: AWS service name (e.g., 'athena', 's3', 'glue')
            region: AWS region override (uses catalog region if None)

        Returns:
            Configured boto3 client for the specified service

        Raises:
            AuthenticationError: When AWS credentials are not available or invalid
            BackendError: When boto3 client creation fails
            ValidationError: When service_name is invalid or unsupported
        """
        try:
            logger.debug(f"Creating boto3 client for service: {service_name}, region: {region}")

            # Check if boto3 is available
            if self.boto3 is None:
                raise BackendError("boto3 library is not available")

            # Create botocore session from quilt3
            botocore_session = self.quilt3.session.create_botocore_session()

            # Create boto3 session with authenticated botocore session
            boto3_session = self.boto3.Session(botocore_session=botocore_session)

            # Create client for the specified service
            client = boto3_session.client(service_name, region_name=region)

            logger.debug(f"Successfully created boto3 client for service: {service_name}")
            return client

        except Exception as e:
            logger.error(f"Boto3 client creation failed: {str(e)}")
            raise BackendError(f"Failed to create boto3 client for {service_name}: {str(e)}")

    def _get_graphql_endpoint(self, registry_url: str) -> str:
        """Extract GraphQL API endpoint from registry URL.

        LEGACY: Converts an S3 registry URL to the corresponding GraphQL API endpoint.
        This is only used for backward compatibility with old code that passes S3 URLs.
        New code should use catalog_config.registry_url directly (which is already HTTPS).

        Args:
            registry_url: S3 registry URL (e.g., "s3://my-registry-bucket")

        Returns:
            GraphQL API endpoint URL (HTTPS)

        Raises:
            ValidationError: When registry URL format is invalid
        """
        try:
            # Extract bucket name from S3 URL
            if not registry_url.startswith("s3://"):
                raise ValidationError("Registry URL must be an S3 URL")

            bucket_name = registry_url.replace("s3://", "").split("/")[0]

            # Construct GraphQL endpoint
            # This is a simplified implementation - in practice, this might need
            # to query the catalog config to get the actual API endpoint
            from quilt_mcp.utils import graphql_endpoint

            api_endpoint = graphql_endpoint(f"https://{bucket_name}.quiltdata.com")

            logger.debug(f"Constructed GraphQL endpoint: {api_endpoint}")
            return api_endpoint

        except Exception as e:
            logger.error(f"GraphQL endpoint construction failed: {str(e)}")
            raise ValidationError(f"Invalid registry URL format: {registry_url}")

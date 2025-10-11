"""
Athena Query Service Implementation

This module provides the core Athena service that uses SQLAlchemy with PyAthena
to execute queries against AWS Athena and manage Glue Data Catalog metadata.
"""

from __future__ import annotations

import os
import logging
from typing import Dict, List, Any, Optional
from cachetools import TTLCache
import boto3
import pandas as pd
from sqlalchemy import create_engine, MetaData, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from ..utils import format_error_response, suppress_stdout
from .quilt_service import QuiltService

logger = logging.getLogger(__name__)


class AthenaQueryService:
    """Core service for Athena query execution and Glue catalog operations."""

    def __init__(
        self,
        use_quilt_auth: bool = True,
        quilt_service: Optional[QuiltService] = None,
        workgroup_name: Optional[str] = None,
        data_catalog_name: Optional[str] = None,
    ):
        """Initialize the Athena service.

        Args:
            use_quilt_auth: Whether to use quilt3 authentication
            quilt_service: Optional QuiltService instance for dependency injection
            workgroup_name: Optional Athena workgroup name (auto-discovered if not provided)
            data_catalog_name: Optional data catalog name (defaults to "AwsDataCatalog")
        """
        self.use_quilt_auth = use_quilt_auth
        self.quilt_service = quilt_service
        self.workgroup_name = workgroup_name
        self.data_catalog_name = data_catalog_name or "AwsDataCatalog"
        self.query_cache = TTLCache(maxsize=100, ttl=3600)  # 1 hour cache

        # Initialize clients
        self._glue_client: Optional[Any] = None
        self._s3_client: Optional[Any] = None
        self._engine: Optional[Engine] = None
        self._base_connection_string: Optional[str] = None  # Store for creating engines with schema_name

    @property
    def glue_client(self):
        """Lazy initialization of Glue client."""
        if self._glue_client is None:
            self._glue_client = self._create_glue_client()
        return self._glue_client

    @property
    def s3_client(self):
        """Lazy initialization of S3 client."""
        if self._s3_client is None:
            self._s3_client = self._create_s3_client()
        return self._s3_client

    @property
    def engine(self):
        """Lazy initialization of SQLAlchemy engine."""
        if self._engine is None:
            self._engine = self._create_sqlalchemy_engine()
        return self._engine

    def _create_sqlalchemy_engine(self) -> Engine:
        """Create SQLAlchemy engine with PyAthena driver."""
        try:
            if self.use_quilt_auth:
                # Use QuiltService for complete abstraction
                quilt_service = self.quilt_service or QuiltService()
                botocore_session = quilt_service.create_botocore_session()
                credentials = botocore_session.get_credentials()

                # Force region to us-east-1 for Quilt Athena workgroup
                # The QuiltUserAthena workgroup and permissions are configured in us-east-1
                region = "us-east-1"

                # Use provided workgroup or discover available workgroups dynamically
                workgroup = self.workgroup_name or self._discover_workgroup(credentials, region)

                # Create connection string with explicit credentials
                # URL encode the credentials to handle special characters
                from urllib.parse import quote_plus

                access_key = quote_plus(credentials.access_key)
                secret_key = quote_plus(credentials.secret_key)

                # Create connection string without hardcoded schema or workgroup
                connection_string = (
                    f"awsathena+rest://{access_key}:{secret_key}@athena.{region}.amazonaws.com:443/"
                    f"?work_group={workgroup}&catalog_name={quote_plus(self.data_catalog_name)}"
                )

                # Add session token if available
                if credentials.token:
                    connection_string += f"&aws_session_token={quote_plus(credentials.token)}"

                # Store base connection string for creating engines with schema_name
                self._base_connection_string = connection_string

                logger.info(f"Creating Athena engine with workgroup: {workgroup}, catalog: {self.data_catalog_name}")
                return create_engine(connection_string, echo=False)

            else:
                # Use default AWS credentials
                region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

                # Use provided workgroup, or discover dynamically, or fall back to environment
                workgroup = (
                    self.workgroup_name
                    or self._discover_workgroup(None, region)
                    or os.environ.get("ATHENA_WORKGROUP", "primary")
                )

                from urllib.parse import quote_plus

                connection_string = f"awsathena+rest://@athena.{region}.amazonaws.com:443/?work_group={workgroup}&catalog_name={quote_plus(self.data_catalog_name)}"

                # Store base connection string for creating engines with schema_name
                self._base_connection_string = connection_string

                logger.info(f"Creating Athena engine with workgroup: {workgroup}, catalog: {self.data_catalog_name}")
                return create_engine(connection_string, echo=False)

        except Exception as e:
            logger.error(f"Failed to create SQLAlchemy engine: {e}")
            raise

    def _discover_workgroup(self, credentials, region: str) -> str:
        """Discover the best available Athena workgroup for the user.

        Uses the consolidated list_workgroups method to avoid code duplication.
        """
        try:
            # Use the consolidated list_workgroups method instead of duplicating logic
            workgroups = self.list_workgroups()

            if not workgroups:
                # Fallback to primary if no workgroups available
                return "primary"

            # Filter workgroups with valid output locations for query execution
            valid_workgroups = [wg["name"] for wg in workgroups if wg.get("output_location") is not None]

            if not valid_workgroups:
                # If no workgroups have output locations, use the first available
                return workgroups[0]["name"]

            # Prioritize workgroups (Quilt workgroups first, then others)
            quilt_workgroups = [name for name in valid_workgroups if "quilt" in name.lower()]
            if quilt_workgroups:
                return quilt_workgroups[0]
            elif valid_workgroups:
                return valid_workgroups[0]
            else:
                # Fallback to primary if no valid workgroups found
                return "primary"

        except Exception as e:
            logger.warning(f"Failed to discover workgroups: {e}")
            # Fallback to environment variable or primary
            return os.environ.get("ATHENA_WORKGROUP", "primary")

    def _create_glue_client(self):
        """Create Glue client for metadata operations."""
        if self.use_quilt_auth:
            try:
                # Use QuiltService for complete abstraction
                quilt_service = self.quilt_service or QuiltService()
                botocore_session = quilt_service.create_botocore_session()
                # Use us-east-1 region for Quilt Athena workgroup resources
                return botocore_session.create_client("glue", region_name="us-east-1")
            except Exception:
                # Fallback to default credentials
                pass
        return boto3.client("glue", region_name="us-east-1")

    def _create_s3_client(self):
        """Create S3 client for result management."""
        if self.use_quilt_auth:
            try:
                # Use QuiltService for complete abstraction
                quilt_service = self.quilt_service or QuiltService()
                botocore_session = quilt_service.create_botocore_session()
                return botocore_session.create_client("s3")
            except Exception:
                # Fallback to default credentials
                pass
        return boto3.client("s3")

    def _get_s3_staging_dir(self) -> str:
        """Get S3 staging directory for query results."""
        return os.environ.get("ATHENA_QUERY_RESULT_LOCATION", "s3://aws-athena-query-results/")

    def discover_databases(self, data_catalog_name: str = "AwsDataCatalog") -> Dict[str, Any]:
        """Discover all databases using Athena SQL queries."""
        try:
            # Use Athena SQL to list schemas (databases) with explicit catalog name
            query = f"SHOW DATABASES IN `{data_catalog_name}`"

            # Reuse execute_query for consistent query execution
            result = self.execute_query(query, database_name=None)

            if not result.get("success"):
                return result

            df = result["data"]
            databases = []
            for _, row in df.iterrows():
                db_name = row.iloc[0]  # First column should be database name
                databases.append(
                    {
                        "name": db_name,
                        "description": "",  # Not available through SHOW DATABASES
                        "location_uri": "",  # Not available through SHOW DATABASES
                        "create_time": None,  # Not available through SHOW DATABASES
                        "parameters": {},
                    }
                )

            return {
                "success": True,
                "databases": databases,
                "data_catalog_name": data_catalog_name,
                "count": len(databases),
            }

        except Exception as e:
            logger.error(f"Failed to discover databases: {e}")
            return format_error_response(f"Failed to discover databases: {str(e)}")

    def discover_tables(
        self,
        database_name: str,
        data_catalog_name: str = "AwsDataCatalog",
        table_pattern: str = '*',
    ) -> Dict[str, Any]:
        """Discover tables using Athena SQL queries with database in connection string."""
        try:
            # Use simple SHOW TABLES (database context set via execute_query's schema_name)
            query = "SHOW TABLES"
            if table_pattern and table_pattern != '*':
                query += f" LIKE '{table_pattern}'"

            # Reuse execute_query which handles database_name in connection string
            result = self.execute_query(query, database_name=database_name)

            if not result.get("success"):
                return result

            df = result["data"]
            tables = []
            for _, row in df.iterrows():
                table_name = row.iloc[0]  # First column should be table name
                tables.append(
                    {
                        "name": table_name,
                        "database_name": database_name,
                        "description": "",  # Not available through SHOW TABLES
                        "owner": "",
                        "create_time": None,
                        "update_time": None,
                        "table_type": "",
                        "storage_descriptor": {
                            "location": "",
                            "input_format": "",
                            "output_format": "",
                            "serde_info": {},
                        },
                        "partition_keys": [],
                        "parameters": {},
                    }
                )

            return {
                "success": True,
                "tables": tables,
                "database_name": database_name,
                "data_catalog_name": data_catalog_name,
                "count": len(tables),
            }

        except Exception as e:
            logger.error(f"Failed to discover tables: {e}")
            return format_error_response(f"Failed to discover tables: {str(e)}")

    def get_table_metadata(
        self, database_name: str, table_name: str, data_catalog_name: str = "AwsDataCatalog"
    ) -> Dict[str, Any]:
        """Get comprehensive table metadata using Athena DESCRIBE."""
        try:
            # Use Athena SQL to describe table instead of direct Glue API
            query = f"DESCRIBE {database_name}.{table_name}"

            # Reuse execute_query for consistent query execution
            result = self.execute_query(query, database_name=None)

            if not result.get("success"):
                return result

            df = result["data"]

            columns = []
            partitions = []

            for _, row in df.iterrows():
                col_name = row.iloc[0]
                col_type = row.iloc[1] if len(row) > 1 else "string"
                col_comment = row.iloc[2] if len(row) > 2 else ""

                # Check if this is a partition column
                # Partition columns often appear after a separator or with special formatting
                if col_name.startswith("#") or "partition" in str(col_comment).lower():
                    continue  # Skip header/separator rows
                elif any(keyword in str(col_name).lower() for keyword in ["partition", "date", "year", "month"]):
                    # This is likely a partition column
                    partitions.append({"name": col_name, "type": col_type, "comment": col_comment})
                else:
                    # Regular column
                    columns.append(
                        {
                            "name": col_name,
                            "type": col_type,
                            "comment": col_comment,
                            "parameters": {},
                        }
                    )

            return {
                "success": True,
                "table_name": table_name,
                "database_name": database_name,
                "data_catalog_name": data_catalog_name,
                "columns": columns,
                "partitions": partitions,
                "table_type": "",  # Not available through DESCRIBE
                "description": "",  # Not available through DESCRIBE
                "owner": "",  # Not available through DESCRIBE
                "create_time": None,  # Not available through DESCRIBE
                "update_time": None,  # Not available through DESCRIBE
                "storage_descriptor": {
                    "location": "",  # Not available through DESCRIBE
                    "input_format": "",  # Not available through DESCRIBE
                    "output_format": "",  # Not available through DESCRIBE
                    "compressed": False,  # Not available through DESCRIBE
                    "serde_info": {},  # Not available through DESCRIBE
                },
                "parameters": {},  # Not available through DESCRIBE
            }

        except Exception as e:
            logger.error(f"Failed to get table metadata: {e}")
            return format_error_response(f"Failed to get table metadata: {str(e)}")

    def execute_query(self, query: str, database_name: str | None = None, max_results: int = 1000) -> Dict[str, Any]:
        """Execute query using SQLAlchemy with PyAthena and return results as DataFrame."""
        try:
            # Determine which engine to use
            # If database_name is provided, create engine with schema_name in connection string
            # This avoids the USE statement which doesn't work with quoted identifiers in Athena
            if database_name:
                from urllib.parse import quote_plus

                # Ensure the base engine is created (triggers lazy initialization)
                _ = self.engine
                # Use stored base connection string and add schema_name
                connection_string = f"{self._base_connection_string}&schema_name={quote_plus(database_name)}"
                engine_to_use = create_engine(connection_string, echo=False)
            else:
                engine_to_use = self.engine

            # Execute query and load results into pandas DataFrame
            # Sanitize query to prevent string formatting issues
            safe_query = self._sanitize_query_for_pandas(query)
            with suppress_stdout():
                df = pd.read_sql_query(safe_query, engine_to_use)

            # Apply result limit
            truncated = False
            if len(df) > max_results:
                df = df.head(max_results)
                truncated = True

            return {
                "success": True,
                "data": df,
                "row_count": len(df),
                "total_rows": len(df) if not truncated else f"{max_results}+",
                "truncated": truncated,
                "columns": list(df.columns),
                "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
                "query": query,
            }

        except SQLAlchemyError as e:
            logger.error(f"SQL execution error: {e}")
            return format_error_response(f"SQL execution error: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to execute query: {e}")
            return format_error_response(f"Query execution failed: {str(e)}")

    def _sanitize_query_for_pandas(self, query: str) -> str:
        """Sanitize query to prevent string formatting issues with pandas/SQLAlchemy."""
        # This is a conservative approach - we don't modify the actual SQL
        # but we ensure it won't cause formatting errors in pandas
        try:
            # For queries with % characters, we need to be careful
            # pandas/SQLAlchemy sometimes tries to format strings
            # The safest approach is to not modify the query at all
            # and let the underlying engine handle it properly
            return query
        except Exception:
            return query

    def format_results(self, result_data: Dict[str, Any], output_format: str = "json") -> Dict[str, Any]:
        """Format query results in requested format."""
        if not result_data.get("success") or result_data.get("data") is None:
            return result_data

        df = result_data["data"]

        try:
            if output_format.lower() == "json":
                formatted_data = df.to_dict(orient="records")
            elif output_format.lower() == "csv":
                formatted_data = df.to_csv(index=False)
            elif output_format.lower() == "table":
                # Format as readable ASCII table
                from ..formatting import format_as_table

                formatted_data = format_as_table(df)
            elif output_format.lower() == "parquet":
                # For parquet, return base64 encoded bytes
                import io
                import base64

                buffer = io.BytesIO()
                df.to_parquet(buffer, index=False)
                formatted_data = base64.b64encode(buffer.getvalue()).decode("utf-8")
            else:
                # Default to JSON
                formatted_data = df.to_dict(orient="records")

            # Update result with formatted data
            result_copy = result_data.copy()
            result_copy["formatted_data"] = formatted_data
            result_copy["format"] = output_format.lower()

            # For auto-detection, add table format when appropriate
            if output_format.lower() in ["json", "csv"]:
                from ..formatting import should_use_table_format, format_as_table

                if should_use_table_format(df):
                    result_copy["formatted_data_table"] = format_as_table(df)
                    result_copy["display_format"] = "table"

            # Remove the DataFrame to make it JSON serializable
            result_copy.pop("data", None)

            return result_copy

        except Exception as e:
            logger.error(f"Failed to format results: {e}")
            return format_error_response(f"Failed to format results: {str(e)}")

    def list_workgroups(self) -> List[Dict[str, Any]]:
        """List available Athena workgroups using the service's authentication patterns."""
        try:
            import boto3

            # Use the same auth pattern as other service methods
            if self.use_quilt_auth:
                # Use QuiltService for complete abstraction
                quilt_service = self.quilt_service or QuiltService()
                botocore_session = quilt_service.create_botocore_session()
                credentials = botocore_session.get_credentials()
                region = "us-east-1"  # Force region for Quilt Athena workgroups

                athena_client = boto3.client(
                    "athena",
                    region_name=region,
                    aws_access_key_id=credentials.access_key,
                    aws_secret_access_key=credentials.secret_key,
                    aws_session_token=credentials.token,
                )
            else:
                region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
                athena_client = boto3.client("athena", region_name=region)

            # List all workgroups and filter to ENABLED only
            response = athena_client.list_work_groups()
            workgroups = []

            # Filter to only ENABLED workgroups before processing
            enabled_workgroups = [wg for wg in response.get("WorkGroups", []) if wg.get("State") == "ENABLED"]

            # Process each ENABLED workgroup
            for wg in enabled_workgroups:
                name = wg.get("Name")
                if not name:
                    continue

                # Preserve original AWS Description from ListWorkGroups
                original_description = wg.get("Description", "")

                try:
                    # Get detailed workgroup info if available
                    wg_details = athena_client.get_work_group(WorkGroup=name)
                    workgroup_info = wg_details.get("WorkGroup", {})
                    config = workgroup_info.get("Configuration", {})

                    workgroups.append(
                        {
                            "name": name,
                            "description": workgroup_info.get("Description", original_description),
                            "creation_time": workgroup_info.get("CreationTime"),
                            "output_location": config.get("ResultConfiguration", {}).get("OutputLocation"),
                            "enforce_workgroup_config": config.get("EnforceWorkGroupConfiguration", False),
                        }
                    )
                except Exception as e:
                    # Log GetWorkGroup failures but preserve original AWS description
                    logger.info(f"GetWorkGroup failed for {name}: {str(e)}")

                    workgroups.append(
                        {
                            "name": name,
                            "description": original_description,
                            "creation_time": wg.get("CreationTime"),
                            "output_location": None,
                            "enforce_workgroup_config": False,
                        }
                    )

            # Sort workgroups: Quilt workgroups first, then alphabetical
            workgroups.sort(
                key=lambda x: (
                    "quilt" not in x["name"].lower(),  # Quilt workgroups first
                    x["name"],  # Alphabetical
                )
            )

            return workgroups

        except Exception as e:
            logger.error(f"Failed to list workgroups in service: {e}")
            raise  # Re-raise to be handled by caller

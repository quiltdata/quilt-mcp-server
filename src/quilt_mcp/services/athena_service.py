"""
Athena Query Service Implementation

This module provides the core Athena service that uses SQLAlchemy with PyAthena
to execute queries against AWS Athena and manage Glue Data Catalog metadata.
"""

from __future__ import annotations

import os
import logging
from typing import Dict, List, Any, Optional, TYPE_CHECKING
from cachetools import TTLCache
import boto3
import pandas as pd
from sqlalchemy import create_engine, MetaData, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

if TYPE_CHECKING:
    from mypy_boto3_glue import GlueClient  # type: ignore[import-not-found]
    from mypy_boto3_s3 import S3Client  # type: ignore[import-not-found]
    from mypy_boto3_athena import AthenaClient  # type: ignore[import-not-found]
    from ..ops.quilt_ops import QuiltOps
else:
    GlueClient = Any
    S3Client = Any
    AthenaClient = Any
    QuiltOps = Any

from ..utils.common import format_error_response, suppress_stdout
from ..ops.factory import QuiltOpsFactory

logger = logging.getLogger(__name__)


class AthenaQueryService:
    """Core service for Athena query execution and Glue catalog operations."""

    _workgroup_cache: TTLCache[str, str] = TTLCache(maxsize=32, ttl=900)

    def __init__(
        self,
        backend: Optional[QuiltOps] = None,
        workgroup_name: Optional[str] = None,
        data_catalog_name: Optional[str] = None,
    ):
        """Initialize the Athena service.

        Args:
            backend: Optional Quilt3_Backend instance for proper backend abstraction
            workgroup_name: Optional Athena workgroup name (auto-discovered if not provided)
            data_catalog_name: Optional data catalog name (defaults to "AwsDataCatalog")
        """
        self.backend = backend or QuiltOpsFactory.create()
        self.workgroup_name = workgroup_name
        self.data_catalog_name = data_catalog_name or "AwsDataCatalog"
        self.query_cache: TTLCache[str, Any] = TTLCache(maxsize=100, ttl=3600)  # 1 hour cache

        # Initialize clients
        self._glue_client: Optional[GlueClient] = None
        self._s3_client: Optional[S3Client] = None
        self._athena_client: Optional[AthenaClient] = None
        self._engine: Optional[Engine] = None
        self._base_connection_string: Optional[str] = None  # Store for creating engines with schema_name

    @property
    def glue_client(self) -> GlueClient:
        """Lazy initialization of Glue client."""
        if self._glue_client is None:
            self._glue_client = self._create_glue_client()
        return self._glue_client

    @property
    def s3_client(self) -> S3Client:
        """Lazy initialization of S3 client."""
        if self._s3_client is None:
            self._s3_client = self._create_s3_client()
        return self._s3_client

    @property
    def engine(self) -> Engine:
        """Lazy initialization of SQLAlchemy engine."""
        if self._engine is None:
            self._engine = self._create_sqlalchemy_engine()
        return self._engine

    def _create_sqlalchemy_engine(self) -> Engine:
        """Create SQLAlchemy engine with PyAthena driver."""
        try:
            region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
            workgroup = self._get_workgroup(region)

            from urllib.parse import quote_plus

            credentials = self._get_athena_credentials(region=region)

            if credentials:
                access_key = quote_plus(credentials.access_key)
                secret_key = quote_plus(credentials.secret_key)
                connection_string = (
                    f"awsathena+rest://{access_key}:{secret_key}@athena.{region}.amazonaws.com:443/"
                    f"?work_group={workgroup}&catalog_name={quote_plus(self.data_catalog_name)}"
                )
                if credentials.token:
                    connection_string += f"&aws_session_token={quote_plus(credentials.token)}"
            else:
                connection_string = (
                    f"awsathena+rest://@athena.{region}.amazonaws.com:443/"
                    f"?work_group={workgroup}&catalog_name={quote_plus(self.data_catalog_name)}"
                )

            self._base_connection_string = connection_string
            logger.info(f"Creating Athena engine with workgroup: {workgroup}, catalog: {self.data_catalog_name}")
            return create_engine(connection_string, echo=False)

        except Exception as e:
            logger.error(f"Failed to create SQLAlchemy engine: {e}")
            raise

    def _discover_workgroup(self, region: str) -> str:
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
                return str(workgroups[0]["name"])

            # Prioritize workgroups (Quilt workgroups first, then others)
            quilt_workgroups = [name for name in valid_workgroups if "quilt" in name.lower()]
            if quilt_workgroups:
                return str(quilt_workgroups[0])
            elif valid_workgroups:
                return str(valid_workgroups[0])
            else:
                # Fallback to primary if no valid workgroups found
                return "primary"

        except Exception as e:
            logger.warning(f"Failed to discover workgroups: {e}")
            # Fallback to environment variable or primary
            fallback: str = os.environ.get("ATHENA_WORKGROUP", "primary")
            return fallback

    def _get_workgroup(self, region: str) -> str:
        """Resolve workgroup with explicit override, env override, and cached discovery."""
        if self.workgroup_name:
            return self.workgroup_name

        env_workgroup = os.environ.get("ATHENA_WORKGROUP")
        if env_workgroup:
            return env_workgroup

        cache_key = f"{region}:{self.data_catalog_name}"
        cached_workgroup = self._workgroup_cache.get(cache_key)
        if cached_workgroup:
            return cached_workgroup

        discovered = self._discover_workgroup(region)
        resolved = discovered or "primary"
        self._workgroup_cache[cache_key] = resolved
        return resolved

    def _create_glue_client(self) -> GlueClient:
        """Create Glue client for metadata operations."""
        try:
            return self.backend.get_aws_client("glue", region="us-east-1")
        except Exception:
            return boto3.client("glue", region_name="us-east-1")

    def _create_s3_client(self) -> S3Client:
        """Create S3 client for result management."""
        try:
            return self.backend.get_aws_client("s3")
        except Exception:
            return boto3.client("s3")

    def _get_athena_credentials(self, region: str) -> Any | None:
        """Extract credentials from backend-provided Athena client."""
        try:
            athena_client = self.backend.get_aws_client("athena", region=region)
            signer = getattr(athena_client, "_request_signer", None)
            credentials = getattr(signer, "_credentials", None)
            if credentials and getattr(credentials, "access_key", None) and getattr(credentials, "secret_key", None):
                return credentials
        except Exception:
            pass
        return None

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
        """Get comprehensive table metadata using Athena DESCRIBE with PyAthena cursor.

        Note: We use PyAthena cursor directly instead of pandas because DESCRIBE returns
        tab-separated values in a single column which pandas cannot parse correctly.
        """
        try:
            from pyathena import connect

            # Determine S3 staging location
            # PyAthena will use the workgroup's output location if we don't specify s3_staging_dir
            region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
            workgroup = self._get_workgroup(region)

            # Create PyAthena connection
            # Note: We rely on workgroup configuration for S3 output location
            connect_kwargs: Dict[str, Any] = {
                "region_name": region,
                "schema_name": database_name,
                "work_group": workgroup,
            }
            credentials = self._get_athena_credentials(region=region)
            if credentials:
                connect_kwargs.update(
                    {
                        "aws_access_key_id": credentials.access_key,
                        "aws_secret_access_key": credentials.secret_key,
                        "aws_session_token": credentials.token,
                    }
                )
            cursor = connect(**connect_kwargs).cursor()

            # Execute DESCRIBE - use backticks for table names with special characters
            query = f'DESCRIBE `{table_name}`'
            cursor.execute(query)

            # Parse tab-separated results
            # DESCRIBE returns: col_name \t data_type \t comment (all in one string per row)
            columns: list[dict[str, str]] = []
            partitions = []

            for row in cursor.fetchall():
                # Each row is a tuple with a single tab-separated string
                line = str(row[0]) if row else ""
                parts = line.split('\t')

                if len(parts) >= 2:
                    col_name = parts[0].strip()
                    col_type = parts[1].strip()
                    col_comment = parts[2].strip() if len(parts) > 2 else ""

                    # Skip empty or header rows
                    if not col_name or col_name.startswith("#"):
                        continue

                    # Check if this is a partition column
                    if any(keyword in col_name.lower() for keyword in ["partition", "date", "year", "month"]):
                        partitions.append({"name": col_name, "type": col_type, "comment": col_comment})
                    else:
                        columns.append(
                            {
                                "name": col_name,
                                "type": col_type,
                                "comment": col_comment,
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
                from quilt_mcp.utils.formatting import format_as_table

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
                from quilt_mcp.utils.formatting import should_use_table_format, format_as_table

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
            region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
            athena_client = self.backend.get_aws_client("athena", region=region)

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

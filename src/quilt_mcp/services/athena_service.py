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
from sqlalchemy import create_engine, MetaData, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from botocore.exceptions import ClientError

from ..utils import format_error_response, suppress_stdout

logger = logging.getLogger(__name__)


class AthenaQueryService:
    """Core service for Athena query execution and Glue catalog operations."""

    def __init__(self, use_jwt_auth: bool = True, allow_ambient: bool = True):
        """Initialize the Athena service.

        Args:
            use_jwt_auth: Whether to use JWT-based authentication (default: True)
        """
        self.use_jwt_auth = use_jwt_auth
        self.allow_ambient = allow_ambient
        self.query_cache = TTLCache(maxsize=100, ttl=3600)  # 1 hour cache

        # Initialize clients
        self._glue_client: Optional[Any] = None
        self._s3_client: Optional[Any] = None
        self._engine: Optional[Engine] = None
        self._cached_session: Optional[boto3.Session] = None

    # ------------------------------------------------------------------
    # Credential/session helpers
    # ------------------------------------------------------------------

    def _build_boto3_session(self) -> boto3.Session:
        """Create a boto3 session using JWT credentials or ambient credentials."""

        # Prefer cached session to avoid repeated credential resolution
        if self._cached_session is not None:
            return self._cached_session

        # Try JWT-derived credentials first
        if self.use_jwt_auth:
            try:
                from ..utils import get_s3_client

                s3_client = get_s3_client()
                credentials = getattr(s3_client, "_get_credentials", lambda: None)()
                if credentials and getattr(credentials, "access_key", None):
                    session = boto3.Session(
                        aws_access_key_id=credentials.access_key,
                        aws_secret_access_key=credentials.secret_key,
                        aws_session_token=getattr(credentials, "token", None),
                    )
                    self._cached_session = session
                    return session
            except Exception as exc:  # pragma: no cover - defensive fallback
                logger.debug("Failed to obtain JWT credentials for Athena: %s", exc)
                if not self.allow_ambient:
                    raise

        if not self.allow_ambient:
            raise RuntimeError("Unable to obtain JWT credentials for Athena")

        # Ambient credentials (ECS task role, instance profile, AWS_PROFILE, etc.)
        session = boto3.Session()
        self._cached_session = session
        return session

    def _determine_region(self, fallback: str = "us-east-1") -> str:
        """Determine AWS region for Athena/Glue operations."""

        env_region = (
            os.getenv("ATHENA_REGION")
            or os.getenv("AWS_REGION")
            or os.getenv("AWS_DEFAULT_REGION")
            or fallback
        )

        session_region = self._cached_session.region_name if self._cached_session else None
        return session_region or env_region

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
            session = self._build_boto3_session()
            credentials = session.get_credentials()
            if not credentials:
                raise RuntimeError("No AWS credentials available for Athena connection")

            frozen = credentials.get_frozen_credentials()
            region = self._determine_region()

            # Discover available workgroup dynamically
            workgroup_info = self._discover_workgroup(session, region)
            workgroup = workgroup_info.get("name") or os.environ.get("ATHENA_WORKGROUP", "primary")

            from urllib.parse import quote_plus

            access_key = quote_plus(frozen.access_key)
            secret_key = quote_plus(frozen.secret_key)

            connection_string = (
                f"awsathena+rest://{access_key}:{secret_key}@athena.{region}.amazonaws.com:443/"
                f"?work_group={workgroup}"
            )

            staging_dir = workgroup_info.get("output_location") or self._get_s3_staging_dir(session, region)
            if staging_dir:
                connection_string += f"&s3_staging_dir={quote_plus(staging_dir)}"

            if frozen.token:
                connection_string += f"&aws_session_token={quote_plus(frozen.token)}"

            logger.info("Creating Athena engine with workgroup: %s", workgroup)
            return create_engine(connection_string, echo=False)

        except Exception as e:
            logger.error(f"Failed to create SQLAlchemy engine: {e}")
            raise

    def _discover_workgroup(self, session: boto3.Session | None, region: str) -> Dict[str, Any]:
        """Discover the best available Athena workgroup for the user.

        Uses the consolidated list_workgroups method to avoid code duplication.
        """
        default = {"name": os.environ.get("ATHENA_WORKGROUP", "primary"), "output_location": None}
        try:
            if session is None:
                session = self._build_boto3_session()

            # Use the consolidated list_workgroups method instead of duplicating logic
            workgroups = self.list_workgroups(session=session, region_override=region)

            if not workgroups:
                # Fallback to primary if no workgroups available
                return default.copy()

            # Filter workgroups with valid output locations for query execution
            valid_workgroups = [wg for wg in workgroups if wg.get("output_location")]

            # Prioritize workgroups (Quilt workgroups first, then others)
            selected = next((wg for wg in valid_workgroups if "quilt" in wg["name"].lower()), None)
            if not selected and valid_workgroups:
                selected = valid_workgroups[0]

            if not selected:
                # If no workgroups have output locations, use the first available workgroup
                selected = workgroups[0]

            # Return a shallow copy to avoid mutating cached structures
            result = dict(selected)
            result.setdefault("name", default["name"])
            result.setdefault("output_location", None)
            return result

        except Exception as e:
            logger.warning(f"Failed to discover workgroups: {e}")
            # Fallback to environment variable or primary
            return default.copy()

    def _create_glue_client(self):
        """Create Glue client for metadata operations."""
        session = self._build_boto3_session()
        region = self._determine_region()
        return session.client("glue", region_name=region)

    def _create_s3_client(self):
        """Create S3 client for result management."""
        session = self._build_boto3_session()
        return session.client("s3")

    def _get_s3_staging_dir(self, session: boto3.Session, region: str) -> str:
        """Get S3 staging directory for query results."""
        configured = os.environ.get("ATHENA_QUERY_RESULT_LOCATION")
        if configured:
            return configured.rstrip("/") + "/"

        try:
            sts = session.client("sts")
            identity = sts.get_caller_identity()
            account = identity.get("Account")
            if account:
                return f"s3://aws-athena-query-results-{account}-{region}/"
        except Exception as exc:  # pragma: no cover - best effort fallback
            logger.debug("Failed to derive account for Athena staging dir: %s", exc)

        return "s3://aws-athena-query-results/"

    def discover_databases(self, catalog_name: str = "AwsDataCatalog") -> Dict[str, Any]:
        """Discover all databases using Athena SQL queries."""
        try:
            # Use Athena SQL to list schemas (databases) with explicit catalog name
            query = f"SHOW DATABASES IN `{catalog_name}`"
            with suppress_stdout():
                df = pd.read_sql_query(query, self.engine)

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
                "catalog_name": catalog_name,
                "count": len(databases),
            }

        except Exception as e:
            logger.error(f"Failed to discover databases: {e}")
            return format_error_response(f"Failed to discover databases: {str(e)}")

    def discover_tables(
        self,
        database_name: str,
        catalog_name: str = "AwsDataCatalog",
        table_pattern: str = None,
    ) -> Dict[str, Any]:
        """Discover tables using Athena SQL queries."""
        try:
            # Properly escape database names with special characters
            if "-" in database_name or any(c in database_name for c in [" ", ".", "@", "/"]):
                escaped_db = f'"{database_name}"'
            else:
                escaped_db = database_name

            # Use Athena SQL to list tables instead of direct Glue API
            query = f"SHOW TABLES IN {escaped_db}"
            if table_pattern:
                query += f" LIKE '{table_pattern}'"

            with suppress_stdout():
                df = pd.read_sql_query(query, self.engine)

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
                "catalog_name": catalog_name,
                "count": len(tables),
            }

        except Exception as e:
            logger.error(f"Failed to discover tables: {e}")
            return format_error_response(f"Failed to discover tables: {str(e)}")

    def get_table_metadata(
        self, database_name: str, table_name: str, catalog_name: str = "AwsDataCatalog"
    ) -> Dict[str, Any]:
        """Get comprehensive table metadata using Athena DESCRIBE."""
        try:
            # Properly escape database and table names with special characters
            if "-" in database_name or any(c in database_name for c in [" ", ".", "@", "/"]):
                escaped_db = f'"{database_name}"'
            else:
                escaped_db = database_name
            
            if "-" in table_name or any(c in table_name for c in [" ", ".", "@", "/"]):
                escaped_table = f'"{table_name}"'
            else:
                escaped_table = table_name
            
            glue = self.glue_client
            response = glue.get_table(
                DatabaseName=database_name,
                Name=table_name,
            )

            table = response.get("Table", {})
            storage_descriptor = table.get("StorageDescriptor", {}) or {}
            columns = [
                {
                    "name": col.get("Name"),
                    "type": col.get("Type"),
                    "comment": col.get("Comment", ""),
                    "parameters": col.get("Parameters", {}),
                }
                for col in storage_descriptor.get("Columns", []) or []
            ]

            partitions = [
                {
                    "name": part.get("Name"),
                    "type": part.get("Type"),
                    "comment": part.get("Comment", ""),
                    "parameters": part.get("Parameters", {}),
                }
                for part in table.get("PartitionKeys", []) or []
            ]

            return {
                "success": True,
                "table_name": table_name,
                "database_name": database_name,
                "catalog_name": catalog_name,
                "columns": columns,
                "partitions": partitions,
                "table_type": table.get("TableType", ""),
                "description": table.get("Description", ""),
                "owner": table.get("Owner", ""),
                "create_time": table.get("CreateTime"),
                "update_time": table.get("UpdateTime"),
                "storage_descriptor": {
                    "location": storage_descriptor.get("Location", ""),
                    "input_format": storage_descriptor.get("InputFormat", ""),
                    "output_format": storage_descriptor.get("OutputFormat", ""),
                    "compressed": storage_descriptor.get("Compressed", False),
                    "serde_info": storage_descriptor.get("SerdeInfo", {}),
                },
                "parameters": table.get("Parameters", {}),
            }

        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code")
            if error_code == "EntityNotFoundException":
                return format_error_response(
                    f"Table not found: {database_name}.{table_name}"
                )

            logger.warning(
                "Glue get_table failed for %s.%s (code=%s); falling back to DESCRIBE query",
                database_name,
                table_name,
                error_code,
            )
            return self._describe_table_via_sql(database_name, table_name, catalog_name)
        except Exception as exc:
            logger.warning(
                "Unexpected error fetching Glue metadata for %s.%s: %s; falling back to DESCRIBE query",
                database_name,
                table_name,
                exc,
            )
            return self._describe_table_via_sql(database_name, table_name, catalog_name)

    def _describe_table_via_sql(self, database_name: str, table_name: str, catalog_name: str) -> Dict[str, Any]:
        """Fallback: describe table structure via DESCRIBE query."""
        if "-" in database_name or any(c in database_name for c in [" ", ".", "@", "/"]):
            escaped_db = f'"{database_name}"'
        else:
            escaped_db = database_name

        if "-" in table_name or any(c in table_name for c in [" ", ".", "@", "/"]):
            escaped_table = f'"{table_name}"'
        else:
            escaped_table = table_name

        query = f"DESCRIBE {escaped_db}.{escaped_table}"

        try:
            with suppress_stdout():
                with self.engine.connect() as conn:
                    result = conn.exec_driver_sql(query)
                    rows = result.fetchall()
                    keys = tuple(result.keys())

            columns: List[Dict[str, Any]] = []
            partitions: List[Dict[str, Any]] = []

            for row in rows:
                mapping = getattr(row, "_mapping", None)
                values = []
                for idx, key in enumerate(keys):
                    if mapping is not None and key in mapping:
                        values.append(mapping.get(key))
                    else:
                        try:
                            values.append(row[idx])
                        except Exception:
                            values.append(None)
                col_name = values[0] if len(values) > 0 else ""
                col_type = values[1] if len(values) > 1 else "string"
                col_comment = values[2] if len(values) > 2 else ""

                if not col_name or str(col_name).startswith("#"):
                    continue

                entry = {
                    "name": col_name,
                    "type": col_type,
                    "comment": col_comment,
                    "parameters": {},
                }

                if "partition" in str(col_comment).lower():
                    partitions.append(entry)
                else:
                    columns.append(entry)

            return {
                "success": True,
                "table_name": table_name,
                "database_name": database_name,
                "catalog_name": catalog_name,
                "columns": columns,
                "partitions": partitions,
                "table_type": "",
                "description": "",
                "owner": "",
                "create_time": None,
                "update_time": None,
                "storage_descriptor": {
                    "location": "",
                    "input_format": "",
                    "output_format": "",
                    "compressed": False,
                    "serde_info": {},
                },
                "parameters": {},
                "query_used": query,
            }
        except Exception as exc:
            logger.error(
                "Failed to describe table via SQL for %s.%s: %s",
                database_name,
                table_name,
                exc,
            )
            return format_error_response(
                f"Failed to get table metadata for {database_name}.{table_name}: {str(exc)}"
            )

    def execute_query(self, query: str, database_name: str = None, max_results: int = 1000) -> Dict[str, Any]:
        """Execute query using SQLAlchemy with PyAthena and return results as DataFrame."""
        try:
            # Set database context if provided
            if database_name:
                # Properly escape database name for USE statement
                if "-" in database_name or any(c in database_name for c in [" ", ".", "@", "/"]):
                    escaped_db = f'"{database_name}"'
                else:
                    escaped_db = database_name

                with self.engine.connect() as conn:
                    conn.execute(text(f"USE {escaped_db}"))

            # Execute query and load results into pandas DataFrame
            # Sanitize query to prevent string formatting issues
            safe_query = self._sanitize_query_for_pandas(query)
            with suppress_stdout():
                df = pd.read_sql_query(safe_query, self.engine)

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

    def list_workgroups(self, session: Optional[boto3.Session] = None, region_override: Optional[str] = None) -> List[Dict[str, Any]]:
        """List available Athena workgroups using the service's authentication patterns."""
        try:
            if session is None:
                session = self._build_boto3_session()

            region = region_override or self._determine_region()
            athena_client = session.client("athena", region_name=region)

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

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

from ..utils import format_error_response, suppress_stdout

logger = logging.getLogger(__name__)


class AthenaQueryService:
    """Core service for Athena query execution and Glue catalog operations."""
    
    def __init__(self, use_quilt_auth: bool = True):
        """Initialize the Athena service.
        
        Args:
            use_quilt_auth: Whether to use quilt3 authentication
        """
        self.use_quilt_auth = use_quilt_auth
        self.query_cache = TTLCache(maxsize=100, ttl=3600)  # 1 hour cache
        
        # Initialize clients
        self._glue_client: Optional[Any] = None
        self._s3_client: Optional[Any] = None
        self._engine: Optional[Engine] = None
        
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
                # Use quilt3 session credentials
                import quilt3
                botocore_session = quilt3.session.create_botocore_session()
                credentials = botocore_session.get_credentials()
                
                # Force region to us-east-1 for Quilt Athena workgroup
                # The QuiltUserAthena workgroup and permissions are configured in us-east-1
                region = 'us-east-1'
                
                # Discover available workgroups dynamically
                workgroup = self._discover_workgroup(credentials, region)
                
                # Create connection string with explicit credentials
                # URL encode the credentials to handle special characters
                from urllib.parse import quote_plus
                
                access_key = quote_plus(credentials.access_key)
                secret_key = quote_plus(credentials.secret_key)
                
                # Create connection string without hardcoded schema or workgroup
                connection_string = (
                    f"awsathena+rest://{access_key}:{secret_key}@athena.{region}.amazonaws.com:443/"
                    f"?work_group={workgroup}"
                )

                
                # Add session token if available
                if credentials.token:
                    connection_string += f"&aws_session_token={quote_plus(credentials.token)}"
                
                logger.info(f"Creating Athena engine with workgroup: {workgroup}")
                return create_engine(connection_string, echo=False)
                    
            else:
                # Use default AWS credentials
                region = os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')
                
                # Discover available workgroups dynamically or fall back to environment
                workgroup = self._discover_workgroup(None, region) or os.environ.get('ATHENA_WORKGROUP', 'primary')
                
                connection_string = (
                    f"awsathena+rest://@athena.{region}.amazonaws.com:443/"
                    f"?work_group={workgroup}"
                )
                
                logger.info(f"Creating Athena engine with workgroup: {workgroup}")
                return create_engine(connection_string, echo=False)
            
        except Exception as e:
            logger.error(f"Failed to create SQLAlchemy engine: {e}")
            raise
    
    def _discover_workgroup(self, credentials, region: str) -> str:
        """Discover the best available Athena workgroup for the user."""
        try:
            import boto3
            
            # Create Athena client with provided credentials or default
            if credentials:
                athena_client = boto3.client(
                    'athena',
                    region_name=region,
                    aws_access_key_id=credentials.access_key,
                    aws_secret_access_key=credentials.secret_key,
                    aws_session_token=credentials.token
                )
            else:
                athena_client = boto3.client('athena', region_name=region)
            
            # List all available workgroups
            response = athena_client.list_work_groups()
            workgroups = []
            
            # Test access to each workgroup and filter valid ones
            for wg in response.get('WorkGroups', []):
                name = wg.get('Name')
                if not name:
                    continue
                    
                try:
                    # Validate workgroup is accessible and properly configured
                    wg_details = athena_client.get_work_group(WorkGroup=name)
                    config = wg_details.get('WorkGroup', {}).get('Configuration', {})
                    
                    # Check if workgroup is enabled and has output location
                    if (wg_details.get('WorkGroup', {}).get('State') == 'ENABLED' and 
                        config.get('ResultConfiguration', {}).get('OutputLocation')):
                        workgroups.append(name)
                except Exception:
                    # Skip workgroups we can't access
                    continue
            
            # Prioritize workgroups (Quilt workgroups first, then others)
            quilt_workgroups = [wg for wg in workgroups if 'quilt' in wg.lower()]
            if quilt_workgroups:
                return quilt_workgroups[0]
            elif workgroups:
                return workgroups[0]
            else:
                # Fallback to primary if no workgroups discovered
                return 'primary'
                
        except Exception as e:
            logger.warning(f"Failed to discover workgroups: {e}")
            # Fallback to environment variable or primary
            return os.environ.get('ATHENA_WORKGROUP', 'primary')
    
    def _create_glue_client(self):
        """Create Glue client for metadata operations."""
        if self.use_quilt_auth:
            try:
                import quilt3
                botocore_session = quilt3.session.create_botocore_session()
                # Use us-east-1 region for Quilt Athena workgroup resources
                return botocore_session.create_client('glue', region_name='us-east-1')
            except Exception:
                # Fallback to default credentials
                pass
        return boto3.client('glue', region_name='us-east-1')
    
    def _create_s3_client(self):
        """Create S3 client for result management."""
        if self.use_quilt_auth:
            try:
                import quilt3
                botocore_session = quilt3.session.create_botocore_session()
                return botocore_session.create_client('s3')
            except Exception:
                # Fallback to default credentials
                pass
        return boto3.client('s3')
    
    def _get_s3_staging_dir(self) -> str:
        """Get S3 staging directory for query results."""
        return os.environ.get('ATHENA_QUERY_RESULT_LOCATION', 's3://aws-athena-query-results/')
    
    def discover_databases(self, catalog_name: str = "AwsDataCatalog") -> Dict[str, Any]:
        """Discover all databases using Athena SQL queries."""
        try:
            # Use Athena SQL to list databases instead of direct Glue API
            with suppress_stdout():
                df = pd.read_sql_query("SHOW DATABASES", self.engine)
            
            databases = []
            for _, row in df.iterrows():
                db_name = row.iloc[0]  # First column should be database name
                databases.append({
                    'name': db_name,
                    'description': '',  # Not available through SHOW DATABASES
                    'location_uri': '',  # Not available through SHOW DATABASES
                    'create_time': None,  # Not available through SHOW DATABASES
                    'parameters': {}
                })
            
            return {
                'success': True,
                'databases': databases,
                'catalog_name': catalog_name,
                'count': len(databases)
            }
            
        except Exception as e:
            logger.error(f"Failed to discover databases: {e}")
            return format_error_response(f"Failed to discover databases: {str(e)}")
    
    def discover_tables(self, database_name: str, catalog_name: str = "AwsDataCatalog", 
                       table_pattern: str = None) -> Dict[str, Any]:
        """Discover tables using Athena SQL queries."""
        try:
            # Use Athena SQL to list tables instead of direct Glue API
            query = f"SHOW TABLES IN {database_name}"
            if table_pattern:
                query += f" LIKE '{table_pattern}'"
                
            with suppress_stdout():
                df = pd.read_sql_query(query, self.engine)
            
            tables = []
            for _, row in df.iterrows():
                table_name = row.iloc[0]  # First column should be table name
                tables.append({
                    'name': table_name,
                    'database_name': database_name,
                    'description': '',  # Not available through SHOW TABLES
                    'owner': '',
                    'create_time': None,
                    'update_time': None,
                    'table_type': '',
                    'storage_descriptor': {
                        'location': '',
                        'input_format': '',
                        'output_format': '',
                        'serde_info': {}
                    },
                    'partition_keys': [],
                    'parameters': {}
                })
            
            return {
                'success': True,
                'tables': tables,
                'database_name': database_name,
                'catalog_name': catalog_name,
                'count': len(tables)
            }
            
        except Exception as e:
            logger.error(f"Failed to discover tables: {e}")
            return format_error_response(f"Failed to discover tables: {str(e)}")
    
    def get_table_metadata(self, database_name: str, table_name: str, 
                          catalog_name: str = "AwsDataCatalog") -> Dict[str, Any]:
        """Get comprehensive table metadata using Athena DESCRIBE."""
        try:
            # Use Athena SQL to describe table instead of direct Glue API
            query = f"DESCRIBE {database_name}.{table_name}"
            
            with suppress_stdout():
                df = pd.read_sql_query(query, self.engine)
            
            columns = []
            partitions = []
            
            for _, row in df.iterrows():
                col_name = row.iloc[0]
                col_type = row.iloc[1] if len(row) > 1 else 'string'
                col_comment = row.iloc[2] if len(row) > 2 else ''
                
                # Check if this is a partition column
                # Partition columns often appear after a separator or with special formatting
                if col_name.startswith('#') or 'partition' in str(col_comment).lower():
                    continue  # Skip header/separator rows
                elif any(keyword in str(col_name).lower() for keyword in ['partition', 'date', 'year', 'month']):
                    # This is likely a partition column
                    partitions.append({
                        'name': col_name,
                        'type': col_type,
                        'comment': col_comment
                    })
                else:
                    # Regular column
                    columns.append({
                        'name': col_name,
                        'type': col_type,
                        'comment': col_comment,
                        'parameters': {}
                    })
            
            return {
                'success': True,
                'table_name': table_name,
                'database_name': database_name,
                'catalog_name': catalog_name,
                'columns': columns,
                'partitions': partitions,
                'table_type': '',  # Not available through DESCRIBE
                'description': '',  # Not available through DESCRIBE
                'owner': '',  # Not available through DESCRIBE
                'create_time': None,  # Not available through DESCRIBE
                'update_time': None,  # Not available through DESCRIBE
                'storage_descriptor': {
                    'location': '',  # Not available through DESCRIBE
                    'input_format': '',  # Not available through DESCRIBE
                    'output_format': '',  # Not available through DESCRIBE
                    'compressed': False,  # Not available through DESCRIBE
                    'serde_info': {}  # Not available through DESCRIBE
                },
                'parameters': {}  # Not available through DESCRIBE
            }
            
        except Exception as e:
            logger.error(f"Failed to get table metadata: {e}")
            return format_error_response(f"Failed to get table metadata: {str(e)}")
    
    def execute_query(self, query: str, database_name: str = None, 
                     max_results: int = 1000) -> Dict[str, Any]:
        """Execute query using SQLAlchemy with PyAthena and return results as DataFrame."""
        try:
            # Set database context if provided
            if database_name:
                with self.engine.connect() as conn:
                    conn.execute(text(f"USE {database_name}"))
            
            # Execute query and load results into pandas DataFrame
            with suppress_stdout():
                df = pd.read_sql_query(query, self.engine)
            
            # Apply result limit
            truncated = False
            if len(df) > max_results:
                df = df.head(max_results)
                truncated = True
            
            return {
                'success': True,
                'data': df,
                'row_count': len(df),
                'total_rows': len(df) if not truncated else f"{max_results}+",
                'truncated': truncated,
                'columns': list(df.columns),
                'dtypes': {col: str(dtype) for col, dtype in df.dtypes.items()},
                'query': query
            }
            
        except SQLAlchemyError as e:
            logger.error(f"SQL execution error: {e}")
            return format_error_response(f"SQL execution error: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to execute query: {e}")
            return format_error_response(f"Query execution failed: {str(e)}")
    
    def format_results(self, result_data: Dict[str, Any], output_format: str = 'json') -> Dict[str, Any]:
        """Format query results in requested format."""
        if not result_data.get('success') or result_data.get('data') is None:
            return result_data
        
        df = result_data['data']
        
        try:
            if output_format.lower() == 'json':
                formatted_data = df.to_dict(orient='records')
            elif output_format.lower() == 'csv':
                formatted_data = df.to_csv(index=False)
            elif output_format.lower() == 'parquet':
                # For parquet, return base64 encoded bytes
                import io
                import base64
                buffer = io.BytesIO()
                df.to_parquet(buffer, index=False)
                formatted_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
            else:
                # Default to JSON
                formatted_data = df.to_dict(orient='records')
            
            # Update result with formatted data
            result_copy = result_data.copy()
            result_copy['formatted_data'] = formatted_data
            result_copy['format'] = output_format.lower()
            
            # Remove the DataFrame to make it JSON serializable
            result_copy.pop('data', None)
            
            return result_copy
            
        except Exception as e:
            logger.error(f"Failed to format results: {e}")
            return format_error_response(f"Failed to format results: {str(e)}")
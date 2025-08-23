# Phase 10: AWS Athena Glue Table Query Specification

## Overview

Phase 10 implements AWS Athena integration functionality that allows the MCP server to discover AWS Glue Data Catalog tables and execute SQL queries against them using Athena. This enables users to query structured data stored in S3 through a familiar SQL interface, with results that can be integrated with Quilt package workflows.

## Requirements

### Functional Requirements

- **Glue Catalog Discovery**: Automatically discover databases and tables in AWS Glue Data Catalog
- **Schema Inspection**: Retrieve table schemas, column types, and metadata
- **SQL Query Execution**: Execute SQL queries against Glue tables using Athena
- **Result Management**: Handle query results with pagination and format options
- **Query History**: Track and manage query execution history
- **Cost Optimization**: Provide query cost estimates and optimization suggestions

### Quality Requirements

- **Query Performance**: Efficient query execution with proper partitioning support
- **Result Streaming**: Handle large result sets with streaming and pagination
- **Error Handling**: Clear error messages for SQL syntax, permissions, and resource issues
- **Cost Awareness**: Transparent cost reporting and budget-friendly defaults
- **Security Conscious**: Proper handling of sensitive data in query results
- **Resource Management**: Automatic cleanup of query results and temporary resources

### Technical Requirements

- **SQLAlchemy Integration**: Use SQLAlchemy with PyAthena driver for query execution
- **PyAthena Driver**: Leverage PyAthena for Athena connectivity and SQL operations
- **Glue Catalog Integration**: Access AWS Glue Data Catalog for metadata discovery
- **S3 Result Storage**: Manage query results stored in S3
- **Authentication Flexibility**: Support authentication via quilt3 assumed roles or native AWS permissions
- **Query Optimization**: Support for partitioning, compression, and columnar formats
- **Result Formatting**: Multiple output formats (JSON, CSV, Parquet)
- **Connection Pooling**: Efficient database connection management via SQLAlchemy

## Implementation Details

### Athena Query Workflow

**Query Execution Process:**
1. **Authentication Setup**: Establish AWS credentials via quilt3 assumed role or native AWS permissions
2. **SQLAlchemy Connection**: Create PyAthena connection string and SQLAlchemy engine
3. **Catalog Discovery**: Enumerate available databases and tables using Glue APIs
4. **Schema Validation**: Validate table schemas and column references via SQLAlchemy reflection
5. **Query Planning**: Analyze query for optimization opportunities
6. **Query Execution**: Execute SQL via SQLAlchemy with PyAthena driver
7. **Result Processing**: Process query results using pandas DataFrames
8. **Result Formatting**: Convert results to requested output format
9. **Resource Cleanup**: Clean up connections and temporary resources

### Query Result Management

**Result Handling Strategy:**
- **Streaming Results**: Large result sets streamed with pagination
- **Result Caching**: Intelligent caching of frequently accessed results
- **Format Options**: Support for JSON, CSV, and Parquet output formats
- **Result Limits**: Configurable limits to prevent runaway queries
- **Cost Tracking**: Track data scanned and estimated costs per query

### Athena Query Tools

**New MCP Tools:**

#### `athena_databases_list`
```python
async def athena_databases_list(
    catalog_name: str = "AwsDataCatalog"
) -> Dict[str, Any]:
    """
    List available databases in AWS Glue Data Catalog.
    
    Args:
        catalog_name: Name of the data catalog (default: AwsDataCatalog)
        
    Returns:
        List of databases with metadata
    """
```

#### `athena_tables_list`
```python
async def athena_tables_list(
    database_name: str,
    catalog_name: str = "AwsDataCatalog",
    table_pattern: str = None
) -> Dict[str, Any]:
    """
    List tables in a specific database.
    
    Args:
        database_name: Name of the database
        catalog_name: Name of the data catalog
        table_pattern: Optional pattern to filter table names
        
    Returns:
        List of tables with metadata and schemas
    """
```

#### `athena_table_schema`
```python
async def athena_table_schema(
    database_name: str,
    table_name: str,
    catalog_name: str = "AwsDataCatalog"
) -> Dict[str, Any]:
    """
    Get detailed schema information for a specific table.
    
    Args:
        database_name: Name of the database
        table_name: Name of the table
        catalog_name: Name of the data catalog
        
    Returns:
        Detailed table schema including columns, types, partitions
    """
```

#### `athena_query_execute`
```python
async def athena_query_execute(
    query: str,
    database_name: str = None,
    max_results: int = 1000,
    output_format: str = "json",
    use_quilt_auth: bool = True
) -> Dict[str, Any]:
    """
    Execute SQL query against Athena using SQLAlchemy/PyAthena.
    
    Args:
        query: SQL query to execute
        database_name: Default database for query context (optional)
        max_results: Maximum number of results to return
        output_format: Output format (json, csv, parquet)
        use_quilt_auth: Use quilt3 assumed role credentials if available
        
    Returns:
        Query execution results with data, metadata, and formatting
    """
```

#### `athena_query_history`
```python
async def athena_query_history(
    max_results: int = 50,
    status_filter: str = None,
    start_time: str = None,
    end_time: str = None
) -> Dict[str, Any]:
    """
    Retrieve query execution history.
    
    Args:
        max_results: Maximum number of queries to return
        status_filter: Filter by query status (SUCCEEDED, FAILED, etc.)
        start_time: Start time for query range (ISO format)
        end_time: End time for query range (ISO format)
        
    Returns:
        List of historical query executions
    """
```

### Athena Service Implementation

**Core Athena Service Engine:**
```python
from sqlalchemy import create_engine, MetaData, inspect
from pyathena import connect
from pyathena.sqlalchemy import AthenaDialect
import pandas as pd

class AthenaQueryService:
    def __init__(self, use_quilt_auth: bool = True):
        self.use_quilt_auth = use_quilt_auth
        self.glue_client = self._create_glue_client()
        self.s3_client = self._create_s3_client()
        self.engine = self._create_sqlalchemy_engine()
        self.query_cache = TTLCache(maxsize=100, ttl=3600)  # 1 hour cache
    
    def _create_sqlalchemy_engine(self):
        """Create SQLAlchemy engine with PyAthena driver."""
        if self.use_quilt_auth:
            # Use quilt3 session credentials
            import quilt3
            session = quilt3.session.get_session()
            credentials = session.get_credentials()
            
            connection_string = (
                f"awsathena+rest://{credentials['AccessKeyId']}:"
                f"{credentials['SecretAccessKey']}@athena.{session.region_name}.amazonaws.com/"
                f"?s3_staging_dir={self._get_s3_staging_dir()}"
                f"&work_group=QuiltUserAthena-quilt-staging-NonManagedRoleWorkgroup"
                f"&aws_session_token={credentials.get('SessionToken', '')}"
            )
        else:
            # Use default AWS credentials
            region = os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')
            connection_string = (
                f"awsathena+rest://@athena.{region}.amazonaws.com/"
                f"?s3_staging_dir={self._get_s3_staging_dir()}"
                f"&work_group=primary"
            )
        
        return create_engine(connection_string, echo=False)
    
    def _create_glue_client(self):
        """Create Glue client for metadata operations."""
        if self.use_quilt_auth:
            import quilt3
            session = quilt3.session.get_session()
            return session.client('glue')
        return boto3.client('glue')
    
    def _create_s3_client(self):
        """Create S3 client for result management."""
        if self.use_quilt_auth:
            import quilt3
            session = quilt3.session.get_session()
            return session.client('s3')
        return boto3.client('s3')
    
    def _get_s3_staging_dir(self) -> str:
        """Get S3 staging directory for query results."""
        return os.environ.get('ATHENA_QUERY_RESULT_LOCATION', 's3://athena-query-results/')
    
    async def discover_databases(self, catalog_name: str) -> List[Dict[str, Any]]:
        """Discover all databases using Glue client."""
        response = self.glue_client.get_databases(CatalogId=catalog_name)
        return response.get('DatabaseList', [])
        
    async def discover_tables(self, database_name: str, catalog_name: str) -> List[Dict[str, Any]]:
        """Discover tables using SQLAlchemy reflection and Glue metadata."""
        inspector = inspect(self.engine)
        table_names = inspector.get_table_names(schema=database_name)
        
        tables = []
        for table_name in table_names:
            # Get table metadata from Glue
            table_metadata = self.glue_client.get_table(
                CatalogId=catalog_name,
                DatabaseName=database_name,
                Name=table_name
            )
            tables.append({
                'name': table_name,
                'metadata': table_metadata.get('Table', {}),
                'columns': inspector.get_columns(table_name, schema=database_name)
            })
        
        return tables
        
    async def get_table_metadata(self, database_name: str, table_name: str, catalog_name: str) -> Dict[str, Any]:
        """Get comprehensive table metadata using SQLAlchemy and Glue."""
        inspector = inspect(self.engine)
        
        # Get column information via SQLAlchemy
        columns = inspector.get_columns(table_name, schema=database_name)
        
        # Get detailed metadata from Glue
        glue_metadata = self.glue_client.get_table(
            CatalogId=catalog_name,
            DatabaseName=database_name,
            Name=table_name
        )
        
        return {
            'table_name': table_name,
            'database_name': database_name,
            'columns': columns,
            'glue_metadata': glue_metadata.get('Table', {}),
            'partitions': inspector.get_pk_constraint(table_name, schema=database_name)
        }
        
    async def execute_query(self, query: str, max_results: int = 1000) -> Dict[str, Any]:
        """Execute query using SQLAlchemy with PyAthena and return results as DataFrame."""
        try:
            # Execute query and load results into pandas DataFrame
            df = pd.read_sql_query(query, self.engine)
            
            # Apply result limit
            if len(df) > max_results:
                df = df.head(max_results)
                truncated = True
            else:
                truncated = False
            
            return {
                'success': True,
                'data': df,
                'row_count': len(df),
                'truncated': truncated,
                'columns': list(df.columns),
                'dtypes': df.dtypes.to_dict()
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'data': None
            }
    
    async def format_results(self, result_data: Dict[str, Any], output_format: str = 'json') -> Dict[str, Any]:
        """Format query results in requested format."""
        if not result_data.get('success') or result_data.get('data') is None:
            return result_data
        
        df = result_data['data']
        
        if output_format.lower() == 'json':
            formatted_data = df.to_dict(orient='records')
        elif output_format.lower() == 'csv':
            formatted_data = df.to_csv(index=False)
        elif output_format.lower() == 'parquet':
            # For parquet, we'd save to a temporary location
            formatted_data = df.to_parquet(index=False)
        else:
            formatted_data = df.to_dict(orient='records')
        
        result_data['formatted_data'] = formatted_data
        result_data['format'] = output_format
        
        return result_data
```

### Query Optimization Features

**Performance Optimization:**
- **Partition Pruning**: Automatic detection and use of partitioned columns
- **Columnar Selection**: Encourage SELECT with specific columns vs SELECT *
- **Compression Analysis**: Recommend optimal file formats and compression
- **Cost Estimation**: Pre-query cost estimates based on data size
- **Query Caching**: Cache results for identical queries
- **Result Pagination**: Handle large result sets efficiently

### Security and Permissions

**Security Implementation:**
- **IAM Role Validation**: Verify proper Athena and Glue permissions
- **Query Sanitization**: Basic SQL injection prevention
- **Data Masking**: Support for sensitive data handling
- **Access Control**: Respect Glue catalog permissions and resource policies
- **Audit Logging**: Log all query executions for security tracking

### SQL Syntax Requirements

**Athena SQL Compatibility:**
- **Table Identifiers**: Use double quotes for table names with special characters (hyphens, spaces, etc.)
  - ✅ Correct: `SELECT * FROM "table-with-hyphens"`
  - ❌ Incorrect: `SELECT * FROM `table-with-hyphens``
- **Column Identifiers**: Use double quotes for column names with special characters
  - ✅ Correct: `SELECT "column-name" FROM my_table`
  - ❌ Incorrect: `SELECT `column-name` FROM my_table`
- **Standard SQL**: Athena uses Presto/Trino SQL syntax, not MySQL backtick syntax
- **Query Validation**: The `athena_query_validate` tool will detect and reject backtick usage

**Supported Query Types:**
- `SELECT` statements with joins, aggregations, and window functions
- `WITH` clauses for common table expressions
- `SHOW` statements for catalog exploration
- `DESCRIBE` statements for schema inspection
- `EXPLAIN` statements for query planning

**Unsupported Operations:**
- Data modification operations (`INSERT`, `UPDATE`, `DELETE`, `CREATE`, `DROP`)
- MySQL-specific syntax including backtick identifiers
- Stored procedures and user-defined functions

## User Experience Flow

### 1. Database Discovery
```
User: "What databases are available in Athena?"

MCP: "Discovering databases in AWS Glue Data Catalog...

     📊 Available Databases (3):
     
     1. analytics_db
        ├── Tables: 15
        ├── Last Updated: 2024-01-15
        └── Description: Customer analytics data warehouse
     
     2. ml_features_db  
        ├── Tables: 8
        ├── Last Updated: 2024-01-20
        └── Description: Machine learning feature store
        
     3. raw_data_db
        ├── Tables: 23
        ├── Last Updated: 2024-01-22
        └── Description: Raw ingested data from various sources"
```

### 2. Table Schema Inspection
```
User: "Show me the schema for analytics_db.customer_events"

MCP: "Table Schema: analytics_db.customer_events
     
     📋 Table Information:
     ├── Location: s3://analytics-data/customer_events/
     ├── Format: Parquet
     ├── Partitions: date, region
     ├── Rows: ~2.5M (estimated)
     └── Size: 1.2 GB
     
     🏗️  Column Schema:
     ├── customer_id (bigint) - Customer identifier
     ├── event_type (string) - Type of customer event  
     ├── timestamp (timestamp) - Event timestamp
     ├── properties (map<string,string>) - Event properties
     ├── date (string) - Partition: Event date (YYYY-MM-DD)
     └── region (string) - Partition: AWS region
     
     💡 Query Tips:
     - Always filter by date for better performance
     - Use region filter when possible
     - Estimated cost per full scan: $0.10"
```

### 3. Query Execution
```
User: "Run query: SELECT event_type, COUNT(*) FROM analytics_db.customer_events WHERE date >= '2024-01-01' GROUP BY event_type LIMIT 10"

Note: For tables with hyphens or special characters, use double quotes:
"SELECT * FROM \"table-with-hyphens\" WHERE \"column-name\" = 'value'"

MCP: "Executing query via SQLAlchemy/PyAthena...
     
     ⏳ Connecting to Athena...
     ⏳ Executing SQL query...
     ⏳ Processing results...
     
     ✅ Query Completed (4.2 seconds)
     
     📊 Results (JSON format):
     [
       {"event_type": "page_view", "count": 125432},
       {"event_type": "purchase", "count": 23891},
       {"event_type": "cart_add", "count": 45123},
       {"event_type": "user_signup", "count": 8234},
       {"event_type": "session_start", "count": 67890}
     ]
     
     📈 Query Details:
     ├── Rows Returned: 5
     ├── Execution Time: 4.2 seconds
     ├── Output Format: JSON
     └── Result Truncated: No
     
     💡 Tip: Use output_format='csv' for CSV output or 'parquet' for structured data"
```

### 4. Query Error Handling
```
User: "SELECT * FROM nonexistent_table"

MCP: "❌ Query Execution Failed
     
     Error Details:
     ├── Type: Table Not Found
     ├── Message: Table 'nonexistent_table' doesn't exist
     ├── Suggestion: Check available tables with athena_tables_list
     └── Execution Time: 1.1 seconds
     
     💡 Available databases: analytics_db, ml_features_db, raw_data_db
     Use athena_tables_list to see tables in each database"
```

## Validation Process

The SPEC-compliant validation follows this 6-step process:

1. **Preconditions** (`make init`): Check AWS credentials, Athena permissions, and Glue access
2. **Execution** (`make run`): Execute Athena discovery and query workflows
3. **Testing** (`make test`): Validate query execution, result handling, and error scenarios
4. **Verification** (`make verify`): Confirm MCP tools respond correctly with sample queries
5. **Zero** (`make zero`): Clean up test resources, query results, and temporary data
6. **Config** (`make config`): Generate `.config` with discovered databases and test results

## Success Criteria

- ✅ Successfully discovers Glue databases and tables with complete metadata
- ✅ Executes SQL queries against Athena with proper error handling
- ✅ Handles query results efficiently with pagination and format options
- ✅ Provides accurate cost estimates and optimization recommendations
- ✅ Manages long-running queries with status polling and cancellation
- ✅ Integrates securely with existing AWS permissions and IAM roles
- ✅ Caches query results and metadata to minimize API calls and costs
- ✅ Supports multiple output formats and handles large result sets

## Files and Structure

```text
app/quilt_mcp/tools/
├── athena_glue.py             # Athena/Glue query tools
└── athena_optimizer.py        # Query optimization utilities

app/quilt_mcp/aws/
├── athena_service.py          # Core Athena service implementation
├── glue_catalog.py           # Glue Data Catalog integration
└── query_manager.py          # Query execution and result management

spec/
└── 10-athena-glue-spec.md    # This specification

tests/
├── test_athena_glue.py       # Athena/Glue tool tests
├── test_query_execution.py   # Query execution tests
└── test_integration_athena.py # Integration tests with real AWS resources
```

## Dependencies

The following additional dependencies are required for Athena/Glue integration:

```toml
[project.dependencies]
# Existing dependencies...
sqlalchemy = ">=2.0.0"        # SQL toolkit and ORM
pyathena = ">=3.0.0"          # Athena driver for SQLAlchemy
pandas = ">=2.0.0"            # Data manipulation (already included)
```

**PyAthena Configuration:**
- **Connection String Format**: `awsathena+rest://` for REST-based connections
- **Authentication**: Supports AWS credentials, assumed roles, and session tokens
- **Result Storage**: Configurable S3 staging directory for query results
- **Workgroup Support**: Integration with Athena workgroups for cost control
- **Quilt Workgroup**: When using quilt3 credentials, uses workgroup "QuiltUserAthena-quilt-staging-NonManagedRoleWorkgroup"

## Security Considerations

- **Query Sanitization**: Basic validation to prevent malicious SQL injection
- **Permission Validation**: Verify IAM permissions before query execution
- **Data Classification**: Handle sensitive data according to security policies  
- **Result Security**: Secure handling of query results containing sensitive information
- **Cost Controls**: Prevent runaway queries that could generate unexpected costs
- **Audit Trail**: Comprehensive logging of all query executions and data access

## Performance Optimization

- **Query Caching**: Cache identical query results with appropriate TTL
- **Metadata Caching**: Cache Glue catalog metadata to reduce API calls
- **Partition Optimization**: Automatic partition pruning recommendations
- **Result Streaming**: Stream large result sets to handle memory efficiently
- **Parallel Execution**: Support concurrent query execution where appropriate
- **Cost Monitoring**: Real-time cost tracking and budget alerts

## Environment Variables

- `ATHENA_QUERY_RESULT_LOCATION`: Default S3 location for query results
- `ATHENA_WORKGROUP`: Default Athena workgroup (default: primary for native AWS, QuiltUserAthena-quilt-staging-NonManagedRoleWorkgroup for quilt3)
- `ATHENA_QUILT_WORKGROUP`: Athena workgroup for quilt3 credentials (default: QuiltUserAthena-quilt-staging-NonManagedRoleWorkgroup)
- `ATHENA_QUERY_TIMEOUT`: Query timeout in seconds (default: 300)
- `ATHENA_MAX_RESULTS_DEFAULT`: Default maximum results per query (default: 1000)
- `GLUE_CATALOG_NAME`: Default Glue catalog name (default: AwsDataCatalog)
- `ATHENA_RESULT_CACHE_TTL`: Result cache TTL in seconds (default: 1800)
- `ENABLE_QUERY_COST_ESTIMATION`: Enable pre-query cost estimation (default: true)
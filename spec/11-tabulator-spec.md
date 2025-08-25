# Phase 11: Quilt Tabulator Integration Specification

## Overview

Phase 11 implements Quilt Tabulator integration functionality that allows the MCP server to create and manage Quilt tabulator tables. Quilt Tabulator is a custom Athena connector that enables SQL querying across multiple Quilt packages, providing a powerful data aggregation layer for package contents.

## Requirements

### Functional Requirements

- **Tabulator Table Management**: Create, update, delete, and list tabulator tables
- **Schema Definition**: Define column schemas with proper data types
- **Pattern Matching**: Configure package name and logical key patterns with named capture groups
- **Parser Configuration**: Support CSV, TSV, and Parquet file formats with custom parsing options
- **Query Control**: Enable/disable open query functionality for tabulator tables
- **Validation**: Validate tabulator configurations before creation/update

### Quality Requirements

- **Configuration Validation**: Ensure tabulator configurations are syntactically correct
- **Error Handling**: Clear error messages for invalid configurations and API failures
- **Performance Awareness**: Provide guidance on performance implications of table configurations
- **Cost Transparency**: Alert users to potential cost implications of extensive querying
- **Security Conscious**: Proper validation of regex patterns and configuration inputs

### Technical Requirements

- **Quilt3 Admin Integration**: Use quilt3.admin module for GraphQL operations
- **YAML Configuration**: Generate proper YAML configurations for tabulator tables
- **Regex Validation**: Validate package and logical key patterns
- **Authentication**: Use Quilt authentication for admin operations
- **Configuration Management**: Handle complex tabulator configurations with proper defaults

## Implementation Details

### Tabulator Configuration Structure

**Standard Tabulator Configuration:**
```yaml
schema:
  - name: column_name
    type: STRING|INT|FLOAT|BOOLEAN|TIMESTAMP
source:
  type: quilt-packages
  package_name: "^bucket/(?<capture_group>[^/]+)/package_name$"
  logical_key: "path/(?<sample_id>[^/]+)/file_pattern\\.(csv|tsv|parquet)$"
parser:
  format: csv|tsv|parquet
  delimiter: "\t"|","
  header: true|false
  skip_rows: 0
```

**Automatic Columns Added by Tabulator:**
- `quilt_package_name`: Full package name
- `quilt_logical_key`: Logical key within package
- Named capture groups from patterns (e.g., `capture_group`, `sample_id`)

### Tabulator Service Implementation

**Core Tabulator Service:**
```python
import yaml
from typing import Dict, List, Any, Optional
from quilt3.admin import AdminClient

class TabulatorService:
    def __init__(self, use_quilt_auth: bool = True):
        self.use_quilt_auth = use_quilt_auth
        self.admin_client = AdminClient() if use_quilt_auth else None
    
    def _build_tabulator_config(
        self,
        schema: List[Dict[str, str]],
        package_pattern: str,
        logical_key_pattern: str,
        parser_config: Dict[str, Any]
    ) -> str:
        """Build YAML configuration for tabulator table."""
        config = {
            'schema': schema,
            'source': {
                'type': 'quilt-packages',
                'package_name': package_pattern,
                'logical_key': logical_key_pattern
            },
            'parser': parser_config
        }
        return yaml.dump(config, default_flow_style=False)
    
    def _validate_schema(self, schema: List[Dict[str, str]]) -> List[str]:
        """Validate schema configuration."""
        errors = []
        valid_types = {'STRING', 'INT', 'FLOAT', 'BOOLEAN', 'TIMESTAMP'}
        
        for column in schema:
            if 'name' not in column:
                errors.append("Schema column missing 'name' field")
            if 'type' not in column:
                errors.append(f"Schema column '{column.get('name', 'unknown')}' missing 'type' field")
            elif column['type'] not in valid_types:
                errors.append(f"Invalid type '{column['type']}' for column '{column['name']}'. Valid types: {valid_types}")
        
        return errors
    
    def _validate_patterns(self, package_pattern: str, logical_key_pattern: str) -> List[str]:
        """Validate regex patterns."""
        errors = []
        import re
        
        try:
            re.compile(package_pattern)
        except re.error as e:
            errors.append(f"Invalid package pattern: {e}")
        
        try:
            re.compile(logical_key_pattern)
        except re.error as e:
            errors.append(f"Invalid logical key pattern: {e}")
        
        return errors
    
    def _validate_parser_config(self, parser_config: Dict[str, Any]) -> List[str]:
        """Validate parser configuration."""
        errors = []
        valid_formats = {'csv', 'tsv', 'parquet'}
        
        if 'format' not in parser_config:
            errors.append("Parser configuration missing 'format' field")
        elif parser_config['format'] not in valid_formats:
            errors.append(f"Invalid format '{parser_config['format']}'. Valid formats: {valid_formats}")
        
        # Format-specific validation
        if parser_config.get('format') in ['csv', 'tsv']:
            if 'delimiter' not in parser_config:
                # Set default delimiter based on format
                parser_config['delimiter'] = '\t' if parser_config['format'] == 'tsv' else ','
            if 'header' not in parser_config:
                parser_config['header'] = True
        
        return errors
    
    async def list_tables(self, bucket_name: str) -> Dict[str, Any]:
        """List all tabulator tables for a bucket."""
        try:
            if not self.admin_client:
                return format_error_response("Admin client not available")
            
            # Execute GraphQL query to list tabulator tables
            response = self.admin_client.bucket_tabulator_tables_list(name=bucket_name)
            
            if not response or 'bucketConfig' not in response:
                return {
                    'success': True,
                    'tables': [],
                    'bucket_name': bucket_name,
                    'count': 0
                }
            
            tables = response['bucketConfig'].get('tabulatorTables', [])
            
            return {
                'success': True,
                'tables': tables,
                'bucket_name': bucket_name,
                'count': len(tables)
            }
            
        except Exception as e:
            logger.error(f"Failed to list tabulator tables: {e}")
            return format_error_response(f"Failed to list tabulator tables: {str(e)}")
    
    async def create_table(
        self,
        bucket_name: str,
        table_name: str,
        schema: List[Dict[str, str]],
        package_pattern: str,
        logical_key_pattern: str,
        parser_config: Dict[str, Any],
        description: str = None
    ) -> Dict[str, Any]:
        """Create a new tabulator table."""
        try:
            if not self.admin_client:
                return format_error_response("Admin client not available")
            
            # Validate inputs
            validation_errors = []
            validation_errors.extend(self._validate_schema(schema))
            validation_errors.extend(self._validate_patterns(package_pattern, logical_key_pattern))
            validation_errors.extend(self._validate_parser_config(parser_config))
            
            if validation_errors:
                return format_error_response(f"Validation errors: {'; '.join(validation_errors)}")
            
            # Build tabulator configuration
            config_yaml = self._build_tabulator_config(
                schema, package_pattern, logical_key_pattern, parser_config
            )
            
            # Execute GraphQL mutation to create table
            response = self.admin_client.bucket_tabulator_table_set(
                bucket_name=bucket_name,
                table_name=table_name,
                config=config_yaml
            )
            
            if response.get('__typename') == 'InvalidInput':
                return format_error_response(f"Invalid input: {response.get('errors', [])}")
            elif response.get('__typename') == 'OperationError':
                return format_error_response(f"Operation error: {response.get('message', 'Unknown error')}")
            
            return {
                'success': True,
                'table_name': table_name,
                'bucket_name': bucket_name,
                'config': config_yaml,
                'description': description or f"Tabulator table for {bucket_name}"
            }
            
        except Exception as e:
            logger.error(f"Failed to create tabulator table: {e}")
            return format_error_response(f"Failed to create tabulator table: {str(e)}")
    
    async def delete_table(self, bucket_name: str, table_name: str) -> Dict[str, Any]:
        """Delete a tabulator table."""
        try:
            if not self.admin_client:
                return format_error_response("Admin client not available")
            
            # Delete by setting config to None
            response = self.admin_client.bucket_tabulator_table_set(
                bucket_name=bucket_name,
                table_name=table_name,
                config=None
            )
            
            if response.get('__typename') == 'InvalidInput':
                return format_error_response(f"Invalid input: {response.get('errors', [])}")
            elif response.get('__typename') == 'OperationError':
                return format_error_response(f"Operation error: {response.get('message', 'Unknown error')}")
            
            return {
                'success': True,
                'table_name': table_name,
                'bucket_name': bucket_name,
                'message': f"Tabulator table '{table_name}' deleted successfully"
            }
            
        except Exception as e:
            logger.error(f"Failed to delete tabulator table: {e}")
            return format_error_response(f"Failed to delete tabulator table: {str(e)}")
    
    async def rename_table(self, bucket_name: str, table_name: str, new_table_name: str) -> Dict[str, Any]:
        """Rename a tabulator table."""
        try:
            if not self.admin_client:
                return format_error_response("Admin client not available")
            
            # Execute GraphQL mutation to rename table
            response = self.admin_client.bucket_tabulator_table_rename(
                bucket_name=bucket_name,
                table_name=table_name,
                new_table_name=new_table_name
            )
            
            if response.get('__typename') == 'InvalidInput':
                return format_error_response(f"Invalid input: {response.get('errors', [])}")
            elif response.get('__typename') == 'OperationError':
                return format_error_response(f"Operation error: {response.get('message', 'Unknown error')}")
            
            return {
                'success': True,
                'old_table_name': table_name,
                'new_table_name': new_table_name,
                'bucket_name': bucket_name,
                'message': f"Tabulator table renamed from '{table_name}' to '{new_table_name}'"
            }
            
        except Exception as e:
            logger.error(f"Failed to rename tabulator table: {e}")
            return format_error_response(f"Failed to rename tabulator table: {str(e)}")
    
    async def get_open_query_status(self) -> Dict[str, Any]:
        """Get tabulator open query status."""
        try:
            if not self.admin_client:
                return format_error_response("Admin client not available")
            
            response = self.admin_client.tabulator_get_open_query()
            
            return {
                'success': True,
                'open_query_enabled': response.get('admin', {}).get('tabulatorOpenQuery', False)
            }
            
        except Exception as e:
            logger.error(f"Failed to get open query status: {e}")
            return format_error_response(f"Failed to get open query status: {str(e)}")
    
    async def set_open_query(self, enabled: bool) -> Dict[str, Any]:
        """Set tabulator open query status."""
        try:
            if not self.admin_client:
                return format_error_response("Admin client not available")
            
            response = self.admin_client.tabulator_set_open_query(enabled=enabled)
            
            return {
                'success': True,
                'open_query_enabled': response.get('admin', {}).get('tabulatorOpenQuery', enabled),
                'message': f"Open query {'enabled' if enabled else 'disabled'}"
            }
            
        except Exception as e:
            logger.error(f"Failed to set open query status: {e}")
            return format_error_response(f"Failed to set open query status: {str(e)}")
```

### Tabulator MCP Tools

#### `tabulator_tables_list`
List all tabulator tables configured for a bucket.

#### `tabulator_table_create`
Create a new tabulator table with schema definition, pattern matching, and parser configuration.

#### `tabulator_table_delete`
Delete an existing tabulator table configuration.

#### `tabulator_table_rename`
Rename an existing tabulator table.

#### `tabulator_open_query_status`
Get the current status of the tabulator open query feature.

#### `tabulator_open_query_toggle`
Enable or disable the tabulator open query feature.

## User Experience Flow

### 1. Listing Tabulator Tables
```
User: "List tabulator tables for bucket my-data-bucket"

MCP: "📋 Tabulator Tables for my-data-bucket (2):

     1. gene_expression_data
        ├── Schema: 4 columns (gene_id, expression_level, sample_id, study_date)
        ├── Package Pattern: ^my-data-bucket/(?<study_date>[^_]+)_(?<study_id>[^_]+)_rnaseq$
        └── File Pattern: salmon/(?<sample_id>[^/]+)/quant.*\\.genes\\.sf$

     2. customer_events
        ├── Schema: 3 columns (event_type, timestamp, properties)
        ├── Package Pattern: ^analytics/(?<date>[^/]+)/events$
        └── File Pattern: events/(?<region>[^/]+)/.*\\.csv$"
```

### 2. Creating a Tabulator Table
```
User: "Create a tabulator table called 'sales_data' for bucket 'analytics' with columns: product_id (STRING), sales_amount (FLOAT), date (STRING)"

MCP: "Creating tabulator table 'sales_data'...

     📊 Table Configuration:
     ├── Table Name: sales_data
     ├── Bucket: analytics
     ├── Schema: 3 columns defined
     │   ├── product_id (STRING)
     │   ├── sales_amount (FLOAT)  
     │   └── date (STRING)
     ├── Package Pattern: ^analytics/(?<date>[^/]+)/sales$
     ├── Logical Key: sales_data/.*\\.csv$
     └── Parser: CSV with header
     
     ✅ Tabulator table 'sales_data' created successfully!
     
     💡 This table will automatically include:
     - quilt_package_name: Full package name
     - quilt_logical_key: File path within package
     - date: Captured from package name pattern"
```

## Validation Process

The SPEC-compliant validation follows this 6-step process:

1. **Preconditions** (`make init`): Check Quilt authentication and admin permissions
2. **Execution** (`make run`): Execute tabulator table creation and management workflows
3. **Testing** (`make test`): Validate table configurations and GraphQL operations
4. **Verification** (`make verify`): Confirm MCP tools respond correctly with sample operations
5. **Zero** (`make zero`): Clean up test tabulator tables and configurations
6. **Config** (`make config`): Generate `.config` with test results and discovered capabilities

## Success Criteria

- ✅ Successfully lists existing tabulator tables with complete metadata
- ✅ Creates new tabulator tables with proper schema and pattern validation
- ✅ Validates tabulator configurations before creation/update
- ✅ Manages tabulator table lifecycle (create, rename, delete)
- ✅ Controls open query functionality for administrative purposes
- ✅ Provides clear error messages for invalid configurations
- ✅ Integrates securely with Quilt authentication and admin permissions
- ✅ Generates proper YAML configurations for complex tabulator setups

## Files and Structure

```text
app/quilt_mcp/tools/
└── tabulator.py              # Tabulator management tools

app/quilt_mcp/services/
└── tabulator_service.py      # Core tabulator service implementation

spec/
└── 11-tabulator-spec.md      # This specification

tests/
├── test_tabulator.py         # Tabulator tool tests
└── test_tabulator_service.py # Tabulator service tests
```

## Dependencies

The following additional dependencies are required for tabulator integration:

```toml
[project.dependencies]
# Existing dependencies...
PyYAML = ">=6.0.0"           # YAML configuration handling
```

## Security Considerations

- **Pattern Validation**: Comprehensive validation of regex patterns to prevent injection
- **Configuration Sanitization**: Proper sanitization of YAML configurations
- **Admin Permissions**: Verify admin permissions before tabulator operations
- **Input Validation**: Strict validation of all user inputs and schema definitions
- **Error Handling**: Safe error handling that doesn't expose sensitive information

## Performance and Cost Considerations

- **Query Performance**: Tabulator tables should use appropriate partitioning patterns
- **Cost Awareness**: Alert users about potential costs of extensive cross-package queries
- **Pattern Efficiency**: Encourage efficient regex patterns that minimize data scanning
- **Schema Optimization**: Guide users toward optimal column types and structures
- **Resource Management**: Monitor and report on tabulator table usage patterns

## Environment Variables

- `QUILT_ADMIN_ENABLED`: Enable admin operations (default: false)
- `TABULATOR_MAX_TABLES_PER_BUCKET`: Maximum tables per bucket (default: 50)
- `TABULATOR_VALIDATION_TIMEOUT`: Validation timeout in seconds (default: 10)
- `TABULATOR_DEFAULT_FORMAT`: Default parser format (default: csv)
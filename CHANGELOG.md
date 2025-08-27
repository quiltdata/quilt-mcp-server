# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.0] - 2025-08-27

### Added
- **Athena/SQL Analytics Integration**: Complete AWS Athena integration for SQL queries on Quilt data
  - `athena_databases_list` - List available Athena databases
  - `athena_tables_list` - List tables in a database  
  - `athena_query_execute` - Execute SQL queries via Athena
  - `athena_query_history` - Retrieve query execution history
  - `athena_query_validate` - Validate SQL syntax
  - `athena_table_schema` - Get detailed table schema information
  - `athena_workgroups_list` - List available Athena workgroups

- **Tabulator Integration**: SQL-queryable views of tabular data in packages
  - `tabulator_tables_list` - List Quilt Tabulator tables
  - `tabulator_table_create` - Create new tabulator table configurations
  - `tabulator_table_delete` - Delete tabulator table configurations
  - `tabulator_table_rename` - Rename tabulator tables
  - `tabulator_open_query_status` - Check open query feature status
  - `tabulator_open_query_toggle` - Enable/disable open query feature

- **GraphQL Integration**: Enhanced search and catalog queries
  - `graphql_query` - Execute GraphQL queries against Quilt catalog
  - `graphql_bucket_search` - Search buckets using GraphQL
  - `graphql_object_search` - Search objects using GraphQL

- **Enhanced Table Formatting**: Improved display of tabular data
  - Pandas DataFrame formatting with proper column alignment
  - Graceful handling of special characters and large datasets
  - Multiple output formats (table, JSON, CSV)

### Fixed
- **Installation Instructions**: Completely revised broken README installation instructions
  - Removed non-functional `uvx quilt-mcp` and `uv run quilt-mcp` commands
  - Added proper local development setup with working `uv sync` → `make app` flow
  - Fixed MCP client configurations with correct PYTHONPATH
  - Consolidated duplicate sections and enhanced troubleshooting

- **Bucket Search Issues**: Fixed inappropriate bucket search behavior (#75)
  - Improved bucket-specific search scoping
  - Better error handling for search operations

- **Test Infrastructure**: Major improvements to test reliability (#70)
  - Converted mocked tests to use real AWS APIs
  - Enhanced test coverage and reliability
  - Added comprehensive Athena and Tabulator test suites
  - Improved CI/CD pipeline with better error reporting

### Changed
- **Tool Count**: Updated from 13 to 66+ comprehensive tools
- **Dependencies**: Added support for Athena, Tabulator, and GraphQL operations
- **Error Handling**: Enhanced error messages with actionable suggestions
- **Documentation**: Improved tool documentation and usage examples

### Technical Details
- **New AWS Services**: Athena, Glue Data Catalog integration
- **New Dependencies**: Added pandas, matplotlib, plotly for data visualization
- **Enhanced Permissions**: Better AWS IAM permission discovery and validation
- **Improved Formatting**: Advanced table and data formatting capabilities

## [0.4.1] - Previous Release

### Added
- Initial MCP server implementation
- Basic Quilt package management tools
- S3 operations and bucket management
- Authentication and permissions checking

---

For more details, see the [GitHub releases](https://github.com/quiltdata/quilt-mcp-server/releases).
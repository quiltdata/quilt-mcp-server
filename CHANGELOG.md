# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.6.3] - 2025-09-10

### Added Tool Exclusion System

- **Tool Exclusion System**: Added ability to exclude deprecated tools to reduce client confusion
  - Excluded `packages_list` (prefer `packages_search`)  
  - Excluded `bucket_objects_list` (prefer `bucket_objects_search`)
  - Clear messaging when tools are skipped during registration

### Fixed Issues

- **Test Infrastructure**: Major improvements to test stability and reliability (#131)
  - Unbroken test suite with improved reliability
  - Enhanced test coverage and validation

- **Package Management**: Enhanced metadata handling and validation (#126)
  - Fixed metadata parameter validation issue in `create_package_enhanced`
  - Improved error handling and parameter processing

- **Authentication**: Better AWS/Quilt integration (#127)
  - Improved Quilt STS authentication compatibility for bucket access
  - Enhanced credential handling and fallback mechanisms

- **Development Infrastructure**: Enhanced development workflow
  - `make kill` target to stop running MCP servers (#125)
  - Improved CI configuration with reduced duplicate runs (#123)

## [0.6.2] - 2025-01-09

### Fixed Test Infrastructure

- **Test Infrastructure**: Fixed flaky tests causing CI failures (#122)
  - Improved test reliability and reduced intermittent failures
  - Enhanced CI stability and consistency

## [0.6.1] - 2025-01-09

### Added Repository Organization

- **Repository Organization**: Comprehensive cleanup and standardization (#101, #106)
  - Complete Ruff lint configuration and code quality improvements
  - Enhanced repository structure and maintainability

### Fixed Build System v6.1

- **Build System**: Removed static manifest.json and use template-based approach (#99)
  - Dynamic manifest generation for better flexibility
  - Improved build process reliability

## [0.6.0] - 2025-01-09

### Fixed Build System v6.0

- **Build System**: Major DXT build system improvements
  - Clean up DXT build structure and resolve build issues
  - Fixed template-based manifest generation
  - Improved build dependencies and processes

## [0.5.9] - 2025-01-09

### Added Release Process

- **Release Process**: Enhanced release automation and testing (#95)

## [0.5.8] - 2025-01-09

### Added Development Infrastructure

- **Development Infrastructure**: Major CI/CD improvements
  - Auto-test README installation instructions (#88)
  - Enhanced integration workflows with forced AWS tests (#94)
  - Version synchronization templates and automation

### Fixed Repository Organization v5.8

- **Repository Organization**: Cleanup and standardization
  - Removed unused build phases (build-docker, catalog-push, deploy-aws) (#84)
  - Fixed DXT Makefile targets to use `tools/dxt` instead of `build-dxt` (#92)  
  - Updated CLAUDE.md references to use top-level location (#86)

### Changed CI/CD

- **CI/CD**: Radically simplified and optimized CI workflows
  - Reduced workflow complexity and improved reliability
  - Better test organization and execution
  - Enhanced build system automation

## [0.5.6] - 2025-01-27

### Fixed

- **DXT Release Generation**: Restored .dxt file generation for releases
  - Fixed GitHub Actions workflow paths after repository reorganization
  - Updated build-dxt/ to tools/dxt/ in all workflow steps
  - Added tag push trigger for releases (v* tags)
  - Fixed DXT artifact paths and asset copying
  - Resolves missing .dxt files in releases since v0.4.0

- **Unit Test Infrastructure**: Resolved test failures and configuration issues
  - Fixed import paths from 'app.quilt_mcp' to 'quilt_mcp' after reorganization
  - Updated test discovery paths in app.sh validation script
  - Resolved pytest fixture errors in test_athena_connection.py
  - Fixed config generation hanging during 'make app' startup
  - Optimized test subset for faster server startup validation

- **Repository Organization**: Completed comprehensive cleanup
  - Moved scattered files into organized directories (tools/, docs/, test_cases/)
  - Updated all internal documentation links and references
  - Restored CLAUDE.md and WORKFLOW.md to active locations
  - Added Cursor IDE integration with automatic rules copying

### Improved

- **CI/CD Pipeline**: Enhanced reliability and performance
  - All unit tests now passing: 378+ tests locally, 383+ on remote
  - Fixed test coverage reporting and validation
  - Improved GitHub Actions workflow triggers and conditions
  - Added comprehensive PR templates and issue forms

- **Developer Experience**: Streamlined development workflow
  - Fast server startup with optimized config generation
  - Better error messages and troubleshooting guides
  - Comprehensive documentation reorganization
  - Automated development environment setup

## [0.5.5] - 2025-08-27

### Added

- **Comprehensive Real-World Test Suite**: Complete validation of all user stories and use cases
  - SAIL Biomedicines dual MCP architecture tests (100% success rate)
  - CCLE computational biology workflow tests
  - Advanced workflow simulation with 40 realistic test cases
  - Integration tests covering all 84 MCP tools
- **Enhanced Test Coverage**: Added test runners for real data validation
  - `test_cases/sail_user_stories_real_test.py` - Tests with actual Benchling and Quilt data
  - `test_cases/ccle_computational_biology_test_runner.py` - Genomics workflow validation
  - `test_cases/mcp_comprehensive_test_simulation.py` - Advanced workflow testing
- **Unified Search Architecture**: Fully tested multi-backend search system
  - Natural language query processing (100% test success)
  - Parallel execution across GraphQL, Elasticsearch, and S3 backends
  - Intelligent fallback mechanisms and error handling
- **Real Data Integration Validation**: Proven cross-system data correlation
  - Successfully linked RNA-seq entries between Benchling and Quilt
  - Validated federated search across 112 results from both systems
  - Demonstrated TestRNA sequence integration with 4 projects and 3 packages

### Changed

- **Test Infrastructure**: Improved test reliability and coverage
  - Fixed tool interface compatibility issues in test runners
  - Enhanced error handling and validation across all test suites
  - Optimized test execution with better parallel processing
- **Documentation**: Updated with comprehensive test results and validation
  - Added real-world use case validation results
  - Documented dual MCP architecture success with actual data
  - Enhanced troubleshooting guides for common issues

### Fixed

- **CCLE Test Runner**: Fixed TypeError in `_generate_next_steps()` method
- **Tool Interface Compatibility**: Resolved parameter passing issues in test frameworks
- **Error Handling**: Improved graceful degradation in test environments
- **Integration Test Stability**: Enhanced test reliability across different environments

### Validated

- **Production Readiness**: Comprehensive validation across all major use cases
  - Bioinformatics Data Integration: 95% confidence, production ready
  - Package Management: 90% confidence, production ready  
  - Search & Discovery: 95% confidence, production ready
  - Metadata Management: 85% confidence, mostly ready
- **Real-World Performance**: Validated with actual scientific data
  - Cross-system search: 871-1769ms average query time
  - Data correlation: Sub-second response for most operations
  - Error resilience: Robust handling across all failure modes
- **Tool Coverage**: All 84 MCP tools properly registered and functional
  - Core functionality: 100% operational
  - Advanced features: 60% fully functional, 40% needs minor setup
  - Error handling: Comprehensive coverage with graceful degradation

### Internal / Maintenance

- **Test Results Archive**: Comprehensive test result files added
  - `sail_real_data_test_results_*.json` - Real data validation results
  - `test_cases/ccle_computational_biology_test_report.json` - Genomics workflow analysis
  - `mcp_test_simulation_report.json` - Advanced workflow validation
- **Version Updates**: Synchronized version across all components to 0.5.5
- **Release Preparation**: Complete validation for production deployment

## [0.4.1] - 2025-08-21


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
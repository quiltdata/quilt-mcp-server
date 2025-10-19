<!-- markdownlint-disable MD013 MD024 -->
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.8.1] - 2025-10-19

### Added

- **Tools-as-Resources Framework**: Complete implementation of MCP Tools-as-Resources (#221)
  - Tools can now be exposed as MCP resources with parameterized URIs
  - Added comprehensive integration and e2e tests for resource registration
  - Fixed AsyncMock usage and pytest-anyio configuration for async testing
  - Improved handling of parameterized resource URIs in FastMCP registration

### Changed

- **Test Configuration**: Configured pytest-anyio to use asyncio backend only for consistency

### Fixed

- **Resource Registration**: Handle parameterized resource URIs correctly in FastMCP registration
- **Testing Infrastructure**: Fix AsyncMock usage in resource tests for proper async testing

## [0.8.0] - 2025-10-18

### Added

- **JWT-Based Authentication**: Complete authentication and authorization system (#220)
  - Implements secure JWT-based authentication for MCP server
  - Role-based access control for admin operations
  - Token-based session management
  - Integration with AWS services for authentication backend

### Changed

- **Test Skip Fixtures Removed**: Tests now fail instead of skip when AWS is misconfigured (#219)
  - Removed `skip_if_no_aws_credentials` function from `tests/helpers.py`
  - Removed `skip_if_no_aws` fixture from `tests/integration/test_athena.py`
  - Removed all imports and usages of skip fixtures across 6 test files
  - Tests will now fail with clear error messages if AWS credentials are not configured
  - Improves test reliability by preventing silent test skips in CI/CD pipelines

### Documentation

- **Authentication Architecture**: Clarified AWS credential flow
  - Documented that AWS credentials are only used for AWS Bedrock integration
  - Updated workshop guides with accurate MCP/Bedrock instructions
  - Organized workshop materials and integrated with main README

## [0.7.5] - 2025-10-17

### Added

- **Data Visualization Tool**: New comprehensive data visualization capabilities
  - `create_data_visualization()` - Create visualizations from CSV/JSON data
  - Support for multiple chart types (boxplot, scatter, line, bar)
  - Automatic ECharts configuration generation
  - Integration with Quilt package metadata
  - Flexible data input (S3, CSV strings, JSON objects)

### Changed

- **Tool Documentation**: Enhanced docstrings for LLM consumption
  - Improved clarity on file structure requirements for quilt_summarize.json
  - Added detailed examples for visualization workflows
  - Better explanation of flat file structures in package creation

### Documentation

- **LLM Behavioral Guidelines**: Added comprehensive agent guidelines ([CLAUDE.md](CLAUDE.md))
  - Action-oriented data exploration patterns
  - Tool execution best practices
  - Complete visualization workflow examples
- **Workshop Materials**: Added comprehensive workshop content and customer prompts guide

## [0.7.4] - 2025-10-16

### Fixed

- **Visualization Function Signatures**: Removed `**kwargs` from `generate_package_visualizations`
  - Fixed FastMCP compatibility issues with parameter validation
  - Ensures all parameters are explicitly defined and validated

## [0.7.3] - 2025-10-16

### Added

- **Visualization Enhancements**: Enhanced visualization capabilities
  - Flexible input handling for various data formats
  - Dashboard support for multi-chart visualizations
  - Customer prompts guide for effective tool usage

## [0.7.2] - 2025-10-02

### Fixed

- **Athena Database Names**: Fixed handling of hyphenated database names
  - Removed buggy `USE` statement that didn't support hyphens
  - Use `schema_name` parameter instead for proper database context

## [0.7.1] - 2025-10-02

### Fixed

- **Athena Query Execution**: Improved database name handling
  - Enhanced support for non-standard database names
  - Better error handling for database selection

## [0.7.0] - 2025-10-01

### Added

- **MCP Resource Framework**: Complete resource system for list-type functions (#189)
  - Implemented standardized Model Context Protocol (MCP) resource system
  - Created 9 resource providers covering admin, S3, Athena, metadata, workflow, package, and tabulator domains
  - Parameterized URIs support (e.g., `tabulator://{bucket}/tables`)
  - Comprehensive backward compatibility layer via `compatibility.py`

- **QuiltService Refactoring**: Major architectural overhaul (#203)
  - Added 27 new operational methods with proper return types
  - User Management (10 methods), Role Management (4 methods), SSO Configuration (3 methods)
  - Tabulator Administration (6 methods), Config & Package (2 methods)
  - Dynamic admin credential checking with `has_admin_credentials()`
  - Proper separation of concerns - service layer owns all quilt3 interaction

### Changed

- **API Consolidation**: Streamlined tool interfaces
  - **Search Functions**: 4 → 1 (`catalog_search`) - 75% API surface reduction (#185)
    - Removed `packages_search`, `bucket_objects_search`, `bucket_objects_search_graphql`
  - **Package Operations**: 4 → 2 functions - 50% API reduction (#184, #187)
    - Standardized on `create_package` and `create_package_from_prefix`
    - Removed obsolete `package_update`, `package_update_metadata`, old `create_package`

- **Resource Migration**: Migrated list-type functions to MCP resources (#204)
  - `admin_users_list` → `admin://users`
  - `admin_roles_list` → `admin://roles`
  - `list_available_resources` → `s3://buckets`
  - `athena_databases_list` → `athena://databases`
  - `athena_workgroups_list` → `athena://workgroups`
  - `list_metadata_templates` → `metadata://templates`
  - `workflow_list` → `workflow://workflows`
  - `package_tools_list` → `package://tools`
  - `tabulator_tables_list` → `tabulator://{bucket}/tables`
  - Total: 9 list functions replaced by resources, tool count 63 → 61

### Removed

- **Obsolete Service Methods**: Deleted 5 anti-pattern methods
  - `get_users_admin()`, `get_roles_admin()`, `get_sso_config_admin()`, `get_tabulator_admin()`, `get_search_api()`
  - Replaced incorrect `is_admin_available()` with `has_admin_credentials()`
  - Deleted `AdminNotAvailableError` and module-level constants
  - Removed 625 lines of obsolete admin checking test code

### Architecture

- **Backend Swapping Enabled**: Service layer now provides operational abstractions
  - Interface is implementation-agnostic
  - All return types properly typed (`dict[str, Any]`, `list[dict[str, Any]]`, `str`, `bool`, `None`)
  - No raw quilt3 modules exposed to callers
  - Better IDE support and static analysis

### Testing

- ✅ 301 tests passing with 100% coverage maintained
- ✅ Zero breaking changes - All MCP tool interfaces unchanged
- ✅ 7 refactoring phases independently tested and committed

## [0.6.19] - 2025-10-13

### Fixed

- **Docker Container Health Checks**: Added missing `curl` command required by ECS health checks
  - Previously only `libcurl4` library was installed, causing ECS health checks to fail silently
  - Added `curl` package to Dockerfile runtime stage for proper health check execution
  - Added comprehensive integration tests to verify curl installation and health check behavior
  - Added `scripts/test-docker-health.sh` debugging tool for developers to simulate ECS health checks locally
  - Tests validate exact ECS health check command: `curl -v -f --max-time 8 http://localhost:80/health`
  - Ensures all health check routes (/health, /healthz, /) work from inside the container

## [0.6.18] - 2025-10-12

### Added

- **Multiple Health Check Routes**: Added support for standard health check endpoint variations
  - `/health` - Standard health check endpoint
  - `/healthz` - Kubernetes-style health check endpoint
  - `/` - Root path health check
  - All routes return consistent JSON response with route identification
  - Automatically registered for HTTP/SSE/streamable-http transports

### Changed

- **Health Check Response Format**: Enhanced to include route identifier
  - Added `"route"` field showing which endpoint was called
  - Helps with debugging and infrastructure monitoring
  - Maintains backward compatibility with existing health checks

### Fixed

- **FastMCP Route Conflicts**: Removed `/mcp/health` and `/mcp/healthz` routes
  - FastMCP reserves `/mcp/*` paths for protocol endpoints
  - These routes were returning 406 (Not Acceptable) errors
  - Infrastructure should use `/health`, `/healthz`, or `/` instead

## [0.6.17] - 2025-10-11

### Added

- **Git-Tag-Based Docker Validation**: Enhanced `make docker-validate` for dev releases
  - Uses `git describe --tags` to find latest tag (including dev prereleases)
  - Displays full image URI being validated for clarity
  - **Public Access Mode**: New `--skip-auth` flag enables validation without AWS credentials
  - Works with public ECR images using `docker manifest inspect`
  - Removed AWS profile requirement from `make docker-validate` target

### Fixed

- **Docker Image Validation**: Fixed size calculation and architecture verification
  - Image size now correctly calculated from layer sizes (was showing 0.0 MB)
  - Architecture verification using `docker buildx imagetools` to inspect config blob
  - Missing or non-amd64 architecture now causes hard validation failure
  - Added `--platform=linux/amd64` to all docker builds for proper metadata
  - ARM64 builds now show clear warnings about emulation and CI requirements

## [0.6.16] - 2025-10-11

### Added

- **Docker Image Validation**: New `make docker-validate` target for comprehensive image verification
  - Validates CI-pushed images in ECR with checksum and architecture details
  - Verifies `latest` tag points to expected version from pyproject.toml
  - Checks for required linux/amd64 architecture (production requirement)
  - Better size formatting (B/KB/MB) and filters attestation manifests
  - No authentication required (uses public ECR repository)

- **Public ECR Repository**: Automatic public read access configuration
  - CI automatically sets ECR repository policy to allow public reads
  - Enables unauthenticated `docker pull` and manifest inspection
  - Allows `docker-validate` to work without AWS credentials

### Changed

- **Docker Build Safety**: arm64 dry-run mode instead of failing
  - `make docker-push` runs in DRY-RUN mode on arm64 machines (M-series Macs)
  - Shows what would happen without actually pushing unusable images
  - Developers can test push workflow locally
  - Production Docker builds must happen in CI on amd64 runners

- **Dynamic AWS Account Detection**: Eliminated hardcoded account IDs
  - `scripts/docker.py` uses AWS STS to detect account and region dynamically
  - `make docker-tools` uses STS for ECR authentication
  - Logs detected AWS account and region for visibility (not redacted in CI)
  - Works correctly across different AWS accounts in CI/CD

- **Docker Image Configuration**: Standardized image naming
  - Consolidated `DOCKER_IMAGE_NAME` configuration into Makefile
  - Added `CI_ACCOUNT` and `CI_REGISTRY` constants for validation
  - Removed redundant environment variables from `env.example`
  - Made image name explicit and consistent across all operations

- **Docker URI Capture**: Release notes now include actual pushed image URI
  - CI captures Docker image URI after successful push
  - Displayed in GitHub release notes for easy reference
  - Users can see exact image location regardless of AWS account

### Fixed

- **CI Docker Builds**: Enabled and fixed Docker image publishing in CI
  - Docker builds now enabled for production releases (v* tags)
  - Docker builds now enabled for dev releases (v*-dev-* tags)
  - Fixed registry detection to work with CI AWS credentials
  - Eliminated duplicate MCPB package builds in release workflow

## [0.6.15] - 2025-10-03

### Added

- **Tabulator Query Tools**: New MCP tools for querying Tabulator tables via Athena
  - `tabulator_buckets_list()` - Discover all buckets (databases) in Tabulator catalog
  - `tabulator_bucket_query(bucket_name, query)` - Query specific bucket with auto-configuration
  - Auto-discovers `tabulator_data_catalog` from catalog configuration (works without authentication)

- **Catalog Configuration**: New `get_catalog_config()` method in QuiltService
  - Fetches catalog metadata from `<catalog>/config.json` endpoint
  - Auto-derives `tabulator_data_catalog` as `quilt-<stack-prefix>-tabulator`
  - Extended `catalog_info` tool to include `region` and `tabulator_data_catalog`

### Fixed

- **Athena Hyphenated Database Names**: Use `schema_name` parameter instead of `USE` statement to support hyphenated database names like "udp-spec"
- **Tabulator Catalog Routing**: Add `catalog_name` parameter to PyAthena connections to route queries to correct catalog
- **Database Discovery**: Refactor `discover_tables()` to use `execute_query()` for consistent catalog/database handling

## [0.6.14] - 2025-09-24

### Added

- **Health Check Endpoint**: Basic health monitoring for container orchestration (#197)
  - New `/health` endpoint returning server status, timestamp, and version info
  - Transport-aware registration (only enabled for HTTP/SSE/streamable-http transports)
  - Comprehensive test coverage for health check functionality
  - Foundation for future enhancements (component health, readiness/liveness probes)

### Changed

- **Docker Integration Tests**: Enhanced to verify health check endpoint availability
  - Tests now validate both `/mcp` and `/health` endpoints
  - Ensures health check responses include proper server metadata

## [0.6.13] - 2025-09-22

### Added

- **Docker Container Support**: Complete HTTP transport implementation for containerized deployment (#195)
  - New Docker image with FastMCP HTTP transport support (`FASTMCP_TRANSPORT=http`)
  - Automated Docker image publishing to ECR during releases
  - Developer tooling: `make docker-build`, `make docker-run`, `make docker-test`
  - Integration test suite validating container readiness and HTTP endpoints
  - Support for HTTP proxy configuration in Claude Desktop

### Changed

- **CLI Entrypoint**: Enhanced to respect pre-set `FASTMCP_TRANSPORT` environment variable
  - Enables flexible transport configuration for container deployments
  - Maintains backward compatibility with stdio transport for local usage

### Documentation

- **Docker Setup Guide**: Added comprehensive documentation for Docker deployment
  - HTTP proxy configuration instructions for Claude Desktop
  - Container usage examples and troubleshooting
  - Release notes capturing Docker implementation details

## [0.6.12] - 2025-09-22

### Fixed

- **GitHub Releases**: Include MCPB file directly in release assets (#193)
  - Users can now download the `.mcpb` file directly from GitHub releases
  - Previously only the release zip bundle was available
  - Both `*.mcpb` and `*-release.zip` files are now uploaded as release assets

## [0.6.11] - 2025-09-21

### Changed

- **MCPB Package Format Migration**: Complete transition from DXT to MCPB format (#152)
  - Replaced `.dxt` package format with `.mcpb` for Claude Desktop integration
  - Simplified build pipeline by eliminating file copying infrastructure
  - Direct UVX execution of `quilt-mcp` package from PyPI
  - Removed obsolete bootstrap scripts and build markers
  - Updated all build targets and workflows for MCPB packaging

### Added

- **MCPB Build System**: New packaging infrastructure for Claude Desktop
  - `make mcpb` - Build MCPB package with embedded manifest
  - `make mcpb-validate` - Validate MCPB package structure
  - Updated release workflow to generate MCPB artifacts
  - Comprehensive migration documentation and guides

### Documentation

- **Migration Resources**: Complete user guidance for DXT to MCPB transition
  - Comprehensive migration guide with step-by-step instructions
  - FAQ for common migration issues
  - Updated installation documentation for MCPB format
  - Release notes explaining breaking changes

## [0.6.10] - 2025-09-21

### Changed

Use `quilt-mcp` as the package name.

## [0.6.9] - 2025-09-21

### Added

- **uv-based Python Packaging Pipeline**: Complete integration for PyPI/TestPyPI publishing
  - `make python-dist` - Build wheel and sdist artifacts using uv build system
  - `make python-publish` - Publish artifacts to PyPI/TestPyPI with credential validation
  - GitHub Actions integration with Trusted Publishing support via PyPA action
  - Full compatibility with existing DXT packaging system

## [0.6.8] - 2025-09-20

### Added

- Behavior-driven unit suites covering error recovery, workflow orchestration, telemetry collectors/transports, optimization integration, tabulator administration, and metadata/naming/structure validators to expand the regression safety net.

### Changed

- Propagated fallback metadata through error recovery responses, marked health checks as degraded when fallbacks trigger, and tightened telemetry transport payloads with explicit transport identifiers.
- Normalized tabulator parser formats, surfaced validation errors, and fixed UTC timestamp generation in metadata/naming validators to prevent runtime exceptions.

### Coverage

- Increased combined test coverage from 57.9% to 61.4%, adding 12 new behavior-driven suites that chart the path toward the 85% project goal.

## [0.6.7] - 2025-09-19

### Added

- **Coverage Planning**: Captured requirements, analysis, specifications, and phased rollout for issue #166 in `spec/2025-09-19-improve-coverage/`.
- **Coverage Analysis Tooling**: Enhanced `scripts/coverage_analysis.py` to produce per-suite and combined CSV summaries without double-counting covered lines.

### Changed

- **Make Targets**: Reworked `make.dev` coverage targets to emit suite-specific XML reports (unit, integration, e2e) and drive aggregation through the coverage analysis script.
- **CI Workflows**: Updated `.github/workflows/push.yml` to execute on merge events so fast PR workflows stay lean while `main` still runs comprehensive coverage.
- **Integration Tests**: Cached `AthenaQueryService` creation, marked the slowest paths with `pytest.mark.slow`, and reused the fixture across test modules to keep coverage runs responsive.
- **Contributor Guidance**: Documented the shared Athena service fixture expectations in `AGENTS.md` for future test additions.

## [0.6.6] - 2025-09-18

### Added

- **Architecture**: Abstract quilt3 dependency (#158, #155)
  - Created centralized QuiltService abstraction layer to isolate all quilt3 API usage
  - Migrated all MCP tools to use QuiltService instead of direct quilt3 imports

### Changed

- **Build System**: Updated .gitignore for better artifact management
- **Code Quality**: Enhanced lint checks and code formatting

## [0.6.5] - 2025-09-11

- Bumped version due to CI failure

## [0.6.4] - 2025-09-11

### Added

- **Claude CLI Integration**: Added `make config-claude` target for Claude CLI integration (#128)
  - Streamlined setup for Claude Code development environment
  - Automated configuration for optimal Claude CLI workflow

### Enhanced

- **Version Support for S3 Objects**: Added versionId support for `bucket_object_text` tool (#137, #142)
  - Support for versioned S3 object retrieval with `?versionId=xyz` syntax
  - Enhanced error handling for version-specific operations (InvalidVersionId, NoSuchVersion, AccessDenied)
  - Complete implementation with comprehensive error messaging

### Tool Management

- **Tool Re-enablement**: Re-enabled `bucket_objects_list` tool
  - Still useful as a complement to bucket search

- **Tool Consolidation**: Disabled `athena_tables_list` tool
  - Does not seem to work
  - Prefer using `athena_query_execute` for table listing operations

### Enhanced Athena Workgroups Management

- **Enhanced Athena Workgroups Listing**: Complete redesign of `athena_workgroups_list` functionality (#133)
  - **ENABLED-only filtering**: Only shows workgroups in ENABLED state for cleaner results
  - **Clean AWS data presentation**: Removed synthetic fields (`accessible`, `state`) that polluted AWS API data
  - **Layered API access patterns**: Graceful degradation when users have varying permission levels
  - **Error-free descriptions**: AWS descriptions no longer contaminated with error messages
  - **Consolidated authentication**: Eliminated code duplication between workgroup discovery methods
  - **Enhanced table formatting**: Better CLI presentation with automatic table detection
  - **Comprehensive test coverage**: 11 BDD tests covering all enhancement scenarios

### Code Quality Improvements

- **Authentication consolidation**: Refactored `_discover_workgroup` to use `list_workgroups` method internally
  - Eliminated 40+ lines of duplicate authentication and workgroup discovery logic
  - Single source of truth for workgroup access patterns
  - Improved maintainability and reduced complexity
- **Test infrastructure**: Fixed CI test failures related to deprecated field references
- **Enhanced error handling**: Clean separation of data presentation and error reporting

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

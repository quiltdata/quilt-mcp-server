<!-- markdownlint-disable MD013 MD024 -->
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.7.0] **Unreleased**

### QuiltService Refactoring - Major Architectural Overhaul (Issue #155)

This release completes a comprehensive refactoring of the `QuiltService` layer to align with the original architectural specification. The service now provides operational abstractions instead of exposing raw quilt3 modules, enabling backend swapping and proper separation of concerns.

**Specification Reference**: See [spec/Archive/155-isolate-quilt3/a1-requirements.md](./spec/Archive/155-isolate-quilt3/a1-requirements.md) for complete details.

### Added

- **27 New Operational Methods in QuiltService**: Replaced module getter methods with typed operational abstractions
  - **User Management** (10 methods): `list_users()`, `get_user()`, `create_user()`, `delete_user()`, `set_user_email()`, `set_user_role()`, `set_user_active()`, `set_user_admin()`, `add_user_roles()`, `remove_user_roles()`, `reset_user_password()`
  - **Role Management** (4 methods): `list_roles()`, `get_role()`, `create_role()`, `delete_role()`
  - **SSO Configuration** (3 methods): `get_sso_config()`, `set_sso_config()`, `remove_sso_config()`
  - **Tabulator Administration** (6 methods): `get_tabulator_access()`, `set_tabulator_access()`, `list_tabulator_tables()`, `create_tabulator_table()`, `delete_tabulator_table()`, `rename_tabulator_table()`
  - **Config & Package** (2 methods): `get_navigator_url()`, `delete_package()`
  - All methods return proper types (`dict[str, Any]`, `list[dict[str, Any]]`, etc.) instead of raw modules or `Any`

- **Dynamic Admin Credential Checking**: Implemented `has_admin_credentials()` method that tests actual admin permissions
  - Replaces incorrect module availability checking with real credential verification via `quilt3.admin.roles.list()`
  - Admin tools and resources now filtered at registration time based on user permissions
  - Non-admin users see clean interface without admin clutter

- **MCP Resource Framework**: Implemented standardized Model Context Protocol (MCP) resource system
  - Created `quilt_mcp.resources` package with base framework (`MCPResource`, `ResourceResponse`, `ResourceRegistry`)
  - Implemented 9 resource providers covering admin, S3, Athena, metadata, workflow, package, and tabulator domains
  - Added parameterized URIs support (e.g., `tabulator://{bucket}/tables`)

### Changed

- **QuiltService API**: Complete refactoring from module getters to operational abstractions (35+ call sites updated)
  - **Tools Updated**: `governance.py` (~25 functions), `tabulator.py` (~8 functions), `catalog.py`, `package_creation.py`
  - **Resources Updated**: `admin.py` (2 resources)
  - All callers now use typed operational methods instead of raw quilt3 module access
  - Backend-agnostic interface enables future backend swapping

- **Tool Consolidation**: Migrated list-type functions to use MCP resources internally
  - `admin_users_list` → `AdminUsersResource` (URI: `admin://users`)
  - `admin_roles_list` → `AdminRolesResource` (URI: `admin://roles`)
  - `list_available_resources` → `S3BucketsResource` (URI: `s3://buckets`)
  - `athena_databases_list` → `AthenaDatabasesResource` (URI: `athena://databases`)
  - `athena_workgroups_list` → `AthenaWorkgroupsResource` (URI: `athena://workgroups`)
  - `list_metadata_templates` → `MetadataTemplatesResource` (URI: `metadata://templates`)
  - `workflow_list` → `WorkflowResource` (URI: `workflow://workflows`)
  - `package_tools_list` → `PackageToolsResource` (URI: `package://tools`)
  - `tabulator_tables_list` → `TabulatorTablesResource` (URI: `tabulator://{bucket}/tables`)

### Removed

- **Module Getter Anti-Patterns**: Deleted 5 methods that exposed raw quilt3 modules
  - `get_users_admin()`, `get_roles_admin()`, `get_sso_config_admin()`, `get_tabulator_admin()`, `get_search_api()`
  - These violated the service layer's purpose by leaking implementation details

- **Obsolete Admin Checking**: Removed incorrect module availability checking system
  - Deleted `is_admin_available()` (checked module existence instead of permissions)
  - Deleted `_require_admin()` (blocked operations unnecessarily)
  - Deleted `AdminNotAvailableError` (operations now fail naturally via quilt3)
  - Removed module-level `ADMIN_AVAILABLE` constants
  - Deleted 625 lines of obsolete test code

- **Legacy List Functions**: Removed and replaced by MCP resources
  - `admin_users_list()`, `admin_roles_list()`, `list_available_resources()`
  - `athena_databases_list()`, `athena_workgroups_list()`
  - `list_metadata_templates()`, `workflow_list()`, `package_tools_list()`, `tabulator_tables_list()`

### Technical Details

- **Resource Benefits**:
  - Standardized resource discovery and introspection via MCP protocol
  - Unified error handling and response format across all list operations
  - Automatic metadata enrichment with resource descriptions and capabilities
  - Support for resource templating and parameterized URIs
  - Future-proof architecture for adding new resource types

- **Breaking Changes**:
  - This is a clean break - no backward compatibility layer
  - All list-type functions have been removed
  - Code using removed functions must migrate to MCP resources
  - See migration guide for details on updating existing code

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

- **Test Coverage System**: Comprehensive test coverage infrastructure
  - Individual test suites (unit: 45%, integration: 49%, e2e: 27%)
  - Combined coverage target of 57.9% with no double-counting
  - Full 14-step GitHub workflow including specification and implementation phases
  - Makefile integration with granular test execution commands

### Changed

- **Build System**: Reorganized test infrastructure
  - Separated test commands by suite type for better control
  - Added XML coverage report generation for aggregation
  - Implemented GitHub issue to PR workflow with spec-driven development

### Fixed

- Test fixture compatibility across Python versions
- Coverage measurement accuracy with proper source path configuration

## [0.6.5] - 2025-09-17

### Added

- **Catalog Search Consolidation**: Unified 4 legacy search functions into single `catalog_search` interface
  - Removed `packages_search`, `bucket_objects_search`, `bucket_objects_search_graphql`
  - All functionality preserved in enhanced `catalog_search` with scope/backend parameters
  - 75% reduction in search API surface area

### Changed

- **Internal Architecture**: Simplified search backend organization
  - Consolidated GraphQL and Elasticsearch implementations
  - Improved error handling and query parsing
  - Enhanced search result ranking and relevance

## [0.6.4] - 2025-09-16

### Added

- **Package Management**: Enhanced package creation and validation
  - Smart file organization with automatic categorization
  - Metadata template system for standardized package descriptions
  - Package integrity validation and accessibility checking

### Fixed

- S3 bucket permission detection for cross-account scenarios
- Package browse functionality for large datasets
- Metadata validation edge cases

## [0.6.3] - 2025-09-15

### Added

- **Workflow Orchestration**: Multi-step operation tracking
  - Workflow creation, step management, and status tracking
  - Template system for common workflows
  - Dependency resolution between workflow steps

### Changed

- **Error Recovery**: Enhanced fallback mechanisms
  - Automatic retry logic for transient failures
  - Graceful degradation for service unavailability
  - Improved error context and recovery suggestions

## [0.6.2] - 2025-09-14

### Added

- **Athena Integration**: SQL query capabilities via AWS Athena
  - Database and table discovery
  - Query execution with result formatting
  - Workgroup management and configuration

### Fixed

- Authentication flow for SSO-enabled catalogs
- Query result pagination for large datasets

## [0.6.1] - 2025-09-13

### Added

- **Admin Tools**: Registry user and role management
  - User creation, modification, and deletion
  - Role assignment and permission management
  - SSO configuration management

### Changed

- **Performance**: Query optimization for large catalogs
  - Caching layer for frequently accessed resources
  - Batch operations for bulk updates

## [0.6.0] - 2025-09-12

### Added

- Initial release of Quilt MCP Server
- Core MCP protocol implementation
- Basic package operations (list, browse, create)
- S3 bucket integration
- Authentication framework

[0.6.9]: https://github.com/quilt/quilt-mcp-server/compare/v0.6.8...v0.6.9
[0.6.8]: https://github.com/quilt/quilt-mcp-server/compare/v0.6.7...v0.6.8
[0.6.7]: https://github.com/quilt/quilt-mcp-server/compare/v0.6.6...v0.6.7
[0.6.6]: https://github.com/quilt/quilt-mcp-server/compare/v0.6.5...v0.6.6
[0.6.5]: https://github.com/quilt/quilt-mcp-server/compare/v0.6.4...v0.6.5
[0.6.4]: https://github.com/quilt/quilt-mcp-server/compare/v0.6.3...v0.6.4
[0.6.3]: https://github.com/quilt/quilt-mcp-server/compare/v0.6.2...v0.6.3
[0.6.2]: https://github.com/quilt/quilt-mcp-server/compare/v0.6.1...v0.6.2
[0.6.1]: https://github.com/quilt/quilt-mcp-server/compare/v0.6.0...v0.6.1
[0.6.0]: https://github.com/quilt/quilt-mcp-server/releases/tag/v0.6.0

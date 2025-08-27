# Repository Structure and Organization

This document provides a comprehensive overview of the Quilt MCP Server repository structure, explaining the purpose and contents of each directory and key file.

## 📁 Repository Overview

```
quilt-mcp-server/
├── 📁 app/                    # Core MCP server implementation
├── 📁 docs/                  # Comprehensive documentation  
├── 📁 tests/                 # Test suite (85%+ coverage)
├── 📁 test_cases/            # Real-world test scenarios
├── 📁 test_results/          # Test execution results
├── 📁 user_stories/          # User story documentation
├── 📁 analysis/              # Performance and analysis reports
├── 📁 scripts/               # Utility scripts and tools
├── 📁 configs/               # Configuration files
├── 📁 documentation/         # Project documentation artifacts
├── 📁 shared/                # Shared utilities and scripts
├── 📁 spec/                  # Technical specifications
├── 📁 build-dxt/             # Claude Desktop extension build
├── 📁 weather/               # Example/demo data
├── 📄 README.md              # Main project documentation
├── 📄 CHANGELOG.md           # Version history and changes
├── 📄 LICENSE.txt            # Apache 2.0 license
├── 📄 pyproject.toml         # Python project configuration
├── 📄 uv.lock                # Dependency lock file
├── 📄 Makefile               # Build and development commands
└── 📄 env.example            # Environment configuration template
```

## 🏗️ Core Application Structure

### `app/` - MCP Server Implementation

The heart of the project containing the MCP server implementation:

```
app/
├── 📄 main.py                # Server entry point and MCP protocol handler
├── 📄 Makefile               # App-specific build commands
├── 📁 quilt_mcp/            # Main server package
│   ├── 📄 __init__.py       # Package initialization (version: 0.5.5)
│   ├── 📄 constants.py      # Global constants and configuration
│   ├── 📄 formatting.py     # Response formatting utilities
│   ├── 📄 utils.py          # Core utilities and server creation
│   ├── 📁 tools/            # 84+ MCP tools implementation
│   │   ├── 📄 __init__.py   # Tool registration and exports
│   │   ├── 📄 auth.py       # Authentication and authorization tools
│   │   ├── 📄 bucket.py     # S3 bucket operations
│   │   ├── 📄 package.py    # Quilt package management
│   │   ├── 📄 search.py     # Search and discovery tools
│   │   ├── 📄 athena.py     # AWS Athena SQL operations
│   │   ├── 📄 tabulator.py  # Quilt Tabulator operations
│   │   ├── 📄 workflow.py   # Workflow management
│   │   ├── 📄 admin.py      # Administrative operations
│   │   └── ... (20 total tool modules)
│   ├── 📁 search/           # Multi-backend search system
│   │   ├── 📄 __init__.py   # Search system initialization
│   │   ├── 📄 unified.py    # Unified search orchestration
│   │   ├── 📄 graphql.py    # GraphQL backend implementation
│   │   ├── 📄 elasticsearch.py # Elasticsearch backend
│   │   ├── 📄 s3_backend.py # S3 direct search backend
│   │   ├── 📄 query_parser.py # Natural language query parsing
│   │   └── ... (13 total search modules)
│   ├── 📁 aws/              # AWS service integrations
│   │   ├── 📄 athena_service.py # Athena service wrapper
│   │   ├── 📄 permission_discovery.py # AWS permission discovery
│   │   └── 📄 __init__.py   # AWS module initialization
│   ├── 📁 validators/       # Input validation
│   │   ├── 📄 __init__.py   # Validation utilities
│   │   ├── 📄 package_validators.py # Package-specific validation
│   │   ├── 📄 s3_validators.py # S3 parameter validation
│   │   └── 📄 search_validators.py # Search query validation
│   ├── 📁 optimization/     # Performance optimization
│   │   ├── 📄 caching.py    # Response caching
│   │   ├── 📄 parallel.py   # Parallel execution utilities
│   │   ├── 📄 rate_limiting.py # Rate limiting implementation
│   │   └── ... (6 total optimization modules)
│   ├── 📁 telemetry/        # Monitoring and observability
│   │   ├── 📄 metrics.py    # Performance metrics collection
│   │   ├── 📄 logging.py    # Structured logging
│   │   ├── 📄 tracing.py    # Distributed tracing
│   │   └── ... (5 total telemetry modules)
│   └── 📁 visualization/    # Data visualization tools
│       ├── 📄 package_viz.py # Package visualization
│       ├── 📄 charts.py     # Chart generation
│       ├── 📄 dashboards.py # Dashboard creation
│       └── ... (18 total visualization modules)
└── 📁 tests/                # App-specific unit tests
    └── 📄 __init__.py       # Test package initialization
```

**Key Files:**
- **`main.py`**: MCP protocol implementation and server startup
- **`quilt_mcp/utils.py`**: Server creation and tool registration
- **`quilt_mcp/tools/`**: Individual MCP tool implementations
- **`quilt_mcp/search/unified.py`**: Multi-backend search orchestration

## 📚 Documentation Structure

### `docs/` - Comprehensive Documentation

```
docs/
├── 📄 CONTRIBUTING.md        # Contributor guidelines and processes
├── 📄 REPOSITORY.md         # This file - repository structure
├── 📄 TESTING.md            # Testing philosophy and practices
├── 📄 TOOLS.md              # Complete tool reference
├── 📄 INSTALLATION.md       # Detailed installation guide
├── 📄 API.md                # MCP protocol and API reference
├── 📄 ARCHITECTURE.md       # System architecture overview
├── 📄 DEPLOYMENT.md         # Deployment guides and options
├── 📄 TROUBLESHOOTING.md    # Common issues and solutions
├── 📄 EXAMPLES.md           # Usage examples and tutorials
├── 📁 images/               # Documentation images and diagrams
└── 📄 quilt-enterprise-schema.graphql # GraphQL schema reference
```

### `documentation/` - Project Artifacts

Historical project documentation and artifacts:

```
documentation/
├── 📄 CLAUDE.md             # Claude Desktop integration guide
├── 📄 PR_DESCRIPTION.md     # PR template and examples
├── 📄 PR_OPTIMIZATION.md    # Performance optimization notes
├── 📄 WORKFLOW.md           # Development workflow documentation
└── 📄 pr_body.md            # PR body template
```

## 🧪 Testing Infrastructure

### `tests/` - Main Test Suite

Comprehensive test suite with 85%+ coverage:

```
tests/
├── 📄 __init__.py           # Test package initialization
├── 📄 conftest.py           # Pytest configuration and fixtures
├── 📄 test_integration.py   # Integration tests
├── 📄 test_unified_search.py # Search system tests
├── 📄 test_athena_smoke.py  # Athena connectivity tests
├── 📄 test_package_operations.py # Package management tests
├── 📄 test_s3_operations.py # S3 operation tests
├── 📄 test_auth_flow.py     # Authentication flow tests
├── 📄 test_error_handling.py # Error handling validation
├── 📄 test_performance.py   # Performance benchmarks
└── ... (31 total test files)
```

### `test_cases/` - Real-World Scenarios

Real-world test scenarios and validation:

```
test_cases/
├── 📄 realistic_quilt_test_cases.json # Comprehensive test scenarios
├── 📄 advanced_workflow_test_cases.json # Advanced workflow tests
├── 📄 sail_biomedicines_test_cases.json # SAIL user story tests
├── 📄 ccle_computational_biology_test_cases.json # Genomics workflows
├── 📄 sail_user_stories_real_test.py # Real data validation
├── 📄 ccle_computational_biology_test_runner.py # Genomics test runner
├── 📄 mcp_comprehensive_test_simulation.py # Comprehensive simulation
├── 📄 direct_mcp_test.py    # Direct MCP protocol tests
├── 📄 interactive_mcp_test.py # Interactive testing tools
└── ... (23 total test files and data)
```

### `test_results/` - Test Execution Results

```
test_results/
├── 📄 mock_llm_mcp_test_results.json # Mock test results
└── ... (additional result files generated during test runs)
```

## 🔧 Development and Build Tools

### `scripts/` - Utility Scripts

Development and operational scripts:

```
scripts/
├── 📄 check_all_readme.py   # Documentation validation
├── 📄 demo_unified_search.py # Search system demo
├── 📄 optimize_mcp.py       # Performance optimization tools
├── 📄 real_mcp_validation.py # Real-world validation
├── 📄 cellxgene-mcp-wrapper.sh # CellxGene integration
├── 📄 start-quilt-mcp.sh    # Server startup script
└── 📄 start_mcp_optimized.sh # Optimized server startup
```

### `shared/` - Shared Utilities

Common utilities used across the project:

```
shared/
├── 📄 check-env.sh          # Environment validation
├── 📄 common.sh             # Common shell functions
├── 📄 test-endpoint.sh      # Endpoint testing
├── 📄 test-tools.json       # Tool testing configuration
├── 📄 tunnel-endpoint.sh    # ngrok tunneling
└── 📄 version.sh            # Version management
```

### `configs/` - Configuration Files

Project configuration and policy files:

```
configs/
├── 📄 athena-glue-partitions-policy.json # AWS Glue partitions policy
├── 📄 athena-glue-policy.json # AWS Glue access policy
├── 📄 cdk.json              # AWS CDK configuration
└── 📄 real_mcp_validation_report.json # Validation report
```

## 🚀 Deployment and Build


### `build-dxt/` - Claude Desktop Extension

```
build-dxt/
├── 📁 assets/              # Extension assets
│   ├── 📄 manifest.json    # Extension manifest
│   ├── 📄 dxt_main.py      # Extension entry point
│   ├── 📄 bootstrap.py     # Bootstrap script
│   ├── 📄 requirements.txt # Python dependencies
│   ├── 📄 README.md        # Extension documentation
│   ├── 📄 LICENSE.txt      # License file
│   └── 📄 icon.png         # Extension icon
└── 📄 Makefile             # DXT build commands
```


## 📊 Analysis and Reporting

### `analysis/` - Performance and Analysis

Performance analysis and project reports:

```
analysis/
├── 📄 ADVANCED_WORKFLOW_ANALYSIS.md # Workflow performance analysis
├── 📄 ATHENA_FIXES_SUMMARY.md # Athena integration fixes
├── 📄 COMPREHENSIVE_GAP_ANALYSIS.md # Feature gap analysis
├── 📄 MCP_COMPREHENSIVE_ANALYSIS.md # MCP implementation analysis
├── 📄 UNIFIED_SEARCH_SUMMARY.md # Search system performance
├── 📄 WORKFLOW_IMPROVEMENTS_ANALYSIS.md # Workflow optimization
└── ... (15 total analysis documents)
```

### `user_stories/` - User Story Documentation

```
user_stories/
├── 📄 SAIL_USER_STORIES_FINAL_RESULTS.md # SAIL Biomedicines results
└── 📄 test_improvements.md # Test improvement documentation
```

## 📋 Specifications and Standards

### `spec/` - Technical Specifications

Detailed technical specifications for each component:

```
spec/
├── 📄 1-app-spec.md        # MCP server specification
├── 📄 5-dxt-spec.md        # DXT build specification
├── 📄 shared.md           # Shared utilities specification
└── ... (18 total specification files)
```

## 🔧 Configuration Files

### Root Configuration Files

- **`pyproject.toml`**: Python project configuration, dependencies, and build settings
- **`uv.lock`**: Locked dependency versions for reproducible builds
- **`Makefile`**: Top-level build commands and development workflows
- **`env.example`**: Environment variable template
- **`.gitignore`**: Git ignore patterns
- **`.dockerignore`**: Docker ignore patterns

### Development Configuration

- **`.github/`**: GitHub Actions workflows and issue templates
- **`.pytest_cache/`**: Pytest cache directory
- **`.venv/`**: Python virtual environment (local development)

## 🎯 Navigation Guide

### For New Contributors

1. **Start Here**: [`README.md`](../README.md) - Project overview and quick start
2. **Contributing**: [`docs/CONTRIBUTING.md`](CONTRIBUTING.md) - How to contribute
3. **Setup**: [`docs/INSTALLATION.md`](INSTALLATION.md) - Detailed setup guide
4. **Architecture**: [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) - System design

### For Users

1. **Installation**: [`README.md#quick-start`](../README.md#-quick-start)
2. **Tool Reference**: [`docs/TOOLS.md`](TOOLS.md) - Complete tool documentation
3. **Examples**: [`docs/EXAMPLES.md`](EXAMPLES.md) - Usage examples
4. **Troubleshooting**: [`docs/TROUBLESHOOTING.md`](TROUBLESHOOTING.md)

### For Developers

1. **Code Structure**: [`app/quilt_mcp/`](../app/quilt_mcp/) - Core implementation
2. **Testing**: [`tests/`](../tests/) and [`test_cases/`](../test_cases/)
3. **Build Tools**: [`Makefile`](../Makefile) and phase-specific Makefiles
4. **Build System**: [`build-dxt/`](../build-dxt/) for Claude Desktop Extension packaging

## 🔄 File Organization Principles

### Naming Conventions

- **Directories**: `lowercase-with-hyphens/` or `snake_case/`
- **Python Files**: `snake_case.py`
- **Documentation**: `UPPERCASE.md` for major docs, `lowercase.md` for specific guides
- **Configuration**: `kebab-case.json` or `snake_case.toml`
- **Scripts**: `kebab-case.sh` or `snake_case.py`

### Organization Principles

1. **Separation of Concerns**: Each directory has a specific purpose
2. **Logical Grouping**: Related files are grouped together
3. **Clear Hierarchy**: Nested structure reflects dependencies
4. **Discoverability**: Important files are easy to find
5. **Maintainability**: Structure supports long-term maintenance

### File Lifecycle

1. **Development**: Files created in appropriate directories
2. **Testing**: Comprehensive tests in `tests/` and `test_cases/`
3. **Documentation**: Updated in `docs/` as features are added
4. **Analysis**: Performance analysis stored in `analysis/`
5. **Deployment**: Build artifacts managed in `build-*/` directories

This structure supports the project's evolution from a simple MCP server to a comprehensive data management platform while maintaining clarity and organization.

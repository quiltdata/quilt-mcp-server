# Quilt MCP Server Brownfield Architecture Document

## Introduction

This document captures the CURRENT STATE of the Quilt MCP Server codebase, including technical debt, workarounds, and real-world patterns. It serves as a reference for AI agents and highly technical managers working on building a reliable DXT (Desktop Extension) for Quilt customers accessing their private AWS cloud stacks.

### Document Scope

Comprehensive documentation focused on DXT reliability, authentication challenges, and testing complexity in a "vibe-coded" codebase.

### Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2025-01-02 | 1.0 | Initial brownfield analysis | Winston (Architect Agent) |

## Quick Reference - Key Files and Entry Points

### Critical Files for Understanding the System

- **Main Entry**: `app/main.py` → `app/quilt_mcp/utils.py:run_server()`
- **DXT Entry**: `tools/dxt/assets/dxt_main.py` → `bootstrap.py` (self-contained)
- **Core Server Logic**: `app/quilt_mcp/utils.py:create_configured_server()`
- **Authentication Module**: `app/quilt_mcp/tools/auth.py` (678 lines, complex)
- **Tool Registration**: `app/quilt_mcp/utils.py:register_tools()` (lines 60-97)
- **84+ Tools**: `app/quilt_mcp/tools/*.py` (19 modules auto-registered)

### DXT Reliability Focus Areas

**Critical for DXT Success:**
- `tools/dxt/assets/bootstrap.py` - Handles venv creation, permissions, dependency installation
- `tools/dxt/assets/dxt_main.py` - Forces stdio transport, environment setup
- `tools/dxt/Makefile` - Build system with incremental builds and validation
- `tools/dxt/assets/check-prereqs.sh` - Environment validation

## High Level Architecture

### Technical Summary

**Purpose**: Standalone MCP Server for Quilt customers to access their custom Quilt stacks in AWS Private Cloud through Claude Desktop.

**Core Challenge**: Bridge between Claude Desktop (MCP client) and private Quilt catalogs with complex authentication flows.

### Actual Tech Stack

| Category | Technology | Version | Notes |
|----------|------------|---------|-------|
| Runtime | Python | 3.11+ | **CRITICAL**: Must be accessible in login shell for DXT |
| MCP Framework | FastMCP | 0.1.0+ | Auto-registers 84+ tools from function introspection |
| MCP Protocol | mcp | 1.12.0+ | Latest protocol version |
| Quilt Integration | quilt3 | 5.6.0+ | **AUTHENTICATION COMPLEXITY**: Custom catalog URLs, JWT flows |
| AWS Integration | boto3 | 1.34.0+ | S3, Athena, permissions discovery |
| HTTP Client | httpx | 0.27.0+ | Async-capable, used for GraphQL queries |
| Visualization | matplotlib, plotly, altair | Various | **TESTING ISSUE**: Import conflicts in mixed environments |
| Bioinformatics | pysam, biopython, pybedtools | Various | **DOMAIN-SPECIFIC**: Genomics workflow support |

### Repository Structure Reality Check

- **Type**: Monorepo with clear separation (app/, tools/, tests/, docs/)
- **Package Manager**: uv (modern Python packaging)
- **Build System**: Makefile-driven with proper dependencies
- **Notable**: Originally "vibe-coded" but now has structure

## Source Tree and Module Organization

### Project Structure (Actual)

```text
quilt-mcp-server/
├── app/                     # Core MCP server code
│   ├── main.py             # Entry point (9 lines, just imports utils.run_server)
│   └── quilt_mcp/
│       ├── tools/          # 84+ MCP tools (19 modules, auto-registered)
│       │   ├── auth.py     # 678 lines - COMPLEX authentication logic
│       │   ├── packages.py # Package management operations
│       │   ├── buckets.py  # S3 bucket operations
│       │   ├── search.py   # Multi-backend search (ES, GraphQL, S3)
│       │   └── [15 more]   # Specialized tools (athena, workflow, etc.)
│       ├── utils.py        # 190 lines - Server creation, tool registration
│       └── visualization/  # Data analysis and genomics visualization
├── tools/dxt/              # **DXT BUILD SYSTEM** - Critical for reliability
│   ├── Makefile           # Sophisticated build with incremental compilation
│   └── assets/
│       ├── bootstrap.py   # **CRITICAL**: Self-contained environment setup
│       ├── dxt_main.py    # DXT entry point with stdio transport
│       ├── check-prereqs.sh # Environment validation (4474 bytes)
│       └── manifest.json  # Claude Desktop extension metadata
├── tests/                  # **TESTING COMPLEXITY** - Multiple paradigms
│   ├── test_*.py          # Unit tests (pytest)
│   ├── fixtures/          # Integration test scenarios
│   └── results/           # Captured test outputs
├── docs/                   # Well-structured documentation
└── pyproject.toml         # Modern Python packaging with dependency groups
```

### Key Modules and Their Purpose

- **Authentication Layer**: `app/quilt_mcp/tools/auth.py:auth_status()` - Complex catalog detection logic
- **Tool Auto-Registration**: `app/quilt_mcp/utils.py:register_tools()` - Introspection-based registration
- **Transport Abstraction**: `app/quilt_mcp/utils.py:run_server()` - Supports stdio, http, sse
- **DXT Bootstrap**: `tools/dxt/assets/bootstrap.py` - **CRITICAL**: Self-contained setup
- **Error Handling**: `app/quilt_mcp/utils.py:format_error_response()` - Standardized error format

## Technical Debt and Known Issues

### Critical Technical Debt

1. **"Vibe-Coded" Origins**: 
   - Original codebase built iteratively without formal architecture
   - Tool registration uses runtime introspection (`inspect.getmembers()`)
   - Some error handling still inconsistent across 84+ tools

2. **Authentication Complexity**: 
   - `auth.py:_get_catalog_info()` has multiple fallback strategies
   - Catalog URL detection tries: `quilt3.logged_in()` → `navigator_url` → `registryUrl`
   - JWT token handling not fully transparent to developers

3. **Testing Architecture Inconsistency**:
   - Mix of unit tests (`test_mcp_server.py`), integration tests (`fixtures/`), and prompt-based tests
   - Test data in JSON fixtures vs. real API calls
   - **Import conflicts**: matplotlib + pytest in some environments

4. **DXT Environment Assumptions**:
   - Assumes Python 3.11+ accessible via `python3` in login shell (not venv)
   - Bootstrap script handles venv creation but permission edge cases exist
   - PATH and environment variable propagation varies by OS

### Workarounds and Gotchas

- **Stdout Suppression**: `utils.py:suppress_stdout()` - Critical for MCP protocol (stdio transport)
- **Tool Registration**: All public functions auto-registered as MCP tools (no explicit decoration)
- **Error Recovery**: `tools/error_recovery.py` temporarily disabled due to "Callable parameter issues"
- **Transport Detection**: Defaults to stdio but can be overridden via `FASTMCP_TRANSPORT` env var
- **AWS Region**: DXT sets `AWS_DEFAULT_REGION=us-east-1` if not specified

## Integration Points and External Dependencies

### External Services Integration

| Service | Purpose | Integration Type | Key Files | Notes |
|---------|---------|------------------|-----------|-------|
| Quilt Catalog | Package management | REST + GraphQL | `auth.py`, `packages.py` | **Complex auth flows** |
| AWS S3 | Object storage | boto3 | `buckets.py`, `s3_package.py` | IAM permission discovery |
| AWS Athena | SQL queries | boto3 | `athena_glue.py` | Query execution and results |
| Elasticsearch | Search | httpx | `search.py` | Fallback search backend |
| GraphQL API | Advanced queries | httpx | `graphql.py` | Schema introspection |

### Internal Integration Points

- **MCP Protocol**: JSON-RPC over stdio (default) or HTTP
- **Tool Auto-Discovery**: Runtime introspection of `tools/*.py` modules
- **Error Propagation**: Standardized via `format_error_response()`
- **Visualization Pipeline**: `visualization/` module with multiple output formats

## Development and Deployment

### Local Development Setup

**Current Working Process** (not ideal, but functional):

1. **Environment Setup**:
   ```bash
   uv sync --group test  # Install all dependencies including test group
   cp env.example .env   # Configure AWS credentials and Quilt settings
   ```

2. **Run Server**:
   ```bash
   make app              # Starts server on localhost:8000
   # OR
   FASTMCP_TRANSPORT=stdio python app/main.py  # For direct MCP testing
   ```

3. **Known Setup Issues**:
   - matplotlib import conflicts in mixed environments
   - AWS credentials must be configured before Quilt authentication
   - Some tools require specific IAM permissions for full functionality

### Build and Deployment Process

**DXT Build Process** (tools/dxt/Makefile):

```bash
make check-tools      # Verify npx, uv availability
make contents         # Copy assets and app code  
make test            # Test bootstrap import structure
make build           # Create .dxt package with official CLI
make validate        # Validate with @anthropic-ai/dxt
make release         # Create distribution zip
```

**Critical Build Dependencies**:
- Node.js (for `npx @anthropic-ai/dxt pack`)
- uv package manager
- Python 3.11+ in PATH

## Testing Reality

### Current Test Coverage

- **Unit Tests**: 85%+ coverage (pytest) - `make coverage`
- **Integration Tests**: Real-world scenarios in `tests/fixtures/`
- **DXT Tests**: Bootstrap validation and import testing
- **Manual Testing**: Tool explorer at `make run-inspector`

### Testing Paradigm Challenges

**Three Testing Approaches**:

1. **Unit Tests** (`test_mcp_server.py`):
   - Mock external dependencies
   - Fast execution, reliable
   - Limited real-world validation

2. **Integration Tests** (`fixtures/*.py`):
   - Real API calls to Quilt/AWS
   - Comprehensive scenarios
   - Require valid credentials

3. **Prompt-Based Tests** (`fixtures/interactive_mcp_test.py`):
   - Simulate actual Claude interactions
   - Test user experience flows
   - Hard to automate reliably

### Running Tests

```bash
# Unit tests (recommended for development)
make coverage                    # Full test suite with coverage

# Isolated module testing (avoid import conflicts)
PYTHONPATH=app uv run pytest tests/test_mcp_server.py -v

# Integration tests (require AWS credentials)
make test-app

# DXT testing
cd tools/dxt && make test       # Bootstrap import validation
```

## DXT Reliability - Key Success Factors

### Files Critical for DXT Success

1. **`tools/dxt/assets/bootstrap.py`** - Self-contained environment setup
   - Creates virtual environment if missing
   - Handles Python executable permissions across platforms
   - Installs dependencies with proper error handling
   - **Reliability Risk**: OS-specific path handling, permission edge cases

2. **`tools/dxt/assets/dxt_main.py`** - DXT entry point
   - Forces stdio transport (required for Claude Desktop)
   - Sets up logging to avoid MCP protocol interference
   - **Critical**: Proper Python path manipulation for bundled dependencies

3. **`tools/dxt/Makefile`** - Build system
   - Incremental builds with dependency tracking
   - Official `@anthropic-ai/dxt` CLI validation
   - **Reliability**: Comprehensive validation pipeline

4. **`tools/dxt/assets/check-prereqs.sh`** - Environment validation
   - Pre-flight checks for Python version, permissions
   - **Missing**: Should be run automatically during installation

### DXT Environment Challenges

**Environment Requirements**:
- Python 3.11+ accessible via `python3` in login shell (not just venv)
- Write permissions for virtual environment creation
- Network access for dependency installation
- AWS credentials configured (separate from Quilt auth)

**Common DXT Failure Modes**:
- Python version mismatches (user has 3.10, requires 3.11+)
- Permission issues in restricted environments
- Network/firewall blocking pip installs
- AWS credential propagation to DXT environment

## Authentication Deep Dive

### Quilt Authentication Complexity

**Multi-Stage Authentication Flow**:

1. **Catalog Configuration**: `quilt3 config https://your-catalog.com`
2. **Interactive Login**: `quilt3 login` (opens browser for JWT flow)
3. **Session Validation**: `quilt3.logged_in()` returns JWT token URL
4. **Permission Discovery**: `aws_permissions_discover()` finds accessible buckets

**Authentication State Detection** (`auth.py:_get_catalog_info()`):

```python
# Priority order for catalog detection:
1. quilt3.logged_in()          # Current JWT session
2. config["navigator_url"]     # Configured catalog
3. config["registryUrl"]       # Registry bucket location
4. "unknown"                   # Fallback
```

### Authentication Gotchas for DXT

- **JWT Token Persistence**: Tokens stored in Quilt config directory
- **AWS vs Quilt Auth**: Separate credential systems (AWS IAM + Quilt JWT)
- **Catalog URL Variants**: Multiple URL formats supported (`navigator_url`, `registryUrl`)
- **Private Cloud**: Customer catalogs at custom domains (not open.quiltdata.com)

## Appendix - Useful Commands and Scripts

### Frequently Used Commands

```bash
# Development
make app                        # Start MCP server
make coverage                   # Run tests with coverage
make validate-app              # Full validation pipeline

# DXT Development
cd tools/dxt && make build     # Build DXT package
cd tools/dxt && make validate  # Validate DXT package
cd tools/dxt && make assess    # Run prerequisites check

# Testing
PYTHONPATH=app uv run pytest tests/test_mcp_server.py -v  # Isolated testing
make test-app                  # Integration tests
```

### Debugging and Troubleshooting

- **Logs**: Server uses stderr for logging (stdout reserved for MCP protocol)
- **Debug Mode**: Set `LOG_LEVEL=DEBUG` for verbose output
- **Tool Explorer**: `cd app && make run-inspector` → http://127.0.0.1:6274
- **MCP Testing**: Use `shared/test-endpoint.sh` for protocol validation

### Critical Environment Variables

```bash
# DXT Configuration
FASTMCP_TRANSPORT=stdio        # Force stdio transport (required for Claude)
AWS_DEFAULT_REGION=us-east-1   # Set if not configured in AWS credentials

# Quilt Configuration  
QUILT_CATALOG_DOMAIN=your-catalog.com    # Target catalog
QUILT_DEFAULT_BUCKET=s3://your-bucket    # Default S3 bucket

# Development
PYTHONPATH=app                 # For isolated module testing
LOG_LEVEL=WARNING             # Reduce noise in DXT environment
```
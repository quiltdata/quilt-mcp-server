# Quilt MCP Server - Phase-based Build System Specifications

This document provides an overview of the 2-phase build pipeline. Each phase has its own dedicated Makefile
and specification for focused, maintainable development.

## Architecture Overview

The Quilt MCP server uses a 2-phase pipeline for local development and desktop extension packaging:

```tree
quilt-mcp-server/
├── app/           # Phase 1: Local MCP server
│   ├── Makefile   # Phase-specific build targets
│   └── main.py    # Server implementation
├── build-dxt/     # Phase 2: Claude Desktop Extension build
│   ├── Makefile   # Phase-specific build targets
│   └── assets/    # DXT package assets
└── shared/        # Common utilities
```

## Phase Specifications

Each phase is fully documented with its own specification:

- **[Phase 1: App](1-app-spec.md)** - Local MCP server with FastMCP
- **[Phase 2: Build-DXT](5-dxt-spec.md)** - Claude Desktop Extension packaging

## Validation System

**Validation** means each phase successfully completes the following process:

1. **Preconditions**: Check dependencies and environment
2. **Execution**: Create/execute phase artifacts
3. **Testing**: Run phase-specific tests
4. **Verification**: Validate functionality

Each phase must fail and abort validation on any error.

## Usage

### Individual Phase Commands

```bash
# Work with specific phases
cd app && make help        # Phase 1 commands
cd build-dxt && make help  # Phase 2 commands
```

### Root Makefile Delegation

The root Makefile delegates to phase-specific Makefiles:

```bash
# Phase execution (delegates to <phase>/Makefile)
make app        # Phase 1: Local MCP server
make build-dxt  # Phase 2: Claude Desktop Extension

# Validation
make validate       # All phases sequentially
make validate-app   # Phase 1 only
make validate-build-dxt # Phase 2 only

# Utilities
make check-env      # Validate environment
make clean          # Clean artifacts
```

## Environment Setup

All phases use shared environment variables from `.env`:

```bash
# Copy example and configure
cp env.example .env

# Validate configuration
make check-env

# Required variables
CDK_DEFAULT_ACCOUNT  # AWS account ID
CDK_DEFAULT_REGION   # AWS region
QUILT_DEFAULT_BUCKET # S3 bucket for Quilt data
QUILT_CATALOG_DOMAIN # Quilt catalog domain
```

## Success Criteria Summary

Each phase has specific success criteria detailed in its SPEC.md:

- **Phase 1 (App)**: Local MCP server functional with ≥85% test coverage
- **Phase 2 (Build)**: Docker container healthy and responsive
- **Phase 3 (Catalog)**: ECR image pushed and validated
- **Phase 4 (Deploy)**: Live ECS service with public ALB endpoint

All phases must pass MCP endpoint validation.

## Port Configuration

Each phase uses different ports to avoid conflicts:

| Phase | Description | Port | Endpoint |
|-------|-------------|------|----------|
| Phase 1 | Local app | 8000 | `http://127.0.0.1:8000/mcp` |
| Phase 2 | Docker build | 8001 | `http://127.0.0.1:8001/mcp` |
| Phase 3 | ECR catalog | 8002 | `http://127.0.0.1:8002/mcp` |
| Phase 4 | AWS deploy | 443/80 | `https://your-alb-url/mcp` |

## Benefits of Phase-Specific Structure

1. **Focused Documentation**: Each phase has targeted specifications
2. **Maintainable Builds**: Phase-specific Makefiles reduce complexity
3. **Independent Development**: Teams can work on phases separately
4. **Clear Dependencies**: Phase order and prerequisites are explicit
5. **Modular Testing**: Each phase validates independently

## Migration from Monolithic Structure

This structure replaces the previous single large Makefile and SPEC.md with:

- 4 focused Makefiles (one per phase)
- 4 detailed SPEC.md files (one per phase)
- Root Makefile that delegates to phase-specific builds
- Cleaner separation of concerns and documentation
For detailed information about any phase, see its dedicated SPEC.md file.

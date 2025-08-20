# Fast MCP Server - Phase-based Deployment Specifications

This document provides an overview of the 4-phase deployment pipeline. Each phase has its own dedicated Makefile and SPEC.md for focused, maintainable development.

## Architecture Overview

The Quilt MCP server uses a 4-phase pipeline for robust build and deployment:

```tree
fast-mcp-server/
├── app/           # Phase 1: Local MCP server
│   ├── Makefile   # Phase-specific build targets
│   └── SPEC.md    # Detailed phase specification
├── build-docker/  # Phase 2: Docker containerization
│   ├── Makefile   # Phase-specific build targets
│   └── SPEC.md    # Detailed phase specification
├── catalog-push/  # Phase 3: ECR registry operations
│   ├── Makefile   # Phase-specific build targets
│   └── SPEC.md    # Detailed phase specification
├── deploy-aws/    # Phase 4: ECS/ALB deployment
│   ├── Makefile   # Phase-specific build targets
│   └── SPEC.md    # Detailed phase specification
└── shared/        # Common utilities
```

## Phase Specifications

Each phase is fully documented with its own specification:

- **[Phase 1: App](app/SPEC.md)** - Local MCP server with FastMCP
- **[Phase 2: Build-Docker](build-docker/SPEC.md)** - Docker containerization
- **[Phase 3: Catalog-Push](catalog-push/SPEC.md)** - ECR registry operations
- **[Phase 4: Deploy-AWS](deploy-aws/SPEC.md)** - ECS/ALB deployment

## Validation System

**Validation** means each phase successfully completes the following SPEC-compliant process:

1. **Preconditions** (`make init-<phase>`): Check dependencies and environment
2. **Execution** (`make <phase>`): Create/execute phase artifacts
3. **Testing** (`make test-<phase>`): Run phase-specific tests
4. **Verification** (`make verify-<phase>`): Validate MCP endpoint functionality
5. **Cleanup** (`make zero-<phase>`): Clean up processes and resources
6. **Configuration** (`make config-<phase>`): Generate `.config` with results

Each phase must fail and abort validation on any error.

## Usage

### Individual Phase Commands

```bash
# Work with specific phases
cd app && make help          # Phase 1 commands
cd build-docker && make help # Phase 2 commands
cd catalog-push && make help # Phase 3 commands
cd deploy-aws && make help   # Phase 4 commands
```

### Root Makefile Delegation

The root Makefile delegates to phase-specific Makefiles:

```bash
# Phase execution (delegates to <phase>/Makefile)
make app        # Phase 1: Local MCP server
make build      # Phase 2: Docker container
make catalog    # Phase 3: ECR registry push
make deploy     # Phase 4: ECS deployment

# Validation (SPEC-compliant 6-step process)
make validate       # All phases sequentially
make validate-app   # Phase 1 only
make validate-build # Phase 2 only
make validate-catalog # Phase 3 only
make validate-deploy # Phase 4 only

# Utilities
make check-env      # Validate environment
make status         # Show deployment status
make clean          # Clean artifacts
make destroy        # Clean up AWS resources
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

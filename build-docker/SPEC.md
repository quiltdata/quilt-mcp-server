# Phase 2: Build-Docker (Containerization) Specification

## Overview

Phase 2 packages the MCP server into a Docker container suitable for deployment, with comprehensive health checking and testing.

## Requirements

### Functional Requirements

- **Docker Image**: `linux/amd64` platform for ECS compatibility
- **Git Versioning**: Image tagged with git SHA for consistency
- **Health Checking**: Container health validation via HTTP endpoints
- **Port Mapping**: Exposes port 8000 internally, 8001 externally for testing

### Quality Requirements

- **Build Success**: Docker build completes without errors
- **Container Health**: Container starts and responds in <30 seconds
- **Process Validation**: MCP server process runs correctly in container
- **Reproducible Builds**: Same git SHA produces identical containers

### Technical Requirements

- **Base Image**: Uses official Python base image
- **Dependencies**: All `uv` dependencies installed in container
- **Multi-stage Build**: Optimized for size and security
- **Working Directory**: Proper WORKDIR and user setup

## Validation Process

The SPEC-compliant validation follows this 6-step process:

1. **Preconditions** (`make init`): Check Docker and dependencies
2. **Execution** (`make build`): Build Docker image with git SHA tag
3. **Testing** (`make test`): Run container health checks
4. **Verification** (`make verify`): Validate MCP endpoint from container
5. **Zero** (`make zero`): Stop running containers
6. **Config** (`make config`): Generate `.config` with image details

## Success Criteria

- ✅ Docker build completes successfully
- ✅ Image tagged with git SHA
- ✅ Container starts in <30 seconds
- ✅ Health check passes (HTTP endpoint responds)
- ✅ MCP server process active in container
- ✅ `.config` file generated with image metadata

## Files and Structure

```text
build-docker/
├── Makefile           # Phase-specific build targets
├── SPEC.md           # This specification
├── build-docker.sh   # Core phase script
├── Dockerfile        # Container definition
└── docker-compose.yml # Development compose file
```

## Image Specifications

- **Image Name**: `quilt-mcp:<git-sha>`
- **Platform**: `linux/amd64`
- **Exposed Port**: 8000
- **Health Check**: Curl to `/mcp` endpoint
- **User**: Non-root user for security

## Environment Variables

- `IMAGE_NAME`: Full image name with tag
- `TAG`: Git SHA used for tagging
- `VERBOSE`: Enable detailed build output
- Docker environment variables

## Common Issues

- **Platform Mismatch**: Ensure `linux/amd64` for ARM Macs
- **Port Conflicts**: Port 8001 must be available for testing
- **Build Context**: Dockerfile runs from project root
- **Health Check Timing**: Allow sufficient startup time
- **Dependencies**: App phase must pass before building

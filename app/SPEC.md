# Phase 1: App (Local MCP Server) Specification

## Overview

Phase 1 establishes a local MCP (Model Context Protocol) server using FastMCP framework with comprehensive testing and validation.

## Requirements

### Functional Requirements

- **Local MCP Server**: Runs on `http://127.0.0.1:8000/mcp`
- **Tool Support**: Implements Quilt data access tools (auth, buckets, packages, package_ops)
- **FastMCP Integration**: Uses FastMCP bridge for MCP protocol compliance
- **Environment Support**: Loads configuration from `.env` file

### Quality Requirements

- **Test Coverage**: ≥85% code coverage (enforced, build fails if below)
- **Unit Tests**: All core modules must have unit tests
- **Integration Tests**: Required in `tests/integration/` directory
- **Import Validation**: All modules must import successfully

### Technical Requirements

- **Python Version**: Compatible with `uv` package manager
- **Dependencies**: Managed via `pyproject.toml`
- **Transport**: Supports both SSE and HTTP transports for MCP
- **Logging**: Structured logging for debugging and monitoring

## Validation Process

The SPEC-compliant validation follows this 6-step process:

1. **Preconditions** (`make init`): Check `uv` installation
2. **Execution** (`make run`): Start local MCP server
3. **Testing** (`make test`): Run unit tests with ≥85% coverage requirement
4. **Verification** (`make verify`): Validate MCP endpoint responds correctly
5. **Zero** (`make zero`): Stop server processes cleanly
6. **Config** (`make config`): Generate `.config` with results

## Success Criteria

- ✅ All unit tests pass
- ✅ Integration tests exist and pass
- ✅ Test coverage ≥85%
- ✅ MCP endpoint responds to `tools/list` requests
- ✅ All imports work correctly
- ✅ Server starts in <10 seconds
- ✅ `.config` file generated with test results

## Files and Structure

```text
app/
├── Makefile           # Phase-specific build targets
├── SPEC.md           # This specification
├── app.sh            # Core phase script
├── main.py           # Server entry point
├── quilt_mcp/        # Main package
│   ├── server.py     # MCP server implementation
│   ├── tools/        # MCP tool implementations
│   ├── core/         # Core processing logic
│   └── adapters/     # FastMCP bridge
└── tests/            # Test suite
    ├── integration/  # Integration tests (required)
    └── *.py         # Unit tests
```

## Environment Variables

- `PYTHONPATH`: Set to app directory for imports
- `FASTMCP_TRANSPORT`: Transport mode (sse, http)
- Standard Quilt environment variables (loaded from `.env`)

## Common Issues

- **Import Errors**: Ensure `PYTHONPATH` is set correctly
- **Coverage Failures**: Add tests for uncovered code paths
- **Server Startup**: Check port 8000 is available
- **Integration Tests**: Must exist in `tests/integration/`

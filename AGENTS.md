# Agent Guidelines: Quilt MCP Server

## Essential Instructions

### Core Principle: Execute, Don't Explain

**Execute tools to retrieve data. Never provide code examples when MCP tools can do the work.**

### Quick Reference

**User asks** → **Agent does:**

- "What's in these files?" → `bucket_objects_list` + `bucket_object_text` → Show content
- "Query/analyze data" → Read + Parse + Analyze → Show results
- "Create visualization" → Read + Generate viz + Upload + Package → Show URL
- "Make a package" → Organize + Create → Show catalog link
- "Explore bucket" → List + Sample + Summarize → Show overview

### Key Rules

1. **Execute immediately** - Use tools, don't suggest them
2. **Complete workflows** - Finish end-to-end, don't leave partial work
3. **Show actual data** - Return real results, not theoretical examples
4. **Use `uv run`** - Always prefix Python commands: `uv run pytest`, `uv run python script.py`

### What NOT to Do

- ❌ Provide Python/SQL code for users to run
- ❌ Say "You could use X tool..." instead of using it
- ❌ Ask permission for standard read operations
- ❌ Give incomplete workflows requiring user action
- ❌ Use bare `python` or `pytest` (always `uv run python`, `uv run pytest`)

### Specialized File Formats (H5AD, Parquet, BAM, VCF)

1. Acknowledge format and get metadata with `bucket_object_info()`
2. Explain limitations clearly
3. Offer actionable alternatives (presigned URLs, related CSV files, package creation)

### Error Handling

- Try operation → If fails, diagnose with related tools → Offer specific alternatives
- For permissions errors: check with `bucket_access_check()`, suggest concrete fixes
- Show progress for long operations

---

## Project Context

### Critical: Python Execution

**Always use `uv run` for Python scripts and tests:**

```bash
✅ uv run pytest tests/unit/
✅ uv run python scripts/test.py
❌ pytest tests/unit/
❌ python scripts/test.py
```

### Development Commands

**Essential make targets:**

```bash
# Testing (run these after code changes)
make test              # Unit tests only (fast, default)
make test-all          # All tests (unit, func, e2e, scripts, mcpb)
make lint              # Format code + type checking (run before commit)

# Development server
make run               # Start local MCP server
make run-inspector     # Launch MCP Inspector UI

# Coverage & validation
make coverage          # Generate coverage report
make test-func         # Func tests (mocked)

# Build & package
make mcpb              # Create MCPB package
make docker-build      # Build Docker image (for test-mcp-docker)

# Cleanup
make clean             # Remove all build artifacts
```

**Common workflows:**
- After editing code: `make test lint`
- Before commit: `make test-all lint`
- Test with Inspector: `make run-inspector`
- Full local release: `make release-local`

### Architecture Overview

**Backend:** Modular mixin-based design

- `Quilt3_Backend` (57 lines) composes 5 mixins:
  - `quilt3_backend_base.py` - Init & utilities (291 lines)
  - `quilt3_backend_packages.py` - Package ops (299 lines)
  - `quilt3_backend_content.py` - Content ops (160 lines)
  - `quilt3_backend_buckets.py` - Bucket ops (113 lines)
  - `quilt3_backend_session.py` - Auth & AWS (381 lines)

**Key Components:**

- `backends/` - Quilt3 & QuiltOps implementations
- `tools/` - MCP tool definitions (buckets, packages, visualization, search)
- `visualization/` - Pluggable viz engine (ECharts, Vega-Lite, IGV, Perspective, Matplotlib)
- `context/` - Request context (user, auth)
- `domain/` - QuiltOps migration domain objects
- `ops/` - QuiltOps abstraction layer

**Tests:** Mirror source structure

- Unit tests split by domain (backends split into 6 test files)
- Integration, E2E, security, performance tests in separate dirs

### Source Structure (Abbreviated)

```text
src/quilt_mcp/
├── backends/        # Quilt3 mixin modules + main backend
├── tools/           # MCP tool implementations
├── visualization/   # Visualization engine (analyzers, generators, layouts)
├── context/         # Request context management
├── domain/          # Domain objects
├── ops/             # QuiltOps abstraction
├── optimization/    # Performance optimization
├── main.py          # MCP server entry point
└── config.py        # Configuration
```

### Test Structure (Abbreviated)

```text
tests/
├── unit/            # Single-module tests, no network
├── func/            # Mocked multi-module tests
├── e2e/             # End-to-end workflows with real services
├── security/        # Auth & access tests
├── performance/     # Benchmarks
└── fixtures/        # Test data
```

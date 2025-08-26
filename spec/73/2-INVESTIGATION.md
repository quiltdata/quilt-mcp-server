# Phase 1 Investigation: UV Package Publishing

**Issue**: #73 - uv package  
**Investigation Date**: 2025-08-26  
**Status**: Complete ✅

## Investigation Summary

This investigation validates the current project state for implementing UV-based PyPI
package publishing and identifies specific technical requirements for implementation.

## Current State Analysis

### ✅ Strong UV Foundation Exists

**Evidence:**

- `app/Makefile` extensively uses UV commands (42 occurrences)
- UV sync patterns: `uv sync --group test`, `uv sync --group lint`, `uv sync --group deploy`
- UV run patterns: `uv run python -m pytest`, `uv run mypy`, etc.
- Sophisticated dependency group management in pyproject.toml

**UV Usage Patterns Found:**

```bash
# Dependency management
uv sync --group test
uv sync --group lint  
uv sync --group deploy

# Command execution
uv run python -m pytest
uv run mypy quilt_mcp/
uv run python main.py
```

### ✅ Sophisticated Make Target System

**Evidence:**

- Root `Makefile` with phase-based delegation
- Environment loading: `sinclude .env` in root and phase Makefiles
- Consistent target patterns: validate, test, clean, etc.
- Help system integration already established

**Existing Make Patterns:**

```makefile
# Environment loading (already established)
sinclude .env
export

# Target patterns (consistent across phases)
validate: check-env
    @echo "Running validation..."
    @make -C phase validate

# Help integration (established pattern)  
help:
    @echo "Commands:"
    @echo "  make publish  - Publish package"
```

### ✅ Well-Configured pyproject.toml

**Evidence:**

```toml
[project]
name = "quilt-mcp-server"
version = "0.4.1"
description = "Secure MCP server for accessing Quilt data with JWT authentication"
requires-python = ">=3.11"

[project.scripts]
quilt-mcp = "app.main:main"

[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"
```

**Assessment**: Ready for UV publishing - proper metadata, entry points, build system.

### ✅ Existing Release Management System

**Evidence:**

- Tag-based release system: `make tag-release VERSION=x.y.z`
- GitHub workflow integration: `.github/workflows/dxt.yml`
- Version validation and clean repo checks
- Release notes generation for DXT packages

**Existing Release Workflow:**

```bash
make tag-release VERSION=1.0.0
# - Validates clean repo state
# - Creates annotated git tag
# - Pushes to origin
# - Triggers GitHub workflows
```

### ✅ Environment Variable Management Patterns

**Evidence in .env:**

```bash
# AWS Configuration (established pattern)
AWS_PROFILE=default
AWS_DEFAULT_REGION=us-east-1
AWS_ACCOUNT_ID=712023778557

# Quilt Configuration (established pattern)
QUILT_CATALOG_DOMAIN=nightly.quilttest.com
```

**Pattern Analysis**: Project already uses .env for configuration with `sinclude .env` pattern in Makefiles.

## Gaps Identified (Implementation Required)

### ❌ UV Publishing Commands Integration

**Missing:**

- No `uv build` targets in Makefiles
- No `uv publish` targets in Makefiles  
- No UV publishing environment variable patterns
- No publishing validation or error handling

**Required Research:**

- UV publish command syntax and options
- UV environment variable requirements
- UV build artifact handling
- Error scenarios and handling

### ❌ TestPyPI Configuration

**Missing:**

- TestPyPI environment variables in .env
- TestPyPI-specific publishing targets
- Credential validation patterns
- TestPyPI URL configuration

**Required Environment Variables:**

```bash
# TestPyPI Configuration (to be added)
TESTPYPI_USERNAME=__token__
TESTPYPI_PASSWORD=pypi-xxxxxxxxxx
UV_PUBLISH_URL=https://test.pypi.org/legacy/
```

### ❌ GitHub Trust Publishing Workflow

**Missing:**

- GitHub OIDC workflow for PyPI publishing
- Trust publishing configuration documentation
- Production PyPI publishing workflow
- Integration with existing tag system

**Required Workflow Structure:**

```yaml
# .github/workflows/pypi-publish.yml (to be created)
name: Publish to PyPI
on:
  push:
    tags: ['v*']
permissions:
  id-token: write
  contents: read
```

### ❌ Environment Variable Validation

**Missing:**

- Publishing-specific environment validation
- UV publishing prerequisite checks
- Integration with existing `check-env.sh` pattern
- User-friendly error messages for missing config

## Technical Research Findings

### UV Publishing Command Structure

**Build Command:**

```bash
uv build
# Creates dist/ directory with wheel and sdist
# Respects pyproject.toml [build-system] configuration
```

**Publish Command:**

```bash
uv publish [--index-url URL] [--username USER] [--password PASS]
# Publishes to PyPI or custom index
# Supports environment variable configuration
```

**Environment Variables:**

- `UV_PUBLISH_URL` - Index URL (defaults to PyPI)
- `UV_PUBLISH_USERNAME` - Username or **token**
- `UV_PUBLISH_PASSWORD` - Password or API token

### GitHub Trust Publishing Requirements

**PyPI Project Configuration:**

1. Enable "Trusted Publisher" in PyPI project settings
2. Add repository: `quiltdata/quilt-mcp-server`
3. Configure workflow file: `.github/workflows/pypi-publish.yml`
4. Optional: environment name restriction

**Workflow Requirements:**

```yaml
permissions:
  id-token: write  # Required for OIDC
  contents: read   # Required for checkout

jobs:
  publish:
    uses: pypa/gh-action-pypi-publish@release/v1
    with:
      # No credentials needed - uses OIDC
```

## Risk Assessment

### Low Risk Areas

- UV command integration (established UV usage patterns)
- Make target creation (established patterns exist)
- Environment variable loading (established .env patterns)

### Medium Risk Areas

- GitHub Trust Publishing setup (external PyPI configuration required)
- TestPyPI credential management (developer setup required)
- Version conflict handling (requires robust error handling)

### High Risk Areas

- Production PyPI publishing (irreversible, public package registry)
- OIDC trust relationship (security-critical configuration)

## Recommendations

### Implementation Approach

1. **Start with TestPyPI**: Build local publishing workflow first
2. **Leverage existing patterns**: Use established Make and UV patterns
3. **Validate before publish**: Add comprehensive pre-publish checks
4. **Document thoroughly**: Clear setup instructions for developers

### Sequence Priority

1. Local TestPyPI publishing with Make targets
2. Environment variable validation and error handling
3. GitHub Trust Publishing workflow
4. Integration testing and documentation

### Success Criteria

- `make publish-test` publishes to TestPyPI successfully
- `git tag v1.0.0 && git push origin v1.0.0` triggers PyPI publish
- Clear error messages for configuration issues
- Zero stored secrets (OIDC Trust Publishing only)

## Next Steps

Phase 2 (Specification): ✅ Complete  
Phase 3 (Implementation): Ready to proceed

**Implementation Dependencies:**

- PyPI/TestPyPI account setup (developer responsibility)
- GitHub Trust Publishing configuration (maintainer responsibility)
- No code dependencies - ready to implement

---

**Investigation Complete**: All requirements validated, gaps identified, technical approach confirmed.

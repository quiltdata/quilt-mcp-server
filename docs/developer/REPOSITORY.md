# Repository Structure and Organization

This document provides a comprehensive overview of the Quilt MCP Server repository structure,
explaining the purpose and contents of each directory and key file.

## 📁 Repository Overview

```text
quilt-mcp-server/
├── 📁 .claude/                # Claude AI assistant configuration
├── 📁 .github/                # GitHub workflows and templates
├── 📁 bin/                    # Executable scripts and utilities
├── 📁 build/                  # Python build artifacts (generated)
├── 📁 dist/                   # Distribution artifacts (generated)  
├── 📁 docs/                   # Comprehensive documentation
├── 📁 spec/                   # Technical specifications and design docs
├── 📁 src/                    # Core source code
├── 📁 tests/                  # Test suite with configurations and fixtures
├── 📄 .env                    # Environment configuration (local)
├── 📄 .gitignore              # Git ignore patterns
├── 📄 CHANGELOG.md            # Version history and changes
├── 📄 CLAUDE.md               # Development guidelines for AI assistants
├── 📄 LICENSE.txt             # Apache 2.0 license
├── 📄 Makefile                # Main build coordination
├── 📄 README.md               # Main project documentation
├── 📄 make.deploy             # Production/packaging workflow
├── 📄 make.dev                # Development workflow
├── 📄 pyproject.toml          # Python project configuration
├── 📄 ruff.toml               # Code linting configuration
└── 📄 uv.lock                 # Dependency lock file
```

## 🏗️ Core Source Structure

### `src/` - Main Source Code

The core implementation of the MCP server:

```text
src/
├── 📄 main.py                 # MCP server entry point
├── 📁 deploy/                 # MCPB deployment assets
│   ├── 📄 README.md          # End-user installation guide
│   ├── 📄 check-mcpb.sh      # Prerequisites validation for end users
│   ├── 📄 icon.png           # MCPB package icon
│   ├── 📄 LICENSE.txt        # License file for package
│   └── 📄 manifest.json.j2   # MCPB manifest template
└── 📁 quilt_mcp/             # Main MCP server package
    ├── 📄 __init__.py        # Package initialization with version
    ├── 📄 constants.py       # Global constants and configuration
    ├── 📄 exceptions.py      # Custom exception classes
    ├── 📄 formatting.py      # Response formatting utilities
    ├── 📄 utils.py           # Core utilities and server creation
    └── 📁 tools/             # 84+ MCP tools implementation
        ├── 📄 __init__.py    # Tool registration and exports
        ├── 📄 auth.py        # Authentication and authorization tools
        ├── 📄 bucket.py      # S3 bucket operations
        ├── 📄 config.py      # Configuration management tools
        ├── 📄 object.py      # S3 object operations
        ├── 📄 package.py     # Quilt package operations
        ├── 📄 registry.py    # Registry operations
        ├── 📄 search.py      # Search and discovery tools
        ├── 📄 system.py      # System utilities
        └── 📄 metadata.py    # Metadata management
```

## 🔧 Development Infrastructure

### `bin/` - Executable Scripts

Development and testing utilities:

```text
bin/
├── 📄 check-dev.sh           # Development environment validation
├── 📄 common.sh              # Common shell functions
├── 📄 mcp-test.py            # Modern MCP endpoint testing (Python)
├── 📄 release.sh             # Release management
├── 📄 test-prereqs.sh        # Legacy prerequisites check
└── 📄 version.sh             # Version management utilities
```

### `tests/` - Test Suite

Comprehensive test coverage with multiple test types:

```text
tests/
├── 📁 fixtures/              # Test data and fixtures
│   ├── 📄 mcp-test.yaml     # MCP testing configuration
│   └── 📁 runners/           # Test runner scripts
├── 📄 test_*.py              # Unit and integration tests
└── 📄 conftest.py            # Pytest configuration
```

## 📚 Documentation Structure

### `docs/` - Documentation Hub

```text
docs/
├── 📁 api/                   # API documentation
├── 📁 architecture/          # System architecture docs
├── 📁 archive/               # Archived documentation
├── 📁 developer/             # Developer guides
│   └── 📄 REPOSITORY.md     # This file
├── 📁 images/                # Documentation images
├── 📁 stories/               # User stories and scenarios
└── 📁 user/                  # End-user documentation
```

### `spec/` - Technical Specifications

Design specifications and implementation tracking:

```text
spec/
├── 📁 87/                    # Issue #87 specifications
├── 📁 100/                   # Issue #100 cleanup specifications
└── 📄 *.md                   # Individual feature specifications
```

## 🚀 Build and Deployment

### Build System

- **`Makefile`**: Main coordination hub that delegates to specialized makefiles
- **`make.dev`**: Development workflow (testing, linting, local server)
- **`make.deploy`**: Production packaging and MCPB creation

### Key Build Targets

**Development:**

- `make run` - Start local MCP server
- `make test` - Run comprehensive test suite
- `make lint` - Code formatting and type checking
- `make clean` - Clean all build artifacts

**Production:**

- `make build` - Prepare production build
- `make mcpb` - Create MCPB package
- `make release` - Full release workflow

## 🔧 Configuration Files

### Core Configuration

- **`pyproject.toml`**: Python project metadata, dependencies, and tool configuration
- **`uv.lock`**: Locked dependency versions for reproducible builds
- **`ruff.toml`**: Code linting and formatting rules
- **`.env`**: Local environment variables (not in git)
- **`env.example`**: Environment template

### CI/CD Configuration

- **`.github/workflows/`**: GitHub Actions for testing and deployment
- **`.github/ISSUE_TEMPLATES/`**: Issue templates for bug reports and features

## 🧠 AI Assistant Integration

### `.claude/` - Claude Configuration

```text
.claude/
├── 📁 agents/                # Specialized agent configurations
└── 📄 config.json           # Claude-specific settings
```

- **`CLAUDE.md`**: Comprehensive development guidelines for AI assistants
- Contains TDD practices, workflow instructions, and coding standards

## 📊 Generated Artifacts

### Build Artifacts (`.gitignore`d)

- **`build/`**: Python build intermediates
- **`dist/`**: Distribution packages and wheels
- **`.ruff_cache/`**: Linting cache for faster runs
- **`.venv/`**: Virtual environment (local development)

### Coverage and Analysis

- **`src/coverage.xml`**: Test coverage reports
- **`build/test-results/`**: Test execution results and reports

## 🏆 Key Features

### Repository Organization Principles

1. **Consolidated Build System**: Single Makefile delegates to specialized workflows
2. **Shallow Directory Hierarchy**: Files are easy to find with logical organization
3. **Spec-Driven Development**: Technical specifications guide implementation
4. **Comprehensive Testing**: 85%+ coverage with unit and integration tests
5. **Modern Tooling**: Uses `uv` for dependencies, `ruff` for linting, pytest for testing

### Development Workflow

1. **Feature specifications** are created in `spec/` directory
2. **TDD implementation** with tests in `tests/` directory  
3. **Code in `src/`** follows clean architecture patterns
4. **Documentation** is maintained alongside implementation
5. **CI/CD** ensures quality through automated testing and deployment

## 📋 Quick Reference

### Most Important Files

- **`README.md`**: Start here for project overview and quick start
- **`CLAUDE.md`**: Essential for AI-assisted development
- **`src/main.py`**: MCP server entry point
- **`pyproject.toml`**: Dependencies and project metadata
- **`Makefile`**: Build commands and workflows

### Getting Started

1. **Clone and setup**: `git clone` → `uv sync` → `cp env.example .env`
2. **Development**: `make run` (server) → `make test` (verify)
3. **Testing**: `bin/mcp-test.py http://localhost:8000/mcp/`
4. **Building**: `make mcpb` (MCPB) → `make release` (distribution)

---

This repository follows modern Python development practices with comprehensive tooling
for building, testing, and deploying production-ready MCP servers.

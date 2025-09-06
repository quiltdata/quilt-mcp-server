<!-- markdownlint-disable MD013 -->
# Release Process Specification

**Status**: Analysis Complete  
**Branch**: 100-feature-cleanup-repomake  
**Issue**: Phase 4 - Analysis Phase  
**Date**: 2025-01-06  

## Executive Summary

This specification documents the complete release process for the Quilt MCP Server, tracing all makefiles, GitHub Actions, and scripts involved in testing and creating releases. The analysis reveals a well-structured but complex release pipeline with several missing dependencies that prevent successful release creation.

## Critical Issues Discovered

### 1. Missing Release Dependencies

**Problem**: `make tag` fails because required files are missing:

- `tools/dxt/assets/manifest.json.j2` (expected by `bin/release.sh:58`)
- `scripts/version-utils.py` (called by `bin/release.sh:63`)

**Current State**: Manifest template exists at `src/deploy/manifest.json.j2` but release script expects it at `tools/dxt/assets/`

### 2. Path Inconsistencies

**Problem**: The Makefile system expects assets in `tools/dxt/assets/` but they're actually located in `src/deploy/`

**Makefile Reference**: `make.deploy:7` defines `ASSETS_DIR := src/deploy` but `bin/release.sh:58` hardcodes `tools/dxt/assets/manifest.json.j2`

## Release Process Architecture

### 1. Entry Points

#### Local Development Release

```bash
make tag          # Create release tag from pyproject.toml version
make tag-dev      # Create development tag with timestamp
make release      # Full release workflow (test → build → package)
```

#### Automated GitHub Release

- **Trigger**: Push tag matching `v*` pattern
- **Action**: `.github/workflows/ci.yml` → `build-and-release` job

### 2. Makefile Target Flow

#### Development Workflow (`make.dev`)

```tree
make test-ci
├── uv sync --group test
├── PYTHONPATH=src uv run pytest tests/ -v --tb=short --color=yes
└── --cov=quilt_mcp --cov-report=term-missing --cov-fail-under=85
```

#### Production Workflow (`make.deploy`)

```tree
make release
├── make test           # Run all tests
├── make lint           # Code formatting and type checking  
├── make build          # Prepare production build environment
│   ├── make check-tools    # Verify npx, uv available
│   ├── make build-contents # Copy assets, app, install deps
│   └── make build-test     # Test bootstrap.py import
├── make validate-package   # Validate DXT package
└── make release-package    # Create release bundle with docs
```

#### Build Process Detail

```tree
make build
├── $(ASSETS_MARKER): Copy src/deploy/* → tools/dxt/build/
│   ├── chmod +x check-dxt.sh
│   ├── sed 's/{{ version }}/$(PACKAGE_VERSION)/g' manifest.json.j2 > manifest.json
│   └── rm manifest.json.j2
├── $(APP_MARKER): Copy src/quilt_mcp/*.py → tools/dxt/build/
└── $(DEPS_MARKER): uv pip install --target tools/dxt/build/lib --no-binary=pydantic-core .
```

#### Package Creation Flow

```tree
make dxt-package
├── make build-contents
├── npx @anthropic-ai/dxt pack tools/dxt/build tools/dxt/dist/quilt-mcp-$(VERSION).dxt
└── make validate-package
    ├── npx @anthropic-ai/dxt info $(PACKAGE_NAME)
    └── npx @anthropic-ai/dxt validate tools/dxt/build/manifest.json
```

#### Release Bundle Creation

```tree
make release-package
├── make validate-package
├── mkdir -p tools/dxt/dist/release
├── cp $(PACKAGE_NAME) tools/dxt/dist/release/
├── cp src/deploy/README.md tools/dxt/dist/release/
├── cp src/deploy/check-dxt.sh tools/dxt/dist/release/
├── cd tools/dxt/dist/release && zip -r ../quilt-mcp-$(VERSION)-release.zip .
└── rm -rf tools/dxt/dist/release
```

### 3. Release Script Flow (`bin/release.sh`)

#### Release Tag Creation (`bin/release.sh release`)

```bash
# 1. Repository State Validation
check_clean_repo()
├── git status --porcelain  # Must be clean
└── exit 1 if uncommitted changes

# 2. Version Resolution  
├── Validate pyproject.toml exists
├── Validate tools/dxt/assets/manifest.json.j2 exists  # ❌ MISSING
├── python3 scripts/version-utils.py get-version      # ❌ MISSING SCRIPT
└── Determine tag type (dev/prerelease/release)

# 3. Tag Creation
├── git pull origin main
├── git tag -a "v$VERSION" -m "$TAG_TYPE v$VERSION"
├── git push origin "v$VERSION"
└── Echo GitHub release URL
```

#### Development Tag Creation (`bin/release.sh dev`)

```bash
# 1. Repository State Validation
check_clean_repo()

# 2. Development Version Generation
├── BASE_VERSION=$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])")
├── TIMESTAMP=$(date +%Y%m%d%H%M%S)
├── DEV_VERSION="$BASE_VERSION-dev-$TIMESTAMP"
└── Validate tag doesn't exist

# 3. Tag Creation  
├── git pull origin $(git rev-parse --abbrev-ref HEAD)
├── git tag -a "v$DEV_VERSION" -m "Development build v$DEV_VERSION"
├── git push origin "v$DEV_VERSION"
└── Echo GitHub prerelease URL
```

### 4. GitHub Actions Workflow

#### CI Pipeline (`.github/workflows/ci.yml`)

```yaml
# Triggers
on:
  push:
    branches: [main]
    tags: ['v*']          # Triggers release process
  pull_request:
    branches: ['**']
  workflow_dispatch:

# Jobs
jobs:
  test:                   # Matrix: Python 3.11, 3.12, 3.13
    ├── Checkout code
    ├── Setup build environment (.github/actions/setup-build-env)
    │   ├── Install uv
    │   ├── uv python install ${{ matrix.python-version }}
    │   └── Cache dependencies (~/.cache/uv, ~/.npm)
    ├── make test-ci (with AWS secrets)
    └── Upload test results

  build-and-release:      # Only on tag push (v*)
    needs: test
    ├── Checkout code  
    ├── Setup build environment (Python 3.11 + Node.js)
    │   ├── Install uv
    │   ├── Setup Node.js 18
    │   ├── npm install -g @anthropic-ai/dxt
    │   └── Cache dependencies
    ├── Extract version from tag
    └── Create release (.github/actions/create-release)
        ├── make dxt-package
        ├── make validate-package
        ├── make release-package
        └── softprops/action-gh-release@v2
            ├── Upload tools/dxt/dist/*-release.zip
            ├── Set prerelease: ${{ contains(inputs.tag-version, '-') }}
            └── Generate release notes
```

#### Build Environment Setup (`.github/actions/setup-build-env`)

```yaml
# Inputs: python-version, include-nodejs, nodejs-version
steps:
  ├── Install uv (astral-sh/setup-uv@v3)
  ├── uv python install ${{ inputs.python-version }}
  ├── Setup Node.js (if include-nodejs == 'true')
  ├── npm install -g @anthropic-ai/dxt (if Node.js enabled)
  └── Cache dependencies (actions/cache@v4)
      └── ~/.cache/uv, ~/.npm
```

#### Release Creation (`.github/actions/create-release`)

```yaml
# Input: tag-version
steps:
  ├── make dxt-package
  ├── make validate-package  
  ├── make release-package
  ├── Create GitHub Release (softprops/action-gh-release@v2)
  │   ├── name: "Quilt MCP DXT v${{ inputs.tag-version }}"
  │   ├── files: tools/dxt/dist/*-release.zip
  │   ├── prerelease: ${{ contains(inputs.tag-version, '-') }}
  │   └── generate_release_notes: true
  └── Upload DXT artifacts (90 day retention)
```

### 5. Supporting Scripts and Assets

#### Version Management

- **`bin/version.sh`**: Git-based version utilities (commit hash, branch)
- **Missing**: `scripts/version-utils.py` (referenced in `bin/release.sh:63`)

#### DXT Package Assets (`src/deploy/`)

- **`manifest.json.j2`**: DXT package manifest template
- **`bootstrap.py`**: DXT entry point script
- **`dxt_main.py`**: Main DXT application
- **`README.md`**: User documentation
- **`check-dxt.sh`**: DXT validation script
- **`requirements.txt`**: Python dependencies
- **`icon.png`**: Package icon
- **`LICENSE.txt`**: License file

#### Testing Scripts (`bin/`)

- **`test-endpoint.sh`**: Endpoint testing
- **`test-prereqs.sh`**: Prerequisites validation
- **`check-dev.sh`**: Development environment check
- **`mcp-test.py`**: MCP protocol testing

## Dependencies and Requirements

### System Dependencies

- **Python**: 3.11+ (tested on 3.11, 3.12, 3.13)
- **Node.js**: 18+ (for DXT CLI)
- **uv**: Python package manager
- **git**: Version control operations

### Python Dependencies (from `pyproject.toml`)

```toml
[dependency-groups]
test = ["pytest>=8.0.0", "pytest-asyncio>=0.23.0", "pytest-cov>=4.0.0", "pytest-timeout>=2.1.0"]
deploy = ["aws-cdk-lib>=2.100.0", "constructs>=10.0.0"]  
lint = ["ruff>=0.1.0"]
dev = ["pytest-xdist>=3.8.0"]
```

### External Tools

- **`@anthropic-ai/dxt`**: DXT package creation and validation
- **AWS CLI**: For cloud deployment (via secrets)

### Environment Variables (CI)

```bash
# AWS Configuration
AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION

# Quilt Configuration  
QUILT_DEFAULT_BUCKET, QUILT_CATALOG_URL, QUILT_TEST_PACKAGE, QUILT_TEST_ENTRY
```

## Version Management Strategy

### Version Sources

1. **`pyproject.toml`** - Primary version source (currently `0.6.0`)
2. **Git tags** - Release versioning (`v{version}`)
3. **Timestamp suffixes** - Development builds (`{version}-dev-{timestamp}`)

### Tag Types and Patterns

```bash
# Release tags
v0.6.0              # Stable release
v0.6.0-rc1          # Release candidate (prerelease)
v0.6.0-beta1        # Beta release (prerelease) 

# Development tags  
v0.6.0-dev-20250106123045  # Development build (prerelease)
```

### Release Classification Logic

- **Release**: No hyphens in version (e.g., `0.6.0`)
- **Prerelease**: Contains hyphens (e.g., `0.6.0-rc1`, `0.6.0-dev-20250106123045`)
- **Development**: Contains "dev" substring

## File Structure and Paths

### Source Organization

```tree
src/
├── quilt_mcp/           # Application source code
└── deploy/              # DXT package assets
    ├── manifest.json.j2     # DXT manifest template
    ├── bootstrap.py         # DXT entry point
    ├── dxt_main.py         # Main application
    ├── README.md           # User documentation
    ├── check-dxt.sh        # Validation script
    ├── requirements.txt    # Dependencies
    ├── icon.png           # Package icon
    └── LICENSE.txt        # License
```

### Build Artifacts

```tree
tools/dxt/
├── build/               # Build staging area
│   ├── manifest.json       # Generated from template
│   ├── bootstrap.py        # Copied from src/deploy/
│   ├── lib/               # Python dependencies
│   └── [other assets]     # Copied from src/deploy/
└── dist/               # Distribution packages
    ├── quilt-mcp-{version}.dxt          # DXT package
    └── quilt-mcp-{version}-release.zip  # Release bundle
```

## Recommended Fixes

### Immediate Actions Required

1. **Fix Path Inconsistencies**

   ```bash
   # Option A: Update bin/release.sh to use correct path
   sed -i 's|tools/dxt/assets/manifest.json.j2|src/deploy/manifest.json.j2|g' bin/release.sh
   
   # Option B: Create missing directory structure  
   mkdir -p tools/dxt/assets
   cp src/deploy/manifest.json.j2 tools/dxt/assets/
   ```

2. **Create Missing Version Utility**

   ```bash
   # Create scripts/version-utils.py with get-version command
   mkdir -p scripts
   # Implement version extraction from pyproject.toml
   ```

3. **Test Release Process**

   ```bash
   # Validate all dependencies before release
   make check-tools
   make test
   make build  
   make validate-package
   ```

### Process Improvements

1. **Add Dependency Validation**
   - Pre-flight checks for all required files
   - Validation of external tool availability
   - AWS credentials validation for CI

2. **Enhance Error Handling**
   - Better error messages for missing dependencies
   - Rollback capabilities for failed releases
   - Dry-run mode for testing

3. **Documentation Updates**
   - Update CLAUDE.md with correct release commands
   - Document all environment variables required
   - Add troubleshooting guide for common failures

## Testing Strategy

### Local Testing Workflow

```bash
# 1. Clean environment test
make clean
make test

# 2. Build validation
make build
make validate-package

# 3. Release preparation (without tagging)
make release-package

# 4. Tag testing (development tag first)
make tag-dev
```

### CI/CD Testing

- Matrix testing across Python versions (3.11, 3.12, 3.13)
- Integration testing with AWS services
- DXT package validation
- Release artifact verification

## Conclusion

The release process is well-architected but currently broken due to missing dependencies and path inconsistencies. The system supports both manual local releases and automated GitHub releases with proper artifact management. Once the immediate fixes are applied, the release pipeline should function correctly for both development and production releases.

**Priority**: HIGH - Release functionality is currently non-functional
**Effort**: LOW - Simple path fixes and missing file creation
**Risk**: LOW - Changes are isolated to build/release infrastructure

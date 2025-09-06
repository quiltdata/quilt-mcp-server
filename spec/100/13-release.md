<!-- markdownlint-disable MD013 -->
# Release Process Specification

**Status**: Design Complete  
**Branch**: 100-feature-cleanup-repomake  
**Issue**: Phase 4 - Clean Release System  
**Date**: 2025-01-06  

## Executive Summary

This specification defines a clean, semantic release process for the Quilt MCP Server. The system uses self-documenting make targets that clearly distinguish between DXT package creation, validation, and GitHub release management.

## Key Design Decisions

### 1. Semantic Target Naming

**Decision**: Use descriptive, unambiguous target names that clearly indicate their function.

**Rationale**: The previous naming was misleading (`make package` created DXT packages, not Python packages). Clear names reduce cognitive overhead and prevent errors.

**Implementation**:

- `make dxt` - Creates DXT package (.dxt file)
- `make dxt-validate` - Validates DXT package integrity
- `make release-zip` - Creates release bundle (.zip with docs)
- `make release` - Creates and pushes release tags
- `make release-local` - Complete local workflow (no push)

### 2. No Backward Compatibility

**Decision**: Remove all confusing legacy targets without aliases.

**Rationale**: Clean break prevents perpetuating confusion. Developers will get clear error messages directing them to correct targets.

**Removed Targets**:

- `package` (misleading - actually creates DXT)
- `dxt-package` (redundant alias)
- `validate-package` (unclear what type of package)
- `release-package` (confusing - creates zip bundle)
- `tag`, `tag-dev` (unclear what they tag)

### 3. Clear Release Workflow

**Decision**: Distinguish between local preparation and actual release creation.

**Rationale**: Release creation involves pushing tags and triggering GitHub Actions. This should be explicit and separate from local validation steps.

**Workflow**:

1. `make release-local` - Local validation and packaging
2. `make release` - Push release tag → GitHub Actions → public release

### 4. DXT Testing Integration

**Decision**: Include DXT package testing in standard test workflow.

**Rationale**: DXT packages are the primary deliverable. Testing should validate the complete build pipeline, not just source code.

## Release System Architecture

### Make Target Structure

```bash
# Development Workflow (make.dev)
make test            # Run all tests (includes DXT validation)
make lint            # Code quality checks

# Production Workflow (make.deploy)  
make build           # Prepare build environment
make dxt             # Create DXT package
make dxt-validate    # Validate DXT package
make release-zip     # Create release bundle with documentation
make release-local   # Complete workflow: test → build → dxt → validate → zip
make release         # Push release tag (triggers GitHub Actions)
make release-dev     # Push development tag (triggers prerelease)

# Dry-run mode (use DRY_RUN=1 environment variable)
DRY_RUN=1 make release     # Show what would happen without pushing
DRY_RUN=1 make release-dev # Show what would happen without pushing
```

### Version Management

**Version Source**: `pyproject.toml` project.version field

**Tag Patterns**:

- `v0.6.0` - Stable release (no hyphens)
- `v0.6.0-rc1` - Release candidate (prerelease)
- `v0.6.0-dev-20250106123045` - Development build (prerelease)

**Scripts**:

- `scripts/version-utils.py` - Extract version from pyproject.toml
- `bin/release.sh` - Tag creation and validation logic

### GitHub Actions Integration

**Trigger**: Push tags matching `v*` pattern

**Workflow**:

1. Test matrix (Python 3.11, 3.12, 3.13)
2. Build DXT package (`make dxt`)
3. Validate package (`make dxt-validate`)
4. Create release bundle (`make release-zip`)
5. Create GitHub release with artifacts

**Artifacts**:

- `quilt-mcp-{version}.dxt` - DXT package
- `quilt-mcp-{version}-release.zip` - Release bundle with documentation

### File Organization

```tree
src/
├── quilt_mcp/              # Application source
└── deploy/                 # DXT package assets
    ├── manifest.json.j2    # Template (version substitution)
    ├── bootstrap.py        # DXT entry point
    ├── README.md           # User documentation
    └── [other assets]

build/                      # Build staging (generated)
├── manifest.json           # Generated from template
├── bootstrap.py            # Copied from src/deploy/
├── lib/                    # Python dependencies
└── [other assets]          # Copied from src/deploy/

dist/                       # Final packages (generated)
├── quilt-mcp-{version}.dxt          # DXT package
└── quilt-mcp-{version}-release.zip  # Release bundle

scripts/
└── version-utils.py        # Version extraction utility

bin/
└── release.sh             # Release management script
```

## Implementation Checklist

### Phase 1: Core Renaming

- [ ] **make.deploy**: Update all paths from `tools/dxt/` to top-level `build/` and `dist/`
- [ ] **make.deploy**: Rename `$(PACKAGE_NAME)` target to `dxt`
- [ ] **make.deploy**: Rename `validate-package` to `dxt-validate`  
- [ ] **make.deploy**: Rename `$(RELEASE_NAME)` target to `release-zip`
- [ ] **make.deploy**: Remove `package` target (dead)
- [ ] **make.deploy**: Remove `dxt-package` target (redundant alias)
- [ ] **make.deploy**: Remove `release-package` target (rename to `release-zip`)
- [ ] **Makefile**: Rename `release` to `release-local`
- [ ] **Makefile**: Rename `tag` to `release`
- [ ] **Makefile**: Rename `tag-dev` to `release-dev`

### Phase 2: Update References

- [ ] **GitHub Actions**: Update `.github/actions/create-release/action.yml`
  - [ ] `make dxt-package` → `make dxt`
  - [ ] `make validate-package` → `make dxt-validate`
  - [ ] `make release-package` → `make release-zip`
  - [ ] Update artifact paths from `tools/dxt/dist/*` to `dist/*`
- [ ] **Help Text**: Update main Makefile help descriptions
- [ ] **Documentation**: Update CLAUDE.md with new target names

### Phase 3: Enhanced Testing

- [ ] **DXT Testing**: Add DXT package validation to `make test`
- [ ] **Bootstrap Test**: Validate DXT bootstrap.py functionality
- [ ] **Manifest Test**: Validate manifest.json generation
- [ ] **Dry Run**: Add `DRY_RUN=1` environment variable support to `make release` and `make release-dev`

### Phase 4: Documentation

- [ ] **CLAUDE.md**: Update with new release commands
- [ ] **README**: Update installation/development instructions
- [ ] **Error Messages**: Provide helpful errors for removed targets

## Success Criteria

1. **Semantic Clarity**: Target names clearly indicate their function
2. **No Confusion**: Removed all misleading target names
3. **Complete Testing**: DXT packages tested as part of standard workflow
4. **Clean Workflow**: Clear separation between local prep and release creation
5. **GitHub Integration**: Automated releases triggered by semantic tags
6. **Documentation**: All references updated to new target names

## Risk Mitigation

**Risk**: Developers using old target names
**Mitigation**: Clear error messages with suggested replacements

**Risk**: CI/CD failures during transition
**Mitigation**: Update GitHub Actions before deploying Makefile changes

**Risk**: Incomplete DXT testing
**Mitigation**: Validate complete build pipeline in test suite

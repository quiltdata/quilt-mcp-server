<!-- markdownlint-disable MD013 -->
# Phase 3 Design: Fix Broken GitHub Actions & Script Organization

**Issue**: [#100 - cleanup repo/make](https://github.com/quiltdata/quilt-mcp-server/issues/100)  
**Based on**: [02-specifications.md](./02-specifications.md)  
**Phase**: 3 of 4 - Fix Broken GitHub Actions & Script Organization

## Overview

Phase 3 addresses a critical issue: GitHub Actions are duplicating Makefile functionality AND referencing non-existent `tools/dxt/` paths (removed in Phase 2). This creates broken CI/CD and violates DRY principle. Move scripts to `bin/` and fix Actions to use existing Makefile targets instead of duplicating logic.

## Critical Issues Discovered

### 1. Broken GitHub Actions References

GitHub Actions reference `tools/dxt/` paths that **no longer exist** (removed in Phase 2):

```yaml
# .github/actions/create-release/action.yml - BROKEN PATHS
- MANIFEST_VERSION=$(python3 -c "import json; print(json.load(open('tools/dxt/build/manifest.json')))")
- cp tools/dxt/dist/quilt-mcp-*.dxt release-package/
- cp tools/dxt/assets/README.md release-package/
- cp tools/dxt/assets/check-prereqs.sh release-package/
- path: tools/dxt/dist/*.dxt
```

**Reality**: These paths don't exist. Assets moved to `src/deploy/` in Phase 2.

### 2. Actions Duplicate Makefile Logic

GitHub Actions manually reimplement what `make.deploy` already does:

```yaml
# Actions manually do:
- name: Build DXT package
  run: make dxt-package
- name: Create release package  
  run: |
    mkdir -p release-package
    cp tools/dxt/dist/quilt-mcp-*.dxt release-package/  # BROKEN
    cp tools/dxt/assets/README.md release-package/      # BROKEN
```

**But `make.deploy` already has:**

- `make release-package` - Creates release bundle with documentation  
- `make validate-package` - Validates DXT package
- Uses correct paths: `src/deploy/` not `tools/dxt/`

## Target State

### 1. Fixed Directory Structure

```tree
bin/           # Build scripts (moved from tools/)
├── test-prereqs.sh   # Environment validation (renamed from check-env.sh)
├── release.sh        # Release workflow (unchanged)
├── test-endpoint.sh  # Endpoint testing (unchanged)
└── version.sh        # Version management (unchanged)

src/deploy/    # DXT assets (already moved in Phase 2)
├── manifest.json.j2
├── README.md
├── check-prereqs.sh
└── ...

tools/         # REMOVED (empty after script migration)
```

### 2. Simplified GitHub Actions

Replace complex manual logic with simple Makefile calls:

```yaml
# BEFORE (broken and duplicated):
- name: Build DXT package
  run: make dxt-package
- name: Create release package  
  run: |
    mkdir -p release-package
    cp tools/dxt/dist/quilt-mcp-*.dxt release-package/  # BROKEN
    cp tools/dxt/assets/README.md release-package/      # BROKEN

# AFTER (working and DRY):
- name: Create release package
  run: make release-package  # Uses correct paths, creates proper bundle
```

## Implementation Strategy

### Step 1: Script Migration

1. **Create `bin/` directory**
2. **Move scripts** from `tools/` to `bin/`:
   - `tools/check-env.sh` → `bin/test-prereqs.sh` (rename for clarity)
   - `tools/release.sh` → `bin/release.sh`
   - `tools/test-endpoint.sh` → `bin/test-endpoint.sh`
   - `tools/version.sh` → `bin/version.sh`
3. **Remove empty `tools/` directory**

### Step 2: Fix Makefile References

Update `make.deploy` to use `bin/` paths:

```makefile
# Lines 119, 123
tag:
    @echo "Creating release tag..."
    @./bin/release.sh release

tag-dev:
    @echo "Creating development tag..."
    @./bin/release.sh dev
```

### Step 3: Fix Broken GitHub Actions

Replace broken manual logic with working Makefile targets:

**`.github/actions/create-release/action.yml`:**

```yaml
# REMOVE broken manual steps:
- name: Create release package
  shell: bash
  run: |
    mkdir -p release-package
    cp tools/dxt/dist/quilt-mcp-*.dxt release-package/  # BROKEN
    cp tools/dxt/assets/README.md release-package/      # BROKEN

# REPLACE with working Makefile target:
- name: Create release package
  shell: bash
  run: make release-package  # Already creates proper bundle
```

### Step 4: Verification

1. **Test Makefile targets**: Ensure `make tag`, `make release-package` work
2. **Test GitHub Actions**: Verify CI/CD uses correct paths
3. **Test end-to-end**: Complete release workflow

## File Changes Required

### Makefile Updates (2 lines)

**`make.deploy`** lines 119, 123:

```makefile
# Before
@./tools/release.sh release
@./tools/release.sh dev

# After  
@./bin/release.sh release
@./bin/release.sh dev
```

### GitHub Actions Fixes (Multiple files)

**`.github/actions/create-release/action.yml`** - Remove broken manual logic:

```yaml
# DELETE broken steps (lines 32-42):
- name: Create release package
  shell: bash
  run: |
    mkdir -p release-package
    cp tools/dxt/dist/quilt-mcp-${{ steps.manifest.outputs.manifest_version }}.dxt release-package/
    cp tools/dxt/assets/README.md release-package/
    cp tools/dxt/assets/check-prereqs.sh release-package/
    cd release-package
    zip -r ../quilt-mcp-${{ inputs.tag-version }}.zip .

# REPLACE with working Makefile call:
- name: Create release package
  shell: bash
  run: make release-package
```

## Success Criteria

### Functional Requirements

- All scripts work from `bin/` location
- `make tag` and `make tag-dev` work correctly
- GitHub Actions use working Makefile targets instead of broken manual logic
- CI/CD creates proper release packages

### Organizational Requirements  

- Scripts in standard `bin/` directory
- No duplication between Makefiles and Actions
- Actions use correct paths (not non-existent `tools/dxt/`)
- Clean directory structure without empty `tools/`

## Risks and Mitigation

### Risk: Actions Still Broken After Fix

**Likelihood**: Medium  
**Impact**: High  
**Mitigation**: Test Actions in feature branch, verify `make release-package` works locally first

### Risk: Missing Release Assets

**Likelihood**: Low  
**Impact**: Medium  
**Mitigation**: Verify `make release-package` includes all required files before fixing Actions

## Timeline

**Total Duration**: 45 minutes

### Phase 3A: Script Migration (15 minutes)

- Create `bin/` directory
- Move 4 scripts, rename `check-env.sh` → `test-prereqs.sh`
- Update `make.deploy` references

### Phase 3B: Fix GitHub Actions (20 minutes)

- Remove broken manual logic from `create-release` action
- Replace with `make release-package` call
- Test that Makefile target works locally

### Phase 3C: Validation (10 minutes)

- Test `make tag` and `make tag-dev`
- Verify Actions syntax is correct
- Commit changes with clear message

## Critical Outcome

After Phase 3:

- **GitHub Actions work** - No more broken `tools/dxt/` references
- **No duplication** - Actions use Makefile targets instead of reimplementing logic
- **Standard organization** - Scripts in `bin/`, proper separation of concerns
- **Maintainable CI/CD** - Single source of truth for build logic

This fixes the broken state left by Phase 2 and establishes proper CI/CD hygiene.

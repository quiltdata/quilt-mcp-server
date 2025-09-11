# Release Workflow Simplification

## Problem Statement

The current tag push workflow creates multiple invocations and complexity:

1. **Local release script** (`bin/release.sh`) creates and pushes tags
2. **GitHub Actions CI** (`ci.yml`) triggers on tag push and runs full build/release pipeline
3. **Multiple Makefile targets** with overlapping functionality

This leads to:
- Confusion about which command to use
- Redundant build processes
- Multiple points of failure
- Unclear separation of concerns

## Current State Analysis

### Release Commands Available
- `make release` → calls `bin/release.sh release` 
- `make release-dev` → calls `bin/release.sh dev`
- `make release-patch/minor/major` → bump version + create release
- `make release-local` → full local build without pushing

### What Happens on Tag Push
1. Local script creates tag with `git tag -a` and pushes with `git push origin`
2. GitHub Actions CI workflow triggers on `refs/tags/v*`
3. CI runs tests then triggers `build-and-release` job
4. `create-release` action builds DXT package and creates GitHub release

### The Problem
The tag push triggers both local completion messages AND GitHub Actions, creating the impression of "multiple invocations" when really it's:
- Local script completing its job (create/push tag)
- GitHub Actions starting its job (build/release)

## Proposed Solution

### Simplified Command Structure

**Single-Purpose Commands:**
- `make release` - Create and push release tag (GitHub Actions handles build/release)
- `make release-dev` - Create and push dev tag (GitHub Actions handles build/release)  
- `make release-local` - Full local build and validation (no push, no GitHub release)

**Version Bump + Release (Convenience):**
- `make release-patch` - Bump patch, commit, push tag
- `make release-minor` - Bump minor, commit, push tag  
- `make release-major` - Bump major, commit, push tag

### Clear Separation of Concerns

1. **Local Development:** `make release-local`
   - Build, test, validate DXT package locally
   - Create release bundle
   - No git operations, no GitHub releases

2. **Release Creation:** `make release` / `make release-dev`
   - Create and push git tags only
   - GitHub Actions handles all building and release creation
   - Clear feedback about what will happen next

3. **Convenience Workflows:** `make release-patch/minor/major`
   - Version bump + commit + tag push
   - Complete workflow for common release scenarios

### Improved User Experience

**Clear Messaging:**
```bash
$ make release
🏷️  Creating and pushing release tag v0.5.10...
✅ Tag v0.5.10 created and pushed
🚀 GitHub Actions will build and create the release
📦 Release will be available at: https://github.com/user/repo/releases/tag/v0.5.10
```

**DRY_RUN Support:**
```bash  
$ DRY_RUN=1 make release
🔍 DRY RUN: Would create release tag v0.5.10
🚀 Would trigger GitHub Actions to build and publish DXT package
📦 Release would be available at: https://github.com/user/repo/releases/tag/v0.5.10
```

## Implementation Plan

### Phase 1: Update Documentation and Messaging
- Improve Makefile target descriptions
- Update release script output messages
- Clarify what each command does

### Phase 2: Streamline Makefile Targets
- Remove redundant intermediate targets
- Consolidate related functionality
- Ensure consistent naming and behavior

### Phase 3: Enhanced User Guidance
- Better error messages when prerequisites are missing
- Clear next-step instructions after each command
- Consistent dry-run support across all targets

## Success Criteria

1. **Clear Command Purpose:** Each make target has a single, well-defined purpose
2. **No Redundant Builds:** Local and CI builds serve different purposes and don't duplicate work
3. **Predictable Behavior:** Users know exactly what will happen when they run a command
4. **Good Error Handling:** Clear messages when things go wrong
5. **Consistent Interface:** All release commands support dry-run mode

## Files to Modify

1. `make.deploy` - Update release targets and messaging
2. `bin/release.sh` - Improve output messages and user guidance
3. `Makefile` - Update help text and target descriptions
4. `CLAUDE.md` - Document the simplified workflow

## Backward Compatibility

All existing `make` commands will continue to work with the same behavior. This is purely a simplification and clarification effort, not a breaking change.
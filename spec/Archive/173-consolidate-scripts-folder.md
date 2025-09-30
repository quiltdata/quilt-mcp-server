<!-- markdownlint-disable MD013 -->
# Specification: Consolidate Scripts Folder

**Issue**: #173 - Consolidate scripts folder
**Branch**: `173-consolidate-scripts-folder`
**Created**: 2025-09-21
**Status**: Specification Complete

## Summary

Consolidate scattered scripts into a more organized structure to improve maintainability, discoverability, and consistency across the repository. This addresses the current fragmentation where scripts exist in multiple locations (`bin/`, `scripts/`, `scripts/test/`) with inconsistent organization.

## Problem Statement

### Current State Analysis

**Script Distribution:**

- `bin/`: Contains executable scripts (`release.sh`, `mcp-test.py`)
- `scripts/`: Contains utility Python scripts (`version-utils.py`, `coverage_analysis.py`)
- `scripts/test/`: Contains test files for scripts (`test_coverage_analysis.py`)

**Issues with Current Structure:**

1. **Inconsistent Organization**:  bin and scripts are the same thing
2. **Missing Scripts**: `scripts/check-env.sh` referenced in README is actually `bin/check-prereqs.sh`
3. **Naming*: 'scripts/test' instead of 'scripts/tests' as elsewhere.

### Impact on Development

- **Developer Confusion**: New contributors struggle to locate appropriate scripts
- **Maintenance Overhead**: Changes require updating multiple locations
- **Build Fragility**: Hardcoded paths create brittle build dependencies
- **Testing Complexity**: Script tests isolated from main test suites

## Solution Design

1. Move `bin/*` scripts into `./scripts`
   1. Update all references to bin/* scripts
   2. Test affected make targets
   3. Commit and push
2. Move 'scripts/test' to 'scripts/tests'
   1. Update and run `make test-scripts`
   2. Commit and push
3. Create PR
   1. Monitor every minute until complete
   2. Check for errors; address

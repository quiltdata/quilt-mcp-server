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

1. **Inconsistent Organization**: Related scripts scattered across multiple directories
2. **Unclear Purpose Hierarchy**: No clear distinction between different script categories
3. **Missing Scripts**: `scripts/check-env.sh` referenced in README but doesn't exist
4. **Build System Coupling**: Makefiles hardcode specific script paths
5. **Discovery Challenges**: Developers must know multiple locations to find scripts

### Impact on Development

- **Developer Confusion**: New contributors struggle to locate appropriate scripts
- **Maintenance Overhead**: Changes require updating multiple locations
- **Build Fragility**: Hardcoded paths create brittle build dependencies
- **Testing Complexity**: Script tests isolated from main test suites

## Solution Design

### Proposed Directory Structure

```text
scripts/
├── README.md                    # Scripts documentation and usage guide
├── build/                       # Build and deployment automation
│   ├── release.sh              # Release management (from bin/)
│   ├── version-utils.py        # Version extraction (existing)
│   └── coverage-analysis.py    # Coverage reporting (existing)
├── dev/                        # Development and testing utilities
│   ├── mcp-test.py             # MCP endpoint testing (from bin/)
│   ├── check-env.sh            # Environment validation (new - was missing)
│   └── test-runner.py          # Test orchestration (potential future addition)
├── deployment/                 # Deployment-specific scripts (future)
│   └── .gitkeep                # Placeholder for future deployment scripts
└── tests/                      # Test files for scripts (renamed from test/)
    ├── test_coverage_analysis.py  # Coverage analysis tests
    ├── test_version_utils.py      # Version utilities tests (new)
    ├── test_mcp_test.py           # MCP test tool tests (new)
    └── fixtures/                  # Test fixtures
        └── sample-coverage.xml    # Sample data for testing
```

### Design Principles

1. **Purpose-Based Organization**: Group scripts by their primary function
2. **Clear Naming**: Directory names clearly indicate script purpose
3. **Consistent Structure**: Parallel structure for scripts and their tests
4. **Backward Compatibility**: Maintain existing script functionality
5. **Documentation-First**: Include comprehensive README for script discovery

### Migration Strategy

#### Phase 1: Structure Creation

- Create new directory structure with README documentation
- Add missing `check-env.sh` script referenced in project README

#### Phase 2: Script Migration

- Move scripts to new locations with git mv to preserve history
- Maintain original files as symlinks during transition period
- Update script shebangs and internal paths if needed

#### Phase 3: Build System Updates

- Update Makefile references to use new script locations
- Add fallback logic to check both old and new locations during transition
- Update any GitHub Actions that reference script paths

#### Phase 4: Documentation Updates

- Update README.md references to new script locations
- Update CLAUDE.md with new script organization
- Add scripts/README.md with comprehensive usage guide

#### Phase 5: Cleanup

- Remove symlinks after verification period
- Clean up empty directories
- Update .gitignore if needed

## Implementation Requirements

### Functional Requirements

#### FR-1: Script Preservation

- All existing scripts must maintain identical functionality
- No changes to command-line interfaces or expected behavior
- Preserve git history during moves

#### FR-2: Build System Compatibility

- All Makefile targets must continue to work without modification
- GitHub Actions must continue to work with new paths
- Local development workflows must remain unaffected

#### FR-3: Documentation Completeness

- README.md must be updated with new script locations
- New scripts/README.md must document all scripts and usage
- CLAUDE.md must reflect new organization patterns

#### FR-4: Test Coverage

- All moved scripts must retain existing test coverage
- New test files must be created for scripts without existing tests
- Test execution must work from new locations

### Non-Functional Requirements

#### NFR-1: Backward Compatibility

- Transition period with symlinks to prevent breakage
- Clear deprecation notices for old paths
- Migration guide for external consumers

#### NFR-2: Maintainability

- Clear separation of concerns between script categories
- Consistent naming and structure patterns
- Comprehensive documentation for future modifications

#### NFR-3: Discoverability

- Central README with script inventory and usage examples
- Clear directory naming indicating script purpose
- Integration with existing help system (make help)

## Testing Strategy

### Test Categories

**Unit Tests:**

- Test each script's core functionality in isolation
- Mock external dependencies (git, AWS, file system)
- Validate command-line argument parsing and error handling

**Integration Tests:**

- Test script execution from new locations
- Verify Makefile integration works correctly
- Test script interactions with build system

**System Tests:**

- End-to-end workflow testing with consolidated structure
- GitHub Actions compatibility verification
- Local development environment testing

**Backward Compatibility Tests:**

- Verify symlinks redirect correctly during transition
- Test that old documentation examples still work
- Validate that external tools can find scripts

### BDD Test Scenarios

```gherkin
Feature: Scripts Consolidation
  As a developer
  I want scripts to be organized logically
  So that I can easily find and use the tools I need

  Scenario: Developer discovers build scripts
    Given I am working on the project
    When I look in the scripts/build directory
    Then I should find release.sh, version-utils.py, and coverage-analysis.py
    And each script should have clear documentation

  Scenario: Makefile continues to work
    Given scripts have been moved to new locations
    When I run "make release"
    Then the build should complete successfully
    And it should use scripts from the new locations

  Scenario: Backward compatibility during transition
    Given symlinks exist for old script locations
    When I run a script using the old path
    Then it should execute successfully
    And display a deprecation notice
```

## Risk Assessment

### High Risk

- **Build System Breakage**: Incorrect Makefile updates could break CI/CD
  - *Mitigation*: Comprehensive testing in feature branch, symlink transition period

### Medium Risk

- **External Tool Dependencies**: Third-party tools may hardcode old paths
  - *Mitigation*: Gradual transition with symlinks, clear communication

### Low Risk

- **Developer Confusion**: Temporary confusion during transition period
  - *Mitigation*: Clear documentation, migration guide, team communication

## Success Criteria

1. **Functional Success**
   - All existing scripts work from new locations
   - All Makefile targets execute successfully
   - All tests pass with new structure

2. **Organizational Success**
   - Scripts logically grouped by purpose
   - Clear documentation for all scripts
   - Consistent naming and structure patterns

3. **Developer Experience Success**
   - New developers can easily find relevant scripts
   - Script purposes are clear from directory structure
   - Documentation provides clear usage examples

## Migration Timeline

### Week 1: Specification and Testing

- Complete specification (this document)
- Write BDD tests for new structure
- Create test fixtures and validation scripts

### Week 2: Implementation

- Create new directory structure
- Move scripts with git mv to preserve history
- Create symlinks for backward compatibility
- Update Makefiles to use new paths

### Week 3: Documentation and Validation

- Update README.md and create scripts/README.md
- Run comprehensive test suite
- Validate all make targets work correctly
- Test GitHub Actions with new structure

### Week 4: Cleanup and Finalization

- Remove symlinks after validation period
- Clean up empty directories
- Update CLAUDE.md with learnings
- Announce completion to team

## Future Considerations

### Script Organization Evolution

- Consider adding `scripts/maintenance/` for database/cleanup scripts
- Potential `scripts/monitoring/` for operational scripts
- Integration with future automation tools

### Tool Integration

- Consider adding script discovery tools
- Potential integration with IDE tooling
- Enhanced make help system with script documentation

### Documentation Automation

- Auto-generate script documentation
- Integration with existing doc generation
- Version-controlled script metadata

---

**Specification Status**: ✅ Complete
**Next Phase**: BDD Test Creation
**Estimated Effort**: 2-3 days
**Dependencies**: None
**Stakeholders**: Development Team, CI/CD Pipeline

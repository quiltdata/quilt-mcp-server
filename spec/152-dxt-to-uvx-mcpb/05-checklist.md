<!-- markdownlint-disable MD013 MD024 -->
# Issue #152: MCPB Implementation Checklist

## Reference Context

**Source**: [04-mcpb-only-spec.md](./04-mcpb-only-spec.md)
**GitHub Issue**: #152
**Branch**: `152-dxt-to-uvx-mcpb`

This checklist tracks the remaining tasks for transitioning from DXT to MCPB format based on the specifications.

## Phase 1: Package Publishing Prerequisites

DONE

## Phase 2: MCPB Packaging Tool Integration

### Build System Updates

- [x] Create `make mcpb` target in Makefile
- [ ] Remove `make dxt` target (preserved for backward compatibility)
- [x] Update dxt references in scripts/release.sh for MCPB
- [x] Update `make release-zip` to include `.mcpb` file
- [ ] Remove DXT-specific build targets and dependencies (preserved for transition)

## Phase 3: Build Pipeline Simplification

### Remove File Copying Infrastructure

- [x] Eliminate `src/deploy/bootstrap.py` (already removed in Phase 2)
- [x] Clean up `build/` directory structure requirements
- [x] Remove marker files (.assets-copied, .app-copied, .deps-installed) (already gone)

### Makefile Cleanup

- [x] Remove `$(ASSETS_MARKER)` targets (commented out)
- [x] Remove `$(APP_MARKER)` targets (commented out)
- [x] Remove `$(DEPS_MARKER)` targets (commented out)
- [x] Simplify `deploy-build` target (already MCPB-focused)
- [x] Update `clean` targets to remove MCPB artifacts

### PyProject.toml Updates

- [x] Remove `[tool.dxt]` configuration section (commented out)
- [x] Ensure `[project.scripts]` section is correct for UVX (verified)
- [x] Verify all dependencies are in `[project.dependencies]` (verified)
- [x] Remove any DXT-specific build configurations (all commented)

## Phase 4: Testing and Validation

### MCPB Package Validation

- [ ] Create `make mcpb-validate` target
- [ ] Test MCPB package structure validation
- [ ] Verify manifest.json is correctly embedded
- [ ] Validate icon and documentation are included
- [ ] Test package can be loaded by Claude Desktop

### Integration Testing

- [ ] Test MCPB installation in Claude Desktop
- [ ] Verify UVX execution from Claude Desktop
- [ ] Confirm environment variables are properly set
- [ ] Test AWS credentials pass-through
- [ ] Validate user configuration dialog works

### End-to-End Testing

- [ ] Test complete workflow: build → package → install → run
- [ ] Verify all MCP tools are accessible
- [ ] Test with different catalog configurations
- [ ] Validate error handling and logging
- [ ] Confirm performance meets requirements

## Phase 5: Documentation and Migration

### Documentation Updates

- [x] Update `src/deploy/README.md` for MCPB
- [x] Update `src/deploy/check-mcpb.sh` script
- [ ] Update main `README.md` installation instructions
- [ ] Create migration guide from DXT to MCPB
- [ ] Update troubleshooting documentation

### User Communication

- [ ] Create release notes for MCPB transition
- [ ] Document breaking changes
- [ ] Provide upgrade instructions
- [ ] Create FAQ for common migration issues

### CI/CD Updates

- [ ] Update GitHub Actions workflows for MCPB
- [ ] Remove DXT build steps
- [ ] Add MCPB validation to CI pipeline
- [ ] Update release workflow for MCPB artifacts

## Phase 6: Cleanup and Deprecation

### Remove Obsolete Files

- [ ] Delete unused bootstrap scripts
- [ ] Remove DXT-specific configuration files
- [ ] Clean up obsolete build artifacts
- [ ] Archive DXT-related documentation

### Code Cleanup

- [ ] Remove DXT references from codebase
- [ ] Update comments and docstrings
- [ ] Remove obsolete build functions
- [ ] Clean up unused imports and dependencies

## Success Criteria Validation

### Functional Requirements

- [ ] MCPB package successfully created
- [ ] Package installs in Claude Desktop
- [ ] UVX execution works correctly
- [ ] All MCP tools remain functional
- [ ] User configuration preserved

### Quality Metrics

- [ ] All tests passing
- [ ] Documentation complete

## Risk Mitigation Tracking

### Critical Risks

- [ ] MCPB tool availability confirmed
- [ ] Claude Desktop compatibility verified
- [ ] PyPI package publishing tested
- [ ] Rollback plan documented

### Migration Risks

- [ ] Parallel DXT support maintained during transition
- [ ] User communication plan executed
- [ ] Support documentation prepared
- [ ] Fallback instructions available

## Notes

- This checklist should be updated as tasks are completed
- Each phase should be completed and tested before moving to the next
- Critical path items are package publishing and MCPB tool availability
- Maintain backward compatibility during transition period

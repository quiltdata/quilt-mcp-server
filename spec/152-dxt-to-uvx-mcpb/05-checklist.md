<!-- markdownlint-disable MD013 MD024 -->
# Issue #152: MCPB Implementation Checklist

## Reference Context

**Source**: [04-mcpb-only-spec.md](./04-mcpb-only-spec.md)
**GitHub Issue**: #152
**Branch**: `152-dxt-to-uvx-mcpb`

This checklist tracks the remaining tasks for transitioning from DXT to MCPB format based on the specifications.

## Phase 1: Package Publishing Prerequisites

### PyPI/TestPyPI Publishing
- [ ] Verify `quilt-mcp` package name availability on PyPI
- [ ] Test package installation with `pip install quilt-mcp`
- [ ] Verify console script `quilt-mcp` works correctly
- [ ] Test UVX execution: `uvx quilt-mcp --version`
- [ ] Confirm package runs with proper MCP stdio transport

### Console Script Validation
- [ ] Verify `src/main.py` entry point works as console script
- [ ] Test that `quilt-mcp` command launches MCP server correctly
- [ ] Validate stdio transport mode is properly configured
- [ ] Ensure no path manipulation is needed (unlike DXT bootstrap)

## Phase 2: MCPB Packaging Tool Integration

### Tool Discovery and Integration
- [ ] Research MCPB packaging tool availability
- [ ] Document MCPB tool installation process
- [ ] Create test MCPB package manually if tool not available
- [ ] Validate MCPB package structure matches specification

### Build System Updates
- [ ] Create `make mcpb` target in Makefile
- [ ] Remove or deprecate `make dxt` target
- [ ] Update `make release-zip` to include `.mcpb` file
- [ ] Remove DXT-specific build targets and dependencies

### Manifest Processing
- [x] Update `manifest.json.j2` to MCPB format
- [ ] Test version substitution still works
- [ ] Validate manifest schema against MCPB requirements
- [ ] Ensure all required MCPB metadata fields are present

## Phase 3: Build Pipeline Simplification

### Remove File Copying Infrastructure
- [ ] Eliminate `src/deploy/bootstrap.py` (no longer needed)
- [ ] Remove `src/deploy/dxt_main.py` (replaced by UVX)
- [ ] Delete `src/deploy/requirements.txt` (redundant with pyproject.toml)
- [ ] Clean up `build/` directory structure requirements
- [ ] Remove marker files (.assets-copied, .app-copied, .deps-installed)

### Makefile Cleanup
- [ ] Remove `$(ASSETS_MARKER)` targets
- [ ] Remove `$(APP_MARKER)` targets
- [ ] Remove `$(DEPS_MARKER)` targets
- [ ] Simplify `deploy-build` target
- [ ] Update `clean` targets to remove MCPB artifacts

### PyProject.toml Updates
- [ ] Remove `[tool.dxt]` configuration section
- [ ] Ensure `[project.scripts]` section is correct for UVX
- [ ] Verify all dependencies are in `[project.dependencies]`
- [ ] Remove any DXT-specific build configurations

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
- [ ] Build time reduced by >50%
- [ ] Package size reduced by >30%
- [ ] Zero file duplication
- [ ] All tests passing
- [ ] Documentation complete

### Performance Validation
- [ ] Startup time ≤2 seconds
- [ ] Memory usage comparable or better
- [ ] No regression in tool response times
- [ ] Efficient package loading

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
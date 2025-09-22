<!-- markdownlint-disable MD013 MD024 -->
# Specification: MCPB-Only Build System

## Reference Context

**Source**: [02-analysis.md](./02-analysis.md)
**GitHub Issue**: #152
**Branch**: `152-dxt-to-uvx-mcpb`

This specification defines the desired end state for transitioning from DXT to MCPB (MCP Bundle) format using UVX for package execution.

## Acceptance Criteria Reference

Based on requirements analysis, this specification addresses:

1. **Format Transition**: Change from `.dxt` to `.mcpb` file extension
2. **Execution Model**: Replace source code copying with `uvx quilt-mcp` package reference
3. **Build Simplification**: Eliminate file duplication and complex copying mechanisms
4. **Claude Desktop Compatibility**: Maintain seamless integration with Claude Desktop

## High-Level Architecture Specifications

### 1. MCPB Package Format Requirements

#### 1.1 File Structure Specification

The MCPB package shall contain:

1. **Manifest File**: JSON configuration with package metadata and execution instructions
2. **Asset Files**: Documentation, README, and configuration templates
3. **Package Reference**: UVX command specification instead of bundled source code

#### 1.2 Package Metadata Requirements

- **Package Name**: `quilt-mcp.mcpb`
- **Version Alignment**: MCPB version must match published PyPI package version
- **Repository Reference**: Correct GitHub repository URL
- **User Configuration Schema**: Preserved from current DXT implementation

#### 1.3 Execution Command Specification

The MCPB manifest shall specify:

```json
{
  "command": ["uvx", "quilt-mcp"],
  "environment": {
    "FASTMCP_TRANSPORT": "stdio",
    "PYTHONNOUSERSITE": "1"
  }
}
```

### 2. Build System Architecture Goals

#### 2.1 Elimination of File Copying

The build system shall:

1. **Remove Source Duplication**: No copying of `src/quilt_mcp/` directory
2. **Remove Dependency Duplication**: No separate `requirements.txt` file
3. **Remove Bootstrap Complexity**: No custom virtual environment creation
4. **Maintain Asset Processing**: Preserve template substitution and asset inclusion

#### 2.2 UVX Integration Requirements

1. **Package Availability**: Ensure `quilt-mcp` is published and accessible via PyPI/TestPyPI
2. **Console Script Validation**: Verify `uvx quilt-mcp` execution works correctly
3. **Version Synchronization**: Build system must validate PyPI package availability

#### 2.3 Build Pipeline Simplification

Target build process:

1. **Asset Preparation**: Process manifest templates and documentation
2. **Version Validation**: Verify PyPI package version availability
3. **MCPB Creation**: Package assets and manifest into `.mcpb` format
4. **Validation**: Test MCPB package integrity and execution

### 3. Integration Specifications

#### 3.1 Claude Desktop Compatibility

The MCPB format shall:

1. **Maintain User Experience**: Installation and configuration identical to current DXT
2. **Preserve Configuration**: All user configuration options remain available
3. **Support Updates**: Package updates through standard Claude Desktop mechanisms
4. **Error Handling**: Clear error messages for package resolution failures

#### 3.2 Makefile Integration

Build targets shall be updated:

1. **`make mcpb`**: Create MCPB package (replaces `make dxt`)
2. **`make mcpb-validate`**: Validate MCPB package integrity
3. **`make release-zip`**: Include `.mcpb` file in release bundle
4. **Cleanup Targets**: Remove DXT-specific build artifacts

### 4. Quality Gates and Validation Criteria

#### 4.1 Package Validation Requirements

1. **Format Compliance**: MCPB package structure validates against specification
2. **Execution Testing**: `uvx quilt-mcp` command executes successfully from MCPB
3. **Environment Verification**: Required environment variables are set correctly
4. **Asset Integrity**: All documentation and configuration files are present

#### 4.2 Integration Testing Requirements

1. **Claude Desktop Integration**: MCPB installs and runs in Claude Desktop environment
2. **User Configuration**: Configuration options work identically to DXT version
3. **Error Scenarios**: Graceful handling of PyPI package unavailability
4. **Update Process**: MCPB updates work through Claude Desktop mechanisms

#### 4.3 Performance Criteria

1. **Startup Time**: MCPB execution time comparable to or better than DXT
2. **Package Size**: MCPB package significantly smaller than DXT (no source bundling)
3. **Build Time**: MCPB build process faster than DXT (no file copying)

### 5. Success Criteria and Measurable Outcomes

#### 5.1 Functional Success Metrics

1. **Format Transition**: 100% replacement of `.dxt` with `.mcpb` in all documentation and build processes
2. **Execution Model**: Complete elimination of source code copying in favor of UVX package reference
3. **Build Simplification**: Removal of all file duplication mechanisms and bootstrap complexity
4. **Compatibility**: Zero regression in Claude Desktop integration functionality

#### 5.2 Quality Metrics

1. **Build Reliability**: MCPB build process succeeds consistently across environments
2. **Package Integrity**: All MCPB packages pass validation requirements
3. **User Experience**: Installation and configuration process unchanged from user perspective
4. **Documentation Accuracy**: All user-facing documentation reflects MCPB format

#### 5.3 Performance Improvements

1. **Package Size Reduction**: MCPB packages at least 50% smaller than equivalent DXT packages
2. **Build Speed**: MCPB build process at least 25% faster than DXT build
3. **Maintenance Overhead**: Elimination of duplicate dependency management

### 6. Technical Uncertainties and Risk Mitigation

#### 6.1 MCPB Tooling Availability

**Uncertainty**: MCPB packaging toolchain may not be fully available or documented

**Risk Mitigation Strategy**:

1. Research current MCPB tooling status and documentation
2. Identify alternative packaging approaches if official tooling unavailable
3. Plan fallback to interim solution maintaining UVX execution model

#### 6.2 Claude Desktop MCPB Support

**Uncertainty**: Claude Desktop may require updates to support MCPB format

**Risk Mitigation Strategy**:

1. Verify Claude Desktop MCPB compatibility requirements
2. Coordinate with Claude Desktop team on timeline and requirements
3. Plan phased rollout if compatibility updates needed

#### 6.3 PyPI Package Availability

**Uncertainty**: UVX execution depends on reliable PyPI package availability

**Risk Mitigation Strategy**:

1. Implement robust package version validation in build process
2. Establish clear error handling for package unavailability scenarios
3. Document PyPI publishing requirements and dependencies

#### 6.4 Configuration Migration

**Uncertainty**: User configurations may require migration for MCPB format

**Risk Mitigation Strategy**:

1. Design MCPB format to maintain configuration compatibility
2. Implement configuration migration tools if necessary
3. Provide clear migration documentation for users

### 7. Migration Strategy Specifications

#### 7.1 Parallel Operation Period

During transition:

1. **Dual Format Support**: Build system produces both DXT and MCPB packages
2. **Documentation Updates**: All references updated to prefer MCPB with DXT fallback
3. **Testing Coverage**: Both formats validated until DXT deprecation

#### 7.2 DXT Deprecation Plan

1. **Phase 1**: Introduce MCPB format alongside DXT
2. **Phase 2**: Make MCPB the default format with DXT option
3. **Phase 3**: Remove DXT build targets and documentation references
4. **Phase 4**: Clean up DXT-related code and assets

#### 7.3 User Communication Strategy

1. **Release Notes**: Clear communication about format transition benefits
2. **Migration Guide**: Step-by-step instructions for users updating packages
3. **Support Documentation**: Troubleshooting guide for MCPB-specific issues

## Architectural Goals Summary

This specification defines a fundamental shift from file-based bundling to package-reference architecture:

1. **Simplification**: Eliminate complex file copying and bootstrap mechanisms
2. **Standardization**: Leverage standard Python packaging and UVX execution
3. **Maintainability**: Remove duplicate dependency management and source copying
4. **Performance**: Reduce package size and build complexity
5. **Reliability**: Use established package management instead of custom solutions

The success of this transition depends on maintaining Claude Desktop compatibility while achieving significant improvements in build simplicity and package efficiency.

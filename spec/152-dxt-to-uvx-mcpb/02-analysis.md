<!-- markdownlint-disable MD013 MD024 -->
# Issue #152: UVX Analysis - Transition from DXT to UVX for MCP Build (MCPB)

## Reference Context

**Source**: [01-requirements.md](./01-requirements.md)
**GitHub Issue**: #152
**Branch**: `152-dxt-to-uvx-mcpb`

This analysis examines the current DXT build system and identifies gaps and challenges for transitioning to a UVX-based MCPB (MCP Bundle) approach.

## Current System Architecture

### 1. DXT Build System Components

#### 1.1 PyProject Configuration

- **Location**: `pyproject.toml` lines 111-114
- **Current Configuration**:

  ```toml
  [tool.dxt]
  bundle = "uv pip install --target build-dxt/build/lib --no-cache-dir --quiet ."
  test = "python build-dxt/build/dxt_main.py"
  pack = "npx @anthropic-ai/dxt pack build-dxt/build build-dxt/dist/quilt-mcp.dxt"
  ```

- **Status**: Uses obsolete directory paths (`build-dxt`) that have been consolidated to `build/`

#### 1.2 Build Pipeline (make.deploy)

- **Staging Directory**: `build/` (consolidated from `build-dxt`)
- **Output Directory**: `dist/`
- **Package Name**: `quilt-mcp.dxt`
- **Key Targets**:
  1. `deploy-build` - Prepares production build environment
  2. `dxt` - Creates DXT package via `npx @anthropic-ai/dxt pack`
  3. `dxt-validate` - Validates package integrity
  4. `release-zip` - Creates distribution bundle

#### 1.3 File Copying Mechanism

- **Assets Copying**: `src/deploy/*` → `build/` (via `$(ASSETS_MARKER)`)
- **Source Code Copying**: `src/quilt_mcp/**/*.py` → `build/quilt_mcp/` (via `$(APP_MARKER)`)
- **Dependencies Installation**: `uv pip install --target build/lib` (via `$(DEPS_MARKER)`)
- **Requirements File**: Duplicated dependencies in `src/deploy/requirements.txt`

### 2. Current Entry Points and Execution Model

#### 2.1 Console Scripts

- **Current Script**: `quilt-mcp = "src.main:main"` in `pyproject.toml` line 53
- **Main Entry Point**: `src/main.py` - Simple wrapper calling `quilt_mcp.utils.run_server()`

#### 2.2 DXT Execution Model

- **Bootstrap Script**: `src/deploy/bootstrap.py`
  - Creates virtual environment in `.venv`
  - Installs dependencies from `requirements.txt`
  - Launches `dxt_main.py` via `os.execv()`
- **DXT Main**: `src/deploy/dxt_main.py`
  - Adds `lib/` and current directory to `sys.path`
  - Forces `FASTMCP_TRANSPORT=stdio`
  - Calls `quilt_mcp.utils.run_server()`

#### 2.3 Manifest Configuration

- **Template**: `src/deploy/manifest.json.j2`
- **Entry Point**: `"bootstrap.py"`
- **Command**: `["python3", "${__dirname}/bootstrap.py"]`
- **Environment**: `{"PYTHONNOUSERSITE": "1"}`

### 3. Existing Code Idioms and Conventions

#### 3.1 Project Structure

- Source code in `src/quilt_mcp/`
- Build artifacts in `build/`
- Distribution in `dist/`
- Deployment assets in `src/deploy/`

#### 3.2 Build Patterns

- Incremental builds using marker files (`.assets-copied`, `.app-copied`, `.deps-installed`)
- Version templating via `sed` substitution
- Tool validation with `check-tools` target

#### 3.3 Python Packaging

- Uses `uv` for dependency management
- Supports `[project.scripts]` console scripts
- UV-based pip installation for bundling

## Current System Constraints and Limitations

### 1. Technical Debt Issues

#### 1.1 File Duplication

- **Dependencies**: Duplicated between `pyproject.toml` and `src/deploy/requirements.txt`
- **Source Code**: Entire `quilt_mcp` module copied to build directory
- **Maintenance Burden**: Changes require updates in multiple locations

#### 1.2 Build Complexity

- **Multi-stage Process**: Assets → App → Dependencies → Pack → Validate
- **Directory Management**: Complex path handling with marker files
- **Tool Dependencies**: Requires both `uv` and `npx/@anthropic-ai/dxt`

#### 1.3 Obsolete Configuration

- **PyProject DXT Config**: References non-existent `build-dxt` paths
- **URL Mismatch**: Manifest template contains incorrect repository URL (`ernest/fast-mcp-server`)

### 2. System Limitations

#### 2.1 Extension Approach

- **File System Dependency**: Relies on copying entire source tree
- **Size Inefficiency**: Bundles full application rather than referencing published package
- **Update Complexity**: Requires full rebuild for any source changes

#### 2.2 Virtual Environment Management

- **Bootstrap Complexity**: Custom venv creation and dependency installation
- **Runtime Overhead**: Environment setup on each launch
- **Path Manipulation**: Complex `sys.path` modifications in `dxt_main.py`

## Gaps Between Current State and Requirements

### 1. Extension Format Transition

#### 1.1 File Extension

- **Current**: `.dxt` (deprecated format)
- **Required**: `.mcpb` (new MCP Bundle format)
- **Impact**: Affects build targets, file naming, and user documentation

#### 1.2 Packaging Tool

- **Current**: `npx @anthropic-ai/dxt pack`
- **Required**: [New MCPB packaging approach (tool TBD)](https://github.com/anthropics/mcpb)

### 2. Execution Model Gap

#### 2.1 Source Distribution

- **Current**: Copies source code into bundle
- **Required**: Use `uvx quilt-mcp` to run published package
- **Challenge**: Requires published package availability and console script configuration

#### 2.2 Dependency Management

- **Current**: Custom virtual environment with pip installation
- **Required**: Leverage UVX's built-in package management
- **Benefit**: Eliminates bootstrap complexity and file copying

### 3. Console Script Requirements

#### 3.1 Current Script

- **Name**: `quilt-mcp`
- **Target**: `src.main:main`
- **Status**: Exists but may need adaptation for UVX usage

#### 3.2 Missing UVX Compatibility

- **UVX Requirement**: Package must be pip-installable with working console script
- **Current Status**: Console script exists but not tested with UVX
- **Gap**: No validation that `uvx quilt-mcp` works correctly

## Architectural Challenges and Design Considerations

### 1. Build System Transformation

#### 1.1 Target Removal Challenge

- **Complex Dependencies**: Current DXT targets deeply integrated with make.deploy
- **Incremental Build Logic**: Marker files and dependency tracking must be adapted
- **Validation Pipeline**: DXT validation needs replacement with MCPB equivalent

#### 1.2 Asset Management

- **Manifest Template**: Needs conversion from DXT to MCPB format
- **Asset Files**: README, scripts, and other deployment assets still needed
- **Version Substitution**: Template processing logic must be maintained

### 2. Execution Environment Challenges

#### 2.1 UVX Integration Points

- **Package Publishing**: Must ensure `quilt-mcp` is available on PyPI/TestPyPI
- **Version Synchronization**: MCPB version must align with published package version
- **Environment Variables**: UVX execution model may differ from current bootstrap approach

#### 2.2 Configuration Compatibility

- **Claude Desktop Integration**: Manifest format changes may affect Desktop integration
- **User Configuration**: Current user config schema must be preserved
- **Transport Configuration**: `FASTMCP_TRANSPORT=stdio` requirement must be maintained

### 3. Development Workflow Impact

#### 3.1 Testing and Validation

- **Local Testing**: Current `make dxt` workflow needs replacement
- **Integration Testing**: DXT validation targets need MCPB equivalents
- **CI/CD Pipeline**: GitHub Actions may need updates for new format

#### 3.2 Release Process

- **Package Publishing**: Must coordinate PyPI publishing with MCPB creation
- **Version Management**: Ensure consistency between PyPI package and MCPB versions
- **Distribution**: Release bundles must include new `.mcpb` format

## Current System Strengths to Preserve

### 1. Build Infrastructure

- **UV Integration**: Existing UV usage provides foundation for UVX transition
- **Incremental Builds**: Marker file approach is efficient for development
- **Version Management**: Automatic version injection from `pyproject.toml`

### 2. Configuration System

- **User Config Schema**: Well-defined configuration options in manifest
- **Environment Handling**: Proper environment variable management
- **Tool Validation**: Robust tool dependency checking

### 3. Release Pipeline

- **Validation Gates**: Comprehensive validation before packaging
- **Bundle Creation**: Complete release bundle with documentation
- **Version Coordination**: Integrated version management across components

## Analysis Summary

The transition from DXT to UVX MCPB represents a significant architectural shift from file-copying to package-reference approach. The current system has well-established patterns and infrastructure that can be adapted, but requires fundamental changes to:

1. **Eliminate file copying mechanisms** in favor of UVX package references
2. **Replace DXT tooling** with MCPB equivalents
3. **Simplify bootstrap process** by leveraging UVX's package management
4. **Maintain compatibility** with Claude Desktop integration requirements
5. **Preserve build quality gates** while adapting to new toolchain

The existing UV integration and console script configuration provide a solid foundation for UVX adoption, but the build system complexity and file duplication represent the primary technical debt that must be addressed during the transition.

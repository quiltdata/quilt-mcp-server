<!-- markdownlint-disable MD013 -->
# GitHub Actions Optimal Structure Specification (A02)

## Overview

This specification defines the optimal structure for GitHub Actions workflows in the Quilt MCP Server repository using a single consolidated workflow with conditional execution based on context.

## Architecture

### Branching Model

**Simple GitHub Flow:**

- Feature branches → main (via PR)
- Version tags → GitHub releases
- No staging/develop complexity

### Workflow Structure

**Single Workflow Approach:**

```tree
.github/
└── workflows/
    └── ci.yml                 # One workflow handles everything
```

**No composite actions needed** - all logic consolidated in one place for maximum simplicity and consistency.

## Single Workflow Design

### Workflow Name: `ci.yml`

**Purpose:** Handle all CI/CD operations based on trigger context

**Triggers:**

- **Pull Requests** → Run unit tests only
- **Push to main** → Run unit + integration tests
- **Version tags** → Run full tests + build DXT + create GitHub release

**Matrix Strategy:**

- **Python versions:** 3.11, 3.12, 3.13 (consistent across all test types)
- **Single runner:** ubuntu-latest (consistent environment)

### Conditional Execution Logic

**Unit Tests:**

- Always run on every trigger
- Fast feedback for all changes
- Matrix across all Python versions

**Integration Tests:**

- Run on main branch pushes
- Run on PRs with `test:integration` label
- Run on manual workflow dispatch
- Same Python matrix for consistency

**DXT Build & Release:**

- Only run on version tags (v*)
- Build DXT package using top-level Makefile
- Validate package before release
- Create GitHub release with DXT assets
- Generate release notes automatically

### Environment Consistency

**Standardized Setup:**

- Same uv installation across all operations
- Same Python installation method
- Same Node.js version when needed
- Same secret injection patterns

**Shared Caching:**

- Single cache strategy for all operations
- Consistent cache keys based on dependencies
- Optimal cache hit rates

**Unified Secret Access:**

- All AWS/Quilt secrets available to all operations
- Consistent environment variable names
- No duplication of secret configuration

## Configuration Standards

### Tool Versions

- **Python:** 3.11, 3.12, 3.13 (matrix)
- **Node.js:** 18 (when DXT CLI needed)
- **Package Manager:** uv everywhere
- **DXT CLI:** @anthropic-ai/dxt latest

### Secret Requirements

**Repository Secrets:**

- AWS_ACCESS_KEY_ID
- AWS_SECRET_ACCESS_KEY  
- AWS_DEFAULT_REGION
- QUILT_CATALOG_URL
- QUILT_DEFAULT_BUCKET
- QUILT_TEST_PACKAGE
- QUILT_TEST_ENTRY
- QUILT_INTEGRATION_BUCKET
- QUILT_READ_POLICY_ARN
- CDK_DEFAULT_ACCOUNT
- CDK_DEFAULT_REGION

### Performance Optimizations

**Caching Strategy:**

- uv cache: `~/.cache/uv`
- npm cache: `~/.npm` (when needed)
- Cache key based on `pyproject.toml` hash

**Parallel Execution:**

- Matrix builds run in parallel
- No artificial job dependencies
- Fast failure propagation

**Timeout Management:**

- Appropriate timeouts for each operation type
- Overall job timeout to prevent hanging

## Benefits

### Maximum Simplicity

- **1 workflow** instead of 5
- **0 composite actions** needed
- **Single file** to maintain
- **Consistent environment** across all operations

### Improved Performance

- **No workflow orchestration overhead**
- **Shared setup costs** across operations
- **Optimal caching** with single strategy
- **Fast feedback** with conditional execution

### Enhanced Consistency

- **Same Python matrix** for all test types
- **Same environment setup** for all operations
- **Same secret access** patterns
- **Same caching** strategy throughout

### Reduced Complexity

- **No composite action debugging**
- **No cross-workflow dependencies**
- **Single place** to update configurations
- **Clear conditional logic** based on triggers

## Operational Behavior

### Pull Request Flow

1. Checkout code
2. Setup environment (uv, Python matrix)
3. Install dependencies
4. Run unit tests with coverage
5. Report results

### Main Branch Flow

1. Checkout code
2. Setup environment (uv, Python matrix)
3. Install dependencies
4. Run unit tests with coverage
5. Run integration tests with AWS
6. Report results

### Release Flow (Version Tags)

1. Checkout code
2. Setup environment (uv, Python, Node.js)
3. Install dependencies + DXT CLI
4. Run full test suite (unit + integration)
5. Build DXT package
6. Validate DXT package
7. Create GitHub release with assets
8. Generate release notes

### Manual Integration Testing

- Developers can add `test:integration` label to PR
- Triggers integration tests on demand
- Same as main branch flow but on PR

## Migration Benefits

### Elimination of Complexity

- Remove 4 obsolete/broken workflows
- No composite actions to maintain
- No workflow orchestration logic
- Single source of truth for all CI/CD

### Improved Maintainability  

- One file to update for version changes
- Consistent behavior across all contexts
- Easier debugging and troubleshooting
- Clear conditional logic

### Enhanced Performance

- Reduced GitHub Actions overhead
- Optimal resource utilization
- Faster feedback cycles
- Better cache utilization

### Simplified Mental Model

- One workflow does everything
- Context determines what runs
- No complex dependencies
- Clear trigger → action mapping

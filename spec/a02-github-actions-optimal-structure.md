<!-- markdownlint-disable MD013 -->
# GitHub Actions Optimal Structure Specification (A02)

## Overview

This specification defines an optimal structure for ALL GitHub Actions workflows in the Quilt MCP Server repository, eliminating duplication, inconsistencies, and technical debt while maintaining security and functionality.

## Current State Analysis

### Existing Workflows

- **test.yml** - Unit tests (uv, Python 3.11-3.13, AWS secrets)
- **integration-test.yml** - Integration tests (uv, conditional execution)
- **dxt.yml** - DXT build/release (tools/dxt, correct paths)
- **staging-deploy.yml** - Staging deployment (pip, build-dxt paths ❌, complex)
- **nightly-build.yml** - PR automation (simple)

### Critical Issues Identified

1. **Path Inconsistencies**: `staging-deploy.yml` uses obsolete `build-dxt` paths
2. **Tool Fragmentation**: Mix of `uv` and `pip` across workflows
3. **Secret Duplication**: AWS/Quilt configuration repeated 15+ times
4. **Setup Duplication**: Python/Node.js setup repeated in every workflow
5. **Version Drift**: Different Python versions tested in different contexts
6. **Missing Modularity**: No reusable components or composite actions
7. **Complex Dependencies**: Staging workflow has brittle job dependency chains

## Optimal Architecture

### Design Principles

1. **Single Source of Truth**: One place for tool versions, secrets, configurations
2. **Modular Reusability**: Composite actions for common operations
3. **Consistent Tooling**: Standardize on `uv` for Python, specific Node.js version
4. **Fail-Fast Design**: Quick feedback with early validation steps
5. **Security-First**: Centralized secret management with minimal exposure
6. **Maintainability**: Clear naming, documentation, and structure

### Proposed Structure

```tree
.github/
├── actions/                    # Composite Actions (Reusable Components)
│   ├── setup-environment/     # Python + Node.js + uv setup
│   ├── build-dxt/             # DXT building and validation
│   ├── run-tests/             # Test execution with configurable scope
│   └── deploy-artifacts/      # Artifact preparation and upload
├── workflows/
│   ├── 01-validate.yml        # Fast validation (linting, basic checks)
│   ├── 02-test.yml            # Unit tests across Python versions
│   ├── 03-integration.yml     # Integration tests with real AWS
│   ├── 04-build.yml           # DXT building and artifact creation
│   ├── 05-staging.yml         # Staging deployment pipeline
│   ├── 06-release.yml         # Production release automation
│   └── 99-maintenance.yml     # Nightly/maintenance tasks
└── config/
    └── shared-config.yml      # Centralized configuration
```

### Reusable Components

#### 1. Environment Setup (`actions/setup-environment`)

```yaml
# Standardized Python + Node.js + uv setup
inputs:
  python-version:
    default: '3.11'
  node-version:
    default: '18'
  install-dxt-cli:
    default: 'false'
```

#### 2. DXT Operations (`actions/build-dxt`)

```yaml
# Standardized DXT building, testing, validation
inputs:
  operation: # build, test, validate, release
  version:
    required: false
runs:
  using: 'composite'
  steps:
    - name: Build DXT
      run: make dxt  # Use top-level Makefile targets
```

#### 3. Test Execution (`actions/run-tests`)

```yaml
# Configurable test runner
inputs:
  test-type: # unit, integration, aws, search, all
  coverage-required:
    default: 'true'
  timeout-minutes:
    default: '20'
```

### Centralized Configuration

#### Environment Matrix

```yaml
# shared-config.yml
python-versions:
  unit-tests: ["3.11", "3.12", "3.13"]
  integration-tests: ["3.11", "3.12"]
  production: "3.11"

node-version: "18"

timeouts:
  checkout: 2
  setup: 5
  unit-tests: 20
  integration-tests: 30
  dxt-build: 15
  staging-deploy: 45
```

#### Secret Configuration

```yaml
# Centralized secret mapping
aws-secrets:
  - AWS_ACCESS_KEY_ID
  - AWS_SECRET_ACCESS_KEY
  - AWS_DEFAULT_REGION

quilt-secrets:
  - QUILT_CATALOG_URL
  - QUILT_DEFAULT_BUCKET
  - QUILT_TEST_PACKAGE
  - QUILT_TEST_ENTRY

integration-secrets:
  - QUILT_READ_POLICY_ARN
  - CDK_DEFAULT_ACCOUNT
  - CDK_DEFAULT_REGION
  - QUILT_INTEGRATION_BUCKET
```

## Workflow Specifications

### 1. Validation Workflow (`01-validate.yml`)

**Purpose**: Fast feedback on basic issues

- **Triggers**: Every push/PR
- **Duration**: <2 minutes
- **Operations**:
  - Code formatting (ruff, prettier)
  - Import validation
  - README command testing
  - Makefile target validation
  - Path consistency checks

### 2. Test Workflow (`02-test.yml`)

**Purpose**: Comprehensive unit testing

- **Triggers**: Every push/PR
- **Matrix**: Python 3.11, 3.12, 3.13
- **Operations**:
  - Unit tests with mocks
  - Coverage reporting (≥85%)
  - AWS integration tests (with secrets)
  - Performance regression detection

### 3. Integration Workflow (`03-integration.yml`)

**Purpose**: Real AWS environment testing

- **Triggers**: main/develop push, PR labels, manual
- **Matrix**: Python 3.11, 3.12
- **Operations**:
  - Full AWS service integration
  - Search functionality testing
  - Permission validation
  - Cross-service compatibility

### 4. Build Workflow (`04-build.yml`)

**Purpose**: DXT package creation and validation

- **Triggers**: After tests pass, tags, manual
- **Operations**:
  - DXT package building (`make dxt`)
  - Package validation (`make validate-dxt`)
  - Cross-platform compatibility testing
  - Artifact upload with retention policies

### 5. Staging Workflow (`05-staging.yml`)

**Purpose**: Full staging environment deployment

- **Triggers**: staging branch push, staging PRs
- **Operations**:
  - Branch source validation (develop → staging only)
  - Full test suite execution
  - DXT package deployment testing
  - Performance benchmarking
  - Staging environment provisioning

### 6. Release Workflow (`06-release.yml`)

**Purpose**: Production release automation

- **Triggers**: Version tags (v*)
- **Operations**:
  - Release candidate validation
  - DXT package signing
  - GitHub release creation
  - Documentation deployment
  - Changelog generation

### 7. Maintenance Workflow (`99-maintenance.yml`)

**Purpose**: Automated maintenance tasks

- **Triggers**: Scheduled, manual
- **Operations**:
  - Dependency updates
  - Nightly builds
  - PR automation (develop → staging)
  - Artifact cleanup
  - Performance monitoring

## Security & Secrets Management

### Secret Organization

```yaml
# Hierarchical secret access
Repository Secrets:
  - Production secrets (releases only)
  - Integration secrets (integration tests)
  - AWS credentials (all workflows)
  - Quilt configuration (all workflows)

Environment Secrets:
  staging:
    - Staging-specific overrides
    - Deployment credentials
  
  production:
    - Production deployment keys
    - Release signing certificates
```

### Secret Usage Patterns

```yaml
# Standardized secret injection
env:
  # AWS Configuration (from composite action)
  AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
  AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
  AWS_DEFAULT_REGION: ${{ secrets.AWS_DEFAULT_REGION || 'us-east-1' }}
  
  # Quilt Configuration (from composite action)  
  QUILT_CATALOG_URL: ${{ secrets.QUILT_CATALOG_URL }}
  QUILT_DEFAULT_BUCKET: ${{ secrets.QUILT_DEFAULT_BUCKET }}
  QUILT_TEST_PACKAGE: ${{ secrets.QUILT_TEST_PACKAGE }}
  QUILT_TEST_ENTRY: ${{ secrets.QUILT_TEST_ENTRY }}
```

## Error Handling & Monitoring

### Failure Strategies

- **Fail-Fast**: Validation failures prevent later stages
- **Parallel Execution**: Independent jobs run concurrently
- **Conditional Dependencies**: Smart job dependency management
- **Graceful Degradation**: Partial failures don't block entire pipeline

### Monitoring & Notifications

```yaml
# Standardized notification patterns
- name: Notify on failure
  if: failure()
  uses: ./.github/actions/notify-team
  with:
    status: failure
    workflow: ${{ github.workflow }}
    job: ${{ github.job }}
    pr-number: ${{ github.event.pull_request.number }}
```

## Performance Optimization

### Caching Strategy

```yaml
# Consistent caching across workflows
- name: Cache Dependencies
  uses: actions/cache@v4
  with:
    path: |
      ~/.cache/uv
      ~/.cache/pip
      ~/.npm
    key: ${{ runner.os }}-deps-${{ hashFiles('**/pyproject.toml', '**/package-lock.json') }}
```

### Artifact Management

```yaml
# Standardized artifact handling
retention-policies:
  test-results: 7 days
  coverage-reports: 30 days
  dxt-packages: 90 days
  staging-artifacts: 14 days
  release-artifacts: permanent
```

### Parallel Execution

```yaml
# Optimized job dependencies
jobs:
  validate: # Always first (2 min)
  
  test: # After validate (15 min)
    needs: [validate]
    
  integration: # Parallel with test (20 min)
    needs: [validate]
    
  build-dxt: # After test passes (10 min)
    needs: [test]
    
  staging: # After all pass (30 min)
    needs: [test, integration, build-dxt]
```

## Migration Benefits

### Immediate Improvements

- **Eliminate Failures**: Fix obsolete `build-dxt` path references
- **Reduce Duplication**: 70% reduction in repeated setup code
- **Improve Consistency**: Standardized tool versions across all workflows
- **Enhanced Security**: Centralized secret management
- **Faster Feedback**: Optimized job dependencies and caching

### Long-term Benefits

- **Maintainability**: Single place to update Python versions, dependencies
- **Scalability**: Easy to add new workflows using existing components
- **Reliability**: Consistent patterns reduce configuration errors
- **Observability**: Standardized monitoring and alerting
- **Developer Experience**: Predictable workflow behavior and clear feedback

## Implementation Priority

### Phase 1: Critical Fixes (Immediate)

1. Fix `staging-deploy.yml` build-dxt paths → tools/dxt
2. Standardize on `uv` across all workflows
3. Create shared environment setup composite action

### Phase 2: Structure Optimization (Week 1)

1. Create reusable DXT build composite action
2. Implement centralized configuration
3. Optimize job dependencies and caching

### Phase 3: Advanced Features (Week 2)

1. Enhanced monitoring and notifications
2. Advanced artifact management
3. Performance optimization and parallel execution

### Phase 4: Documentation & Training (Week 3)

1. Update all workflow documentation
2. Create troubleshooting guides
3. Team training on new structure

## Success Metrics

### Quantitative Goals

- **Build Time**: Reduce average workflow duration by 30%
- **Failure Rate**: Reduce workflow failures by 50% through better validation
- **Maintenance**: Reduce time to update dependencies/versions by 80%
- **Secret Management**: 100% centralized secret usage

### Qualitative Goals

- **Developer Experience**: Clear, predictable workflow behavior
- **Reliability**: Consistent success rates across all workflows
- **Security**: No exposed secrets or credential leakage
- **Maintainability**: Single source of truth for all configurations

## Risk Assessment

### High Risk

- **Breaking Changes**: Migration must maintain current functionality
- **Secret Migration**: Ensure no credential exposure during transition
- **Dependency Issues**: Potential conflicts between uv and pip during migration

### Mitigation Strategies

- **Gradual Migration**: Migrate one workflow at a time
- **Parallel Testing**: Run old and new workflows in parallel initially
- **Rollback Plan**: Maintain old workflows until new ones are validated
- **Comprehensive Testing**: Validate all scenarios before full migration

## Conclusion

The proposed optimal structure eliminates current technical debt, improves reliability, enhances security, and provides a scalable foundation for future workflow development. The modular design with reusable components will significantly reduce maintenance overhead while improving the developer experience.

Implementation should prioritize critical fixes first, then gradually migrate to the optimal structure while maintaining full functionality throughout the transition.

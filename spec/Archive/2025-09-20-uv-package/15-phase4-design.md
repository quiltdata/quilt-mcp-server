<!-- markdownlint-disable MD013 MD025 -->
# Phase 4: OIDC PyPI Publishing Design

## Overview

This specification defines the migration from password-based PyPI authentication to OIDC (OpenID Connect) trusted publishing for both PyPI and TestPyPI in the `create-release` GitHub Action.

## Current State Analysis

### Current Action Configuration (.github/actions/create-release/action.yml:20-25)

```yaml
- name: Publish to PyPI/TestPyPI
  uses: pypa/gh-action-pypi-publish@release/v1
  with:
    password: ${{ inputs.pypi-token }}
    repository-url: ${{ inputs.pypi-repository-url }}
    packages-dir: dist/
```

### Current Workflow Usage

**Production Release (push.yml:52-83)**

- Runs on production tags (`v*` excluding `v*-dev-*`)
- Has `id-token: write` permission (line 58)
- Uses create-release action without PyPI parameters

**Development Release (pr.yml:59-96)**

- Runs on development tags (`v*-dev-*`)
- Missing `id-token: write` permission
- Uses create-release action without PyPI parameters

## Problem Statement

1. **Security**: Password-based authentication requires storing sensitive tokens in GitHub secrets
2. **Missing PyPI Parameters**: Current action calls don't specify PyPI repository or tokens
3. **Missing Permissions**: Dev workflow lacks required OIDC permissions
4. **No Environment Separation**: Production and development publishing aren't properly segregated

## Design Requirements

### R1: OIDC Authentication

- Eliminate password-based authentication
- Use GitHub's OIDC provider for trusted publishing
- Configure separate trusted publishers for PyPI and TestPyPI

### R2: Environment Separation

- Production tags publish to PyPI
- Development tags publish to TestPyPI
- Proper GitHub Environment configuration with approval gates

### R3: Workflow Permissions

- Both workflows must have `id-token: write` permission
- Maintain existing `contents: write` for GitHub releases

### R4: Backward Compatibility

- Maintain existing action interface
- Preserve current tag-based triggering logic

## Proposed Solution

### 1. GitHub Environment Setup

**PyPI Environment** (Manual setup required):

- Name: `pypi`
- Protection rules: Manual approval required
- Trusted publisher configuration on PyPI.org

**TestPyPI Environment** (Manual setup required):

- Name: `testpypi`
- Protection rules: No approval required
- Trusted publisher configuration on test.pypi.org

### 2. Modified Action Interface

**Key Changes to .github/actions/create-release/action.yml:**

```yaml
# Add new input parameter
inputs:
  pypi-repository-url:
    description: 'PyPI repository URL (empty for PyPI, https://test.pypi.org/legacy/ for TestPyPI)'
    required: false
    default: ''

# Replace existing PyPI step (lines 20-25)
- name: Publish to PyPI/TestPyPI
  uses: pypa/gh-action-pypi-publish@release/v1
  with:
    repository-url: ${{ inputs.pypi-repository-url }}
    packages-dir: dist/
    # Remove: password: ${{ inputs.pypi-token }}
```

### 3. Updated Workflow Jobs

**Production Release Job (push.yml) - Key Changes:**

```yaml
prod-release:
  environment: pypi  # NEW: Use PyPI environment
  # permissions already include id-token: write

  steps:
    - name: Create production release
      uses: ./.github/actions/create-release
      with:
        tag-version: ${{ steps.version.outputs.tag_version }}
        # pypi-repository-url defaults to '' for PyPI
```

**Development Release Job (pr.yml) - Key Changes:**

```yaml
dev-release:
  environment: testpypi  # NEW: Use TestPyPI environment
  permissions:           # NEW: Add permissions block
    contents: write
    id-token: write

  steps:
    - name: Create dev release
      uses: ./.github/actions/create-release
      with:
        tag-version: ${{ steps.version.outputs.tag_version }}
        pypi-repository-url: https://test.pypi.org/legacy/  # NEW: TestPyPI URL
```

### 4. Trusted Publisher Configuration

**PyPI Configuration** (manual setup on pypi.org):

- Project name: `quilt-mcp`
- Owner: `quiltdata`
- Repository name: `quilt-mcp-server`
- Workflow filename: `push.yml`
- Environment name: `pypi`

**TestPyPI Configuration** (manual setup on test.pypi.org):

- Project name: `quilt-mcp`
- Owner: `quiltdata`
- Repository name: `quilt-mcp-server`
- Workflow filename: `pr.yml`
- Environment name: `testpypi`

## Implementation Plan

### Phase 4.1: Action Modification

1. Update action.yml to support pypi-repository-url parameter
2. Remove password-based authentication
3. Simplify to single publishing step with variable repository URL

### Phase 4.2: Workflow Updates

1. Add permissions block to dev-release job
2. Add environment specifications to both jobs
3. Update action calls with environment parameter

### Phase 4.3: GitHub Configuration

1. Create PyPI and TestPyPI environments
2. Configure protection rules (manual approval for PyPI)
3. Set up trusted publishers on PyPI.org and test.pypi.org

### Phase 4.4: Testing & Validation

1. Test with development tag (TestPyPI)
2. Test with production tag (PyPI)
3. Verify manual approval workflow for production
4. Validate PEP 740 attestation generation

## Security Benefits

1. **No Stored Secrets**: Eliminates need for PyPI tokens in GitHub secrets
2. **Environment Separation**: Clear separation between production and test publishing
3. **Approval Gates**: Manual approval required for production releases
4. **Audit Trail**: GitHub environments provide detailed audit logging
5. **Attestation**: Automatic PEP 740 attestation generation for enhanced supply chain security

## Migration Strategy

### Immediate Changes (No Risk)

- Update action.yml interface
- Add environment parameter support
- Update workflow permissions and environment assignments

### Coordinated Changes (Requires Setup)

- GitHub environment creation
- Trusted publisher configuration
- Remove existing PyPI token secrets (after validation)

## Testing Plan

### Development Testing

1. Create test development tag
2. Verify TestPyPI publication
3. Check PEP 740 attestation generation

### Production Testing

1. Create test production tag
2. Verify manual approval trigger
3. Confirm PyPI publication after approval
4. Validate GitHub release creation

## Rollback Plan

If issues occur:

1. Revert action.yml changes
2. Re-add password authentication with existing secrets
3. Remove environment specifications from workflows
4. Investigation can proceed without blocking releases

## Success Criteria

- [x] Specification created
- [ ] Action modified to support OIDC
- [ ] Workflows updated with environment configuration
- [ ] GitHub environments created
- [ ] Trusted publishers configured
- [ ] Successful TestPyPI publication from dev tag
- [ ] Successful PyPI publication from production tag
- [ ] PEP 740 attestations generated
- [ ] Existing password-based secrets removed

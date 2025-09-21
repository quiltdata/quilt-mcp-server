# Phase 4: OIDC PyPI Publishing - Implementation Plan

## ✅ COMPLETED: Phases 4.1 & 4.2 - Code Changes

### ✅ Phase 4.1: Action Modification

- **Updated**: `.github/actions/create-release/action.yml`
  - Added `pypi-repository-url` input parameter with default empty string
  - Removed password-based authentication (`password: ${{ inputs.pypi-token }}`)
  - Simplified PyPI publishing step to use OIDC with repository URL parameter

### ✅ Phase 4.2: Workflow Updates

- **Updated**: `.github/workflows/push.yml` (Production workflow)
  - Added TODO comment for environment setup: `# TODO: Add environment specification after manual setup: environment: pypi`
  - Permissions already included `id-token: write`
  - Action call defaults to PyPI (empty repository-url)

- **Updated**: `.github/workflows/pr.yml` (Development workflow)
  - Added TODO comment for environment setup: `# TODO: Add environment specification after manual setup: environment: testpypi`
  - Added permissions block with `contents: write` and `id-token: write`
  - Action call includes `pypi-repository-url: https://test.pypi.org/legacy/`

**Note**: Environment specifications are commented out until manual GitHub environment setup is completed to avoid schema validation issues.

## 🔄 TODO: Phase 4.3 - GitHub Configuration (Manual Setup Required)

### Step 1: Create GitHub Environments

**Navigate to**: `https://github.com/quiltdata/quilt-mcp-server/settings/environments`

#### Create PyPI Environment

1. Click "New environment"
2. Name: `pypi`
3. **Environment protection rules**:
   - ✅ **Required reviewers**: Add repository maintainers
   - ✅ **Wait timer**: 0 minutes (optional: add delay for review time)
   - ✅ **Deployment branches**: Selected branches and tags
     - Add rule: `refs/tags/v*` (exclude `refs/tags/v*-dev-*`)
4. Click "Configure environment"

#### Create TestPyPI Environment

1. Click "New environment"
2. Name: `testpypi`
3. **Environment protection rules**:
   - ❌ **Required reviewers**: Leave unchecked (automated for dev releases)
   - ❌ **Wait timer**: 0 minutes
   - ✅ **Deployment branches**: Selected branches and tags
     - Add rule: `refs/tags/v*-dev-*`
4. Click "Configure environment"

### Step 2: Uncomment Environment Specifications

After creating the GitHub environments, update the workflow files:

1. **Edit** `.github/workflows/push.yml`:

   ```yaml
   # Change this line:
   # TODO: Add environment specification after manual setup: environment: pypi

   # To this:
   environment: pypi
   ```

2. **Edit** `.github/workflows/pr.yml`:

   ```yaml
   # Change this line:
   # TODO: Add environment specification after manual setup: environment: testpypi

   # To this:
   environment: testpypi
   ```

### Step 3: Configure Trusted Publishers

#### PyPI.org Configuration

1. **Navigate to**: <https://pypi.org/manage/project/quilt-mcp/settings/>
2. **Scroll to**: "Trusted publishing"
3. **Click**: "Add a new trusted publisher"
4. **Select**: "GitHub"
5. **Fill in**:
   - Owner: `quiltdata`
   - Repository name: `quilt-mcp-server`
   - Workflow filename: `push.yml`
   - Environment name: `pypi`
6. **Click**: "Add trusted publisher"

#### TestPyPI Configuration

1. **Navigate to**: <https://test.pypi.org/manage/project/quilt-mcp/settings/>
2. **If project doesn't exist**:
   - First upload may need to be done manually with API token
   - Alternative: Create project through web interface
3. **Scroll to**: "Trusted publishing"
4. **Click**: "Add a new trusted publisher"
5. **Select**: "GitHub"
6. **Fill in**:
   - Owner: `quiltdata`
   - Repository name: `quilt-mcp-server`
   - Workflow filename: `pr.yml`
   - Environment name: `testpypi`
7. **Click**: "Add trusted publisher"

## 🧪 Phase 4.4 - Testing & Validation

### Pre-Testing Checklist

- [ ] GitHub environments created (`pypi`, `testpypi`)
- [ ] Environment protection rules configured
- [ ] Trusted publishers configured on both PyPI and TestPyPI
- [ ] Code changes pushed to repository

### Development Testing (TestPyPI)

#### Test 1: Create Development Tag

```bash
# Create and push development tag
git tag v0.5.10-dev-$(date +%Y%m%d%H%M%S)
git push origin --tags
```

#### Expected Behavior

1. **Workflow Trigger**: `pr.yml` workflow should trigger on `v*-dev-*` tag
2. **Environment**: Job should wait for `testpypi` environment (no approval needed)
3. **OIDC Authentication**: PyPI publish step should use OIDC without password
4. **TestPyPI Upload**: Package should appear on <https://test.pypi.org/project/quilt-mcp/>
5. **PEP 740 Attestation**: Attestation should be generated automatically

#### Validation Steps

- [ ] Workflow runs without errors
- [ ] No password authentication attempted
- [ ] TestPyPI shows new version
- [ ] Attestation visible in PyPI UI
- [ ] GitHub release created

### Production Testing (PyPI)

#### Test 2: Create Production Tag

```bash
# Create and push production tag
git tag v0.5.10
git push origin --tags
```

#### Expected Behavior

1. **Workflow Trigger**: `push.yml` workflow should trigger on `v*` tag (excluding `v*-dev-*`)
2. **Environment**: Job should wait for `pypi` environment approval
3. **Manual Approval**: Repository maintainer must approve deployment
4. **OIDC Authentication**: PyPI publish step should use OIDC without password
5. **PyPI Upload**: Package should appear on <https://pypi.org/project/quilt-mcp/>
6. **PEP 740 Attestation**: Attestation should be generated automatically

#### Validation Steps

- [ ] Workflow triggers and waits for approval
- [ ] Manual approval process works
- [ ] Workflow runs without errors after approval
- [ ] No password authentication attempted
- [ ] PyPI shows new version
- [ ] Attestation visible in PyPI UI
- [ ] GitHub release created

### Error Scenarios to Test

#### Test 3: Invalid Environment Configuration

- Remove trusted publisher temporarily
- Verify meaningful error message in workflow

#### Test 4: Permission Issues

- Test with insufficient permissions
- Verify proper error handling

### Monitoring & Verification

#### GitHub Actions Logs

Check for these log indicators:

- ✅ `Generating ephemeral OIDC token`
- ✅ `Successfully exchanged OIDC token`
- ❌ `Using password authentication` (should not appear)

#### PyPI/TestPyPI Interface

Verify these elements:

- [ ] Package version updated
- [ ] Publication source shows "GitHub Actions"
- [ ] Attestation badge visible
- [ ] Attestation details accessible

## 🔧 Troubleshooting Guide

### Common Issues

#### 1. "Workflow does not have permission to use environment"

**Solution**: Ensure environment deployment branch rules include the correct tag patterns:

- PyPI: `refs/tags/v*` (excluding dev tags)
- TestPyPI: `refs/tags/v*-dev-*`

#### 2. "Authentication failed" / "Invalid token"

**Solution**: Verify trusted publisher configuration matches exactly:

- Owner, repository, workflow filename, environment name must match
- Case sensitivity matters

#### 3. "Environment protection rules block deployment"

**Solution**:

- For PyPI: Ensure required reviewers are available and approve
- For TestPyPI: Check that no blocking protection rules are set

#### 4. "Package already exists" on TestPyPI

**Solution**: TestPyPI doesn't allow re-uploading same version:

- Use unique development version numbers
- Include timestamp in dev tags: `v*-dev-YYYYMMDDHHMMSS`

### Rollback Procedure

If issues occur and immediate rollback is needed:

1. **Revert Action Changes**:

```bash
git revert <commit-hash-of-action-changes>
```

2. **Re-add Password Authentication** (temporary):

```yaml
# In action.yml, restore:
- name: Publish to PyPI/TestPyPI
  uses: pypa/gh-action-pypi-publish@release/v1
  with:
    password: ${{ inputs.pypi-token }}
    repository-url: ${{ inputs.pypi-repository-url }}
    packages-dir: dist/
```

3. **Update Workflow Calls** (temporary):

```yaml
# Add inputs back to workflow calls
uses: ./.github/actions/create-release
with:
  tag-version: ${{ steps.version.outputs.tag_version }}
  pypi-token: ${{ secrets.PYPI_API_TOKEN }}
  pypi-repository-url: https://test.pypi.org/legacy/  # For TestPyPI
```

## 📋 Post-Implementation Checklist

### Immediate Tasks (After successful testing)

- [ ] Remove password-based PyPI tokens from GitHub secrets
- [ ] Update documentation to reflect OIDC authentication
- [ ] Notify team of new approval process for production releases
- [ ] Document environment configuration for future reference

### Long-term Benefits Verification

- [ ] Reduced secret management overhead
- [ ] Enhanced security audit trail
- [ ] Improved supply chain security with attestations
- [ ] Clear separation between production and development publishing

### Security Audit

- [ ] Verify no PyPI tokens remain in GitHub secrets
- [ ] Confirm trusted publisher configuration is minimal (specific to workflows)
- [ ] Review environment protection rules are appropriate
- [ ] Validate attestation generation is working consistently

## 📝 Documentation Updates Needed

After successful implementation, update these documents:

- [ ] `README.md` - Remove references to PyPI token setup
- [ ] `CONTRIBUTING.md` - Add OIDC authentication section
- [ ] `.github/workflows/README.md` - Document environment approval process
- [ ] Release process documentation - Update for new approval workflow

## 🎯 Success Criteria

✅ **Implementation Complete When**:

- [ ] All code changes deployed
- [ ] GitHub environments configured and functional
- [ ] Trusted publishers set up on both PyPI and TestPyPI
- [ ] Successful test deployment to TestPyPI
- [ ] Successful test deployment to PyPI (with approval)
- [ ] PEP 740 attestations generated for both
- [ ] Legacy password authentication removed
- [ ] Documentation updated

## 📞 Support Contacts

**For GitHub Environment Issues**:

- GitHub Support: <https://support.github.com/>
- GitHub Actions Documentation: <https://docs.github.com/en/actions>

**For PyPI/TestPyPI Issues**:

- PyPI Support: <https://pypi.org/help/>
- Trusted Publishing Documentation: <https://docs.pypi.org/trusted-publishers/>

**For Repository-Specific Issues**:

- Repository maintainers
- Internal DevOps team

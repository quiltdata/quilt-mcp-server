# Specification: UV Package Publishing for quilt-mcp-server

**Issue**: #73 - uv package  
**Status**: Phase 2 - Specification  
**Target**: Add UV-based PyPI package publishing with Make targets

## Cross-Validation: Phase 1 Investigation Complete ✅

**Validated Findings:**

- ✅ Strong UV foundation exists (app/Makefile extensive usage)
- ✅ Sophisticated Make target system with .env loading (root + phase-specific)
- ✅ pyproject.toml well-configured (version 0.4.1, proper metadata)
- ✅ DXT package workflow already exists (.github/workflows/dxt.yml)
- ✅ Release tag system exists (make tag-release, etc.)
- ✅ Missing: UV publish commands, TestPyPI config, GitHub Trust Publishing setup

**Gaps Identified:**

- No `uv publish` integration in Make targets
- No TestPyPI environment variable configuration in .env
- No GitHub Trust Publishing workflow for PyPI releases
- No UV publishing environment variable validation

## End-User Requirements

### FR-1: Local TestPyPI Publishing

**As a developer**, I want to publish the package to TestPyPI using UV with local credentials, so that I can
validate package publishing before production releases.

**Acceptance Criteria:**

- Make target `publish-test` publishes to TestPyPI using UV
- Uses TestPyPI credentials from .env file
- Validates UV publishing environment variables before publishing
- Provides clear success/failure feedback with URLs
- Fails gracefully with helpful error messages if credentials missing

### FR-2: Production PyPI Publishing via GitHub Trust Publishing

**As a maintainer**, I want automated PyPI publishing triggered by git tags using GitHub Trust Publishing, so
that releases are secure and don't require stored secrets.

**Acceptance Criteria:**

- GitHub workflow publishes to PyPI on version tags (v*)
- Uses GitHub OIDC Trust Publishing (no stored PyPI tokens)
- Only publishes from main branch tags
- Validates package build before publishing
- Creates GitHub release with package details

### FR-3: Environment Variable Validation

**As a developer**, I want pre-publish validation of required environment variables, so that publishing
failures are caught early with clear guidance.

**Acceptance Criteria:**

- Make target validates required UV publishing environment variables
- Provides specific error messages for missing variables
- Supports both TestPyPI and PyPI configurations
- Integrates with existing check-env.sh pattern

### FR-4: Make Target Integration

**As a developer**, I want consistent Make targets for package publishing, so that it follows the established
project patterns and can load .env configuration.

**Acceptance Criteria:**

- Follows existing Make target patterns (loads .env, uses UV)
- Provides help documentation via `make help`
- Integrates with existing release tag workflow
- Supports both local development and CI/CD usage

## Behavior-Driven Development Tests

### Scenario: Local TestPyPI Publishing Success

```gherkin
Given I am in the project root directory
And I have valid TestPyPI credentials in .env
And the package version is not already published to TestPyPI
When I run "make publish-test"
Then UV should build the package successfully
And UV should publish to TestPyPI successfully
And I should see the TestPyPI package URL in the output
And the command should exit with code 0
```

### Scenario: Missing TestPyPI Credentials

```gherkin
Given I am in the project root directory
And TestPyPI credentials are missing from .env
When I run "make publish-test"
Then I should see an error message about missing TestPyPI credentials
And I should see instructions for configuring credentials
And the command should exit with code 1
And no publishing attempt should be made
```

### Scenario: GitHub Trust Publishing on Tag

```gherkin
Given a version tag "v1.0.0" is pushed to main branch
And GitHub Trust Publishing is configured for the repository
When the GitHub workflow runs
Then the package should build successfully
Then the package should publish to PyPI successfully
And a GitHub release should be created
And the release should include package details and PyPI link
```

### Scenario: Environment Variable Validation

```gherkin
Given I am in the project root directory
When I run "make check-publish-env"
Then UV publishing environment variables should be validated
And missing variables should be reported with specific error messages
And valid configurations should be confirmed
And guidance should be provided for missing variables
```

## Integration Test Requirements

### IT-1: End-to-End TestPyPI Publishing

- **Setup**: Clean environment with test credentials
- **Test**: Complete publish-test workflow
- **Verify**: Package appears on TestPyPI with correct metadata
- **Cleanup**: Package deletion (if supported) or version increment

### IT-2: GitHub Trust Publishing Workflow

- **Setup**: Mock GitHub OIDC environment  
- **Test**: Workflow execution with trust publishing
- **Verify**: Proper OIDC token generation and PyPI authentication
- **Note**: Use TestPyPI for integration testing

### IT-3: Make Target Environment Loading

- **Setup**: .env file with TestPyPI configuration
- **Test**: Make target loads and uses environment variables correctly
- **Verify**: UV commands receive proper environment variables
- **Cleanup**: Restore original .env state

### IT-4: Version Validation Integration

- **Setup**: Various version states (published/unpublished)
- **Test**: Publishing behavior with version conflicts
- **Verify**: Appropriate error handling and user guidance

## Non-Functional Requirements

### NFR-1: Security

- TestPyPI credentials stored only in local .env (gitignored)
- Production publishing uses GitHub OIDC Trust Publishing only
- No PyPI tokens stored in GitHub secrets
- UV commands use secure authentication methods

### NFR-2: Reliability

- Pre-publish validation prevents common failure modes
- Graceful error handling with actionable error messages
- Idempotent operations where possible
- Clear success/failure indicators

### NFR-3: Maintainability

- Follows existing project patterns and conventions
- Consistent with current Make target structure
- Uses established UV and environment variable patterns
- Documentation integrated with existing help system

### NFR-4: Usability

- Clear make help documentation for new targets
- Intuitive error messages with resolution guidance
- Consistent with existing developer workflow
- Fast feedback on configuration issues

## Technical Architecture

### UV Publishing Commands Research

**UV Build Command:**

```bash
uv build
```

- Builds wheel and source distribution
- Outputs to `dist/` directory
- Respects pyproject.toml configuration

**UV Publish Command:**

```bash
uv publish [--index-url INDEX_URL] [--username USERNAME] [--password PASSWORD]
```

- Publishes built packages to PyPI/TestPyPI
- Supports environment variables for credentials
- Can specify custom index URLs

**Environment Variables:**

- `UV_PUBLISH_URL` - Custom index URL (e.g., TestPyPI)
- `UV_PUBLISH_USERNAME` - PyPI username
- `UV_PUBLISH_PASSWORD` - PyPI password/token
- `UV_PUBLISH_TOKEN` - API token (alternative to username/password)

### TestPyPI Configuration

**Required .env additions:**

```bash
# TestPyPI Configuration for UV Publishing
TESTPYPI_USERNAME=__token__
TESTPYPI_PASSWORD=pypi-xxxxxxxxxx
UV_PUBLISH_URL=https://test.pypi.org/legacy/
```

### GitHub Trust Publishing Setup

**Required PyPI Project Settings:**

- Enable "Trusted Publisher" for repository
- Configure: organization/repo, workflow file, environment (optional)

**Workflow Requirements:**

- `id-token: write` permission
- `pypa/gh-action-pypi-publish` action
- Runs only on version tags from main branch

## Implementation Plan

### Phase 1: Local TestPyPI Publishing

1. Add UV publish environment variables to .env example
2. Create `make publish-test` target
3. Add environment variable validation
4. Add BDD tests for local publishing workflow

### Phase 2: GitHub Trust Publishing

1. Create GitHub workflow for tag-based publishing
2. Configure OIDC trust relationship documentation
3. Add production publishing integration tests
4. Update release process documentation

### Phase 3: Integration & Testing

1. Complete integration test suite
2. Update existing release tag workflow
3. Add help documentation
4. Final validation against all requirements

## Dependencies & Constraints

### Prerequisites

- UV 0.1.0+ (already satisfied)
- PyPI/TestPyPI account with appropriate permissions
- GitHub repository with Actions enabled
- pyproject.toml properly configured (already satisfied)

### Breaking Changes

- None expected - additive functionality only

### Migration Requirements

- Update .env with TestPyPI credentials for local development
- Configure GitHub Trust Publishing for production releases

---

**Next Phase**: Implementation (Phase 3)  
**Dependencies**: None - ready for implementation  
**Estimated Complexity**: Medium (leverages existing patterns)

# BDD Test Specification: UV Package Publishing

**Issue**: #73 - uv package  
**Phase**: 2 - Specification  
**Test Framework**: pytest-bdd with real UV commands

## Test Structure

### Test Organization
```
tests/
├── test_uv_publishing.py         # Main BDD test file  
├── test_publish_environment.py   # Environment validation tests
├── test_make_targets.py          # Make target integration tests
└── fixtures/
    ├── publishing/               # Test fixtures for publishing
    └── environments/             # Environment configuration fixtures
```

## Feature: Local TestPyPI Publishing

### Background
```gherkin
Background: Clean publishing environment
  Given I am in the project root directory
  And the dist/ directory is clean
  And UV is installed and available
```

### Scenario: Successful TestPyPI Publishing
```gherkin
Scenario: Publish package to TestPyPI with valid credentials
  Given I have valid TestPyPI credentials in .env:
    """
    TESTPYPI_USERNAME=__token__
    TESTPYPI_PASSWORD=pypi-AgEIcHlwaS5vcmc...
    UV_PUBLISH_URL=https://test.pypi.org/legacy/
    """
  And the package version is "0.4.1-test-{timestamp}"
  When I run "make publish-test"
  Then UV should build the package successfully
  And the output should contain "Building wheel"
  And the output should contain "Building source distribution"
  And UV should publish to TestPyPI successfully  
  And the output should contain "Uploading quilt_mcp_server"
  And the output should contain "https://test.pypi.org/project/quilt-mcp-server"
  And the command should exit with code 0
  And the package should be downloadable from TestPyPI
```

### Scenario: Missing TestPyPI credentials
```gherkin
Scenario: Attempt publishing without TestPyPI credentials
  Given TestPyPI credentials are missing from .env
  When I run "make publish-test"
  Then I should see the error "TestPyPI credentials not configured"
  And I should see "Please add TESTPYPI_USERNAME and TESTPYPI_PASSWORD to .env"
  And I should see "See docs/PUBLISHING.md for setup instructions"
  And the command should exit with code 1
  And no UV publish command should be executed
```

### Scenario: Invalid TestPyPI credentials
```gherkin
Scenario: Attempt publishing with invalid credentials
  Given I have invalid TestPyPI credentials in .env:
    """
    TESTPYPI_USERNAME=__token__
    TESTPYPI_PASSWORD=invalid-token
    UV_PUBLISH_URL=https://test.pypi.org/legacy/
    """
  When I run "make publish-test"
  Then UV should build the package successfully
  But UV should fail to publish with authentication error
  And the output should contain "Authentication failed"
  And the command should exit with code 1
```

### Scenario: Package version already exists
```gherkin
Scenario: Attempt publishing duplicate version to TestPyPI
  Given I have valid TestPyPI credentials in .env
  And the package version "0.4.1" already exists on TestPyPI
  When I run "make publish-test"
  Then UV should build the package successfully
  But UV should fail to publish with version conflict error
  And the output should contain "File already exists"
  And the command should exit with code 1
  And I should see guidance about version bumping
```

## Feature: Environment Variable Validation

### Scenario: Valid publishing environment
```gherkin
Scenario: Validate complete TestPyPI environment configuration
  Given I have complete TestPyPI configuration in .env:
    """
    TESTPYPI_USERNAME=__token__
    TESTPYPI_PASSWORD=pypi-AgEIcHlwaS5vcmc...
    UV_PUBLISH_URL=https://test.pypi.org/legacy/
    """
  When I run "make check-publish-env"
  Then I should see "✅ TestPyPI configuration valid"
  And I should see "✅ UV publishing environment ready"
  And the command should exit with code 0
```

### Scenario: Missing required environment variables
```gherkin
Scenario: Validate environment with missing variables
  Given my .env file is missing TestPyPI configuration
  When I run "make check-publish-env"
  Then I should see "❌ Missing required environment variables:"
  And I should see "  - TESTPYPI_USERNAME"
  And I should see "  - TESTPYPI_PASSWORD"
  And I should see "  - UV_PUBLISH_URL"
  And I should see "Add these variables to .env file"
  And the command should exit with code 1
```

### Scenario: Partial environment configuration
```gherkin
Scenario: Validate environment with some missing variables
  Given I have partial TestPyPI configuration in .env:
    """
    TESTPYPI_USERNAME=__token__
    # Missing TESTPYPI_PASSWORD
    UV_PUBLISH_URL=https://test.pypi.org/legacy/
    """
  When I run "make check-publish-env"
  Then I should see "❌ Missing required environment variables:"
  And I should see "  - TESTPYPI_PASSWORD"
  And I should not see "TESTPYPI_USERNAME" in the missing list
  And I should not see "UV_PUBLISH_URL" in the missing list
  And the command should exit with code 1
```

## Feature: Make Target Integration

### Scenario: Make help includes publishing targets
```gherkin
Scenario: Publishing targets appear in make help
  When I run "make help"
  Then the output should contain "Publishing Commands:"
  And the output should contain "make publish-test"
  And the output should contain "make check-publish-env"
  And the output should contain "Publish package to TestPyPI"
  And the output should contain "Validate publishing environment"
```

### Scenario: Make target loads environment variables
```gherkin
Scenario: Publishing target uses .env configuration
  Given I have TestPyPI credentials in .env
  When I run "make publish-test" with debug output
  Then the UV publish command should use credentials from .env
  And the environment variables should be properly exported
  And no credentials should appear in command output or logs
```

### Scenario: Make target fails without UV
```gherkin
Scenario: Publishing fails when UV is not available
  Given UV is not installed or not in PATH
  When I run "make publish-test"
  Then I should see "Error: uv not found"
  And I should see "Please install uv first"
  And the command should exit with code 1
```

## Feature: GitHub Trust Publishing

### Scenario: GitHub workflow publishes on version tag
```gherub
Scenario: Automated PyPI publishing via GitHub Trust Publishing
  Given I have a clean main branch
  And GitHub Trust Publishing is configured for the repository
  When I push a version tag "v1.0.0" to main
  Then the GitHub workflow should trigger
  And the workflow should build the package
  And the workflow should publish to PyPI using OIDC
  And the workflow should create a GitHub release
  And the release should link to the PyPI package
```

**Note**: This scenario requires GitHub environment setup and will be tested with TestPyPI in CI.

### Scenario: Workflow fails on non-main branch tags
```gherkin
Scenario: GitHub workflow rejects tags from feature branches
  Given I am on a feature branch "feature/test-publishing"
  When I push a version tag "v1.0.0-test"
  Then the GitHub workflow should not trigger PyPI publishing
  Or the workflow should exit early with branch validation error
  And no package should be published to PyPI
```

## Integration Test Requirements

### IT-1: End-to-End TestPyPI Flow
```python
def test_end_to_end_testpypi_publish():
    """
    Integration test: Complete TestPyPI publishing workflow
    
    Prerequisites:
    - Valid TestPyPI account and token
    - Unique version number for test
    - Clean dist/ directory
    
    Test Steps:
    1. Configure TestPyPI credentials in temp .env
    2. Run make publish-test
    3. Verify package appears on TestPyPI
    4. Verify package metadata is correct
    5. Verify package can be installed from TestPyPI
    
    Cleanup:
    - Remove test .env configuration
    - Clean dist/ directory
    """
```

### IT-2: Environment Validation Integration
```python
def test_environment_validation_integration():
    """
    Integration test: Environment validation with real UV commands
    
    Test Steps:
    1. Test with various .env configurations
    2. Verify UV command parameter passing
    3. Verify error handling and user guidance
    4. Test environment variable precedence
    """
```

### IT-3: Make Target Environment Loading
```python
def test_make_target_environment_loading():
    """
    Integration test: Make targets properly load and use .env
    
    Test Steps:
    1. Create test .env with publishing configuration
    2. Run make targets with environment tracing
    3. Verify correct environment variables reach UV commands
    4. Test environment variable isolation and cleanup
    """
```

## Test Implementation Guidelines

### Fixture Patterns
```python
@pytest.fixture
def testpypi_credentials():
    """Provide valid TestPyPI credentials for testing."""
    return {
        'TESTPYPI_USERNAME': '__token__',
        'TESTPYPI_PASSWORD': os.getenv('TESTPYPI_TOKEN_FOR_TESTS'),
        'UV_PUBLISH_URL': 'https://test.pypi.org/legacy/',
    }

@pytest.fixture  
def temp_env_file(tmp_path):
    """Create temporary .env file for testing."""
    env_file = tmp_path / '.env'
    yield env_file
    # Cleanup handled by tmp_path
```

### Mock Patterns for UV Commands
```python
@pytest.fixture
def mock_uv_commands(monkeypatch):
    """Mock UV build and publish commands for unit testing."""
    build_mock = Mock(return_value=CompletedProcess(args=[], returncode=0))
    publish_mock = Mock(return_value=CompletedProcess(args=[], returncode=0))
    
    monkeypatch.setattr('subprocess.run', Mock(side_effect=[build_mock, publish_mock]))
    return build_mock, publish_mock
```

### Test Data Management
```python
def generate_test_version():
    """Generate unique version for TestPyPI publishing tests."""
    import time
    timestamp = int(time.time())
    return f"0.4.1-test-{timestamp}"
```

---

**BDD Test Coverage**: Complete behavioral specification for all publishing scenarios  
**Integration Tests**: Real UV command testing with TestPyPI  
**Mock Strategy**: Unit tests use mocked UV commands, integration tests use real commands
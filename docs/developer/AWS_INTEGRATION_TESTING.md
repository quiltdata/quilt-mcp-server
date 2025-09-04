# AWS Integration Testing Setup Guide

This guide explains how to set up AWS credentials and environment for integration testing in GitHub Actions.

## Overview

The project uses a two-tier testing strategy:

1. **Unit Tests** (`test.yml`): Fast tests with mocks, run on every PR
2. **Integration Tests** (`integration-test.yml`): Real AWS tests, run on main branch or when labeled

## Required GitHub Secrets

To enable integration testing, configure the following secrets in your GitHub repository:

### Core AWS Credentials
```
AWS_ACCESS_KEY_ID          - AWS access key for test user/role
AWS_SECRET_ACCESS_KEY      - AWS secret key for test user/role  
AWS_DEFAULT_REGION         - AWS region (default: us-east-1)
```

### Quilt-Specific Settings
```
QUILT_DEFAULT_BUCKET       - S3 bucket for package testing (e.g., "my-quilt-test-bucket")
QUILT_CATALOG_URL          - Quilt catalog URL (e.g., "https://demo.quiltdata.com")
QUILT_TEST_PACKAGE         - Known package name for testing (e.g., "test/sample-package")
QUILT_TEST_ENTRY           - Known S3 object for testing (e.g., "test-file.csv")
```

### Optional Advanced Settings
```
QUILT_READ_POLICY_ARN      - IAM policy ARN for read permissions
CDK_DEFAULT_ACCOUNT        - AWS account ID for CDK deployment tests
CDK_DEFAULT_REGION         - AWS region for CDK deployment tests
```

## AWS Permissions Setup

The integration test user/role needs the following permissions:

### Minimum S3 Permissions
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:ListBucket",
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject"
            ],
            "Resource": [
                "arn:aws:s3:::your-test-bucket",
                "arn:aws:s3:::your-test-bucket/*"
            ]
        }
    ]
}
```

### IAM Permissions for Discovery Tests
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "iam:GetUser",
                "iam:ListAttachedUserPolicies",
                "iam:GetPolicy",
                "iam:GetPolicyVersion",
                "s3:ListAllMyBuckets",
                "s3:GetBucketLocation"
            ],
            "Resource": "*"
        }
    ]
}
```

## Test Triggering

### Automatic Triggers
- **Unit tests**: Run on every push and PR
- **Integration tests**: Run on pushes to `main` branch

### Manual Triggers

#### 1. Add Label to PR
Add the `test:integration` label to any PR to trigger integration tests.

#### 2. Manual Workflow Dispatch
Go to Actions → Integration Tests → Run workflow
- Choose test scope: `all`, `aws`, `search`, or `permissions`

### Command Line Examples
```bash
# Trigger via GitHub CLI
gh workflow run integration-test.yml -f test_scope=aws

# Add integration test label to PR
gh pr edit 123 --add-label "test:integration"
```

## Local Development

### Running Integration Tests Locally
```bash
# Set up environment
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export QUILT_DEFAULT_BUCKET=your-test-bucket

# Run all integration tests
cd app && make test

# Run specific test suites (all included in main test suite)
make test              # Full local test suite including AWS, search, permissions
```

### Running Unit Tests (No AWS)
```bash
cd app && make test-ci
```

## Test Organization

### Test Markers
- `@pytest.mark.aws`: Tests requiring AWS credentials
- `@pytest.mark.search`: Tests requiring Quilt search functionality
- `@pytest.mark.slow`: Long-running tests

### File Organization
```
app/tests/
├── test_bucket_tools.py        # Unit tests (mocked)
├── test_integration.py         # Full integration tests (@aws, @search)
├── test_permissions.py         # Permission discovery (@aws)
├── test_s3_package.py         # S3-to-package functionality (@aws)
├── test_quilt_tools.py        # Quilt API tests (mocked)
└── test_*.py                  # Other unit tests
```

## Debugging Failed Tests

### Check Test Logs
1. Go to GitHub Actions → Failed workflow
2. Expand the "Run integration tests" step
3. Look for specific error messages

### Common Issues

#### Authentication Errors
```
Error: Unable to locate credentials
```
**Solution**: Check that AWS secrets are correctly configured

#### Permission Denied
```
Error: Access Denied
```
**Solution**: Verify IAM permissions for the test bucket/resources

#### Timeout Errors
```
Error: Test timed out after 60 seconds
```
**Solution**: Check network connectivity or increase timeout

### Local Debugging
```bash
# Run single test with verbose output
cd app
export PYTHONPATH="$(pwd)"
uv run python -m pytest tests/test_permissions.py::TestAWSPermissionsDiscover::test_discover_permissions_success -v -s

# Run with timeout debugging
uv run python -m pytest tests/test_integration.py -v --timeout=30 --timeout-method=thread
```

## Best Practices

### 1. Use Dedicated Test Resources
- Create separate S3 buckets for testing
- Use test-specific IAM roles with minimal permissions
- Avoid using production data in tests

### 2. Clean Up Test Data
- Tests should clean up any resources they create
- Use unique names with UUIDs for test objects
- Set up bucket lifecycle policies to automatically delete old test data

### 3. Handle Rate Limits
- Tests include appropriate timeouts
- Retry logic for transient failures
- Avoid running too many parallel requests

### 4. Security
- Never commit AWS credentials to code
- Use GitHub secrets for all sensitive data
- Regularly rotate test credentials
- Monitor test resource usage

## Example Test Bucket Setup

```bash
# Create test bucket
aws s3 mb s3://my-quilt-integration-tests

# Upload test data
echo "test,data,1,2,3" > test-file.csv
aws s3 cp test-file.csv s3://my-quilt-integration-tests/

# Set lifecycle policy to clean up old test data
aws s3api put-bucket-lifecycle-configuration \
  --bucket my-quilt-integration-tests \
  --lifecycle-configuration file://test-lifecycle.json
```

Example `test-lifecycle.json`:
```json
{
    "Rules": [
        {
            "ID": "DeleteOldTestData",
            "Status": "Enabled",
            "Filter": {"Prefix": "test-"},
            "Expiration": {"Days": 7}
        }
    ]
}
```

This ensures test data is automatically cleaned up after 7 days.

#!/bin/bash
# Script to help set up GitHub secrets for CI/CD

echo "🔐 GitHub Secrets Setup Guide"
echo "================================"
echo
echo "To enable GitHub Actions for testing and deployment, set up these secrets:"
echo "Go to: https://github.com/quiltdata/fast-mcp-server/settings/secrets/actions"
echo

# Load current .env if it exists
if [ -f ".env" ]; then
    source .env
    echo "📋 Required secrets (copy these exact names and values):"
    echo
    echo "🔑 AWS_ACCESS_KEY_ID"
    echo "   Value: <your-aws-access-key-id>"
    echo
    echo "🔑 AWS_SECRET_ACCESS_KEY" 
    echo "   Value: <your-aws-secret-access-key>"
    echo
    echo "🔑 QUILT_READ_POLICY_ARN"
    echo "   Value: ${QUILT_READ_POLICY_ARN}"
    echo
    echo "📋 Optional secrets (will use defaults if not set):"
    echo
    echo "🔑 CDK_DEFAULT_ACCOUNT"
    echo "   Value: ${CDK_DEFAULT_ACCOUNT:-<auto-detected>}"
    echo
    echo "🔑 CDK_DEFAULT_REGION"
    echo "   Value: ${CDK_DEFAULT_REGION:-us-east-1}"
    echo
else
    echo "❌ No .env file found. Create one first:"
    echo "   cp env.example .env"
    echo "   # Edit .env with your values"
    echo "   ./tests/setup-github-secrets.sh"
    exit 1
fi

echo "💡 How to get AWS credentials:"
echo "1. Create an IAM user with programmatic access"
echo "2. Attach these policies:"
echo "   - Your Quilt read policy: ${QUILT_READ_POLICY_ARN}"
echo "   - AWS managed: AWSCloudFormationFullAccess"
echo "   - AWS managed: IAMFullAccess (for CDK bootstrap)"
echo "   - AWS managed: AmazonS3FullAccess (for CDK assets)"
echo "   - AWS managed: AWSLambda_FullAccess"
echo "   - AWS managed: AmazonAPIGatewayAdministrator"
echo "3. Copy the Access Key ID and Secret Access Key"
echo
echo "🚀 After setting up secrets:"
echo "   - Tests run automatically on every push/PR"
echo "   - Deployment runs automatically on push to main branch"
echo "   - Manual deployment: Go to Actions → Deploy to AWS → Run workflow"

#!/bin/bash
# Script to automatically set up GitHub secrets for CI/CD using GitHub CLI

set -e  # Exit on any error

echo "🔐 Automated GitHub Secrets Setup"
echo "=================================="
echo

# Check if gh CLI is installed and authenticated
if ! command -v gh &> /dev/null; then
    echo "❌ GitHub CLI (gh) is not installed. Install it first:"
    echo "   brew install gh"
    echo "   # or visit: https://cli.github.com/"
    exit 1
fi

# Check if authenticated
if ! gh auth status &> /dev/null; then
    echo "❌ Not authenticated with GitHub CLI. Run:"
    echo "   gh auth login"
    exit 1
fi

# Load current .env if it exists
if [ ! -f ".env" ]; then
    echo "❌ No .env file found. Create one first:"
    echo "   cp env.example .env"
    echo "   # Edit .env with your values"
    exit 1
fi

source .env

echo "📋 Setting up repository secrets..."
echo

# Function to set secret safely
set_secret() {
    local name="$1"
    local value="$2"
    local required="$3"
    
    if [ -z "$value" ] && [ "$required" = "true" ]; then
        echo "❌ Required secret $name is empty in .env file"
        return 1
    fi
    
    if [ -n "$value" ]; then
        echo "🔑 Setting $name..."
        if echo "$value" | gh secret set "$name"; then
            echo "   ✅ $name set successfully"
        else
            echo "   ❌ Failed to set $name"
            return 1
        fi
    else
        echo "⏩ Skipping optional $name (not set in .env)"
    fi
}

echo "Setting required secrets..."

# AWS credentials (you need to add these to your .env file)
if [ -n "$AWS_ACCESS_KEY_ID" ]; then
    set_secret "AWS_ACCESS_KEY_ID" "$AWS_ACCESS_KEY_ID" "true"
else
    echo "❌ AWS_ACCESS_KEY_ID not found in .env. Add it manually:"
    echo "   echo 'AWS_ACCESS_KEY_ID=your_key_here' >> .env"
fi

if [ -n "$AWS_SECRET_ACCESS_KEY" ]; then
    set_secret "AWS_SECRET_ACCESS_KEY" "$AWS_SECRET_ACCESS_KEY" "true"
else
    echo "❌ AWS_SECRET_ACCESS_KEY not found in .env. Add it manually:"
    echo "   echo 'AWS_SECRET_ACCESS_KEY=your_secret_here' >> .env"
fi

# Required Quilt policy ARN
set_secret "QUILT_READ_POLICY_ARN" "$QUILT_READ_POLICY_ARN" "true"

echo
echo "Setting optional secrets with defaults..."

# Optional with defaults
set_secret "CDK_DEFAULT_ACCOUNT" "$CDK_DEFAULT_ACCOUNT" "false"
set_secret "CDK_DEFAULT_REGION" "${CDK_DEFAULT_REGION:-us-east-1}" "false"

echo
echo "🎉 GitHub secrets setup complete!"
echo
echo "📋 Secrets set in repository:"
gh secret list

echo
echo "💡 Next steps:"
echo "1. If AWS credentials aren't set, add them to .env and run this script again"
echo "2. Push changes to trigger GitHub Actions"
echo "3. Check Actions tab to see if workflows run successfully"
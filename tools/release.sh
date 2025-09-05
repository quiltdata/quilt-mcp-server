#!/bin/bash
# Release Management Script
# Consolidates complex release workflows from original Makefile

set -e

# Variables
REPO_URL=$(git config --get remote.origin.url | sed 's/.*github.com[:/]\(.*\)\.git/\1/')

check_clean_repo() {
    echo "🔍 Checking repository state..."
    if [ -n "$(git status --porcelain)" ]; then
        echo "❌ Repository has uncommitted changes. Please commit or stash them first."
        git status --short
        exit 1
    fi
    echo "✅ Repository is clean"
}

tag_dev() {
    echo "🔍 Creating development tag..."
    check_clean_repo
    
    echo "🔍 Reading base version from pyproject.toml..."
    BASE_VERSION=$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])")
    if [ -z "$BASE_VERSION" ]; then
        echo "❌ Could not read version from pyproject.toml"
        exit 1
    fi
    
    TIMESTAMP=$(date +%Y%m%d%H%M%S)
    DEV_VERSION="$BASE_VERSION-dev-$TIMESTAMP"
    echo "📋 Generated dev version: $DEV_VERSION"
    
    if git tag | grep -q "^v$DEV_VERSION$"; then
        echo "❌ Tag v$DEV_VERSION already exists"
        exit 1
    fi
    
    echo "🏷️  Creating development tag v$DEV_VERSION..."
    git pull origin $(git rev-parse --abbrev-ref HEAD)
    git tag -a "v$DEV_VERSION" -m "Development build v$DEV_VERSION"
    git push origin "v$DEV_VERSION"
    echo "✅ Development tag v$DEV_VERSION created and pushed"
    echo "🚀 GitHub Actions will now build and publish the DXT package as a prerelease"
    echo "📦 Release will be available at: https://github.com/$REPO_URL/releases/tag/v$DEV_VERSION"
}

tag_release() {
    echo "🔍 Creating release tag..."
    check_clean_repo
    
    echo "🔍 Reading version from pyproject.toml..."
    if [ ! -f "pyproject.toml" ]; then
        echo "❌ pyproject.toml not found"
        exit 1
    fi
    if [ ! -f "tools/dxt/assets/manifest.json.j2" ]; then
        echo "❌ manifest.json.j2 template not found at tools/dxt/assets/manifest.json.j2"
        exit 1
    fi
    
    MANIFEST_VERSION=$(python3 scripts/version-utils.py get-version)
    if [ -z "$MANIFEST_VERSION" ]; then
        echo "❌ Could not read version from pyproject.toml"
        exit 1
    fi
    
    echo "📋 Found version: $MANIFEST_VERSION"
    if echo "$MANIFEST_VERSION" | grep -q "dev"; then
        echo "🏷️  Creating development tag v$MANIFEST_VERSION..."
        TAG_TYPE="Development build"
    elif echo "$MANIFEST_VERSION" | grep -q -- "-"; then
        echo "🏷️  Creating prerelease tag v$MANIFEST_VERSION..."
        TAG_TYPE="Prerelease"
    else
        echo "🏷️  Creating release tag v$MANIFEST_VERSION..."
        TAG_TYPE="Release"
    fi
    
    if git tag | grep -q "^v$MANIFEST_VERSION$"; then
        echo "❌ Tag v$MANIFEST_VERSION already exists"
        exit 1
    fi
    
    git pull origin main
    git tag -a "v$MANIFEST_VERSION" -m "$TAG_TYPE v$MANIFEST_VERSION"
    git push origin "v$MANIFEST_VERSION"
    echo "✅ Tag v$MANIFEST_VERSION created and pushed"
    echo "🚀 GitHub Actions will now build and publish the DXT package"
    echo "📦 Release will be available at: https://github.com/$REPO_URL/releases/tag/v$MANIFEST_VERSION"
}

# Main script logic
case "${1:-}" in
    "dev")
        tag_dev
        ;;
    "release")
        tag_release
        ;;
    *)
        echo "Usage: $0 {dev|release}"
        echo ""
        echo "Commands:"
        echo "  dev     - Create development tag with timestamp"
        echo "  release - Create release tag from pyproject.toml version"
        exit 1
        ;;
esac
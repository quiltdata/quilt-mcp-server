#!/bin/bash
# Release Management Script
# Consolidates complex release workflows from original Makefile

set -e

# Variables
REPO_URL=$(git config --get remote.origin.url | sed 's/.*github.com[:/]\(.*\)\.git/\1/')
DRY_RUN=${DRY_RUN:-0}

check_clean_repo() {
    echo "🔍 Checking repository state..."
    if [ -n "$(git status --porcelain)" ]; then
        echo "❌ Repository has uncommitted changes. Please commit or stash them first."
        git status --short
        exit 1
    fi
    echo "✅ Repository is clean"
}

push_pending_commits() {
    echo "🔄 Checking for pending commits to push..."

    # Check if there are commits ahead of the remote
    if [ -n "$(git log --oneline @{u}..HEAD 2>/dev/null)" ]; then
        if [ "$DRY_RUN" = "1" ]; then
            echo "🔍 DRY RUN: Would push pending commits:"
            git log --oneline @{u}..HEAD
        else
            echo "📤 Pushing pending commits to remote..."
            git push
            echo "✅ Pushed pending commits"
        fi
    else
        echo "✅ No pending commits to push"
    fi
}

bump_version() {
    local version_type="$1"
    
    if [ -z "$version_type" ]; then
        echo "❌ Version type required: major, minor, patch"
        echo "Usage: $0 bump [major|minor|patch]"
        exit 1
    fi
    
    if [ "$version_type" != "major" ] && [ "$version_type" != "minor" ] && [ "$version_type" != "patch" ]; then
        echo "❌ Invalid version type: $version_type"
        echo "Valid types: major, minor, patch"
        exit 1
    fi
    
    if [ "$DRY_RUN" != "1" ]; then
        check_clean_repo
    fi
    
    echo "🔍 Reading current version from pyproject.toml..."
    CURRENT_VERSION=$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])")
    if [ -z "$CURRENT_VERSION" ]; then
        echo "❌ Could not read version from pyproject.toml"
        exit 1
    fi
    
    echo "📋 Current version: $CURRENT_VERSION"
    
    # Parse semantic version (MAJOR.MINOR.PATCH)
    if ! echo "$CURRENT_VERSION" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+$'; then
        echo "❌ Version must be in MAJOR.MINOR.PATCH format (e.g., 1.2.3)"
        exit 1
    fi
    
    MAJOR=$(echo "$CURRENT_VERSION" | cut -d. -f1)
    MINOR=$(echo "$CURRENT_VERSION" | cut -d. -f2)  
    PATCH=$(echo "$CURRENT_VERSION" | cut -d. -f3)
    
    # Bump version based on type
    case "$version_type" in
        "major")
            MAJOR=$((MAJOR + 1))
            MINOR=0
            PATCH=0
            ;;
        "minor")
            MINOR=$((MINOR + 1))
            PATCH=0
            ;;
        "patch")
            PATCH=$((PATCH + 1))
            ;;
    esac
    
    NEW_VERSION="$MAJOR.$MINOR.$PATCH"
    echo "📋 New version: $NEW_VERSION"
    
    if [ "$DRY_RUN" = "1" ]; then
        echo "🔍 DRY RUN: Would update pyproject.toml version from $CURRENT_VERSION to $NEW_VERSION"
        return
    fi
    
    echo "✏️  Updating pyproject.toml..."
    sed -i.bak "s/version = \"$CURRENT_VERSION\"/version = \"$NEW_VERSION\"/" pyproject.toml
    
    # Verify the change
    UPDATED_VERSION=$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])")
    if [ "$UPDATED_VERSION" != "$NEW_VERSION" ]; then
        echo "❌ Failed to update version. Rolling back..."
        mv pyproject.toml.bak pyproject.toml
        exit 1
    fi
    
    rm pyproject.toml.bak
    echo "✅ Version updated from $CURRENT_VERSION to $NEW_VERSION"
    echo "💡 Don't forget to commit this change before creating a release!"
}

tag_dev() {
    echo "🔍 Creating development tag..."

    if [ "$DRY_RUN" != "1" ]; then
        check_clean_repo
        push_pending_commits
    fi
    
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
    
    if [ "$DRY_RUN" = "1" ]; then
        echo "🔍 DRY RUN: Would execute:"
        push_pending_commits
        echo "  git pull origin $(git rev-parse --abbrev-ref HEAD)"
        echo "  git tag -a \"v$DEV_VERSION\" -m \"Development build v$DEV_VERSION\""
        echo "  git push origin \"v$DEV_VERSION\""
        echo "🚀 Would trigger GitHub Actions to build and publish DXT package as prerelease"
        echo "📦 Release would be available at: https://github.com/$REPO_URL/releases/tag/v$DEV_VERSION"
        return
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

    if [ "$DRY_RUN" != "1" ]; then
        check_clean_repo
        push_pending_commits
    fi
    
    echo "🔍 Reading version from pyproject.toml..."
    if [ ! -f "pyproject.toml" ]; then
        echo "❌ pyproject.toml not found"
        exit 1
    fi
    if [ ! -f "src/deploy/manifest.json.j2" ]; then
        echo "❌ manifest.json.j2 template not found at src/deploy/manifest.json.j2"
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
    
    if [ "$DRY_RUN" = "1" ]; then
        echo "🔍 DRY RUN: Would execute:"
        push_pending_commits
        echo "  git pull origin main"
        echo "  git tag -a \"v$MANIFEST_VERSION\" -m \"$TAG_TYPE v$MANIFEST_VERSION\""
        echo "  git push origin \"v$MANIFEST_VERSION\""
        echo "🚀 Would trigger GitHub Actions to build and publish DXT package"
        echo "📦 Release would be available at: https://github.com/$REPO_URL/releases/tag/v$MANIFEST_VERSION"
        return
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
        if [ "${2:-}" = "--dry-run" ]; then
            DRY_RUN=1
        fi
        tag_dev
        ;;
    "release")
        if [ "${2:-}" = "--dry-run" ]; then
            DRY_RUN=1
        fi
        tag_release
        ;;
    "bump")
        if [ "${3:-}" = "--dry-run" ]; then
            DRY_RUN=1
        fi
        bump_version "${2:-}"
        ;;
    *)
        echo "Usage: $0 {dev|release|bump} [options]"
        echo ""
        echo "Commands:"
        echo "  dev              - Create development tag with timestamp"
        echo "  release          - Create release tag from pyproject.toml version"  
        echo "  bump {type}      - Bump version in pyproject.toml"
        echo ""
        echo "Bump types:"
        echo "  major            - Increment major version (1.2.3 → 2.0.0)"
        echo "  minor            - Increment minor version (1.2.3 → 1.3.0)"
        echo "  patch            - Increment patch version (1.2.3 → 1.2.4)"
        echo ""
        echo "Options:"
        echo "  --dry-run        - Show what would be done without making changes"
        echo ""
        echo "Environment Variables:"
        echo "  DRY_RUN=1        - Enable dry-run mode"
        echo ""
        echo "Examples:"
        echo "  $0 bump patch           # Bump patch version"
        echo "  $0 bump minor --dry-run # Preview minor version bump"
        echo "  $0 dev                  # Create dev tag"
        echo "  $0 release              # Create release tag"
        exit 1
        ;;
esac
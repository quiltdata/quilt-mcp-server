#!/bin/bash

# Test script to validate bug report issue template functionality
# Checks for template existence and creates test issue

set -e

echo "Checking for bug report template..."

# Check if bug report template exists
if [ ! -f ".github/ISSUE_TEMPLATE/bug_report.md" ]; then
    echo "❌ Bug report template not found at .github/ISSUE_TEMPLATE/bug_report.md"
    exit 1
fi

echo "✅ Bug report template found"

# Verify template has required YAML frontmatter
if ! grep -q "labels.*bug" ".github/ISSUE_TEMPLATE/bug_report.md"; then
    echo "❌ Bug report template missing 'bug' label in frontmatter"
    exit 1
fi

echo "✅ Bug report template has correct label configuration"

echo "Creating test bug report issue..."

# Create the test issue using gh CLI with template
ISSUE_URL=$(gh issue create \
    --title "Test Bug Report - Template Validation" \
    --body "**Bug Description**
This is a test bug report created to validate the bug report template functionality.

**Steps to Reproduce**
1. Run test script
2. Create test issue
3. Verify issue creation

**Expected Behavior**
Issue should be created successfully with bug label

**Actual Behavior**
Issue creation in progress...

**Environment Information**
- OS: $(uname -s)
- Script: test-bug-report.sh
- Date: $(date)

**Additional Context**
This is an automated test issue and will be closed immediately.")

echo "Created issue: $ISSUE_URL"

# Extract issue number from URL
ISSUE_NUMBER=$(basename "$ISSUE_URL")
echo "Issue number: $ISSUE_NUMBER"

# Verify the issue exists and has correct label
echo "Verifying issue details..."
ISSUE_INFO=$(gh issue view "$ISSUE_NUMBER" --json number,title,labels,state)
echo "Issue info: $ISSUE_INFO"

# Check if bug label was applied
if echo "$ISSUE_INFO" | grep -q '"name":"bug"'; then
    echo "✅ Bug label correctly applied"
else
    echo "❌ Bug label not found"
    exit 1
fi

# Close the test issue
echo "Closing test issue..."
gh issue close "$ISSUE_NUMBER" --comment "Test completed successfully. Bug report template validation passed."

echo "✅ Test completed successfully!"
echo "Issue #$ISSUE_NUMBER was created, verified, and closed."
# Bug Report Issue Template Specification

## Overview

Add a GitHub issue template specifically for bug reports to improve issue quality and standardize bug report information collection.

## Requirements

### Template Location

- Create bug report template in `.github/ISSUE_TEMPLATE/` directory
- Use YAML frontmatter format for GitHub issue template configuration

### Required Fields

1. **Bug Description** - Clear, concise description of the bug
2. **Steps to Reproduce** - Numbered list of exact steps to reproduce the issue
3. **Expected Behavior** - What should happen
4. **Actual Behavior** - What actually happens
5. **Environment Information**:
   - Operating System
   - Python version
   - Package version
   - Relevant dependencies
6. **Additional Context** - Screenshots, logs, or other relevant information

### Template Configuration

- Title: "Bug Report"
- Description: "Report a bug or unexpected behavior"
- Labels: Automatically apply "bug" label
- Assignees: None (allow manual assignment)

### Template Features

- Clear instructions for each section
- Markdown formatting examples
- Placeholder text to guide users
- Validation prompts to ensure completeness

## Acceptance Criteria

- Template appears in GitHub issue creation interface
- Template automatically applies "bug" label
- All required fields are clearly defined
- Template provides helpful guidance for bug reporting
- Template follows GitHub issue template best practices
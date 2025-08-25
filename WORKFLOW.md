# WORKFLOW.md

Standardized Workflow for processing GitHub issues (as a precursor to full automation).

## Prerequisites

Before starting, ensure you have:

- Repository write access
- Ability to run scripts (`./scripts/*`)
- Git commit permissions
- Branch creation permissions
- GitHub PR read/write permissions

## Workflow Steps

### 1. Issue Analysis

```bash
# Retrieve and analyze the GitHub Issue for this branch
gh issue view $(git branch --show-current | grep -o '[0-9]\+')
```

### 2. Permission Verification

Confirm you have: write, run scripts, commit, branch, push/read PR permissions

### 3. Specification Development

Create specification in `./spec/` folder:

```bash
# Create spec directory if it doesn't exist
mkdir -p spec
# Create spec file
touch spec/<feature-name>.md
```

**Spec Requirements:**

- Specify end-user functionality, development process, and recommended technology
- Include comprehensive BDD tests (Behavior-driven, NOT unit tests)
- Include 'live' integration test specifications against actual stack
- MUST NOT include actual code implementation
- MAY suggest function signatures and input/output types
- Break into sub-specs for separately mergeable units if needed

```bash
# Commit the spec
git add spec/
git commit -m "spec: Add specification for <feature-name>"

# Fix IDE diagnostics and commit if needed
git add .
git commit -m "fix: Address IDE diagnostics in spec"
```

### 4. Spec Branch Creation

```bash
git checkout -b spec/<feature-name>
git push -u origin spec/<feature-name>
```

### 5. BDD Test Implementation

```bash
# Implement BDD tests based on spec
git add tests/
git commit -m "test: Add BDD tests for <feature-name>"
```

### 6. Test Validation (Red Phase)

```bash
# Run tests to verify they fail (expected behavior)
npm test # or pytest, etc.
git add .
git commit -m "test: Verify BDD tests fail without implementation"
```

### 7. Integration Test Implementation

```bash
# Check environment setup
./scripts/check-env.sh
# Implement integration tests
git add .
git commit -m "test: Add integration tests for <feature-name>"
```

### 8. Test Branch PR

```bash
gh pr create --base spec/<feature-name> --title "test: BDD and integration tests for <feature-name>" --body "Adds comprehensive test suite as specified in spec/<feature-name>.md"
```

### 9. Implementation Branch

```bash
git checkout -b impl/<feature-name>
git push -u origin impl/<feature-name>
```

**Red/Green/Refactor Cycle:**

```bash
# RED: Implement minimal code to make tests pass
git add .
git commit -m "feat: Initial implementation (red phase)"

# GREEN: Make tests pass
git add .
git commit -m "feat: Complete implementation (green phase)"

# REFACTOR: Clean up code
git add .
git commit -m "refactor: Clean up implementation"
```

### 10. Coverage Enhancement

```bash
# Ensure 100% BDD test coverage
npm run test:coverage # or equivalent
git add .
git commit -m "test: Achieve 100% BDD coverage"
```

### 11. Implementation PR

```bash
gh pr create --base <test-branch> --title "feat: Implementation for <feature-name>" --body "Implements functionality specified in spec/<feature-name>.md with full test coverage"
```

### 12. Integration Test Verification

```bash
# Run full integration test suite
./scripts/check-env.sh && npm run test:integration
```

### 13. PR Merge

```bash
# Squash and merge PR into test branch
gh pr merge --squash
```

### 14. Repeat Process

For additional specs, return to step 3.

## Execution Guidelines for CLAUDE

- Use `TodoWrite` tool to track progress through workflow steps
- Always check current branch and git status before proceeding
- Run IDE diagnostics check after each significant change
- Verify test commands exist before running (check package.json, Makefile, etc.)
- Use `gh` commands for all GitHub operations
- Commit messages should follow conventional commit format
- Ask for clarification if environment setup scripts don't exist

## Required Repository Permissions

Add to `.claude/permissions.md` or equivalent:

```markdown
## Workflow Permissions
- allow: git checkout, commit, push, branch operations
- allow: gh issue view, pr create, pr merge
- allow: npm/python/script execution for testing
- allow: file creation in spec/, test/, src/ directories
```

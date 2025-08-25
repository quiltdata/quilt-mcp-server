# WORKFLOW.md

Standardized Workflow for processing GitHub issues (as a precursor to full automation).

## Prerequisites

Ensure you have sufficient permissions:
- Write access to repository
- Ability to run scripts
- Commit permissions
- Branch creation permissions
- Push/read PR permissions

## Workflow Steps

1. **Retrieve the GitHub Issue for this branch**
   ```bash
   gh issue view <issue_number>
   ```

2. **Ensure you have sufficient permissions**: write, run scripts, commit, branch, push/read PR

3. **Write a spec in the ./spec folder**
   - Specs should specify the end-user functionality, development process, and recommended technology
   - Must include comprehensive BDD tests (Behavior, NOT unit test implementation)
   - Must also include a 'live' integration test against an actual stack
   - They MUST NOT include actual code; save that for implementation
   - They MAY suggest function signatures and input/output types
   - If necessary, break spec into sub-specs for separately mergeable units (e.g. pre-factoring)
   - Commit the spec
   - Fix IDE Diagnostics. Commit.

4. **Create a branch for the (first) spec**
   ```bash
   git checkout -b spec/<feature-name>
   ```

5. **Implement the BDD tests** (commit)

6. **Verify the tests run and fail due to the missing functionality** (commit)

7. **Implement the integration tests and run** (use check-env script to warn if environment not configured)

8. **Create a PR for the tests** (against spec branch)

9. **Create a branch for the implementation**: Red / Green / Refactor (commit each step)
   ```bash
   git checkout -b impl/<feature-name>
   ```

10. **Increase coverage to 100% on the BDD** (commit)

11. **Create PR for the implementation** (against test branch)

12. **Verify integration tests pass**

13. **Squash PR into test branch**

14. **Repeat for additional specs**

## Notes

- Each commit should be atomic and represent a single logical change
- Always run tests before committing
- Fix IDE diagnostics immediately after making changes
- Use descriptive commit messages that explain the "why" not just the "what"
- Integration tests should use the check-env script to validate environment configuration
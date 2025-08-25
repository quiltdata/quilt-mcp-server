# WORKFLOW.md

Standardized workflow for processing GitHub issues.

## Process Overview

1. **Analyze GitHub issue** for this branch
2. **Create specification** in `./spec/` folder with:
   - End-user functionality requirements
   - BDD test specifications (behavior, not implementation)
   - Integration test requirements against actual stack
   - No actual code implementation
3. **Create spec branch** (`spec/<feature-name>`)
4. **Implement BDD tests** that fail without implementation
5. **Create test PR** against spec branch
6. **Create implementation branch** (`impl/<feature-name>`)
7. **Follow Red/Green/Refactor TDD cycle**
8. **Achieve 100% BDD coverage**
9. **Create implementation PR** against test branch
10. **Verify integration tests pass**
11. **Merge with squash**
12. **Repeat for additional specs**

## Requirements

- Specifications must be behavior-focused, not implementation-focused
- All tests must be written before implementation
- Integration tests must run against actual stack
- Use conventional commit messages
- Fix IDE diagnostics after changes
- Track progress with TodoWrite tool

# WORKFLOW.md

Standardized workflow for processing GitHub issues.

## Process Overview

1. Analyze GitHub issue for this branch (usually the numeric prefix)
   1. Ask the user if anything is unclear
   1. Ensure you have sufficient permissions for the necessary actions
   1. Create a short, safe "feature-name" to use for child branches
1. Create specification in `./spec/` folder with:
   - End-user functionality requirements
   - BDD test specifications (behavior, not implementation)
   - Integration test requirements against actual stack
   - Any relevant non-functional requirements
   - No actual code implementation
1. Plan Pre-Factoring
   - "Make the change easy, so you can make the easy change"
   - For non-trivial changes, break the spec into sub-specs using the Prefactoring meta-pattern
1. Investigation phase – resolve open issues in the specification:
   - Research existing solutions and tools (as required by NFR5)
   - Investigate technical unknowns and implementation questions
   - Validate assumptions through proof-of-concept research
   - Update specification with findings and concrete implementation paths
1. Push and create initial PR for the first spec
   1. Implement BDD tests that fail due to missing implementation
   1. Write "live" integration tests (ensure we have right .env config to )
   1. Commit and push
1. Start implementation
   1. Follow Red/Green/Refactor TDD cycle
   1. Commit each step of the way
   1. Achieve 100% BDD coverage
   1. Push
   1. Review PR for errors or comments, and resolve them.
1. Start integration testing
   1. Verify integration tests run
   1. Ensure integration tests pass
   1. Push
1. Update PR description, with inline test results and links to key documents, to streamline human review
1. Repeat for additional subspecs, if any

## Requirements

- Specifications must be behavior-focused, not implementation-focused
- All tests must be written before implementation
- Integration tests must run against actual stack
- Use conventional commit messages
- Fix IDE diagnostics after changes
- Track progress with TodoWrite tool

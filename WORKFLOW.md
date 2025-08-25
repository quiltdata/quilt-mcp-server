# WORKFLOW.md

Standardized workflow for processing GitHub issues.

## Process Overview

1. Create a TODO for yourself to ensure you follow this ENTIRE workflow process.
   1. **Delegate to sub-agents early** for complex workflows (>5 steps) to prevent context loss
1. **Phase 1: Investigation** (Use `research-analyst` sub-agent)
   1. Analyze GitHub issue for this branch (usually the numeric prefix)
   1. **Critical**: Evaluate existing repository scripts and patterns FIRST
   1. Ask the user if anything is unclear
   1. Ensure you have sufficient permissions for the necessary actions
   1. Create a short, safe "feature-name" to use for child branches
1. **Phase 2: Specification** (Use `business-analyst` sub-agent)
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
1. **Phase 3: Test Implementation** (Use `qa-expert` sub-agent)
   1. Push and create initial PR for the first spec
   1. Implement BDD tests that fail due to missing implementation
   1. Write "live" integration tests (ensure we have right .env config)
   1. Commit and push
1. **Phase 4: Feature Implementation** (Use `code-reviewer` sub-agent for TDD)
   1. Start implementation
      1. Follow Red/Green/Refactor TDD cycle
      1. Commit each step of the way
      1. Achieve 100% BDD coverage
      1. Push
      1. Review PR for errors or comments, and resolve them.
1. **Phase 5: Integration & Validation** (Use `qa-expert` sub-agent)
   1. Start integration testing
      1. Verify integration tests run
      1. Ensure integration tests pass
      1. Push
1. **Phase 6: PR Management** (Use `code-reviewer` sub-agent)
   1. Update PR description, with inline test results and links to key documents, to streamline human review
1. **Repeat** for additional subspecs, if any

## Sub-Agent Delegation Strategy

**Automatic Delegation**: Sub-agents are invoked automatically based on phase context and task requirements
**Manual Override**: Use explicit delegation when you need specialized focus: "Use the research-analyst sub-agent to..."
**Context Preservation**: Each sub-agent maintains isolated context to prevent spillover and ensure predictable execution
**Orchestration**: Main agent coordinates between phases and reviews sub-agent deliverables

## Requirements

- Specifications must be behavior-focused, not implementation-focused
- All tests must be written before implementation
- Integration tests must run against actual stack
- Use conventional commit messages
- Fix IDE diagnostics after changes
- Track progress with TodoWrite tool

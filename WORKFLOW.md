# WORKFLOW.md

Standardized workflow for processing GitHub issues.

## Process Overview

**PRIMARY WORKFLOW ORCHESTRATION**: Use the `workflow-orchestrator` sub-agent to manage the entire process flow, state transitions, and coordination between phases. This ensures reliable execution of complex multi-phase workflows.

1. **Workflow Initialization**
   1. Delegate entire workflow to `workflow-orchestrator` sub-agent for process management
   1. Each agent MUST a TODO for itself to ensure it follows this ENTIRE workflow process
   1. **Workflow-orchestrator handles all phase transitions and state management**

2. **Phase 1: Investigation** (Orchestrated via `research-analyst` sub-agent)
   1. Analyze GitHub issue for this branch (usually the numeric prefix)
   1. **Critical**: Evaluate existing repository scripts and patterns FIRST
   1. Ask the user if anything is unclear
   1. Ensure you have sufficient permissions for the necessary actions

3. **Phase 2: Specification** (Orchestrated via `business-analyst` sub-agent)
   1. **Cross-Validation**: Verify `research-analyst` findings are complete and accurate
      - Confirm all investigation requirements from Phase 1 are satisfied
      - Validate that technical unknowns have been properly researched
      - Ensure existing patterns and tools have been appropriately identified
   1. Create specification in `./spec/<issue-number>/` folder with:
      - End-user functionality requirements
      - BDD test specifications (behavior, not implementation)
      - Integration test requirements against actual stack
      - Any relevant non-functional requirements
      - No actual code implementation
      - All scratch documents, investigation notes, and working documents within the issue folder
   1. Plan Pre-Factoring
      - "Make the change easy, so you can make the easy change"
      - For non-trivial changes, break the spec into sub-specs using the Prefactoring meta-pattern
   1. Investigation phase – resolve open issues in the specification:
      - Research existing solutions and tools (as required by NFR5)
      - Investigate technical unknowns and implementation questions
      - Validate assumptions through proof-of-concept research
      - Update specification with findings and concrete implementation paths

4. **Phase 3: Test Implementation** (Orchestrated via `qa-expert` sub-agent)
   1. **Cross-Validation**: Validate that `business-analyst` specifications are testable and complete
      - Confirm all BDD scenarios are properly defined and testable
      - Verify integration test requirements are feasible and complete  
      - Ensure all functional and non-functional requirements have corresponding test coverage
      - Flag any untestable or ambiguous requirements for clarification
   1. Push and create initial PR for the first spec
   1. Implement BDD tests that fail due to missing implementation
   1. Write "live" integration tests (ensure we have right .env config)
   1. Commit and push

5. **Phase 4: Feature Implementation** (Orchestrated via `code-reviewer` sub-agent for TDD)
   1. **Cross-Validation**: Verify that `qa-expert` tests properly cover all specification requirements
      - Confirm all BDD scenarios from specification have corresponding tests
      - Verify integration tests cover all specified integration points
      - Ensure test suite will properly validate the implementation when complete
      - Check that tests follow TDD principles and will drive implementation correctly
   1. Start implementation
      1. Follow Red/Green/Refactor TDD cycle
      1. Commit each step of the way
      1. Achieve 100% BDD coverage
      1. Push
      1. Review PR for errors or comments, and resolve them.

6. **Phase 5: Integration & Validation** (Orchestrated via `qa-expert` sub-agent)
   1. **Cross-Validation**: Validate that `code-reviewer` implementation meets all specification requirements
      - Confirm all functional requirements from specification are implemented
      - Verify all non-functional requirements are satisfied
      - Ensure all BDD scenarios pass with the implementation
      - Check that integration points work as specified
      - Validate error handling meets specification requirements
   1. Start integration testing
      1. Verify integration tests run
      1. Ensure integration tests pass
      1. Push

7. **Phase 6: PR Management** (Orchestrated via `code-reviewer` sub-agent)
   1. **Cross-Validation**: Verify that all previous phases' requirements have been satisfied
      - Confirm investigation findings were properly addressed
      - Verify specification requirements are fully implemented
      - Ensure all test requirements are satisfied with 100% coverage
      - Validate integration and validation results meet specification
      - Check that all cross-phase requirements are satisfied
   1. Update PR description, with inline test results and links to key documents, to streamline human review

8. **Repeat** for additional subspecs, if any

## Sub-Agent Delegation Strategy

**Primary Orchestration**: The `workflow-orchestrator` sub-agent manages the entire workflow process, handling:

- State machine implementation for workflow phases
- Error compensation and retry logic
- Transaction management across phases
- Process coordination and handoffs between specialist sub-agents

**Specialist Sub-Agents**: Each phase delegates to domain experts:

- `research-analyst`: Investigation and information gathering
- `business-analyst`: Requirements analysis and specification creation  
- `qa-expert`: Test implementation and validation
- `code-reviewer`: Implementation review and TDD guidance

**Cross-Validation Requirements**: Each sub-agent MUST validate previous phases' work:

- `business-analyst` MUST verify `research-analyst` findings are complete and accurate
- `qa-expert` MUST validate that `business-analyst` specifications are testable and complete
- `code-reviewer` MUST verify that `qa-expert` tests properly cover all specification requirements
- `qa-expert` (Phase 5) MUST validate that `code-reviewer` implementation meets all specification requirements
- `code-reviewer` (Phase 6) MUST verify that all previous phases' requirements have been satisfied

**Validation Checkpoints**: At each phase transition, the receiving sub-agent must:
1. Review all artifacts from previous phases
2. Identify any gaps, inconsistencies, or missing requirements
3. Flag issues for correction before proceeding
4. Confirm all requirements from their domain expertise are satisfied

**Context Preservation**: Each sub-agent maintains isolated context to prevent spillover and ensure predictable execution
**Error Handling**: Workflow-orchestrator provides systematic error recovery and rollback capabilities
**Observable Execution**: All workflow state transitions are tracked and visible for debugging and monitoring

## Requirements

- Specifications must be behavior-focused, not implementation-focused
- All tests must be written before implementation
- Integration tests must run against actual stack
- Use conventional commit messages
- Fix IDE diagnostics after changes
- Track progress with TodoWrite tool

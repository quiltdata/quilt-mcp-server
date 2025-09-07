# AI Agent Guide for IRS/DSCO Methodology

**Foundation**: Implements [Accountability-Driven Development (ADD)](https://ihack.us/2025/08/22/add-the-beat-accountability-driven-development-in-an-ai-world/) principles - "autonomy with accountability" through structured phases and binary review gates.

**Complete Methodology**: See [spec/112/02-specifications.md](./112/02-specifications.md) for full IRS/DSCO specification.

## Critical Requirements

- **Each document lives in separate branch/PR** for binary approval
- **Historical documents are immutable** - no post-completion edits
- **Use TodoWrite tool** for progress tracking
- **Follow TDD cycle** for implementation phases
- **Run `make test` and `make lint`** before phase completion

## Quick Reference: IRS/DSCO Process

1. **I**ssue - Problem identification and GitHub issue tracking
1. **R**equirements - User stories, acceptance criteria, success metrics
1. **S**pecifications - Engineering constraints, technical goals (NO implementation details)
1. **/** - Divide into Phases (separate branches and PRs for binary review)
1. **D**esign - Phase-specific technical design documents  
1. **S**tage - Implementation with TDD and staged commits
1. **C**hecklist - Validation procedures and progress tracking
1. **O**rchestrator - Process coordination and dependency management

## Integrated IRS/DSCO Workflow

### Step 0: Create GitHub Issue

🤖 **AI Agent**: Create GitHub issue for problem identification
- Document problem scope and business impact
- Identify stakeholders and affected systems
- Establish tracking number for IRS/DSCO process
- Link to any related issues or PRs

👤 **Human Review**: Validate issue scope and priority
- Confirm problem statement accuracy
- Approve priority and milestone assignment
- Authorize IRS/DSCO process initiation
- **Branch**: Create `spec/{issue-number}` for IRS phase

---

## IRS Phase (Analysis)

### Step 1: Requirements Analysis

🤖 **AI Agent**: Create [01-requirements.md](./100/01-requirements.md)
```
Using the GitHub issue from Step 0, create requirements document following IRS/DSCO methodology:

- Reference the GitHub issue number and problem statement
- Expand the issue description into detailed user stories: "As a [role], I want [functionality] so that [benefit]"
- Convert issue scope into numbered acceptance criteria
- Build on issue context for high-level implementation approach (no technical details)
- Define measurable success criteria based on issue impact

Format as markdown with clear sections and numbered lists.
```

👤 **Human Review**: Validate problem understanding and acceptance criteria
- Verify user stories capture actual needs
- Confirm acceptance criteria are measurable
- Approve or request revisions
- **Binary approval required** - clear "yes/no" decision

### Step 2: Engineering Specifications

🤖 **AI Agent**: Create [02-specifications.md](./100/02-specifications.md)
```
Using the requirements document from Step 1, create specifications document following IRS/DSCO methodology:

- Reference the acceptance criteria from 01-requirements.md
- Transform user stories into current state analysis with quantitative metrics
- Convert acceptance criteria into proposed target state with specific measurable goals
- Break down the implementation approach from requirements into detailed phases
- Derive success metrics from the requirements success criteria (quantitative and qualitative)
- Assess risks based on requirements complexity and constraints
- Map requirements dependencies to technical dependencies

EXCLUDE: Implementation code, detailed procedures, technology-specific details.
Format as markdown with clear sections and numbered lists.
```

👤 **Human Review**: Confirm engineering approach and success metrics
- Validate technical feasibility
- Approve phase breakdown strategy
- Confirm success metrics are appropriate
- **Branch**: Create `impl/{feature-name}` for DSCO phase
- **Binary approval required** - clear "yes/no" decision

---

## DSCO Phase (Implementation)

### Step 3: Implementation Phases

For each implementation phase (repeat as needed):

🤖 **AI Agent**: Create Design Document ([03-phase1-design.md](./100/03-phase1-design.md), [05-phase2-design.md](./100/05-phase2-design.md), [07-phase3-design.md](./100/07-phase3-design.md))
```
Using the specifications document from Step 2, create phase-specific design document following IRS/DSCO methodology:

- Reference the specific phase from the implementation phases breakdown in 02-specifications.md
- Design technical architecture to meet the target state goals for this phase
- Make design decisions that address the constraints and dependencies identified in specifications
- Create implementation strategy that aligns with the success metrics from specifications
- Plan integration points with other phases as outlined in the phase breakdown
- Justify technology choices against the risk assessment and constraints from specifications

Focus on "what" and "how" for this specific phase, grounded in specifications.
Format as markdown with clear sections.
```

👤 **Human Review**: Approve technical architecture and implementation strategy
- Validate design decisions
- Confirm integration approach
- Approve technology choices
- **Use specialized agents**: workflow-orchestrator for complex phases
- **Binary approval required** before implementation

🤖 **AI Agent**: Create Checklist Document ([04-phase1-checklist.md](./100/04-phase1-checklist.md), [06-phase2-checklist.md](./100/06-phase2-checklist.md), [08-phase3-checklist.md](./100/08-phase3-checklist.md))
```
Using the design document from this phase, create validation checklist following IRS/DSCO methodology:

- Break down the implementation strategy from the design into granular tasks with [ ] status tracking
- Create validation procedures that verify each design decision is properly implemented
- Define testing requirements that validate the architecture and integration points from design
- Establish quality gates that confirm success metrics from specifications are met
- Link back to original GitHub issue and reference acceptance criteria from requirements

Use checkbox format for trackable progress.
Format as markdown with task lists.
```

🤖 **AI Agent**: Implement with TDD following design
```
Using the design document for this phase, implement following TDD:

- Write failing tests for each design component first
- Implement minimum code to pass tests
- Refactor while keeping tests green
- Use TodoWrite tool for granular progress tracking
- Commit with format: "feat: implement {component} from phase{N} design"
- Run `make test`, `make lint`, and IDE diagnostics after each change
```

👤 **Human Review**: Code quality, testing, and functionality validation
- Review implementation against design
- Validate test coverage and quality
- Confirm functionality meets requirements
- **Use code-reviewer agent** for complex validation
- **All tests must pass** before approval
- **100% coverage required** for implementation
- Approve phase completion

### Step 4: Final Integration

🤖 **AI Agent**: Process coordination and final integration
```
Using all completed phase checklists from Step 3, coordinate final integration:

- Verify all checkboxes are completed across all phase checklists
- Validate that implementation meets all acceptance criteria from 01-requirements.md
- Confirm all success metrics from 02-specifications.md are achieved
- Test integration points identified in all design documents
- Prepare release documentation referencing original GitHub issue resolution
```

👤 **Human Review**: Final approval and release authorization
- Complete system validation
- Approve for production deployment
- Document lessons learned
- **All quality gates must pass** before release

---

## Appendix

### Specialized Agent Usage

**workflow-orchestrator**: Complex multi-phase implementations, dependency management, process coordination

**research-analyst**: Problem investigation, requirements gathering, technology research

**business-analyst**: User story creation, acceptance criteria, success metrics, business value

**code-reviewer**: Implementation validation, architecture review, security assessment

### Anti-Deception Framework

- Concrete artifacts for review (no "trust me" implementations)
- Atomic change units (one PR per phase/document)
- Branch isolation (specs cannot be modified during implementation)
- Immutable specifications (historical accuracy preserved)

### Tools and Commands

- `make test` - Run all tests including DXT validation
- `make lint` - Code formatting and type checking
- `make coverage` - Test coverage reporting
- `gh` commands - GitHub operations
- `TodoWrite` tool - Progress tracking

### Commit Patterns

- **Spec commits**: "docs: add {phase} documentation for issue #{N}"
- **Implementation commits**: Follow TDD cycle with conventional commits
- **Review commits**: "review: complete phase {N} validation"
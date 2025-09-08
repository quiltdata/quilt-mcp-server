# IRS/DSCO Methodology Implementation Guide

**Foundation**: Implements [Accountability-Driven Development (ADD)](https://ihack.us/2025/08/22/add-the-beat-accountability-driven-development-in-an-ai-world/) principles through the IRS/DSCO structured development process.

**Universal Patterns**: See [AGENTS.md](./AGENTS.md) for core AI collaboration principles that underlie this methodology.

**Complete Specification**: See [spec/112/02-specifications.md](./112/02-specifications.md) for detailed IRS/DSCO methodology specification.

## IRS/DSCO Process Overview

**IRS Phase (Analysis)**:
1. **I**ssue - Problem identification and GitHub issue tracking
2. **R**equirements - User stories, acceptance criteria, success metrics  
3. **S**pecifications - Engineering constraints, technical goals (NO implementation details)

**/** - **Divide into Phases** (separate branches and PRs for binary review)

**DSCO Phase (Implementation)**:
4. **D**esign - Phase-specific technical design documents
5. **S**tage - Implementation with BDD and staged commits  
6. **C**hecklist - Validation procedures and progress tracking
7. **O**rchestrator - Process coordination and dependency management

## Document Structure Pattern

**Sequential numbering for chronological phases**:
- `01-requirements.md` - Problem definition and acceptance criteria
- `02-specifications.md` - Engineering constraints and success metrics
- `{x}-phase{N}-design.md` - Phase N technical design (x = 2N+1)
- `{x+1}-phase{N}-checklist.md` - Phase 1 validation and tracking
- `{M}-review.md` - Implementation review and lessons learned

## Initiate IRS/DSCO Workflow

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
- **Branch**: Use GitHub to create `{issue-number}-short-name` for IRS phase
- Open in Editor / Agenta (typically VS Code + Claude Code)

---

### Step 1: Requirements Analysis

🤖 **AI Agent**: Create [01-requirements.md](./100/01-requirements.md) using a Business Analyst or Product Owner agent (ideally with product/market/customer context)
```
Using the GitHub issue from Step 0, create requirements document following IRS/DSCO methodology in @spec/WORKFLOW.md:

- Reference the GitHub issue number and problem statement
- Expand the issue description into detailed user stories: "As a [role], I want [functionality] so that [benefit]"
- Convert issue scope into numbered acceptance criteria
- Build on issue context for high-level implementation approach (no technical details)
- Define measurable success criteria based on issue impact
- Identify "Open Questions" for relevant information you cannot inver

Format as markdown with clear sections and numbered lists. Fix IDE Diagnostics.
```

👤 **Human Review**: Validate problem understanding and acceptance criteria
- Address Open Questions
- Verify user stories capture actual needs
- Confirm acceptance criteria are measurable
- Approve, edit or request revisions before initaiting next step

### Step 2: Engineering Specifications

🤖 **AI Agent**: Create [02-specifications.md](./100/02-specifications.md) using an appropriate architecture or developer agent. 
```
Using the requirements document from Step 1, create specifications document following the IRS/DSCO methodology in @spec/WORKFLOW.md:

- Reference the acceptance criteria from 01-requirements.md
- Propose implementation architecture consistent with the current repository
- Write high-level specs describing the ideal end state (NO Implementation details)
- Perform gap-analysis against current repository state
- Identify "pre-factoring" opportunities: make the change easy, then make the easy change
- Break implementation down into Phases that can be sequentially reviewed and merged
- Do NOT write the actual implementation or any code samples (at most: signatures)
- Identify technical (architectural, algorithmic, dependency) uncertainties and risks

EXCLUDE: Implementation code, detailed procedures.
Format as markdown with clear sections and numbered lists.
```

👤 **Human Review**: Confirm engineering approach and success metrics
- Validate technical feasibility
- Approve phase breakdown strategy
- Confirm success metrics are appropriate
- Approve, edit or request revisions before initaiting next step

---

### Step 3: Implementation Phases

For each implementation phase (repeat as needed):

#### Step 3a: Create Design Document

Examples:

- [03-phase1-design.md](./100/03-phase1-design.md)
- [05-phase2-design.md](./100/05-phase2-design.md)
- [07-phase3-design.md](./100/07-phase3-design.md)

🤖 **AI Agent**: Create Design Document using a developer agent with the relevant skills

```
Using the specifications document from Step 2, create phase-specific design document following the IRS/DSCO methodology in @spec/WORKFLOW.md:

- Reference the specific phase from the implementation phases breakdown in 02-specifications.md
- Design technical architecture to meet the target state goals for this phase
- Make design decisions that address the constraints and dependencies identified in specifications
- Create implementation strategy that aligns with the success metrics from specifications
- Plan integration points with other phases as outlined in the phase breakdown
- Justify technology choices against the risk assessment and constraints from specifications

Focus on "what" and "how" for this specific phase, grounded in specifications.
Format as markdown with clear sections. Fix IDE Diagnostics.
```

👤 **Human Review**: Approve technical architecture and implementation strategy
- Validate design decisions
- Confirm integration approach
- Approve technology choices
- Commit design document, then create a NEW child branch and PR for implementation

#### Step 3b: Create Design Document

Examples:

- [04-phase1-checklist.md](./100/04-phase1-checklist.md)
- [06-phase2-checklist.md](./100/06-phase2-checklist.md)
- [08-phase3-checklist.md](./100/08-phase3-checklist.md)

🤖 **AI Agent**: Create Checklist Document using a developer agent with the relevant skills

```
Using the design document from this phase, create validation checklist following the IRS/DSCO methodology in @spec/WORKFLOW.md:

- Break down the implementation strategy from the design into granular tasks with [ ] status tracking
- Create validation procedures that verify each design decision is properly implemented
- Define testing requirements that validate the architecture and integration points from design
- Establish quality gates that confirm success metrics from specifications are met
- Link back to original GitHub issue and reference acceptance criteria from requirements

Use checkbox format for trackable progress.
Format as markdown with task lists. Fix IDE Diagnostics.
```

#### Step 3b: Implement with BDD following design

🤖 **AI Agent**: Implement with BDD following design
```
Using the design document for this phase, implement following BDD:

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
- **Implementation commits**: Follow BDD cycle with conventional commits
- **Review commits**: "review: complete phase {N} validation"
# IRS/DSCO Methodology Implementation Guide

**Foundation**: Implements [Accountability-Driven Development (ADD)](https://ihack.us/2025/08/22/add-the-beat-accountability-driven-development-in-an-ai-world/) principles through the IRS/DSCO structured development process.

**Universal Patterns**: See [AGENTS.md](./AGENTS.md) for core AI collaboration principles that underlie this methodology.

**Complete Specification**: See [spec/112/02-specifications.md](./112/02-specifications.md) for detailed IRS/DSCO methodology specification.

**Examples**: See `./spec/100/*.md` for real-world examples of each document

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

#### 🤖 Issue Prompt (to Agent)

**AI Agent**: Create GitHub issue for problem identification
- Document problem scope and business impact
- Identify stakeholders and affected systems
- Establish tracking number for IRS/DSCO process
- Link to any related issues or PRs

#### 👤 Issue Review (by Human)

**Human Review**: Validate issue scope and priority
- Confirm problem statement accuracy
- Approve priority and milestone assignment
- Authorize IRS/DSCO process initiation
- **Branch**: Use GitHub to create `{issue-number}-short-name` for IRS phase
- Open in Editor / Agenta (typically VS Code + Claude Code)

---

### Step 1: Requirements Analysis

#### 🤖 Requirements Prompt (to Agent)

> Create `spec/{issue_number}/01-requirements.md` using a Business Analyst or Product Owner agent, following the Requirements Instructions in Step 1 of @spec/WORKFLOW.md

#### 📝 Requirements Instructions (for Agent)

Using the GitHub issue from Step 0, create requirements document following IRS/DSCO methodology:

- Reference the GitHub issue number and problem statement
- Expand the issue description into detailed user stories: "As a [role], I want [functionality] so that [benefit]"
- Convert issue scope into numbered acceptance criteria
- Build on issue context for high-level implementation approach (no technical details)
- Define measurable success criteria based on issue impact
- Identify "Open Questions" for relevant information you cannot infer

Format as markdown with clear sections and numbered lists. Fix IDE Diagnostics.

#### 👤 Requirements Review (by Human)

Validate problem understanding and acceptance criteria
- Address Open Questions
- Verify user stories capture actual needs
- Confirm acceptance criteria are measurable
- Approve, edit or request revisions before initiating next step

---

### Step 2: Engineering Specifications

#### 🤖 Specification Prompt (to Agent)

> Create `spec/{issue_number}/02-specifications.md` using an appropriate architecture or developer agent, following the Specification Instructions in Step 2 of @spec/WORKFLOW.md

#### 📝 Specification Instructions (for Agent)

Using the requirements document from Step 1, create a specifications document that:

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

#### 👤 Specification Review (by Human)

Confirm engineering approach and success metrics
- Validate technical feasibility
- Approve phase breakdown strategy
- Confirm success metrics are appropriate
- Approve, edit or request revisions before initiating next step

---

### Step 3: Implementation Phases

For each implementation phase (repeat as needed):

#### Step 3a: Create Design Document

##### 🤖 Design Prompt (to Agent)

> Create `spec/{issue_number}/{n}-phase{k}-design.md` using a developer agent with the relevant skills, following the Design Instructions in Step 3a of @spec/WORKFLOW.md

##### 📝 Design Instructions (for Agent)

Using the specifications document from Step 2, create phase-specific design document following the IRS/DSCO methodology:

- Reference the specific phase from the implementation phases breakdown in 02-specifications.md
- Design technical architecture to meet the target state goals for this phase
- Make design decisions that address the constraints and dependencies identified in specifications
- Create implementation strategy that aligns with the success metrics from specifications
- Plan integration points with other phases as outlined in the phase breakdown
- Justify technology choices against the risk assessment and constraints from specifications

Focus on "what" and "how" for this specific phase, grounded in specifications.
Format as markdown with clear sections. Fix IDE Diagnostics.

##### 👤 Design Review (by Human)

Approve technical architecture and implementation strategy
- Validate design decisions
- Confirm integration approach
- Approve technology choices
- Commit design document, then create a NEW child branch and PR for implementation

#### Step 3b: Create Checklist Document

##### 🤖 Checklist Prompt (to Agent)

> Create:
> 1. a new branch `{issue-number}-short-name/{n}-phase{k}`
> 2. a`spec/{issue_number}/{n+1}-phase{k}-checklist.md`  Checklist Document using a project manager agent with the relevant skills, following the Checklist Instructions in Step 3b of @spec/WORKFLOW.md (then commit + push)
> 3. a PR for the new branch against the original branch

##### 📝 Checklist Instructions (for Agent)

Using the design document from this phase, create validation checklist following the IRS/DSCO methodology:

- Break down the implementation strategy into coherent Stages that can be iteratively committed, pushed, and tested
- Break each stage into granular tasks with [ ] status tracking
- Create validation procedures that verify each design decision is properly implemented
- Define Behavior-Driven Development (BDD) requirements that validate the architecture and integration points from design
  - Do NOT write any code in this document
  - Do concisely itemize critical test cases 
- Establish quality gates that confirm success metrics from specifications are met
- Link back to original GitHub issue and reference acceptance criteria from requirements

Use checkbox format for trackable progress.
Format as markdown with task lists. Fix IDE Diagnostics.

##### 👤 Checklist Review (by Human)

Approve checklist and validation procedures
- Confirm tasks and validation steps are comprehensive
- Approve, edit or request revisions before implementation

#### Step 3c: Implement with BDD following design

##### 🤖 Implementation Prompt (to Agent)

> Implement with BDD following design, using the Implementation Instructions in Step 3c of @spec/WORKFLOW.md and an Orchestrator agent.

##### 📝 Implementation Instructions (for Agent)

Using the design document for this phase, implement following BDD:

- Use TodoWrite tool for granular progress tracking (unless Agent has another mechanism)
- Write any scratch documents in the `spec/{issue_number}/` folder
- Write failing behavior-driven tests for each design component first (using same methodology as existing tests)
  - Test the expected behavior, NOT the implementation details
- Commit failing tests before beginning implementation
- Implement minimum code to pass tests
  - Clearly annotate if/when/why you had to modify tests after the fact
- Commit and push to PR, address any issues
- Refactor while keeping tests green
- Commit with format: "feat: implement {component} from phase{N} design"
- After each major change:
  - Run `make test`
  - Run `make lint`
  - Fix IDE diagnostics
  - Update Checklist
  - Commit and push
  - Fix PR errors, address/reply to PR comments; repeat if necessary
- When implementation appears done:
  - Ensure checklist is a) updated, and b) accurate
  - Check coverage, increase to 85%+
  - Resolve any outdated PR comments
  - Update the PR description to facilitate Review

##### 👤 Implementation Review (by Human)

Code quality, testing, and functionality validation

- Ensure checklist is completed
- Review implementation against design
- Validate test coverage and quality
- Confirm functionality meets requirements
- Merge PR into feature branch

---

### Step 4: Final Integration

#### 🤖 Integration Prompt (to Agent)

> Process coordination and final integration, following the Integration Instructions in Step 4 of @spec/WORKFLOW.md

#### 📝 Integration Instructions (for Agent)

Using all completed phase checklists from Step 3, coordinate final integration:

- Verify all checkboxes are completed across all phase checklists
- Validate that implementation meets all acceptance criteria from 01-requirements.md
- Confirm all success metrics from 02-specifications.md are achieved
- Test integration points identified in all design documents
- Prepare release documentation referencing original GitHub issue resolution

#### 👤 Integration Review (by Human)

Final approval and release authorization
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
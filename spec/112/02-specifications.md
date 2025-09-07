# Specifications: IRS/DSCO Process Documentation

**Issue**: [#112 - IRS/DSCO](https://github.com/quiltdata/quilt-mcp-server/issues/112)  
**Based on**: [01-requirements.md](./01-requirements.md)
**Type**: Process Documentation Specification
**Priority**: Medium

## Process Specification: IRS/DSCO Methodology

### Core Methodology Definition

The IRS/DSCO methodology implements **Accountability-Driven Development (ADD)** principles for AI-assisted software development. It provides "autonomy with accountability" by creating structured phases where AI can contribute effectively while maintaining human oversight and trust.

**Foundation**: Based on ADD's BPM Trinity (Branch/Phase/Meta-pattern), this methodology addresses the core challenge: "in the age of AI, accountability is the bottleneck."

**Acronym Breakdown** (ADD-aligned):
1. **I**ssue - Problem identification and tracking (accountability scope)
2. **R**equirements - User expectations and acceptance criteria (human validation)
3. **S**pecifications - Engineering goals and constraints (trust boundaries)
4. **/** - Divide into Phases (separate branches and PRs for binary review)
5. **D**esign - Phase-specific design documents (technical accountability)
6. **S**tage - Implementation staging and execution (commit and test each unit)
7. **C**hecklist - Validation and testing procedures (quality gates)
8. **O**rchestrator - Process coordination via Orchestration agent (AI autonomy with oversight)

### Document Structure Pattern

Based on analysis of spec/100 reference implementation, the IRS/DSCO methodology follows this document pattern:

#### Analysis Phase (IRS)
1. **01-requirements.md** - Problem statement, user stories, acceptance criteria
2. **02-specifications.md** - Engineering goals, constraints, success metrics (WITHOUT implementation details)

#### Implementation Phase (DSCO)  
3. **{i}-phase{N}-design.md** - Technical design for specific implementation phase
4. **{i}-phase{N}-checklist.md** - Validation procedures and implementation tracking
5. **{i}-phase{N}-progress.md** - Progress tracking and status updates (as needed)
6. **{i}-review.md** - Phase completion analysis and lessons learned

### File Organization Principles

#### Numbering Convention
- **Sequential numbering** (01, 02, 03...) for chronological phases
- **Descriptive names** indicating phase and document type
- **Consistent markdown format** (.md for all documentation)

#### Directory Structure (example)
```
spec/{issue-number}/
├── 01-requirements.md           # Problem definition and acceptance criteria
├── 02-specifications.md         # Engineering constraints and success metrics
├── 03-phase1-design.md          # Phase 1 technical design
├── 04-phase1-checklist.md       # Phase 1 validation and tracking
├── 05-phase2-design.md          # Phase 2 technical design  
├── 06-phase2-checklist.md       # Phase 2 validation and tracking
├── 07-phase3-design.md          # Phase 3 technical design
├── 08-phase3-checklist.md       # Phase 3 validation and tracking
├── 09-review.md                 # Implementation review
├── 10-phase3a-checklist.md      # Additional phase validation (if needed)
├── 11-improvements.md           # Identified improvements
├── 12-final-checklist.md        # Complete validation
└── 13-release.md                # Release documentation
```

### Phase Workflow Specification

#### Analysis Phase
- **Issue Identification**: Document problem scope, stakeholders, business impact
- **Requirements Gathering**: Define user expectations, acceptance criteria, success metrics
- **Specification Writing**: Engineering constraints, technical goals, validation criteria
- **Specification Review**: Ensure completeness before implementation begins

#### Implementation Phase  
- **Design Documentation**: Technical approach, architecture decisions, implementation strategy
- **Staged Implementation**: Break complex features into manageable phases
- **Validation Checklists**: Comprehensive testing and quality assurance procedures
- **Progress Tracking**: Regular status updates and milestone verification
- **Process Coordination**: Orchestrate workflow stages and manage dependencies

### Document Content Specifications

#### Requirements Document (01)
**Must Include**:
- Problem statement with business context
- User story format: "As a [role], I want [functionality] so that [benefit]"
- Acceptance criteria (numbered list)
- Implementation approach (high-level only)
- Success criteria (measurable outcomes)

#### Specifications Document (02)
**Must Include**:
- Current state analysis with quantitative metrics
- Proposed target state with specific measurable goals
- Implementation plan broken into phases
- Success metrics (quantitative and qualitative)
- Risk assessment and mitigation strategies
- Dependencies and external requirements

**Must NOT Include**:
- Actual implementation code
- Detailed implementation procedures
- Technology-specific implementation details

#### Design Documents (03, 05, 07...)
**Must Include**:
- Phase-specific technical design
- Architecture decisions and rationale
- Implementation strategy for that phase
- Integration points with other phases
- Technology choices and justification

#### Checklist Documents (04, 06, 08...)
**Must Include**:
- Granular implementation tasks with status tracking
- Validation procedures for each task
- Testing requirements and success criteria
- Quality gates and milestone verification
- Issue tracking and resolution status

### Documentation Standards

#### Writing Guidelines
- **Clear and actionable language** - avoid ambiguous terms
- **Numbered lists** for acceptance criteria and success metrics
- **Consistent formatting** across all documents
- **Quantitative metrics** where possible (percentages, counts, timelines)
- **Reference links** between related documents

#### Version Control
- Documents are **historical records** - do not update after completion
- Each document represents the state of knowledge at time of creation
- Create new documents for iterations rather than updating existing ones
- Use git commits to track document evolution

### Process Coordination

#### Human Developer Usage
- Follow documents sequentially for systematic approach
- Use checklists to track progress and ensure completeness
- Reference specifications to validate implementation decisions
- Review completed phases to inform future work

#### AI Agent Usage  
- spec/AGENTS.md should be symbolically linked to CLAUDE.md for accessibility
- AI agents should reference methodology for structured problem-solving
- Use TodoWrite tool to track progress through workflow phases
- Follow same document patterns for consistency

### Integration with Development Workflow (ADD BPM Trinity)

#### Branch Strategy (Accountability Unit)
- **Specification branches**: `spec/{issue-number}` for analysis phase
- **Implementation branches**: `impl/{feature-name}` for development phase  
- **Binary review process**: Each branch gets clear "yes/no" approval
- **Smallest unit of accountability**: Each AI-generated work lives in its own branch/PR

#### Phase Strategy (Work Cadence)
1. **Spec Phase**: Intent description and requirements (IRS documents)
2. **Test Phase**: Executable specifications and BDD tests
3. **Implementation Phase**: Code writing with staged commits
4. **Validation Phase**: User acceptance and quality verification

#### Meta-pattern (Prefactoring)
- **Test → Refactor → Implement** sequence for stable foundations
- **Prepare ground before feature implementation**
- **Quality gates** at each phase transition
- **Comprehensive validation** documented in checklists

### Success Criteria for IRS/DSCO Implementation

#### Process Documentation
- Complete specification of IRS/DSCO methodology
- Clear phase definitions and document templates
- Integration with existing development workflow
- Reference implementation available in spec/100

#### Usability Requirements
- **Human accessible** - developers can follow methodology independently
- **AI accessible** - AI agents can reference and apply methodology
- **Minimal and concise** - easy to scan and understand quickly
- **Actionable prompts** - clear triggers for each phase

#### Quality Standards
- **Systematic approach** to complex problem breakdown
- **Comprehensive validation** at each development stage
- **Clear documentation** and progress tracking
- **Template consistency** for future feature development

## Dependencies and Constraints

### External Dependencies
- GitHub issue tracking for problem identification
- Git version control for document evolution
- Existing development tools and workflow integration

### Internal Dependencies  
- CLAUDE.md symbolic link for AI agent accessibility
- WORKFLOW.md integration for branch strategy
- TodoWrite tool usage for progress tracking
- BDD testing framework for validation

### Process Constraints
- Documents must be created in sequential order
- Specifications must be complete before implementation begins
- Each phase requires validation before proceeding to next phase
- Historical documents should not be modified after completion

## Notes

This specification defines the **what** and **structure** of the IRS/DSCO methodology without prescribing specific implementation tools or technologies. The methodology implements Accountability-Driven Development (ADD) principles to address the fundamental challenge: **"in the age of AI, accountability is the bottleneck."**

**Key ADD Principles Implemented**:
- **Autonomy with Accountability**: AI can contribute within structured phases with human oversight
- **Binary Review Process**: Clear "yes/no" decisions on AI-generated work
- **Phase-based Cadence**: Structured workflow that maintains trust and quality
- **Prefactoring Meta-pattern**: Prepare foundations before implementation

Reference implementation available in spec/100 demonstrates practical application of this methodology for repository cleanup and makefile consolidation project.

**Further Reading**: [Add the Beat: Accountability-Driven Development in an AI World](https://ihack.us/2025/08/22/add-the-beat-accountability-driven-development-in-an-ai-world/)
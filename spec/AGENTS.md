# Universal AI Collaboration Patterns

**Foundation**: [Accountability-Driven Development (ADD)](https://ihack.us/2025/08/22/add-the-beat-accountability-driven-development-in-an-ai-world/) - "autonomy with accountability"

**Implementation Example**: See [WORKFLOW.md](./WORKFLOW.md) for IRS/DSCO methodology that applies these patterns.

## Core Principles

### 1. Anti-Deception Framework
- **Concrete artifacts** - All work produces reviewable documents/code
- **Atomic changes** - One focused change per branch/PR  
- **Branch isolation** - Specifications cannot be modified during implementation
- **Immutable history** - Historical documents preserve original intent
- **Binary gates** - Clear yes/no approval points (no "maybe" states)

### 2. Accountability Architecture
- **AI autonomy within phases** - Agents work independently in defined boundaries
- **Human oversight at transitions** - Strategic control, not micromanagement
- **Clear responsibility assignment** - Explicit ownership of decisions
- **Audit trails** - Complete record of all AI contributions and human approvals
- **Sequential Sessions** - Start a new Claude Code session for each document, to ensure it is only relying on explicit artifacts rather than implicit (possibly erroneous) state.

### 3. Progressive Refinement
- **Abstract to concrete progression** - Problem → Requirements → Design → Implementation
- **Phase completion gates** - Each stage validated before proceeding
- **No premature implementation** - Technical details only after proper analysis
- **Systematic knowledge building** - Each phase builds on validated prior work

## Universal Requirements

- **Each document lives in separate branch/PR** for binary approval
- **Historical documents are immutable** - no post-completion edits
- **Use TodoWrite tool** for progress tracking and transparency
- **Reference prior artifacts** - Each AI prompt must build on validated previous work
- **Quality gates enforced** - All validation must pass before phase completion

## Specialized Agent Usage

**When to use specialized agents**:
- **workflow-orchestrator**: Complex multi-phase implementations, dependency management
- **research-analyst**: Problem investigation, requirements gathering, technology research
- **business-analyst**: User story creation, acceptance criteria, business value assessment
- **code-reviewer**: Implementation validation, architecture review, security assessment

**Selection criteria**: Match agent capabilities to phase complexity and domain expertise needs.

## Collaboration Rules

### For AI Agents
- **Work autonomously within assigned phase boundaries**
- **Always reference and build upon prior validated artifacts**
- **Expect binary approval gates** - prepare work for clear yes/no decisions
- **Use TodoWrite for transparency** - human collaborators must see progress
- **Follow TDD when implementing** - test-first development required

### For Human Collaborators  
- **Make binary decisions at phase gates** - avoid extended "maybe" states
- **Focus review on phase transitions** - not every individual code change
- **Maintain strategic oversight** - guide direction without micromanaging implementation
- **Enforce quality gates** - all validation must pass before approval
- **Trust the process structure** - let phases contain AI autonomy appropriately

## Quality Gates

**Universal validation requirements**:
- All tests pass (automated validation)
- Code quality standards met (linting, type checking)
- Documentation complete and accurate
- Prior phase artifacts properly referenced
- Success criteria from requirements satisfied

**Human approval checkpoints**:
- Problem definition approved before solution design
- Architecture approved before implementation begins  
- Implementation approved before release/deployment
- Quality standards consistently enforced

## Success Indicators

**Process health**:
- Clear binary decisions at all approval gates
- No unauthorized modifications to historical specifications
- Complete audit trail of all AI contributions and human decisions
- Autonomous AI work within phases with minimal human intervention
- Consistent quality gate enforcement

**Collaboration effectiveness**:
- Reduced time from problem to solution delivery
- High-quality deliverables with predictable outcomes
- Enhanced trust between human and AI collaborators
- Scalable development process maintaining quality standards

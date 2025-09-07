# Agent Guide for Spec-Driven Development

**Foundation**: [Accountability-Driven Development (ADD)](https://ihack.us/2025/08/22/add-the-beat-accountability-driven-development-in-an-ai-world/) - "autonomy with accountability"

**Full Guide**: See [WORKFLOW.md](./WORKFLOW.md) for complete IRS/DSCO workflow and prompts.

## Critical Requirements

- **Each document lives in separate branch/PR** for binary approval
- **Historical documents are immutable** - no post-completion edits
- **Use TodoWrite tool** for progress tracking
- **Follow TDD cycle** for implementation phases
- **Run `make test` and `make lint`** before phase completion

## IRS/DSCO Process

**IRS Phase (Analysis)**:
1. **I**ssue → GitHub issue (branch: `spec/{issue-number}`)
2. **R**equirements → [01-requirements.md](./100/01-requirements.md) (user stories, acceptance criteria)
3. **S**pecifications → [02-specifications.md](./100/02-specifications.md) (engineering goals, NO implementation)

**DSCO Phase (Implementation)**:
4. **D**esign → [0X-phaseN-design.md](./100/03-phase1-design.md) (branch: `impl/{feature-name}`)
5. **S**tage → TDD implementation with TodoWrite tracking
6. **C**hecklist → [0X-phaseN-checklist.md](./100/04-phase1-checklist.md) (validation tasks)
7. **O**rchestrator → Final integration and release

## Key Rules

- **Each AI prompt MUST reference prior artifacts** (not just dependencies)
- **Binary human approval required** at each phase gate
- **Use specialized agents**: workflow-orchestrator (complex phases), code-reviewer (validation)
- **All quality gates must pass** before phase completion

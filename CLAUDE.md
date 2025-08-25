# Development Guidelines for Claude

## Core Philosophy

**TEST-DRIVEN DEVELOPMENT IS NON-NEGOTIABLE.** Every single line of production code must be written in response to a failing test. No exceptions. This is not a suggestion or a preference - it is the fundamental practice that enables all other principles in this document.

I follow Test-Driven Development (TDD) with a strong emphasis on behavior-driven testing and functional programming principles. All work should be done in small, incremental changes that maintain a working state throughout development.

## Quick Reference

**Key Principles:**

- Write tests first (TDD)
- Test behavior, not implementation
- Small, pure functions
- Use real schemas/types in tests, never redefine them

**Preferred Tools:**

- **Language**:Python 
- **State Management**: Prefer immutable patterns

## Testing Principles

### Behavior-Driven Testing

- **No "unit tests"** - this term is not helpful. Tests should verify expected behavior, treating implementation as a black box
- Test through the public API exclusively - internals should be invisible to tests
- No 1:1 mapping between test files and implementation files
- Tests that examine internal implementation details are wasteful and should be avoided
- **Coverage targets**: 100% coverage should be expected at all times, but these tests must ALWAYS be based on business behaviour, not implementation details
- Tests must document expected business behaviour


### Test Organization

```
src/
  features/
    payment/
      payment-processor.py
      payment-validator.py
      payment-processor.test.py // The validator is an implementation detail. Validation is fully covered, but by testing the expected business behaviour, treating the validation code itself as an implementation detail
```

### Test Data Pattern

Use factory functions with optional overrides for test data:

- Single-parameter pure functions
- Well-established functional patterns (map, filter, reduce callbacks)
- Mathematical operations where order is conventional

## Development Workflow

### Spec-Driven Development (aligned with WORKFLOW.md)

Before any implementation begins:

1. **Create specification** in `./spec/` folder:
   - Specify end-user functionality, development process, and recommended technology
   - Include comprehensive BDD tests (Behavior-driven, NOT unit tests)
   - Include 'live' integration test specifications against actual stack
   - MUST NOT include actual code implementation
   - MAY suggest function signatures and input/output types
   - Break into sub-specs for separately mergeable units if needed

2. **Branch strategy**:
   - `spec/<feature-name>` for specifications
   - `impl/<feature-name>` for implementation
   - PRs: tests against spec branch, implementation against test branch

### TDD Process - THE FUNDAMENTAL PRACTICE

**CRITICAL**: TDD is not optional. Every feature, every bug fix, every change MUST follow this process:

Follow Red-Green-Refactor strictly (aligned with WORKFLOW.md steps 6, 9, 10):

1. **Red**: Write a failing test for the desired behavior. NO PRODUCTION CODE until you have a failing test.
   - Commit: `"test: Add BDD tests for <feature-name>"`
   - Verify tests fail: `"test: Verify BDD tests fail without implementation"`
   
2. **Green**: Write the MINIMUM code to make the test pass. Resist the urge to write more than needed.
   - Initial: `"feat: Initial implementation (red phase)"`  
   - Complete: `"feat: Complete implementation (green phase)"`
   
3. **Refactor**: Assess the code for improvement opportunities. If refactoring would add value, clean up the code while keeping tests green.
   - Commit: `"refactor: Clean up implementation"`
   - Coverage: `"test: Achieve 100% BDD coverage"`

**Common TDD Violations to Avoid:**

- Writing production code without a failing test first
- Writing multiple tests before making the first one pass
- Writing more production code than needed to pass the current test
- Skipping the refactor assessment step when code could be improved
- Adding functionality "while you're there" without a test driving it

**Remember**: If you're typing production code and there isn't a failing test demanding that code, you're not doing TDD.



### Refactoring - The Critical Third Step

Evaluating refactoring opportunities is not optional - it's the third step in the TDD cycle. After achieving a green state and committing your work, you MUST assess whether the code can be improved. However, only refactor if there's clear value - if the code is already clean and expresses intent well, move on to the next test.

#### What is Refactoring?

Refactoring means changing the internal structure of code without changing its external behavior. The public API remains unchanged, all tests continue to pass, but the code becomes cleaner, more maintainable, or more efficient. Remember: only refactor when it genuinely improves the code - not all code needs refactoring.

#### When to Refactor

- **Always assess after green**: Once tests pass, before moving to the next test, evaluate if refactoring would add value
- **When you see duplication**: But understand what duplication really means (see DRY below)
- **When names could be clearer**: Variable names, function names, or type names that don't clearly express intent
- **When structure could be simpler**: Complex conditional logic, deeply nested code, or long functions
- **When patterns emerge**: After implementing several similar features, useful abstractions may become apparent

**Remember**: Not all code needs refactoring. If the code is already clean, expressive, and well-structured, commit and move on. Refactoring should improve the code - don't change things just for the sake of change.

#### Refactoring Guidelines

##### 1. Commit Before Refactoring

Always commit your working code before starting any refactoring. This gives you a safe point to return to:

```bash
git add .
git commit -m "feat: add payment validation"
# Now safe to refactor
```

##### 2. Look for Useful Abstractions Based on Semantic Meaning

Create abstractions only when code shares the same semantic meaning and purpose. Don't abstract based on structural similarity alone - **duplicate code is far cheaper than the wrong abstraction**.



**Questions to ask before abstracting:**

- Do these code blocks represent the same concept or different concepts that happen to look similar?
- If the business rules for one change, should the others change too?
- Would a developer reading this abstraction understand why these things are grouped together?
- Am I abstracting based on what the code IS (structure) or what it MEANS (semantics)?

**Remember**: It's much easier to create an abstraction later when the semantic relationship becomes clear than to undo a bad abstraction that couples unrelated concepts.

##### 3. Understanding DRY - It's About Knowledge, Not Code

DRY (Don't Repeat Yourself) is about not duplicating **knowledge** in the system, not about eliminating all code that looks similar.



##### 4. Maintain External APIs During Refactoring

Refactoring must never break existing consumers of your code:


##### 5. Verify and Commit After Refactoring

**CRITICAL**: After every refactoring:

1. Run all tests - they must pass without modification
2. Run static analysis (linting, type checking) - must pass
3. Commit the refactoring separately from feature changes



#### Refactoring Checklist

Before considering refactoring complete, verify:

- [ ] The refactoring actually improves the code (if not, don't refactor)
- [ ] All tests still pass without modification
- [ ] All static analysis tools pass (linting, type checking)
- [ ] No new public APIs were added (only internal ones)
- [ ] Code is more readable than before
- [ ] Any duplication removed was duplication of knowledge, not just code
- [ ] No speculative abstractions were created
- [ ] The refactoring is committed separately from feature changes


```

### Commit Guidelines

- Each commit should represent a complete, working change
- Use conventional commits format:
  ```
  feat: add payment validation
  fix: correct date formatting in payment processor
  refactor: extract payment validation logic
  test: add edge cases for payment validation
  ```
- Include test changes with feature changes in the same commit

### Pull Request Standards

- Every PR must have all tests passing
- All linting and quality checks must pass
- Work in small increments that maintain a working state
- PRs should be focused on a single feature or fix
- Include description of the behavior change, not implementation details

## Working with Claude

### Expectations

When working with my code:

1. **ALWAYS FOLLOW TDD** - No production code without a failing test. This is not negotiable.
2. **Use TodoWrite tool** - Track progress through workflow steps, especially for complex tasks (see WORKFLOW.md)
3. **Think deeply** before making any edits
4. **Understand the full context** of the code and requirements
5. **Ask clarifying questions** when requirements are ambiguous
6. **Think from first principles** - don't make assumptions
7. **Assess refactoring after every green** - Look for opportunities to improve code structure, but only refactor if it adds value
8. **Keep project docs current** - update them whenever you introduce meaningful changes
   **At the end of every change, update CLAUDE.md with anything useful you wished you'd known at the start**.
   This is CRITICAL - Claude should capture learnings, gotchas, patterns discovered, or any context that would have made the task easier if known upfront. This continuous documentation ensures future work benefits from accumulated knowledge

### Code Changes

When suggesting or making changes:

- **Start with a failing test** - always. No exceptions.
- After making tests pass, always assess refactoring opportunities (but only refactor if it adds value)
- After refactoring, verify all tests and static analysis pass, then commit
- Respect the existing patterns and conventions
- Maintain test coverage for all behavior changes
- Keep changes small and incremental
- Provide rationale for significant design decisions

**If you find yourself writing production code without a failing test, STOP immediately and write the test first.**

### WORKFLOW.md Execution Guidelines

When following the standardized workflow:

- **Always check current branch and git status** before proceeding with any step
- **Run IDE diagnostics check** after each significant change and commit fixes immediately
- **Verify test commands exist** before running (check package.json, Makefile, etc.)
- **Use `gh` commands for all GitHub operations** (issue view, pr create, pr merge)
- **Follow conventional commit format** for all commits
- **Ask for clarification** if environment setup scripts don't exist (./scripts/check-env.sh)
- **Use issue analysis command**: `gh issue view $(git branch --show-current | grep -o '[0-9]\+')`
- **Create proper branch hierarchy**: spec/<feature> → test branch → impl/<feature>

### Communication

- Be explicit about trade-offs in different approaches
- Explain the reasoning behind significant design decisions
- Flag any deviations from these guidelines with justification
- Suggest improvements that align with these principles
- When unsure, ask for clarification rather than assuming

## Summary

The key is to write clean, testable, functional code that evolves through small, safe increments. Every change should be driven by a test that describes the desired behavior, and the implementation should be the simplest thing that makes that test pass. When in doubt, favor simplicity and readability over cleverness.

## Pre-approved Commands

Claude Code has permission to run the following commands without asking:

### Makefile Targets (Recommended)

```bash
# Environment Setup
make check-env              # Validate .env configuration

# Phase Commands
make app                    # Phase 1: Run local MCP server
make build                  # Phase 2: Build Docker container  
make catalog                # Phase 3: Push to ECR registry
make deploy                 # Phase 4: Deploy to ECS Fargate

# Validation Commands (SPEC-compliant)
make validate               # Validate all phases sequentially
make validate-app           # Validate Phase 1 only
make validate-build         # Validate Phase 2 only
make validate-catalog       # Validate Phase 3 only
make validate-deploy        # Validate Phase 4 only

# Testing Commands
make test-app               # Phase 1 testing only
make test-build             # Phase 2 testing only
make test-deploy            # Phase 4 testing only
make coverage               # Run tests with coverage (fails if <85%)

# Verification Commands (MCP Endpoint Testing)
make verify-app             # Verify Phase 1 MCP endpoint
make verify-build           # Verify Phase 2 MCP endpoint
make verify-catalog         # Verify Phase 3 MCP endpoint
make verify-deploy          # Verify Phase 4 MCP endpoint

# Initialization Commands (Precondition Checks)
make init-app               # Check Phase 1 preconditions
make init-build             # Check Phase 2 preconditions
make init-catalog           # Check Phase 3 preconditions
make init-deploy            # Check Phase 4 preconditions

# Cleanup Commands
make clean                  # Clean build artifacts
make zero-app               # Stop Phase 1 processes
make zero-build             # Stop Phase 2 containers
make zero-catalog           # Stop Phase 3 containers
make zero-deploy            # Disable Phase 4 endpoint (preserve stack)

# Utilities
make status                 # Show deployment status
make destroy                # Clean up AWS resources
```

### Direct Phase Scripts (Alternative)

```bash
# Phase 1: App (Local MCP Server)
./app/app.sh run
./app/app.sh test
./app/app.sh coverage
./app/app.sh validate
./app/app.sh clean

# Phase 2: Build-Docker (Containerization)
./build-docker/build-docker.sh build
./build-docker/build-docker.sh test
./build-docker/build-docker.sh run
./build-docker/build-docker.sh validate
./build-docker/build-docker.sh clean

# Phase 3: Catalog-Push (ECR Registry)
./catalog-push/catalog-push.sh push
./catalog-push/catalog-push.sh pull
./catalog-push/catalog-push.sh test
./catalog-push/catalog-push.sh login
./catalog-push/catalog-push.sh validate

# Phase 4: Deploy-AWS (ECS/ALB Deployment)
./deploy-aws/deploy-aws.sh deploy
./deploy-aws/deploy-aws.sh test
./deploy-aws/deploy-aws.sh status
./deploy-aws/deploy-aws.sh validate
./deploy-aws/deploy-aws.sh destroy
```

### Shared Utilities

```bash
# Environment and validation
./shared/validate.sh all
./shared/validate.sh app
./shared/validate.sh build
./shared/validate.sh catalog
./shared/validate.sh deploy

# MCP endpoint testing
./shared/test-endpoint.sh -p app -t
./shared/test-endpoint.sh -p build -t
./shared/test-endpoint.sh -p catalog -t
./shared/test-endpoint.sh -p deploy -t
```

### Docker Operations

```bash
# Docker commands for ECS deployment
docker build --platform linux/amd64 -t quilt-mcp:* -f build-docker/Dockerfile .
docker run --rm -p 8000:8000 quilt-mcp:*
docker run --rm -p 8001:8000 quilt-mcp:*  # Phase 2 testing
docker run --rm -p 8002:8000 quilt-mcp:*  # Phase 3 testing
docker tag quilt-mcp:* *
docker push *
docker pull *
docker images quilt-mcp
docker rmi quilt-mcp:*
docker stop *
docker logs *
docker inspect *
```

### Testing & Validation

```bash
# Unit and integration testing
uv run python -m pytest app/tests/ -v
uv run python -m pytest app/tests/ --cov=quilt_mcp --cov-report=term-missing --cov-fail-under=85

# MCP endpoint testing
curl -X POST http://localhost:8000/mcp -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
curl -X POST http://localhost:8001/mcp -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
curl -X POST http://localhost:8002/mcp -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

### AWS Operations

```bash
# CDK operations (from deploy-aws/)
cd deploy-aws && uv run cdk deploy --require-approval never --app "python app.py"
cd deploy-aws && uv run cdk destroy --app "python app.py"
cd deploy-aws && uv run cdk bootstrap --app "python app.py"
cd deploy-aws && uv run cdk synth --app "python app.py"
cd deploy-aws && uv run cdk diff --app "python app.py"

# CloudFormation & AWS CLI
aws cloudformation describe-stacks --stack-name QuiltMcpFargateStack --region *
aws cloudformation describe-stack-resources --stack-name QuiltMcpFargateStack --region *
aws sts get-caller-identity

# ECS & ECR operations
aws ecs describe-clusters --cluster *
aws ecs describe-services --cluster * --services *
aws ecs list-tasks --cluster *
aws ecs describe-tasks --cluster * --tasks *
aws ecr describe-repositories
aws ecr describe-images --repository-name *
aws ecr get-login-password --region * | docker login --username AWS --password-stdin *

# Logs (ECS/ALB)
aws logs tail /ecs/* --follow --region *
aws logs tail /aws/elasticloadbalancing/* --follow --region *
aws logs describe-log-groups
```

### Environment & Dependencies

```bash
# UV package management
uv sync
uv sync --group test
uv run *
uv lock
uv add *
uv remove *

# Python execution
python -c "*"
python app/main.py
python app/tests/test_mcp_response_format.py

# Environment setup
make check-env                              # Validate environment
cp env.example .env                         # Set up environment file
set -a && source .env && set +a            # Load environment
source .env
printenv
echo *
```

### Development Tools

```bash
# Git operations
git status
git diff
git log --oneline -n 10
git add *
git commit -m "*"
git push
git clean -fd
git checkout -b *
git checkout *
git branch *
git merge *

# GitHub CLI operations (for WORKFLOW.md)
gh issue view *
gh issue list
gh pr create --base * --title "*" --body "*"
gh pr list
gh pr merge --squash
gh pr view *

# File operations
find . -name "*.py" -type f
mkdir -p *
mv * *
cp * *
rm -f *
rm -rf *
touch *

# System utilities  
chmod +x */.*sh
ls -la *
head *
tail *
cat *
curl *
grep -r * *

# Process management
timeout * *
sleep *
kill *
pkill *
```

### WORKFLOW.md Specific Permissions

```bash
# Workflow operations (as defined in WORKFLOW.md)
mkdir -p spec/
touch spec/*.md
git checkout -b spec/*
git checkout -b impl/*
git push -u origin spec/*
git push -u origin impl/*

# Test operations
npm test
npm run test:coverage
npm run test:integration
pytest
./scripts/check-env.sh

# Branch and PR operations
gh pr create --base spec/* --title "test: *" --body "*"
gh pr create --base * --title "feat: *" --body "*"
gh pr merge --squash

# Issue analysis
gh issue view $(git branch --show-current | grep -o '[0-9]\+')
```

## Environment Variables

Environment variables are automatically loaded from `.env` and managed by `shared/common.sh`. Use `make check-env` to validate your configuration.

Key variables (see `env.example` for complete list):

- `CDK_DEFAULT_ACCOUNT` - AWS account ID (auto-derived from AWS CLI)
- `CDK_DEFAULT_REGION` - AWS region (default: us-east-1)
- `ECR_REGISTRY` - ECR registry URL (auto-constructed if not set)
- `QUILT_DEFAULT_BUCKET` - S3 bucket for Quilt data
- `QUILT_CATALOG_DOMAIN` - Quilt catalog domain

## Port Configuration

Each phase uses different ports to avoid conflicts:

| Phase | Description | Port | Endpoint |
|-------|-------------|------|----------|
| Phase 1 | Local app | 8000 | `http://127.0.0.1:8000/mcp` |
| Phase 2 | Docker build | 8001 | `http://127.0.0.1:8001/mcp` |
| Phase 3 | ECR catalog | 8002 | `http://127.0.0.1:8002/mcp` |
| Phase 4 | AWS deploy | 443/80 | `https://your-alb-url/mcp` |

## Workflow Documentation

### SPEC-Compliant Validation Workflow

The validation system follows SPEC.md requirements:

1. **Check preconditions**: `make init-<phase>`
2. **Execute phase**: `make <phase>`  
3. **Test artifacts**: `make test-<phase>`
4. **Verify MCP endpoint**: `make verify-<phase>`
5. **Cleanup processes**: `make zero-<phase>`

### Full Pipeline Examples

```bash
# Complete validation (all phases)
make validate

# Individual phase validation
make validate-app
make validate-build  
make validate-catalog
make validate-deploy

# Execution pipeline (no validation)
make app build catalog deploy

# Testing pipeline
make test-app test-build test-deploy
```

### Version Management

All phases use **git SHA** as version tag to prevent skew:

- Local image: `quilt-mcp:abc123f`  
- ECR image: `${ECR_REGISTRY}/quilt-mcp:abc123f`
- ECS service: Deployed with `abc123f`

## Development Server Options

### Local Development

```bash
make app                    # Local server on http://127.0.0.1:8000/mcp
```

### External Access via ngrok

```bash
make remote-export          # Expose local server via ngrok tunnel
```

The `remote-export` command:

- Starts the MCP server locally on port 8000
- Creates an ngrok tunnel with predictable URL: `https://uniformly-alive-halibut.ngrok-free.app`
- MCP endpoint available at: `https://uniformly-alive-halibut.ngrok-free.app/mcp`
- Automatically handles cleanup when stopped with Ctrl+C
- Requires ngrok installation and authtoken configuration

Use `remote-export` for:

- Testing with Claude Desktop from different machines
- Sharing your development server with team members (consistent URL)
- Testing MCP integrations from external services
- Demonstrating MCP functionality remotely

## Security Notes

- All ECS tasks use IAM roles with minimal required permissions
- API endpoints are protected with JWT authentication via ALB
- Docker builds are isolated and use official base images
- No secrets are logged or exposed in responses
- All network traffic goes through ALB with security groups

## Important Instruction Reminders

Do what has been asked; nothing more, nothing less.
NEVER create files unless they're absolutely necessary for achieving your goal.
ALWAYS prefer editing an existing file to creating a new one.
NEVER proactively create documentation files (*.md) or README files. Only create documentation files if explicitly requested by the User.

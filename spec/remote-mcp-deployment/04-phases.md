<!-- markdownlint-disable MD013 -->
# Phases — Remote MCP Server Deployment

## Phase 1 — Discovery & Planning
- Audit AWS `sales-prod` environment (ECS services, ALB, IAM, networking).
- Produce architecture plan for remote MCP deployment (auth, networking, scaling).
- Validate assumptions with stakeholders (frontend, auth, infra).

## Phase 2 — Infrastructure Foundations
- Create Terraform module for MCP service (task definition, service, target group, listener rule, log groups).
- Implement ECR repository setup and integrate with CI image publishing.
- Add health endpoint support to MCP server if required by ALB checks.

## Phase 3 — Integration & Testing
- Configure Quilt frontend to target remote MCP endpoint (dev/staging).
- Implement auth/CORS configuration; test via FastMCP proxy and frontend client.
- Add Terraform tests and smoke tests (possibly using pytest or scripts).

## Phase 4 — Documentation & Release
- Document deployment process, infrastructure parameters, and proxy usage.
- Provide CloudFormation template or guidance for non-Terraform consumers.
- Finalize CLAUDE/AGENTS notes; update INSTALLATION/README as necessary.
- Run end-to-end verification and hand off for review/launch.


<!-- markdownlint-disable MD013 -->
# Phase 2 Design — Infrastructure Foundations

## Objectives
1. Implement Terraform module + supporting resources for MCP service on ECS Fargate.
2. Wire container image publishing (ECR repository, CI integration).
3. Provide health check endpoint and configuration for ALB.

## Key Tasks
- Create `modules/mcp-server` (or similar) with task definition, service, target group, listener rule, SGs, IAM roles, log groups.
- Update `deploy/terraform` entrypoints to consume module for at least one environment.
- Extend CI to ensure ECR repository exists and image tags align with Terraform variables.
- Implement/confirm MCP server health endpoint (e.g., `/healthz`) and expose necessary env vars.
- Update Terraform tests to cover new module (listener host/path, priority, container settings).

## Deliverables
- Terraform module with examples and documentation.
- Updated Terraform tests passing locally and in CI.
- Health endpoint support in application code.
- CI pipeline updates for ECR integration.


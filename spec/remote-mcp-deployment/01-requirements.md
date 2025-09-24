<!-- markdownlint-disable MD013 -->
# Requirements — Remote MCP Server Deployment

## Issue Reference
- GitHub: [#190 – Implement Remote MCP Server Deployment for Quilt Stack Integration](https://github.com/quiltdata/quilt-mcp-server/issues/190)
- Priority: High – enables production availability of the MCP server

## Problem Statement
The Quilt MCP Server currently runs locally or via ad-hoc Docker usage. To serve production users, we need a managed AWS deployment that integrates with the existing Quilt stack (ECS/Fargate, ALB, Terraform modules). The deployment must support HTTP-based MCP transport, Quilt authentication, and observability with minimal operational friction.

## User Stories
1. **As a Quilt platform engineer**, I want to deploy the MCP server alongside existing Quilt services in AWS so that it is reachable by the Quilt frontend without custom local setup.
2. **As a Quilt frontend developer**, I want a stable MCP endpoint with CORS and auth configured so that the web client can invoke MCP tools securely.
3. **As a DevOps engineer**, I want reusable Terraform/CloudFormation modules and clear documentation so that future environments (dev, staging, prod) can adopt the MCP server quickly.
4. **As a security engineer**, I want the MCP deployment to follow AWS best practices (least-privilege IAM, secure networking, health monitoring) so that the new surface does not increase risk.

## Acceptance Criteria
1. Remote MCP server container is deployed to AWS ECS Fargate and reachable through the existing ALB.
2. Terraform module encapsulates the MCP service (task definition, service, security groups, listeners) with environment-specific parameters.
3. Docker image publishing pipeline targets an ECR repository suitable for remote deployment (multi-arch not required initially but amd64 mandatory).
4. Deployment includes health checks, logging to CloudWatch, and integration with Quilt auth/CORS configuration.
5. Documentation explains how to build, publish, deploy, and integrate the remote MCP server, including Claude/HTTP proxy considerations.
6. Automated tests and/or validation scripts cover infrastructure configuration (e.g., Terraform unit tests like `tests/test_terraform_mcp_alb.py`).
7. CloudFormation template (or guidance) exists for consumers not yet on the Terraform stack.

## Constraints & Assumptions
- The MCP server must serve HTTP transport (SSE) on `/mcp/` and accept Quilt authentication tokens.
- Infrastructure must align with existing `sales-prod` conventions (naming, tagging, logging).
- Security groups must restrict access to approved subnets/frontend components.
- Assume AWS credentials are available for CI/CD and manual deployment steps.
- Terraform 1.8+ and AWS provider 5.x are available.
- Claude Desktop still requires a stdio proxy; remote documentation must note this.

## Open Questions
1. What is the canonical domain/host for the remote MCP endpoint (e.g., `mcp.quiltdata.com` vs existing ALB path rule)?
2. Do we need blue/green or canary deployments for MCP updates, or is standard rolling update sufficient?
3. Which Quilt authentication mechanism (cookies, bearer tokens, signed URLs) should the MCP server enforce in production?
4. Does the frontend require additional CORS headers beyond the existing Quilt defaults?
5. Are there compliance requirements (logging retention, IAM boundary) specific to MCP versus existing services?
6. Should we provision staging and production ECR repositories separately?

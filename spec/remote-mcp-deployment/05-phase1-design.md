<!-- markdownlint-disable MD013 -->
# Phase 1 Design — Discovery & Planning

## Objectives
1. Understand current AWS Quilt stack topology relevant to MCP deployment.
2. Identify integration points, constraints, and required configuration inputs.
3. Produce a concrete deployment plan (networking, auth, scaling, observability).

## Key Tasks
- Enumerate existing ECS services, task definitions, target groups, listener rules.
- Capture security group rules and subnet allocations applicable to MCP service.
- Review auth flow between frontend and backend to determine MCP requirements.
- Document required environment variables/secrets for MCP server in production.
- Align with stakeholders (frontend, platform, security) on requirements.

## Deliverables
- Discovery report (could be markdown in repo) summarizing findings.
- Updated open questions resolved or captured for later phases.
- Confirmed list of Terraform inputs/outputs for module design.


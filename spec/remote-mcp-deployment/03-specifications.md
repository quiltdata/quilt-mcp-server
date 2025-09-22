<!-- markdownlint-disable MD013 -->
# Specifications — Remote MCP Server Deployment

## 1. Target Outcomes
1. Remote MCP server runs on AWS ECS Fargate within the existing Quilt VPC, behind the shared ALB.
2. Infrastructure is provisioned via a reusable Terraform module with sensible defaults and overrides.
3. Docker image publishing pipeline aligns with AWS ECR repository naming and tagging conventions.
4. Load balancer listener/target-group rules expose `/mcp/` (or dedicated host+path) with streaming-friendly configuration and health checks.
5. Application integrates with Quilt auth (header/token validation) and emits structured logs to CloudWatch.
6. Documentation guides engineers through build, deploy, proxying, and frontend integration steps.
7. Optional CloudFormation template mirrors the Terraform module for teams still on CFN.

## 2. Architectural Design Principles
1. **Immutable infrastructure**: Container images built via CI, deployed to ECS via Terraform.
2. **Modularity**: New Terraform module should encapsulate MCP-specific resources but reuse shared patterns (logging, service discovery) where possible.
3. **Security by default**: Restrict inbound traffic via security groups and enforce TLS via ALB. IAM roles follow least privilege.
4. **Observability**: Enable CloudWatch logging, metrics, and optionally alarms for unhealthy targets.
5. **Configurability**: Allow environment-specific overrides (image tag, desired count, CPU/memory, auth endpoints) through module variables.
6. **Compatibility**: Ensure SSE/HTTP requirements (idle timeout) are satisfied end-to-end.

## 3. Functional Specifications
1. **Terraform Module**
   - Inputs: VPC ID, subnets, ALB listener ARN, desired count, image URI/tag, CPU/memory, environment variables, log retention, security group IDs.
   - Outputs: Service name, target group ARN, listener rule ID, URL (host/path), CloudWatch log group, IAM role ARNs.
   - Resources: ECS task definition (Fargate), ECS service, target group, listener rule, security groups, CloudWatch log group, IAM execution/task roles, optional Parameter Store entries.
2. **Docker Image Publishing**
   - Extend existing GitHub Actions workflow to push to designated ECR repository (maybe new repository `quilt-mcp-server`).
   - Document manual push/pull instructions for developers.
3. **Application Configuration**
   - Provide environment variables for auth endpoints, allowed origins, `FASTMCP_TRANSPORT=http`, health endpoint binding (expose `/healthz`).
   - Optionally implement a lightweight health handler returning 200 to satisfy ALB health checks.
4. **Frontend Integration**
   - Define canonical endpoint (host/path). Document required headers (auth tokens, Accept) for SSE.
   - Provide guidance for Claude: use FastMCP proxy even when hitting remote endpoint.
5. **CloudFormation**
   - Template references same container image + environment variables; outputs similar to Terraform module.
6. **Testing**
   - Add Terraform tests verifying new module (e.g., target group path, listener priority).
   - Provide smoke test script for remote endpoint (curl with proper Accept header or using FastMCP client).

## 4. Non-Functional Specifications
1. **Performance**: Start with modest Fargate sizing (e.g., 0.5 vCPU / 1GB) and scaling to maintain low latency for SSE connections.
2. **Availability**: At least one task per AZ (>=2 desired tasks recommended). Health checks ensure automatic replacement.
3. **Security**: TLS termination at ALB, enforce HTTPS. IAM roles limit access to required AWS services (S3, Athena etc.).
4. **Reliability**: Deployments via Terraform with versioned image tags. Rollback by reapplying previous tag.
5. **Maintainability**: Clear README/INSTALLATION updates; CLAUDE/AGENTS docs capture proxy pattern.

## 5. Deliverables & Documentation
1. `deploy/terraform/mcp-server.tf` (or module) implementing ECS resources.
2. New Terraform module under `modules/mcp-server` (if aligning with repo structure) + example usage.
3. CloudFormation template (e.g., `deploy/cloudformation/mcp-server.yaml`).
4. Documentation updates (INSTALLATION.md, docs/developer/REPOSITORY.md, CLAUDE.md) covering remote deployment.
5. Terraform tests (existing or new) validating module outputs.
6. CI pipeline adjustments for ECR push and optional Terraform validation.

## 6. Open Risks / Mitigations
1. **Auth integration**: If Quilt auth logic is complex, consider reverse proxy or share auth middleware with other services. Mitigation: collaborate with auth team; add env vars for token validation endpoints.
2. **SSE compatibility**: Ensure ALB idle timeout > MCP session duration. Mitigation: set target group deregistration delay & keepalive settings explicitly.
3. **Operational load**: Provide runbooks/alerts. Mitigation: Document CloudWatch dashboards/log groups.
4. **Cross-repo dependencies**: Changes might span multiple Quilt repos. Mitigation: clearly document dependencies and coordinate merges.


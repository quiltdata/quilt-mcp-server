<!-- markdownlint-disable MD013 -->
# Analysis — Remote MCP Server Deployment

## 1. Current Infrastructure Landscape
1. **Local-only MCP server**: Today the MCP server is run via `uv run` or the new Docker container. No managed AWS deployment exists.
2. **Quilt production stack**: The `sales-prod` environment uses ECS Fargate services behind an Application Load Balancer, managed via Terraform modules (`deploy/terraform`) and CloudFormation remnants.
3. **Existing IaC patterns**:
   - Terraform modules define ECS tasks, ALB listeners/rules, security groups.
   - `tests/test_terraform_mcp_alb.py` already validates ALB wiring for MCP (likely early groundwork).
   - Release tooling publishes artifacts but not container images to a remote registry yet (image publishing added in issue #188; ECR integration must be enabled for remote deployment).
4. **Auth & networking**:
   - Quilt services typically rely on Cognito/Quilt auth layers. The MCP server must validate requests or sit behind an auth-aware proxy.
   - VPC design includes private subnets for services, public subnets for ALB. Security groups restrict inbound traffic.

## 2. Gaps vs Requirements
1. **No remote task definition**: Terraform lacks a module to provision an MCP ECS service.
2. **Container registry**: We have ECR publishing workflow (from previous issue) but need to wire repository names, policies, and Terraform references.
3. **Health checks/CORS**: The MCP server exposes `/mcp/` and 406 errors if Accept header mismatched; ALB health checks must target a dedicated endpoint (maybe add `/healthz`). CORS/auth settings must be enforced at application layer or via ALB headers.
4. **CI/CD**: While GitHub Actions can push images, infrastructure deploy pipeline needs integration (manual Terraform run? automated?).
5. **Documentation**: No remote deployment guide covering AWS setup, proxies, or frontend integration.
6. **Proxy requirement**: Claude and other stdio clients still require a FastMCP proxy; remote docs must reflect that to avoid 406 misunderstandings.

## 3. Risks & Constraints
1. **SSE through ALB**: Must ensure ALB listener supports streaming responses (keep-alive, idle timeout). Need to confirm existing ALB settings.
2. **Auth**: Without proper auth, remote MCP could expose internal tools. Need integration with Quilt auth (likely header/token validation inside MCP server or WAF/ALB rules).
3. **Operational complexity**: Introducing new Terraform modules should align with existing naming conventions to avoid drift.
4. **Testing**: Need automated validation of Terraform (unit tests) plus possibly integration tests hitting remote endpoint (mocked for CI?).
5. **Performance**: MCP requests may be long-lived; Fargate sizing and scaling must account for concurrency.

## 4. Relevant Repositories & Components
1. **This repo**: Houses MCP server code, Terraform tests (`tests/test_terraform_mcp_alb.py`), and docs.
2. **quiltdata/deployment** and **quiltdata/iac**: Likely contain shared modules or pipelines; need to inspect for patterns to reuse (naming, module layout).
3. **quiltdata/quilt**: Frontend code—determine how MCP client is initialized (URL, headers).
4. **quiltdata/enterprise**: May include enterprise-specific configurations needed for auth/compliance.

## 5. Required Integrations & Future-State Considerations
1. **ECR**: Ensure repository is created (maybe via Terraform). CI must push versioned tags consumed by ECS task definitions.
2. **Terraform module**: Provide parameters for image tag, CPU/memory, desired count, env variables (transport, auth endpoints), logging.
3. **CloudFormation**: Provide template for teams not yet on Terraform (maybe referencing same parameters).
4. **Monitoring**: CloudWatch log group, metrics (ALB TargetGroup, ECS Service). Consider alarms if required.
5. **Documentation**: Must cover build->publish->deploy flow, CORS/auth configuration, and local proxy guidance for clients.

## 6. Dependencies & Open Research Items
1. Confirm health endpoint for MCP server; may need to implement a simple `/healthz` route responding 200.
2. Determine authorized audiences and tokens required for production (Quilt auth team input).
3. Evaluate if additional AWS services (Secrets Manager, Parameter Store) are needed for configuration.
4. Verify Terraform test harness to add new tests (maybe expand existing `tests/test_terraform_mcp_alb.py`).


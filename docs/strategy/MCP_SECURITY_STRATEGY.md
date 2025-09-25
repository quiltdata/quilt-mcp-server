# Quilt MCP Server Security & Deployment Strategy

## 1. Business Objectives & Success Criteria
- **Unified experience** – Serve both desktop (stdio/quilt3) and web (JWT/HTTP) MCP clients without cross-contaminating authentication context.
- **Enterprise-ready deployment** – Provide a hardened AWS reference architecture customers can adopt with minimal customisation.
- **Operational confidence** – Deliver auditable logging, clear runbooks, and least-privilege IAM guidance so security teams can approve the service quickly.

**Success metrics**
- < 1% authentication error rate across client types in production.
- Full Terraform/CDK/CloudFormation parity with documented IAM policies consumed by at least one pilot customer.
- All secret values moved to AWS Secrets Manager/SSM with zero plain-text secrets in task definitions.
- Runtime security regression tests (JWT validation, role assumption) passing in CI on every merge.

## 2. Current-State Analysis

| Area | Observations | Gaps |
|------|--------------|------|
| Runtime auth | Contextvars isolate requests (`src/quilt_mcp/runtime_context.py`) and middleware restores env vars after each call (`src/quilt_mcp/utils.py:584`). | Need clearer documentation plus telemetry on context reset failures. |
| Deployment | Terraform module provisions Fargate service behind ALB with logs and health checks (`deploy/terraform/modules/mcp_server`). | Outbound SG open to `0.0.0.0/0`; secrets injected as plaintext env vars. |
| IAM | Task role created with optional inline policy; automatic role assumption uses STS identity tagging (`docs/architecture/AUTHENTICATION_ARCHITECTURE.md:462`). | Lack of vetted sample policies for customer data domains. |
| Tooling | Makefile automates Docker/ECS deployments; tests cover auth edge cases. | No golden-path docs comparing CDK and CloudFormation options. |

## 3. Tool Categories & Authentication Needs

| Tool Category | Primary AWS Services | Auth Path |
|---------------|---------------------|-----------|
| S3 / Package operations (`src/quilt_mcp/tools/buckets.py`, `package_ops.py`) | S3, Quilt API | Prefer JWT runtime claims; fallback to quilt3 session. |
| Governance & Permission discovery (`src/quilt_mcp/services/permission_discovery.py`) | STS, IAM, S3, Glue, Athena | Requires assumed role or task role with elevated IAM; cache results per context. |
| Bearer auth utilities (`src/quilt_mcp/tools/bearer_auth.py`) | Quilt API, GraphQL | Consume runtime access token; disallow operations if runtime context absent. |
| GraphQL search (`src/quilt_mcp/services/graphql_bearer_service.py`) | Quilt GraphQL endpoint | Reuse runtime token; fallback to env only for backward compatibility. |

## 4. Four-Week Phased Implementation Plan

### Week 1 – Baseline hardening
- Migrate JWT/role secrets to AWS Secrets Manager; update Terraform and sample task definition.
- Add SG/NACL guidance for restricted egress.
- Enhance runtime context logging + metrics (success/failure counters).

### Week 2 – Customer deployment deliverables
- Port Terraform module to CDK construct & CloudFormation template with identical parameters.
- Package sample IAM policies and Secrets Manager wiring examples.
- Author runbook covering `/healthz` validation, log inspection, and rollback steps.

### Week 3 – Testing & observability
- Expand integration tests to verify context reset under concurrent load.
- Add CloudWatch dashboards + alarms (auth failures, 5xx responses, unhealthy targets).
- Document positive/negative auth test matrix in implementation spec.

### Week 4 – Pilot & feedback
- Deploy hardened stack in Quilt staging + one pilot customer account using preferred IaC flavor.
- Collect security review feedback; adjust policies, diagrams, docs.
- Finalise success metrics & handoff package (strategy, spec, diagrams, README).

## 5. Security Considerations & Controls
- **Secrets management** – Require Secrets Manager for JWT/signing keys; enforce via Terraform/CDK validation.
- **Least privilege** – Provide curated IAM policy snippets per tool category; encourage customers to scope S3 resources explicitly.
- **Runtime isolation** – Monitor context push/reset operations; fail closed when auth metadata missing.
- **Network controls** – Document recommended ALB/WAF integration and SG egress restrictions.
- **Audit readiness** – Ensure CloudTrail, CloudWatch logs, and ECS Exec usage are captured; align with SOC2 tooling.

## 6. Next Steps & Owners
- **Platform** – Implement Secrets Manager + SG improvements, deliver IaC parity.
- **Security** – Review sample IAM policies, validate WAF/Waiver requirements.
- **Docs** – Maintain architecture strategy bundle (this document, implementation spec, diagram, README) in `docs/strategy/` and `docs/architecture/`.

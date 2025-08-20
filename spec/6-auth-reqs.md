# Authenticating to Quilt's Built-In MCP Server

Here's the real problem I want to solve.  I want the MCP server to assume a specific Role when executing on behalf of any given user.

In the Quilt stack, we rely on the OIDC to "authenticate" the user, but then use our own database to map that onto a role (sometimes with hints from the claims).

This needs to work with generic MCP clients (e.g., Claude.AI and Claude Desktop) and potentially standalone agents (without a GUI).

## Goals

- Allow Quilt services to call tools via an **MCP Server** while preserving Quilt's existing **SSO → user → role** mapping.
- Keep the MCP server **auth‑dumb**: all authentication/authorization decisions happen at the edge; the server only executes after an allow decision.
- Work with **generic MCP clients** (Claude Desktop/AI) and **headless agents** (no GUI).
- Provide **per‑user AWS isolation** by assuming a role **on behalf of the user** for each request.

## Non‑Goals

- Replacing Quilt’s SSO/IdP or existing role mapping logic.
- Embedding OAuth UI into third‑party MCP clients.

## High‑Level Architecture

1. **Front Door (API Gateway HTTP API)**
   - Requires `Authorization: Bearer` tokens; rejects otherwise.
   - Integrates with a **Lambda authorizer** for OIDC/OIDC‑A validation and policy enforcement.
2. **Authorizer**
   - Verifies OIDC token (issuer, signature, `aud`, expiry).
   - Extracts `sub`, `org/tenant`, and optional OIDC‑A claims (agent model, delegation chain, attestation).
   - Performs **DB lookup**: `(sub, tenant, claim hints) → {roleArn, allowedTags, limits}`.
   - Returns **Allow/Deny** and injects upstream headers: `x-decided-role`, `x-source-identity`, `x-session-tags` (JSON), and optional policy context.
3. **MCP Server on Fargate (private)**
   - Reads the headers; calls **STS AssumeRole** with `SourceIdentity=<sub>` and `Tags=<allowedTags>`; uses resulting creds for AWS access during the request.
   - Does **not** make auth decisions; treats missing/invalid headers as 403.
4. **Downstream AWS Resources**
   - Enforce **ABAC** using `aws:PrincipalTag/*` and audit using CloudTrail with `sourceIdentity`.

## Client Authentication Requirements

- **Token required** for every MCP request.
- Support two issuance paths so we can “force SSO” for any client:
  - **Device Authorization Grant** for generic/3rd‑party clients (display verification URI + user code).
  - **Auth Code + PKCE** for first‑party desktop apps (custom URI scheme).
- Tokens must target the MCP audience (e.g., `aud = api://quilt-mcp`).
- (Optional, recommended) **DPoP** support at the gateway for sender‑constrained tokens.

## Authorization & Role Assumption

- Authorizer is the **sole source of truth** for mapping user→role; clients cannot influence the chosen role.
- MCP server must assume only the **role provided** by the authorizer and pass through:
  - `SourceIdentity = user_sub` for end‑to‑end attribution.
  - `Tags = [{Key:"tenant",Value:"…"}, …]` for ABAC.
- **Target role trust policy** must:
  - Allow only the **ECS task role** to `sts:AssumeRole`.
  - Require `sts:TagSession` and restrict **tag keys/values**.
  - Require `sts:SourceIdentity` to be present and well‑formed.
- Session duration defaults 15–30 minutes; configurable per tenant/policy.

## OIDC / OIDC‑A Requirements

- Accept standard OIDC ID/Access tokens.
- If present, consume **OIDC‑A** claims for policy (e.g., delegation chain, agent metadata, attestation evidence).
- No dependency on vendors: claims may be injected at IdP (rules/hooks) or inferred by the authorizer.

## Networking & Deployment

- API Gateway → **VPC Link** → NLB/ALB → **ECS/Fargate** service in private subnets.
- MCP server exposes only private listeners; all traffic must pass through the gateway.
- Optional **mTLS** at custom domain; authorizer receives cert info via headers for additional checks.

## Observability, Audit, and Compliance

- Log all authorizer decisions with `(sub, tenant, roleArn, tags, policyId, requestId)`.
- CloudTrail must show `sourceIdentity=<sub>` on all AWS API calls from assumed roles.
- Emit structured audit events for: login, token issuance/refresh, allow/deny, role assumption, and tool invocation.
- Add metric alarms for deny spikes, STS error rates, and unusual tag distributions.

## Rate‑Limiting & Abuse Controls

- Per‑user and per‑tenant rate limits at the gateway.
- Quotas for MCP operations (e.g., tokens, tool calls, data volume) derived from the DB mapping.
- Content filtering/WAF rules at the gateway before reaching MCP.

## Secrets & Data Handling

- MCP server reads no long‑lived credentials; only STS temp creds.
- Never pass AWS creds via headers; **only** pass the decision (role/tags).
- Encrypt at rest (KMS) and in transit (TLS); restrict environment variables to non‑secrets.

## Availability & Performance

- Authorizer cold start budget: ≤ 250 ms p95 (use provisioned concurrency if needed).
- End‑to‑end auth+route overhead budget: ≤ 500 ms p95.
- Horizontal scaling of Fargate tasks; health checks via ALB/NLB.

## Operations

- Runbooks for: token outages, DB mapping failures, STS throttling, and role trust misconfig.
- Canary to continuously verify: token validation, mapping, role assumption, and ABAC access to a test resource.
- Infrastructure as code (CDK/Terraform) with security reviews for IAM diffs.

## Backwards Compatibility

- If a client cannot do device flow, provide a minimal **Web Portal** to copy a short‑lived token manually (feature‑flagged, disabled by default).

## Open Questions

- Do we want mandatory DPoP or mTLS for all tenants?
- Minimum claim set required by policy (sub, tenant, org)?
- Per‑tool vs per‑tenant roles—where do we draw the boundary?

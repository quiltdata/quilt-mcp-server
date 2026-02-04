# A16: Multiuser Architecture

## Prime Objective

Establish true **single-tenant, multiuser** architecture where each MCP server deployment serves ONE organization
with multiple users, eliminating unnecessary tenant tracking complexity.

## Key Insight

**Each deployment = one tenant (implicit). Only track users (explicit).**

Every Quilt MCP server deployment is a standalone tenant. There's no need to track "which tenant" - it's implicit
in the deployment configuration. We only need to track "which user" for authentication and audit.

## Core Success Criteria

1. **Catalog JWT only** - Use ONLY real Quilt catalog JWTs (with `id`, `uuid`, `exp` claims)
2. **No tenant tracking** - Zero `tenant_id` references in code or top-level docs
3. **Stateless multiuser** - NO workflows, templates, or persistent storage in multiuser mode

## Specifications

- [Spec 17: Multiuser Terminology](./01-multiuser-terminology.md) - Rename multitenant → multiuser
- [Spec 18: Multiuser Implementation](./02-multiuser-implementation.md) - Remove tenant tracking, enforce stateless architecture

## Impact

- ~835 lines of code removed (tenant tracking + cloud storage)
- Simplified context (user ID only, no tenant ID)
- Clear separation: multiuser = stateless, local dev = stateful

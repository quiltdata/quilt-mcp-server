# JWT-Only Authentication Requirements

## Problem Statement

Multiple overlapping authentication paths (quilt3 desktop flow, IAM role headers, bearer validation, unified services) make the MCP server unreliable. We need a single, well-defined JWT authentication mechanism—grounded in the Quilt catalog's enhanced JWT claims—to authorize MCP tools and S3 access.

## User Stories

1. As a Quilt web user, I want to present my enhanced JWT to the MCP server and have it authorize tool access per my Quilt roles and bucket entitlements without any additional prompts.
2. As a platform operator, I want the MCP server to reject requests with missing or invalid JWTs and emit clear diagnostics so we can debug authentication failures rapidly.
3. As an MCP tool developer, I want a single authorization helper that exposes AWS clients and Quilt metadata derived from the JWT claims so that tools can consistently interact with S3 and Quilt APIs.

## Acceptance Criteria

1. Tool endpoints hit without a valid `Authorization: Bearer <token>` header produce a 401 response (health probes remain unauthenticated) and do not attempt alternative auth paths.
2. Valid JWTs are decoded using Quilt's decompression rules (matching `catalog/app/services/jwt-decompression-utils.js`) and the resulting permissions/buckets/roles drive tool authorization.
3. Tool helper functions retrieve boto3 clients configured from JWT-derived AWS credentials (either inline credentials or by assuming the ARN encoded in the token) with no quilt3 or environment fallbacks.
4. Auth middleware and services log structured troubleshooting data (token presence, decode status, permission mismatches) without leaking secrets.
5. Test coverage includes success and failure cases for JWT decoding, permission enforcement, and middleware responses.

## Open Questions

1. Should the MCP server contact Quilt APIs to validate JWT signatures (versus trusting shared secret verification only)?
2. How should temporary AWS credentials be provisioned—embedded in JWT payload, or assumed via role ARN on every request?
3. Do we need per-request caching, or is direct JWT decoding per call acceptable for target throughput?


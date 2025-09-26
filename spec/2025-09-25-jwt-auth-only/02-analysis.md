# JWT-Only Authentication Analysis

## Current State Summary

- `src/quilt_mcp/utils.py` registers FastAPI middleware that attempts bearer validation, role-assumption headers, and quilt3 fallbacks in a single flow.
- `src/quilt_mcp/services/bearer_auth_service.py` already decodes enhanced Quilt JWTs but coexists with `auth_service.py`, `unified_auth_service.py`, and desktop-specific logic.
- Tool helpers (`src/quilt_mcp/tools/auth_helpers.py`) call `UnifiedAuthService`, which tries to detect runtime environment (web, desktop, hybrid) and may return boto3 sessions derived from quilt3 or IAM roles.
- Runtime state is tracked via `runtime_context` but is polluted by multiple schemes (`bearer`, `assume-role`, `desktop`).

## Pain Points

1. **Conflicting Credential Sources**: Tools receive either mocked dicts, quilt3 sessions, or bare environment variables; S3 clients frequently fail due to missing credentials.
2. **Duplicated JWT Logic**: `BearerAuthService` implements decompression akin to Quilt's utilities, while `unified_auth_service` maintains a separate, simplified parser.
3. **Middleware Complexity**: The HTTP middleware mutates environment variables, pushes runtime states, and conditionally assumes IAM roles, making debugging hard.
4. **Testing Fragility**: Existing tests rely on patching multiple services and expect fallback behaviors that contradict the desired JWT-only flow.

## Constraints

- JWT structure and decompression must align with Quilt's implementation (`catalog/app/services/jwt-decompression-utils.js`).
- The MCP server will operate behind HTTP/S (not stdio) for web clients, so middleware must enforce Authorization headers.
- Desktop/quilt3 flows are out of scope; removing them should not break CLI tools that rely on HTTP transport.

## Opportunities

- Collapse authentication around `BearerAuthService`, promoting it to the singular entry point.
- Simplify runtime auth state to carry JWT claims plus derived AWS credentials.
- Provide structured logging/metrics around JWT decode results to ease troubleshooting.
- Introduce focused tests that validate middleware 401 responses, decoded permissions, and S3 client creation.


# 05 - Security & Credentials

**Date:** 2026-02-16  
**Reviewer:** Codex

## Commands Executed

- `grep -r "password|secret|token" src/quilt_mcp/ --exclude-dir=__pycache__ | grep -v test`
- `grep -r "logger.*credential|logger.*token" src/quilt_mcp/`
- `sed -n` review of:
  - `src/quilt_mcp/backends/quilt3_backend_session.py`
  - `src/quilt_mcp/context/request_context.py`
  - `src/quilt_mcp/config.py`
- `rg` scans for:
  - logging patterns around token/secret/auth headers
  - tool parameter annotations (`Annotated`, `Field`)
  - mode isolation controls (`OperationNotSupportedError`, mode flags)

## Security Scan Results

- No obvious hardcoded secrets/credentials found in production code.
- Token/secret/password references are primarily parameter names, auth plumbing, or validation/error messaging.
- `__pycache__` binary hits were excluded from assessment.

## Credential Handling Review

- `quilt3_backend_session.py` logs operational context but does not log credential values.
- JWT middleware logs missing/invalid header conditions without token contents.
- Runtime auth state carries access token in-memory/request-scope, which is expected for auth flow.
- Fallback JWT support from env exists in middleware; this is functional but increases risk if enabled broadly.

## Input Validation Coverage

- Tool/service interfaces include `Annotated[...]` + `Field(...)` constraints/descriptions across major APIs.
- Domain validation is present in backend/session methods (e.g., catalog URL checks).

## SQL Injection / Query Safety

- SQL/Athena execution tools intentionally accept query text from callers.
- No explicit query sanitization layer was observed in this gate.
- Risk classification: **contextual** (expected for query tools, but should be governed by permissions and audit controls).

## Known Vulnerabilities / Risks

1. Fallback JWT env token path can be risky if used outside controlled environments.
2. Query execution endpoints rely on caller-supplied SQL; abuse prevention depends on IAM/workgroup permissions and policy controls.

## Remediation Priority

- **High:** Ensure fallback JWT env usage is disabled/restricted in production deployments.
- **Medium:** Add explicit policy docs/guards for arbitrary SQL execution contexts.
- **Medium:** Consider static checks to prevent future token/header logging regressions.

## Pass/Fail Status

- No hardcoded credentials/secrets: ✅ Pass
- IAM credentials never logged: ✅ Pass
- JWT tokens handled securely (no leakage): ⚠️ Warning (in-memory + fallback env token path)
- Input validation on tool parameters: ✅ Pass
- SQL injection prevention (if applicable): ⚠️ Warning (query APIs accept raw SQL by design)
- Secure defaults for all configurations: ⚠️ Warning (fallback token path should be tightly controlled)
- Credential isolation between modes verified: ✅ Pass (mode gating + `OperationNotSupportedError` checks)

**Section Result:** ⚠️ **Warning**

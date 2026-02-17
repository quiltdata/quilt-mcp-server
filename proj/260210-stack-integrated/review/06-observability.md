# 06 - Observability

**Date:** 2026-02-16  
**Reviewer:** Codex

## Commands Executed

- `grep -r "logger\." src/quilt_mcp/{backends,tools,ops}/ | head -20`
- `grep -r "except Exception" src/quilt_mcp/`
- `ls src/quilt_mcp/backends/`
- `sed -n` review of `src/quilt_mcp/backends/platform_backend.py`
- `rg -n "retry|timeout|backoff" src/quilt_mcp/{backends,tools,ops,services}`

## Logging Coverage Assessment

- Logging is broadly present across backends/tools.
- Many log calls are plain string logs; some include structured context (`extra={...}`), but usage is not uniform.
- Critical path modules (`platform_backend`, `quilt3_backend_session`) log auth/config/query events.

## Error Handling Patterns

- Extensive use of `except Exception` exists across codebase.
- Pattern quality varies:
  - Some paths convert to domain-specific errors with context.
  - Other paths catch broad exceptions with less structured categorization.

## Missing Observability / Gaps

1. Structured logging conventions are inconsistent (mixed free-form and contextual logs).
2. Broad exception catches are numerous, reducing error-type visibility.
3. Checklist reference `quiltops_graphql_backend.py` is stale; backend implementation lives in `platform_backend.py`.

## Log Sanitization Check

- Direct logging of token/secret values was not observed in sampled critical paths.
- JWT middleware logs auth failures without printing token content.

## Timeout/Retry Logic

- Timeout settings are present in major service calls (GraphQL, auth exchange, search/doc fetch).
- Retry/backoff logic exists (`tools/error_recovery.py`) and in selected operational flows.
- Retry behavior is not uniformly applied to all external-call paths.

## Pass/Fail Status

- Structured logging in place: ⚠️ Warning (present but not consistently structured)
- Error messages actionable: ✅ Pass (generally contextualized)
- Critical operations logged (auth, backend selection): ⚠️ Warning (auth logged; selection logging less explicit)
- No sensitive data in logs: ✅ Pass (no direct leakage observed)
- Exception handling consistent: ❌ Fail (heavy broad `except Exception` usage)
- Timeout/retry logic present: ✅ Pass (present in core paths)

**Section Result:** ⚠️ **Warning**

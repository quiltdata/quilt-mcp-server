# Spec 17: Multiuser Terminology Correction

**Status**: Planning
**Priority**: High
**Type**: Refactoring
**Impact**: System-wide terminology fix

---

## Context

**This is a NEW feature with NO external user visibility yet.**

Therefore:

- ✅ Clean global find-and-replace
- ✅ Single environment variable: `QUILT_MULTIUSER_MODE`
- ❌ NO backward compatibility needed
- ❌ NO deprecation warnings
- ❌ NO migration guides

---

## Problem

The codebase incorrectly uses "multitenant" terminology when it actually implements **multiuser** architecture:

### Multitenant (What We DON'T Have)

- Multiple separate organizations/companies (tenants) on shared infrastructure
- Strong data isolation between tenants
- Each tenant has separate data, users, configs
- Example: Salesforce where Company A cannot see Company B's data

### Multiuser (What We DO Have)

- Multiple users within the same organization
- Users share access to organizational resources (Quilt catalogs)
- JWT-based per-user authentication
- All users operate within same organizational/catalog context

---

## Scope

**181+ files** containing "multitenant" references:

- 8 core source files
- 23 test files
- 3 scripts
- 2 build config files
- 50+ documentation files
- 1 environment variable

---

## Terminology Mapping

### Global Replacements

```
multitenant → multiuser
multi-tenant → multi-user
multi_tenant → multi_user
MULTITENANT → MULTIUSER
MultiTenant → MultiUser
is_multitenant → is_multiuser
QUILT_MULTITENANT_MODE → QUILT_MULTIUSER_MODE
```

### Preserved "Tenant" Concept

**Keep unchanged** (refers to Quilt catalog owner, which is correct):

- `tenant_id` - Catalog/bucket owner identifier
- `extract_tenant_id()` - Extracts catalog owner from context
- `TenantValidationError` - Validates tenant IDs
- Any "tenant" reference meaning organizational catalog owner

---

## Implementation Plan

### Phase 1: Core Source (8 files)

**Configuration:**

- `src/quilt_mcp/config.py` - `ModeConfig.is_multiuser`, `QUILT_MULTIUSER_MODE`
- `src/quilt_mcp/main.py` - Error messages

**Context Layer:**

- `src/quilt_mcp/context/factory.py` - `_multiuser_mode` attribute
- `src/quilt_mcp/context/tenant_extraction.py` - Comments
- `src/quilt_mcp/context/exceptions.py` - Exception messages

**Other:**

- `src/quilt_mcp/ops/factory.py` - Comments
- `src/quilt_mcp/runtime_context.py`
- `src/quilt_mcp/utils.py`

### Phase 2: Tests (23 files)

**Rename test files (git mv):**

```bash
tests/integration/test_multitenant.py → test_multiuser.py
tests/security/test_multitenant_security.py → test_multiuser_security.py
tests/load/test_multitenant_load.py → test_multiuser_load.py
```

**Update content:**

- Test configs: `tests/conftest.py`, `tests/stateless/conftest.py`
- Helpers: `tests/jwt_helpers.py`
- Unit tests (5 files)
- Integration tests (2 files)
- Stateless tests (4 files)
- Performance tests (1 file)

### Phase 3: Scripts & Build (5 files)

**Rename scripts (git mv):**

```bash
scripts/test-multitenant.py → test-multiuser.py
scripts/tests/mcp-test-multitenant.yaml → mcp-test-multiuser.yaml
```

**Update:**

- `scripts/tests/start-stateless-docker.sh` - Docker env var
- `Makefile` - Targets: `test-multiuser`, `test-multiuser-fake`
- `make.dev` - Dev targets

### Phase 4: Documentation (50+ files)

**Rename directory (git mv):**

```bash
spec/a10-multitenant → spec/a10-multiuser
```

**Update all docs:**

- `README.md`, `CHANGELOG.md`
- `docs/deployment/jwt-mode-ecs.md`
- `docs/request_scoped_services.md`, `docs/STATELESS_TESTING.md`
- `docs/archive/UNIFIED_SEARCH_SUMMARY.md`
- All specs: `a10-multiuser/`, `a13-mode-config/`, `a15-platform/`, `a11-client-testing/`
- Internal: `.kiro/specs/`

---

## Key Code Changes

### config.py (Simplified)

```python
class ModeConfig:
    """Configuration for deployment mode selection."""

    def __init__(self):
        multiuser_mode = os.getenv("QUILT_MULTIUSER_MODE", "false")
        self._multiuser_mode = multiuser_mode.lower() == "true"

    @property
    def is_multiuser(self) -> bool:
        """True if running in multiuser mode (JWT auth, Platform backend)."""
        return self._multiuser_mode

    @property
    def is_local_dev(self) -> bool:
        """True if running in local development mode."""
        return not self._multiuser_mode
```

### Test Configuration

```python
# tests/conftest.py
@pytest.fixture(scope="session", autouse=True)
def set_local_dev_mode():
    with patch.dict(os.environ, {"QUILT_MULTIUSER_MODE": "false"}):
        yield

# tests/stateless/conftest.py
@pytest.fixture(scope="session")
def multiuser_mode():
    with patch.dict(os.environ, {"QUILT_MULTIUSER_MODE": "true"}):
        yield
```

### Makefile

```makefile
.PHONY: test-multiuser
test-multiuser:
 QUILT_MULTIUSER_MODE=true $(UV_RUN) pytest tests/integration/test_multiuser.py -v

.PHONY: test-multiuser-fake
test-multiuser-fake:
 ./scripts/test-multiuser.py --fake-backend
```

---

## Testing Strategy

### Validation Checklist

- [ ] `QUILT_MULTIUSER_MODE=true` enables multiuser mode
- [ ] `QUILT_MULTIUSER_MODE=false` enables local dev mode
- [ ] JWT auth works in multiuser mode
- [ ] All tests pass: `make test-all`
- [ ] Make targets work: `make test-multiuser`
- [ ] Scripts work: `./scripts/test-multiuser.py`
- [ ] Docker starts with `QUILT_MULTIUSER_MODE`
- [ ] No broken doc links
- [ ] Lint passes: `make lint`

---

## Critical Files

1. `src/quilt_mcp/config.py` - Mode configuration
2. `src/quilt_mcp/main.py` - Entry point
3. `src/quilt_mcp/context/factory.py` - Context creation
4. `tests/conftest.py` - Test setup
5. `Makefile` - Build targets
6. `README.md` - Public docs

---

## Architecture Context

### Multiuser Mode (`QUILT_MULTIUSER_MODE=true`)

**What it enables:**

- JWT-based user authentication (each user has unique token)
- Platform/GraphQL backend (not direct S3)
- HTTP transport (stateless, server-friendly)
- Per-request user context (audit trail, authorization)

**Use case:** Multiple users in an organization accessing shared Quilt catalogs

### Local Dev Mode (`QUILT_MULTIUSER_MODE=false`)

**What it enables:**

- IAM-based local credentials (AWS env)
- Quilt3 backend (direct S3/boto3)
- stdio transport (CLI/desktop apps)
- Static configuration (single developer)

**Use case:** Individual developer working locally

---

## File Inventory

### Source Code (8 files)

- `src/quilt_mcp/config.py`
- `src/quilt_mcp/main.py`
- `src/quilt_mcp/context/factory.py`
- `src/quilt_mcp/context/tenant_extraction.py`
- `src/quilt_mcp/context/exceptions.py`
- `src/quilt_mcp/ops/factory.py`
- `src/quilt_mcp/runtime_context.py`
- `src/quilt_mcp/utils.py`

### Test Files (23 files)

**Unit:** 5 files in `tests/unit/`
**Integration:** 2 files in `tests/integration/`
**Security:** 1 file in `tests/security/`
**Load:** 1 file in `tests/load/`
**Performance:** 1 file in `tests/performance/`
**Stateless:** 4 files in `tests/stateless/`
**Infrastructure:** `tests/conftest.py`, `tests/jwt_helpers.py`

### Scripts (3 files)

- `scripts/test-multitenant.py` (rename)
- `scripts/tests/start-stateless-docker.sh`
- `scripts/tests/mcp-test-multitenant.yaml` (rename)

### Build Config (2 files)

- `Makefile`
- `make.dev`

### Documentation (50+ files)

- Specs: `a10-multitenant/` (rename), `a13-mode-config/`, `a15-platform/`, `a11-client-testing/`
- Docs: `README.md`, `CHANGELOG.md`, `docs/deployment/`, `docs/archive/`
- Internal: `.kiro/specs/`

---

## Success Criteria

- [ ] All "multitenant" → "multiuser" (except preserved "tenant" concepts)
- [ ] `QUILT_MULTIUSER_MODE` works correctly
- [ ] All tests pass: `make test-all`
- [ ] Lint passes: `make lint`
- [ ] Documentation accurate
- [ ] File renames use `git mv` (preserve history)
- [ ] No functional changes (pure refactoring)

---

## Related Specifications

- [Spec 02: GraphQL Backend](02-graphql.md)
- [Spec 08: Multitenant Testing](08-multitenant-testing-spec.md) - Will be updated
- [Spec 09: Quick Start Multitenant](09-quick-start-multitenant.md) - Will be updated
- [Spec 14: Local Auth Bridge](14-local-auth-bridge.md)
- [a13-mode-config specs](../a13-mode-config/)

---

**Author**: Claude
**Date**: 2026-02-02
**Status**: Ready for Implementation

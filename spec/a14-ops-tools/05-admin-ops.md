# Spec: QuiltOps Admin/Governance Refactoring

## Goal

Refactor `governance_service.py` to use QuiltOps abstraction pattern.

## Current State

`GovernanceService` directly imports and calls `quilt3.admin.*` modules:

- quilt3.admin.users
- quilt3.admin.roles
- quilt3.admin.sso_config
- quilt3.admin.tabulator

## Target Architecture

```
GovernanceService (services layer)
    ↓ calls
QuiltOps.admin_* methods (ops abstraction)
    ↓ delegates
Quilt3Backend.admin_* implementations (backend layer)
    ↓ calls
quilt3.admin.* modules
```

---

## Tasks

### Task 1: Create Domain Objects

**File:** `src/quilt_mcp/domain/admin.py` (new)

**Objects:**

- `User` - name, email, is_active, is_admin, is_sso_only, is_service, date_joined, last_login, role, extra_roles
- `Role` - id, name, arn, typename
- `SSOConfig` - text, timestamp, uploader

**Decisions:**

- Dataclass or Pydantic?
- Optional fields: None or defaults?
- DateTime: datetime objects or ISO strings?
- Role references: nested Role objects or string names?

---

### Task 2: Add QuiltOps Abstract Methods

**File:** `src/quilt_mcp/ops/quilt_ops.py`

**Method groups:**

**Users (10 methods):**

- `admin_user_list() -> List[User]`
- `admin_user_get(name: str) -> User`
- `admin_user_create(name, email, role, extra_roles) -> User`
- `admin_user_delete(name: str) -> None`
- `admin_user_set_email(name: str, email: str) -> User`
- `admin_user_set_admin(name: str, admin: bool) -> User`
- `admin_user_set_active(name: str, active: bool) -> User`
- `admin_user_reset_password(name: str) -> None`
- `admin_user_set_role(name, role, extra_roles, append) -> User`
- `admin_user_add_roles(name: str, roles: List[str]) -> User`
- `admin_user_remove_roles(name, roles, fallback) -> User`

**Roles (1 method):**

- `admin_role_list() -> List[Role]`

**SSO Config (3 methods):**

- `admin_sso_config_get() -> Optional[SSOConfig]`
- `admin_sso_config_set(config: str) -> SSOConfig`
- `admin_sso_config_remove() -> None`

**Tabulator (2 methods):**

- `admin_tabulator_open_query_get() -> bool`
- `admin_tabulator_open_query_set(enabled: bool) -> None`

**Decisions:**

- Return domain objects or dicts?
- Raise exceptions (UserNotFoundError, etc.) or return Optional/Result?
- Keep async signatures even though quilt3.admin is sync?
- Validation in QuiltOps or service layer?

---

### Task 3: Implement Quilt3Backend Admin Methods

**File:** `src/quilt_mcp/backends/quilt3_backend_admin.py` (new mixin)

**Pattern:**

```python
def admin_user_get(self, name: str) -> User:
    import quilt3.admin.users as admin_users
    user_obj = admin_users.get(name)
    return self._convert_user(user_obj)
```

**Responsibilities:**

- Import quilt3.admin modules
- Call quilt3.admin functions
- Convert quilt3 objects → domain objects
- Let exceptions propagate (or wrap them)

**Decisions:**

- New mixin file or extend existing backend file?
- Exception handling: pass-through or wrap in custom types?
- Where to check ADMIN_AVAILABLE: backend init, per-method, or QuiltOps layer?
- Conversion helpers: private methods in mixin or separate converter module?

**Integration:** Add mixin to `Quilt3_Backend` class composition

---

---

### Task 4: Refactor GovernanceService

**File:** `src/quilt_mcp/services/governance_service.py`

**Changes:**

- Remove `import quilt3.admin.*`
- Remove module-level `admin_users`, `admin_roles`, etc. variables
- Add `self.quilt_ops: QuiltOps` (inject in **init**)
- Replace `admin_users.get(name)` → `self.quilt_ops.admin_user_get(name)`
- Convert domain objects → response dicts in each tool function

**Keep in service layer:**

- Input validation (empty checks, email format)
- Response formatting (`{"success": True, "message": ...}`)
- Table formatting calls
- Error handling with `format_error_response()`

**Decisions:**

- How to inject QuiltOps instance?
- Keep `_check_admin_available()` or rely on QuiltOps/backend?
- Keep `_handle_admin_error()` or move exception handling elsewhere?
- Domain object → dict conversion: manual or add `.to_dict()` method?

---

### Task 5: Update Tests

**File:** `tests/unit/test_governance_service.py`

**Changes:**

- Mock `QuiltOps` instead of `quilt3.admin.*` modules
- Return domain objects from mocked QuiltOps methods
- Test domain object conversion in service layer

**Keep:**

- Same test coverage and assertions
- Test structure (one test per tool function)

**Decisions:**

- Mock at QuiltOps level or Quilt3Backend level?
- Create shared fixtures for domain objects?
- Test backward compatibility with existing exception types?

---

## Migration Order

1. **Create domain objects** - No dependencies, can coexist
2. **Add QuiltOps methods** - Abstract definitions, no consumers yet
3. **Implement Quilt3Backend mixin** - Can be tested in isolation
4. **Update GovernanceService** - One method group at a time:
   - User management (11 methods)
   - Role management (1 method)
   - SSO config (3 methods)
   - Tabulator (2 methods)
5. **Update tests** - After each service method group

**Rollback:** Each step can be committed independently

---

## Key Decisions Required

1. **Error handling:** Pass-through quilt3.admin exceptions or create custom exception types?
2. **Validation location:** Service (current), QuiltOps, or backend?
3. **Response format:** Who converts domain objects to dicts? Service or QuiltOps?
4. **Admin availability check:** Where to enforce `ADMIN_AVAILABLE` requirement?
5. **Async signatures:** Keep `async def` in QuiltOps even though quilt3.admin is sync?
6. **Backward compatibility:** Maintain module-level exception exports for tests?

---

## DECISIONS (Based on Existing Patterns)

### 1. Domain Objects: `@dataclass(frozen=True)` ✅ Matches existing

**Pattern:** All domain objects use frozen dataclasses

- Package_Info, Auth_Status, Content_Info all use `@dataclass(frozen=True)`
- quilt3.admin returns Pydantic models → convert to dataclasses

**DateTime:** `Optional[str]` in ISO 8601 format

- Backend: `user.date_joined.isoformat() if user.date_joined else None`
- Matches: Package_Info.modified_date is `str`

**Nested objects:** Use domain objects, not strings

- `role: Optional[Role]` (domain object)
- `extra_roles: List[Role]` (domain objects)
- Service layer flattens to strings in response dict

### 2. QuiltOps Return Types: Domain objects ✅ Matches existing

```python
def admin_user_list() -> List[User]          # like search_packages() -> List[Package_Info]
def admin_user_get(name: str) -> User         # like get_auth_status() -> Auth_Status
def admin_sso_config_get() -> Optional[SSOConfig]
```

### 3. Exceptions: Wrap in QuiltOps types ✅ Matches existing

**Map quilt3.admin → QuiltOps:**

- `UserNotFoundError` → `ops.exceptions.NotFoundError`
- `BucketNotFoundError` → `ops.exceptions.NotFoundError`
- `Quilt3AdminError` → `ops.exceptions.BackendError`
- Generic → `ops.exceptions.BackendError`

**Existing:** QuiltOps defines AuthenticationError, BackendError, ValidationError, NotFoundError, PermissionError

### 4. Async Signatures: Keep `async def` ✅ Matches existing

All QuiltOps methods are async even when backend is sync (enables future async backends)

### 5. Validation: Service layer ✅ Keep current

Service validates empty strings, email format, required params. Backend trusts input.

### 6. Response Format: Service converts ✅ Matches current

```
Backend: quilt3 object → domain object
QuiltOps: return domain object
Service: domain object → {"success": True, "user": {...}}
```

### 7. Admin Availability: Service __init__ ✅ Keep current

Service checks `ADMIN_AVAILABLE` at tool boundary, fails fast with formatted error

### 8. Backend: New mixin `quilt3_backend_admin.py` ✅ Matches architecture

```text
class Quilt3_Backend_Admin:
    async def admin_user_list(self) -> List[User]:
        import quilt3.admin.users
        users = quilt3.admin.users.list()
        return [self._user_to_domain(u) for u in users]

    def _user_to_domain(self, u) -> User:
        return User(name=u.name, email=u.email, ...)

# Add to Quilt3_Backend composition (currently 5 mixins, add 6th)
```

**Native format from quilt3.admin:**

- Returns Pydantic models with fields: name, email, is_active, is_admin, is_sso_only,
  is_service, date_joined (datetime), last_login (datetime), role (Role object),
  extra_roles (List[Role])
- Backend extracts fields → constructs frozen dataclass

---

## Success Criteria

- [ ] No `quilt3.admin` imports in `governance_service.py`
- [ ] All admin operations go through `QuiltOps` abstraction
- [ ] Domain objects defined and tested
- [ ] Backend mixin integrated into `Quilt3_Backend`
- [ ] All existing tests pass (with minimal mock updates)
- [ ] Code coverage maintained
- [ ] Backend can be mocked/swapped without changing service layer

# Why Platform_Backend Should Be a Separate Project

## Executive Summary

The current `quilt-mcp-server` architecture assumes Quilt3_Backend and Platform_Backend are **interchangeable implementations of the same interface**. However, they are fundamentally **different products** serving different deployment models with largely different tool sets (<50% overlap). A separate project for Platform_Backend is recommended.

---

## Current Architecture Problem

### The QuiltOps Abstraction Assumes Wrong Things

```python
# Current design: backends are swappable
class QuiltOps(ABC):
    @abstractmethod
    def search_packages(self, ...) -> List[Package_Info]: ...
    @abstractmethod
    def create_package_revision(self, ...) -> Package_Creation_Result: ...
    # ... assumes both backends implement identical methods
```

**Reality:**
- Tool overlap is <50%
- Different capabilities per deployment model
- Forcing common interface creates artificial constraints

### What We Have vs. What We Need

| Current Architecture | Actual Requirements |
|---------------------|---------------------|
| Shared QuiltOps interface | Different tool sets |
| Factory pattern to swap backends | Different products, not swappable |
| 7-layer abstraction stack | Unnecessary for single-backend projects |
| IAM + OAuth + quilt3 session support | OAuth-only for Platform |
| Single codebase, single release | Different priorities, different release cycles |

---

## Why Separate Projects

### 1. Fundamentally Different Tool Sets

With <50% tool overlap, the backends are not "different implementations of the same thing" - they are **different products**.

| Quilt3_Backend (Local) | Platform_Backend (Multi-tenant) |
|------------------------|--------------------------------|
| quilt3 library integration | GraphQL API only |
| IAM credentials | OAuth tokens |
| Single-user context | Multi-tenant isolation |
| Local/desktop deployment | Cloud/SaaS deployment |
| Package operations via quilt3 | Platform-native operations |

Forcing these into one interface means:
- Artificial method stubs in one backend
- Conditional logic everywhere
- Neither backend is clean

### 2. Different Auth Models

**Quilt3_Backend:**
- AWS IAM credentials
- quilt3 session management
- boto3 credential chains
- Optional JWT for some deployments

**Platform_Backend:**
- OAuth-only
- Token refresh
- Multi-tenant credential isolation
- No AWS credential management

Mixing these in one codebase creates complexity (current auth layer is 400+ lines across multiple files).

### 3. Different Release Priorities

| Aspect | Quilt3_Backend | Platform_Backend |
|--------|----------------|------------------|
| Priority | Maintenance mode | Active development |
| Release frequency | Stable, infrequent | Rapid iteration |
| Breaking changes | Avoid | Expected during development |
| User base | Existing local users | New platform customers |

Coupling them means:
- Platform changes risk breaking local deployments
- Local stability requirements slow Platform development
- Testing burden doubles

### 4. Current Codebase Baggage

The assessment found significant technical debt:

| Issue | Impact on Platform_Backend |
|-------|---------------------------|
| 40:1 glue-to-work ratio | Would inherit unnecessary complexity |
| 6-mixin backend composition | Overkill for OAuth-only GraphQL backend |
| 389 private helpers, 25% duplicated | Would need cleanup before adding new code |
| 3 god classes (500+ lines each) | Wrong patterns to build on |
| 7 unused dependencies | Bloated container images |

Starting fresh avoids inheriting this debt.

### 5. Cleaner Mental Model

**One repo, two backends:**
- "Which backend does this code affect?"
- "Will this change break the other backend?"
- "How do I test both deployment modes?"

**Separate projects:**
- Platform_Backend is self-contained
- Changes don't affect local deployments
- Clear ownership and responsibility

---

## What CAN Be Shared

Some components are genuinely reusable:

```
quilt-mcp-common/  (optional shared library)
├── visualization/          # ECharts, IGV generators
│   ├── engine.py
│   ├── analyzers/
│   └── generators/
├── validators/             # Package naming, structure validation
│   ├── naming_validator.py
│   └── structure_validator.py
├── models/                 # Pydantic response models (if API shapes align)
│   └── responses.py
└── errors/                 # Base exception patterns
    └── exceptions.py
```

**Note:** Sharing is optional. If maintaining a third package adds overhead, these can be copied or inlined. The visualization engine (~2,000 lines) is the strongest candidate for extraction.

---

## What Should NOT Be Shared

| Component | Why Not Share |
|-----------|---------------|
| Tool definitions | Different capabilities, different MCP tools |
| Backend implementation | quilt3 library vs GraphQL - nothing in common |
| Auth layer | OAuth-only vs IAM/quilt3 session |
| Context management | Single-user vs multi-tenant isolation |
| Configuration | Different env vars, different modes |
| Tests | Different integration targets |

---

## Recommended Structure

### Option A: Completely Separate Repos

```
github.com/quiltdata/quilt-mcp-local/      # Current repo, renamed
github.com/quiltdata/quilt-mcp-platform/   # New repo, clean slate
```

**Pros:** Maximum independence, clear separation
**Cons:** No code sharing, potential divergence

### Option B: Monorepo with Separate Packages

```
github.com/quiltdata/quilt-mcp/
├── packages/
│   ├── local/              # Quilt3_Backend (current code, cleaned up)
│   ├── platform/           # Platform_Backend (new, OAuth/GraphQL)
│   └── common/             # Shared utilities (optional)
├── pyproject.toml          # Workspace configuration
└── README.md
```

**Pros:** Shared CI/CD, easier to extract common code later
**Cons:** Still some coupling, workspace tooling complexity

### Option C: Separate Repos + Shared Library (Recommended)

```
github.com/quiltdata/quilt-mcp-server/     # Current repo (Quilt3_Backend)
github.com/quiltdata/quilt-mcp-platform/   # New repo (Platform_Backend)
github.com/quiltdata/quilt-mcp-common/     # Shared utilities (if needed)
```

**Pros:**
- Platform_Backend gets clean slate
- Current repo unchanged (no migration risk)
- Shared library is optional and can be added later

**Cons:** Three repos to maintain (but common/ is optional)

---

## Migration Path

### Phase 1: Create Platform_Backend Project (Now)

1. Create new `quilt-mcp-platform` repository
2. Minimal structure: OAuth auth, GraphQL client, MCP tools
3. No dependencies on current codebase
4. Fast iteration, clean architecture

### Phase 2: Stabilize Current Repo (Optional)

1. Rename to `quilt-mcp-local` for clarity
2. Remove Platform_Backend stub
3. Remove unused abstractions (QuiltOps ABC, factory)
4. Remove unused dependencies (plotly, pysam, etc.)

### Phase 3: Extract Common Library (If Needed)

1. Identify components used by both
2. Extract to `quilt-mcp-common`
3. Version and publish as internal package
4. Both projects depend on common library

---

## Platform_Backend: Clean Slate Architecture

A new project can avoid the current complexity:

```
quilt-mcp-platform/
├── src/quilt_mcp_platform/
│   ├── auth/               # OAuth-only, simple
│   │   └── oauth.py        # Token management (~100 lines)
│   ├── graphql/            # Platform GraphQL client
│   │   └── client.py       # Single module (~200 lines)
│   ├── tools/              # MCP tool definitions
│   │   ├── packages.py     # Platform package operations
│   │   ├── search.py       # Platform search
│   │   └── admin.py        # Platform admin (if needed)
│   ├── models/             # Response models
│   │   └── responses.py
│   └── main.py             # Entry point
├── tests/
├── pyproject.toml
└── README.md
```

**Target complexity:**
- 2-3 layers (tools → graphql → API), not 7
- ~2,000 lines total, not 33,000
- No mixins, no factory, no ABC interfaces
- OAuth-only, no credential chain complexity

---

## Conclusion

| Factor | Same Repo | Separate Project |
|--------|-----------|------------------|
| Tool overlap (<50%) | Forced commonality | Natural separation |
| Auth models | Mixed complexity | Clean OAuth-only |
| Release priorities | Coupled releases | Independent velocity |
| Technical debt | Inherited | Fresh start |
| Maintenance | Single codebase | Clear ownership |
| Risk | Changes affect both | Isolated changes |

**Recommendation:** Create `quilt-mcp-platform` as a separate project. Start clean, move fast, avoid inheriting complexity that doesn't serve the multi-tenant use case.

The current `quilt-mcp-server` can continue serving local deployments with minimal changes. Shared utilities can be extracted later if genuine reuse opportunities emerge.

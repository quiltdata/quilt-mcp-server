# Stack-Integrated MCP Server Design

> Version 1.0 | February 16, 2026

## Purpose

This document captures the key design decisions made to enable a single Quilt MCP codebase that
supports both local development and remote multiuser deployment. Each decision addresses a specific
problem and documents alternatives considered.

## Context

**Problem:** We need to support two fundamentally different deployment modes:

- Local development: Single user, AWS credentials, full feature set, stateful operations
- Remote deployment: Multiple users, JWT auth, stateless operations, horizontal scaling

**Goal:** Achieve this without maintaining separate codebases or creating complex feature
matrices.

## Key Design Decisions

### 1. Single Codebase Architecture

**Decision:** Maintain one codebase for both local and remote deployments

**Why:** Code drift is expensive. Maintaining two codebases means duplicate testing, duplicate bug fixes,
and diverging feature sets. Every change requires coordination.

**Trade-offs:** Some code complexity to support both modes, but eliminates duplication costs

### 2. Backend Abstraction (QuiltOps)

**Decision:** Abstract all Quilt operations behind domain-driven interfaces

**Why:** Two deployment modes require fundamentally different implementation strategies:

- Local: Python quilt3 library with local state
- Remote: GraphQL API with stateless operation

Coupling MCP tools directly to either implementation locks us into one mode.

**Trade-offs:** Additional abstraction layer, but enables independent evolution of both backends

### 3. Modular Backend Architecture

**Decision:** Split backend implementations into focused mixins rather than monolithic classes

**Why:** A single backend class implementing all operations creates several problems:

- Large files (1000+ lines) are hard to navigate and test
- Changes to package operations risk breaking bucket operations
- Different concerns (auth vs content vs packages) intertwined

**Alternatives Considered:**

- Monolithic backend class: Rejected - becomes unmaintainable at scale
- Separate service classes: Rejected - doesn't align with interface-based design
- Mixin composition: **Chosen** - clean separation with shared base functionality

**Trade-offs:** More files to manage, but each is focused and independently testable

### 4. Dual Authentication Modes

**Decision:** Support both IAM and JWT authentication from a single codebase

**Why:** Different deployment modes have incompatible authentication requirements:

- Local: Users already authenticated with AWS (IAM credentials, profiles, quilt3 sessions)
- Remote: Must authenticate each HTTP request independently (no shared session state)

**Trade-offs:** Must handle two auth paths, but each mode gets appropriate auth mechanism

### 5. Request Context Architecture

**Decision:** Use request-scoped services instead of global singletons

**Why:** Global singleton services create security and isolation problems in multiuser scenarios:

- User A's credentials could leak to User B's request
- Permission caches shared between users
- Session state persists across requests

**Trade-offs:** Services recreated per request (minimal cost), but guarantees isolation

### 6. Stateful vs Stateless Operations

**Decision:** Disable stateful operations in multiuser mode

**Why:** Remote deployments need horizontal scaling:

- Load balancers route requests to any available server
- Servers can be added/removed dynamically
- No server has "the" workflow state or template files

Stateful operations assume a single, long-lived process.

**Trade-offs:** Some features unavailable in multiuser mode, but remote deployment becomes practical

### 7. Platform GraphQL Backend

**Decision:** Implement a complete GraphQL-native backend parallel to the quilt3 backend

**Why:** The quilt3 library is fundamentally incompatible with multiuser remote deployment:

- Requires local filesystem for package operations
- Manages session state in ~/.quilt directory
- Not designed for concurrent multiuser access

The Platform already provides a GraphQL API - we can use it directly.

**Trade-offs:** Parallel implementations to maintain, but each optimized for its deployment mode

### 8. Admin/User Role Split

**Decision:** Separate admin and user operations into distinct interfaces (AdminOps vs QuiltOps)

**Why:** Admin operations have fundamentally different characteristics:

- Different permission requirements
- Different audit requirements
- Used by different roles
- Mixing them creates unclear boundaries

**Trade-offs:** Additional interface to implement, but clear role separation

### 9. Unified Tabulator Operations

**Decision:** Extract tabulator operations into a shared mixin rather than duplicating in each backend

**Why:** Tabulators are managed via GraphQL API in both backends:

- Same GraphQL queries and mutations
- Same response parsing logic
- Only authentication headers differ

Duplicating this code violates DRY and creates maintenance burden.

**Alternatives Considered:**

- Duplicate tabulator code in each backend: Rejected - maintenance burden
- Separate tabulator service: Rejected - breaks backend encapsulation
- Shared mixin with auth hooks: **Chosen** - reuse code, backends provide auth

**Trade-offs:** Mixin dependency, but eliminates ~200 lines of duplication

### 10. Dynamic Resource Discovery

**Decision:** Resources advertise their availability dynamically based on deployment mode

**Why:** Different deployment modes support different features. Clients need to know what's available:

- Tests should skip unavailable features, not fail
- MCP clients need clear feedback about mode restrictions
- Hard-coded feature lists get out of sync

**Alternatives Considered:**

- Static configuration file: Rejected - gets out of sync with code
- Runtime errors when accessing unavailable features: Rejected - poor developer experience
- Dynamic discovery via MCP protocol: **Chosen** - self-documenting, adapter pattern

**Trade-offs:** Small runtime overhead for discovery, but better client adaptability

## Configuration Summary

### Mode Selection

```bash
# Local development (default)
# Uses AWS credentials, full feature set
QUILT_MULTIUSER_MODE=false  # or unset

# Remote multiuser deployment
# JWT required, stateless only
QUILT_MULTIUSER_MODE=true
MCP_JWT_SECRET=<secret>
QUILT_CATALOG_URL=https://catalog.example.com
QUILT_REGISTRY_URL=s3://registry-bucket
```

## Design Outcomes

These decisions deliver:

1. **Single Codebase**: No code drift between deployment modes
2. **Clear Isolation**: Request-scoped services prevent credential leakage
3. **Flexible Auth**: IAM for local dev, JWT for remote deployment
4. **Horizontal Scaling**: Stateless remote mode supports load balancing
5. **Self-Documenting**: Dynamic resource discovery shows available features

**Key Trade-off**: Some architectural complexity to support both modes, balanced against eliminating the
cost of maintaining separate codebases and preventing feature drift.

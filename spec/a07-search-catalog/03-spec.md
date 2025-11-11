# Search Catalog Tool: Implementation Specification

**Date:** 2025-11-10
**Status:** Ready for Implementation
**Version:** 0.9.0 (Breaking Changes)

---

## Core Principle

**`search_catalog` searches Quilt catalog indices (Elasticsearch/GraphQL) ONLY.**
It is NOT a general-purpose S3 listing tool.

---

## Key Changes

### 1. Remove S3 Backend

**Rationale**: S3 listing ≠ catalog search. Different data, different semantics.

**Action**:

- Remove `S3FallbackBackend` from search backends
- Direct users to `bucket_objects_list` for S3 exploration
- Fail explicitly when no catalog search available

### 2. Smart Single-Backend Selection

**Current**: Parallel fan-out to all backends, aggregate results
**New**: Select one backend, use it

```python
def select_search_backend() -> SearchBackend:
    if not authenticated():
        raise AuthenticationRequired()

    # Prefer GraphQL (Enterprise features)
    if graphql.available:
        return graphql

    # Fallback to Elasticsearch (standard)
    if elasticsearch.available:
        return elasticsearch

    # No search available
    raise SearchNotAvailable()
```

### 3. Explicit Error Handling

**Never return fake answers.** Every failure includes:

- Clear error message
- Error category (authentication, authorization, not_applicable, etc.)
- How to fix it
- Alternative tools to use

**Example**:

```json
{
  "success": false,
  "error": "Search catalog requires authentication",
  "error_category": "authentication",
  "fix": {"command": "quilt3.login()"},
  "alternatives": {"bucket_objects_list": "List S3 objects"}
}
```

### 4. Integrate Backend Status

**New Helper**: `get_search_backend_status()`

**Integrated in**:

1. `catalog_info` resource → Discovery
2. `search_catalog` results → Debugging

**Returns**:

```json
{
  "available": true,
  "backend": "elasticsearch",
  "capabilities": ["metadata_search", "content_search"],
  "status": "ready"
}
```

---

## Backend Documentation

### Elasticsearch Backend

- **What**: Wraps `quilt3.Bucket.search()` and `quilt3.search_packages()`
- **When**: Standard in all hosted Quilt deployments
- **Requires**: `quilt3.login()` + search permissions
- **Searches**: Packages, object metadata, content

### GraphQL Backend

- **What**: Direct GraphQL queries to Enterprise catalog
- **When**: Enterprise deployments only
- **Requires**: `quilt3.login()` + Enterprise catalog + `/graphql` endpoint
- **Searches**: Packages, buckets, relationships, advanced queries

### ~~S3 Backend~~ (REMOVED)

- **Why Removed**: Not equivalent to catalog search
- **Alternative**: Use `bucket_objects_list` for S3 key exploration

---

## Implementation Tasks

### Phase 1: Remove S3 Backend

- [ ] Mark `S3FallbackBackend` as deprecated
- [ ] Remove from backend registry initialization
- [ ] Update tests to remove S3 backend cases
- [ ] Add tests for explicit failure when no backends available

### Phase 2: Smart Backend Selection

- [ ] Implement `_select_primary_backend()` method
- [ ] Update search flow to use single backend
- [ ] Remove parallel backend execution
- [ ] Update response format (single `backend_used` field)

### Phase 3: Error Handling

- [ ] Define `ErrorCategory` enum
- [ ] Create `SearchException` base class
- [ ] Implement `AuthenticationRequired` exception
- [ ] Implement `SearchNotAvailable` exception
- [ ] Add structured error responses
- [ ] Update all backend error handling

### Phase 4: Backend Status Integration

- [ ] Create `get_search_backend_status()` helper
- [ ] Integrate into `catalog_info` resource
- [ ] Include in `search_catalog` responses
- [ ] Add capability detection per backend

### Phase 5: Lazy Initialization

- [ ] Add `ensure_initialized()` to base backend
- [ ] Defer auth checks until first search
- [ ] Remove init-time authentication failures
- [ ] Add `refresh_status()` method

---

## Error Response Schema

```typescript
interface SearchErrorResponse {
  success: false;
  error: string;                    // Human-readable
  error_category: ErrorCategory;    // Enum
  details: {
    cause: string;
    authenticated: boolean;
    catalog_url: string | null;
  };
  fix: {
    required_action: string;
    command?: string;
    documentation?: string;
  };
  alternatives: {
    [tool_name: string]: string;
  };
}
```

---

## Success Metrics

1. **No Fake Answers**: 0% S3 listings presented as search results
2. **Error Quality**: 100% failures include actionable guidance
3. **Auth Detection**: 100% auth failures detected upfront
4. **Clear Alternatives**: Every failure suggests specific tools

---

## Migration Guide

### For Users

**Old**: Search falls back to S3 listing (confusing)
**New**: Search fails explicitly with guidance (clear)

### For AI Agents

**Old**: Gets S3 keys, presents as search results
**New**: Gets explicit error, switches to `bucket_objects_list`

---

## Breaking Changes (v0.9.0)

- S3 backend removed from `search_catalog`
- Response format changed (single `backend_used` not array)
- No longer returns results when backends unavailable
- Error response format changed (added structured fields)

---

## Timeline

**Week 1**: Remove S3 backend, update tests
**Week 2**: Smart backend selection, error handling
**Week 3**: Backend status integration, lazy init

---

## Related Documents

- [01-analysis.md](01-analysis.md) - Technical architecture analysis
- [02-response.md](02-response.md) - Detailed design response

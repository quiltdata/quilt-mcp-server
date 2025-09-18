<!-- markdownlint-disable MD013 -->
# Architecture - Isolate quilt3 Dependency (Simplified)

**GitHub Issue**: #155 "[isolate quilt3](https://github.com/quiltdata/quilt-mcp-server/issues/155)"
**Requirements Reference**: [01-requirements.md](./01-requirements.md)
**Analysis Reference**: [02-analysis.md](./02-analysis.md)

## Executive Summary

This architecture takes a **pragmatic, minimal-change approach** to isolate quilt3 dependencies by leveraging existing patterns in the codebase. The solution focuses on environment detection and conditional imports/fallbacks rather than complex abstraction layers.

## Core Problem

The MCP server needs to work in stack deployments where:

1. quilt3 package isn't available or can't authenticate interactively
2. Stack services provide direct APIs for the same functionality
3. The MCP tool interface must remain unchanged

## Simple Solution: Build-Time Configuration + Optional Dependencies

### Key Abstractions

#### 1. Optional Dependency Handling
Import quilt3 safely with try/except. If not available, fall back to direct boto3/environment-based approaches. This is determined at import time, not runtime.

#### 2. Configuration Source Selection
Two distinct configuration paths: quilt3-based (local) and environment-based (stack). The available path is determined by what's installed, not dynamic detection.

#### 3. Consistent Tool Interfaces
All MCP tools maintain identical signatures and behavior regardless of which configuration source is available. Users see no difference in functionality.

## Implementation Plan (2 Simple PRs)

### PR 1: Optional Dependency Foundation

- Add `src/quilt_mcp/quilt3_compat.py` for safe imports
- Update existing `get_s3_client()` and `get_sts_client()` functions to handle missing quilt3
- Update configuration loading to fall back to environment variables
- Add environment variable documentation

**Files changed**: 4-6 files
**Lines changed**: ~150 lines

### PR 2: Tool Interface Consistency

- Update all MCP tools to work without quilt3
- Add environment-based fallbacks for package operations
- Ensure error messages are clear when features unavailable
- Update build/packaging to handle optional quilt3

**Files changed**: 15-20 files
**Lines changed**: ~250 lines

## Key Advantages of This Approach

### 1. Leverages Existing Patterns

- The codebase already has `use_quilt_auth` flags
- Client factory functions already exist
- Fallback patterns are already established
- Error handling patterns are already consistent

### 2. Minimal Code Changes

- No major refactoring required
- No new frameworks or complex abstractions
- Builds on existing architectural decisions
- Preserves all existing functionality

### 3. Simple to Understand

- Clear environment detection logic
- Obvious fallback chains
- Standard Python conditional imports
- Easy to debug and maintain

### 4. Incremental Implementation

- Each PR can be independently tested
- Local development unaffected during transition
- Stack mode enabled progressively
- Easy to rollback if issues arise

### 5. No Over-Engineering

- No dependency injection containers
- No abstract service interfaces
- No complex factory hierarchies
- No strategy pattern implementations

## Environment Variables for Stack Configuration

**Stack configuration (when quilt3 unavailable):**

- `CATALOG_URL=https://...` - Catalog web interface
- `REGISTRY_URL=s3://bucket` - Package registry
- `GRAPHQL_URL=https://.../graphql` - GraphQL API endpoint

**Authentication:**

- `AWS_ROLE_ARN=arn:aws:iam::...` - Service role for stack auth

## Testing Strategy

### 1. Import-Time Testing

- Mock quilt3 import availability for unit tests
- Environment variable-based testing for stack mode
- Separate test suites for each configuration

### 2. Fallback Testing

- Test with quilt3 unavailable
- Test with partial service availability
- Test error conditions and messages

### 3. Integration Testing

- Test full workflows in both environments
- Validate tool interface consistency
- Performance testing for both modes

## Success Criteria

1. **Local development unchanged**: All existing functionality preserved
2. **Stack deployment working**: MCP server runs successfully in stack environment
3. **Same tool interface**: No changes to MCP tool signatures
4. **Clear error messages**: Users understand when features unavailable
5. **Simple codebase**: No complex abstractions, easy to maintain

## What This Approach Avoids

- ❌ Dependency injection frameworks
- ❌ Abstract service interfaces requiring 20+ classes
- ❌ Factory pattern hierarchies
- ❌ Strategy pattern implementations
- ❌ Multi-layer architecture diagrams
- ❌ Complex configuration management systems
- ❌ Service discovery frameworks

## What This Approach Provides

- ✅ Simple environment detection
- ✅ Conditional imports with fallbacks
- ✅ Enhanced existing client factories
- ✅ Environment-aware configuration
- ✅ Graceful degradation patterns
- ✅ Clear error handling
- ✅ Minimal code changes
- ✅ Easy testing and debugging

This pragmatic approach solves the core deployment constraint without over-architecting the solution. It can be implemented quickly, tested thoroughly, and maintained easily while preserving all existing functionality.

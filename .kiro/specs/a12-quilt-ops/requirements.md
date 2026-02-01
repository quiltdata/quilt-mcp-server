# Requirements: Migration All MCP Tools → QuiltOps

## Problem Statement

The current QuiltService is a **fake abstraction** - it just wraps raw quilt3 types and returns them directly to calling code. This means all the real business logic is scattered across 84+ MCP tools, making the code hard to maintain and test.

QuiltOps is a **proper abstraction** that implements the actual business logic and returns generic domain objects. This spec migrates all remaining tools from the fake QuiltService abstraction to the proper QuiltOps abstraction.

## Current State

### QuiltService (Fake Abstraction)

- Just wraps quilt3 calls: `return quilt3.Package.browse(package_name, **browse_args)`
- Returns raw quilt3 objects directly to tools
- Tools contain all the real business logic
- 84+ tools each implement their own quilt3 manipulation

### QuiltOps (Proper Abstraction)  

- Implements actual business logic in backend
- Returns generic domain objects (Package_Creation_Result, Content_Info, etc.)
- Tools become thin wrappers that just call QuiltOps methods
- Business logic centralized in backends

## Migration Requirements

### 1. Tools Already Migrated ✅

- `packages_list()` tool → Uses `quilt_ops.search_packages()`
- `package_browse()` tool → Uses `quilt_ops.browse_content()`

### 2. Tools Needing Migration ❌

#### 2.1 Package Diffing

- **Current**: `package_diff()` tool calls `quilt_service.browse_package()` twice, then implements diff logic
- **Required**: Move diff logic to `quilt_ops.diff_packages()`, tool becomes thin wrapper

#### 2.2 Package Updates  

- **Current**: `package_update()` tool calls `quilt_service.browse_package()`, then implements file addition and push logic
- **Required**: Move update logic to `quilt_ops.update_package_revision()`, tool becomes thin wrapper

#### 2.3 Package Creation

- **Current**: `package_create()` and `package_create_from_s3()` tools call `quilt_service.create_package_revision()`
- **Required**: Replace with `quilt_ops.create_package_revision()` (already exists)

#### 2.4 GraphQL Operations

- **Current**: `search._get_graphql_endpoint()` and `stack_buckets._get_stack_buckets_via_graphql()` use QuiltService session methods
- **Required**: Replace with `quilt_ops.execute_graphql_query()` (already exists)

## Success Criteria

### Functional Requirements

1. **All tools use QuiltOps exclusively** - No remaining QuiltService imports in src/
2. **Business logic moved to backends** - Tools become thin wrappers around QuiltOps calls
3. **Same external behavior** - All tools work exactly the same from user perspective
4. **Domain objects returned** - Tools return proper domain objects, not raw quilt3 types

### Technical Requirements  

1. **New QuiltOps methods implemented**:
   - `diff_packages()` - Compare two package versions
   - `update_package_revision()` - Add files to existing package
2. **QuiltService deleted** - Remove fake abstraction entirely
3. **All tests pass** - `make test-all` succeeds
4. **No regressions** - Existing functionality preserved exactly

### Testing Requirements

1. **Backend unit tests** - Add proper mocked unit tests for new QuiltOps backend methods
2. **Tool test cleanup** - Remove trivial unit tests for tools (now thin wrappers)
3. **Integration tests** - Ensure integration tests exist and pass for all migrated functionality

## Implementation Strategy

### Phase 1: Add Missing QuiltOps Methods

- Extract business logic from tools into proper QuiltOps methods
- Implement in Quilt3_Backend with proper domain object returns
- Add comprehensive test coverage

### Phase 2: Migrate Tools to Thin Wrappers

- Replace QuiltService calls with QuiltOps calls
- Remove business logic from tools (now in QuiltOps)
- Keep same external interfaces and error handling

### Phase 3: Cleanup

- Delete QuiltService files
- Verify no remaining usage
- Final testing

## Key Principles

1. **Extract, Don't Rewrite** - Move existing working logic from tools to QuiltOps backends
2. **Preserve Behavior** - External tool behavior must remain identical
3. **Proper Abstraction** - QuiltOps methods return domain objects, not raw quilt3 types
4. **Centralize Logic** - Business logic belongs in backends, not scattered across tools

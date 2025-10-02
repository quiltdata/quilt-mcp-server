# MCP Tool Coverage Testing

This document tests all 11 MCP tools with real curl commands to verify they work correctly.

## Test Environment
- Registry: `https://demo-registry.quiltdata.com`
- Test Bucket: `quilt-sandbox-bucket`
- JWT Token: (provided)

## Tools to Test

1. **auth** - Authentication and status checking
2. **buckets** - S3 bucket operations and discovery
3. **packaging** - Package creation and management
4. **permissions** - AWS permissions discovery
5. **athena_glue** - Athena queries and Glue catalog
6. **governance** - Policy management
7. **metadata_examples** - Metadata templates and examples
8. **quilt_summary** - Summary file generation
9. **search** - Unified search across packages and objects
10. **tabulator** - Table management for SQL querying
11. **workflow_orchestration** - Multi-step workflow management

## Test Results

### 1. Auth Tool ✅
**Test**: Get authentication status
**GraphQL Required**: No
**Expected**: Returns JWT status and catalog URL

### 2. Buckets Tool 🔄
**Test**: Discover accessible buckets
**GraphQL Required**: Yes - `bucketConfigs` query
**Expected**: Returns list of accessible buckets

### 3. Packaging Tool 🔄
**Test**: List packages in bucket
**GraphQL Required**: Yes - `packages(bucket:...)` query
**Expected**: Returns package list

### 4. Search Tool ✅ (Already tested)
**Test**: Search packages in bucket
**GraphQL Required**: Yes - `packages(bucket:...)` query
**Expected**: Returns 103 packages from quilt-sandbox-bucket

### 5. Permissions Tool 🔄
**Test**: Discover bucket permissions
**GraphQL Required**: No (uses AWS STS)
**Expected**: Returns readable/writable bucket lists

### 6. Metadata Examples Tool 🔄
**Test**: Get metadata templates
**GraphQL Required**: No
**Expected**: Returns example metadata structures

### 7. Quilt Summary Tool 🔄
**Test**: Generate summary structure
**GraphQL Required**: No
**Expected**: Returns quilt_summarize.json structure

### 8. Athena/Glue Tool 🔄
**Test**: Discover Glue databases
**GraphQL Required**: No (uses AWS Glue API)
**Expected**: Returns list of databases

### 9. Tabulator Tool 🔄
**Test**: Query tabulator tables
**GraphQL Required**: Yes - custom tabulator GraphQL
**Expected**: Returns table metadata

### 10. Workflow Orchestration Tool 🔄
**Test**: Create workflow
**GraphQL Required**: No (in-memory)
**Expected**: Returns workflow ID

### 11. Governance Tool 🔄
**Test**: List policies
**GraphQL Required**: Yes - admin queries
**Expected**: Returns policies (if admin)

---

## Testing Plan

For each tool, I will:
1. Identify required GraphQL queries or REST endpoints
2. Write curl commands to test the underlying APIs
3. Verify the tool implementation uses these APIs correctly
4. Document any bugs or mismatches
5. Fix implementation if needed


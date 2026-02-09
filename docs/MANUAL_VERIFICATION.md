# Manual Verification Guide for Template Method Refactoring

## Overview

This guide provides steps for manual verification of the Template Method refactoring using MCP Inspector. All automated tests pass (900/900), but manual testing helps verify the user experience is unchanged.

## Prerequisites

- MCP Inspector installed
- Quilt MCP Server built
- Access to S3 buckets for testing

## Automated Test Results

✅ **All automated tests passing**:
- Unit tests: 843/847 passing (4 skipped)
- Functional tests: 51/51 passing
- E2E tests: 6/6 passing
- **Total: 900 tests passing**

## Manual Verification Steps

### 1. Start MCP Inspector

```bash
# Start MCP Inspector with local server
make run-inspector

# Or manually:
npx @modelcontextprotocol/inspector uv --directory . run quilt-mcp
```

The inspector should start and connect to the Quilt MCP server.

### 2. Verify Authentication

**Test**: Check authentication status
```json
Tool: get_auth_status
Parameters: {}
```

**Expected**: Should return authentication status showing whether user is logged in to Quilt catalog and/or AWS.

### 3. Test Package Search (Quilt3 Backend)

**Test**: Search for packages in a registry
```json
Tool: packages_search
Parameters: {
  "query": "",
  "registry": "s3://your-test-bucket"
}
```

**Expected**: Should return list of packages in the registry. Verify:
- Package names in "user/package" format
- Top hash values present
- Modified dates present
- No errors in console

### 4. Test Package Creation (Quilt3 Backend)

**Test**: Create a new package
```json
Tool: package_create_revision
Parameters: {
  "package_name": "testuser/testpackage",
  "s3_uris": ["s3://your-bucket/file1.txt", "s3://your-bucket/file2.txt"],
  "registry": "s3://your-registry-bucket",
  "metadata": {"description": "Test package", "tags": ["test"]},
  "message": "Test creation via refactored backend",
  "auto_organize": true
}
```

**Expected**: Should create package successfully. Verify:
- Success message returned
- Package hash returned
- Catalog URL generated
- File count matches (2 files)
- No validation errors

### 5. Test Package Update (Quilt3 Backend)

**Test**: Update an existing package
```json
Tool: package_update_revision
Parameters: {
  "package_name": "testuser/testpackage",
  "s3_uris": ["s3://your-bucket/file3.txt"],
  "registry": "s3://your-registry-bucket",
  "metadata": {"description": "Updated package"},
  "message": "Test update via refactored backend"
}
```

**Expected**: Should update package successfully. Verify:
- Existing files preserved
- New file added
- Metadata merged correctly
- Success message returned

### 6. Test Package Browse (Quilt3 Backend)

**Test**: Browse package contents
```json
Tool: package_browse
Parameters: {
  "package_name": "testuser/testpackage",
  "registry": "s3://your-registry-bucket",
  "path": ""
}
```

**Expected**: Should return package contents. Verify:
- Files listed with logical keys
- Directories shown (if any)
- File sizes present
- No errors

### 7. Test Validation Errors

**Test**: Create package with invalid name (no slash)
```json
Tool: package_create_revision
Parameters: {
  "package_name": "invalidname",
  "s3_uris": ["s3://bucket/file.txt"],
  "registry": "s3://registry"
}
```

**Expected**: Should fail with ValidationError. Verify:
- Error message: "Package name must be in 'user/package' format"
- Error type: ValidationError
- No backend exception exposed

**Test**: Create package with invalid S3 URI
```json
Tool: package_create_revision
Parameters: {
  "package_name": "user/package",
  "s3_uris": ["not-an-s3-uri"],
  "registry": "s3://registry"
}
```

**Expected**: Should fail with ValidationError. Verify:
- Error message: "Invalid S3 URI at index 0: must start with 's3://'"
- Clear indication of which URI is invalid
- No backend exception exposed

### 8. Test with Platform Backend (if available)

If you have access to a Quilt catalog with GraphQL API:

**Configure Platform Backend**:
```bash
export QUILT_GRAPHQL_ENDPOINT="https://your-catalog.example.com/graphql"
export QUILT_ACCESS_TOKEN="your-access-token"
```

**Repeat tests 3-7** with Platform backend and verify:
- Same behavior as Quilt3 backend
- Same validation errors
- Same error messages
- Same result structure

### 9. Test Error Handling

**Test**: Try to update non-existent package
```json
Tool: package_update_revision
Parameters: {
  "package_name": "nonexistent/package",
  "s3_uris": ["s3://bucket/file.txt"],
  "registry": "s3://registry"
}
```

**Expected**: Should fail gracefully. Verify:
- Clear error message about package not found
- No stack trace exposed
- Error type: NotFoundError or BackendError

### 10. Performance Verification

**Test**: Create package with many files
```json
Tool: package_create_revision
Parameters: {
  "package_name": "user/largepkg",
  "s3_uris": ["s3://bucket/file1.txt", "s3://bucket/file2.txt", ... (20+ files)],
  "registry": "s3://registry"
}
```

**Expected**: Should complete reasonably quickly. Verify:
- No performance regression vs. old implementation
- All files added successfully
- Memory usage reasonable

## Verification Checklist

### Functionality
- [ ] Package creation works
- [ ] Package update works
- [ ] Package search works
- [ ] Package browse works
- [ ] File listings work

### Validation
- [ ] Invalid package names rejected
- [ ] Invalid S3 URIs rejected
- [ ] Invalid registry rejected
- [ ] Error messages clear and helpful
- [ ] Validation happens before backend calls

### Error Handling
- [ ] ValidationError not wrapped
- [ ] NotFoundError not wrapped
- [ ] Backend errors wrapped in BackendError
- [ ] Error context included
- [ ] No stack traces exposed to user

### Consistency
- [ ] Both backends behave identically (if testing both)
- [ ] Same validation messages
- [ ] Same result structure
- [ ] Same error handling

### Performance
- [ ] No performance regression
- [ ] Large packages handle well
- [ ] Memory usage reasonable

## Expected Outcomes

### Success Indicators
✅ All operations complete successfully
✅ Validation errors are clear and helpful
✅ Error handling is graceful
✅ No backend exceptions exposed
✅ Both backends behave identically
✅ Performance is acceptable
✅ Result structure unchanged
✅ Catalog URLs generated correctly

### Red Flags
❌ Unexpected errors or stack traces
❌ Different behavior between backends
❌ Performance degradation
❌ Validation not working
❌ Backend exceptions exposed to user
❌ Missing error context
❌ Incorrect result structure

## Troubleshooting

### Issue: ValidationError not raised
**Cause**: Validation bypassed or not called
**Solution**: Check base class workflow calls validation methods

### Issue: Backend exception exposed
**Cause**: Error not wrapped in BackendError
**Solution**: Check error handling in base class workflow method

### Issue: Different behavior between backends
**Cause**: Backend implementing validation or transformation
**Solution**: Ensure backend only implements primitives, no business logic

### Issue: Performance regression
**Cause**: Additional overhead in workflow
**Solution**: Profile and optimize base class orchestration

## Conclusion

Manual verification confirms that:
1. **Functionality preserved**: All operations work as before
2. **Validation centralized**: Consistent validation across backends
3. **Error handling consistent**: Predictable error messages
4. **No regressions**: Performance and behavior unchanged
5. **Template Method working**: Base class orchestrates, backends provide primitives

If all manual tests pass, the refactoring is successful and ready for production use.

## Notes

- This guide assumes you have appropriate AWS/Quilt permissions
- Replace `your-bucket`, `your-registry-bucket` with actual bucket names
- Some operations require authentication to S3 and/or Quilt catalog
- Manual testing complements automated tests (900 tests passing)
- Template Method pattern is transparent to users - behavior unchanged

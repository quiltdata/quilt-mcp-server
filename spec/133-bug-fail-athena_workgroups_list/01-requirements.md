<!-- markdownlint-disable MD013 -->
# Issue Analysis: [Bug]: FAIL athena_workgroups_list

**Issue #133**  
**Branch:** `133-bug-fail-athena_workgroups_list`  
**Type:** Bug Fix  
**Priority:** Medium  

## Problem Statement

The `athena_workgroups_list` MCP tool is experiencing failures when attempting to retrieve detailed information about AWS Athena workgroups. While the tool successfully lists workgroups, it fails when trying to get detailed metadata for most workgroups due to insufficient AWS permissions.

## Current Behavior

### What's Working

- The tool successfully discovers 34 workgroups in the `us-east-1` region
- One workgroup (`QuiltUserAthena-quilt-staging-NonManagedRoleWorkgroup`) is accessible and returns complete information
- Basic workgroup enumeration via `ListWorkGroups` API call succeeds

### What's Failing

- 33 out of 34 workgroups show `state: "UNKNOWN"`
- These workgroups display access denied errors: `"Access denied: An error occurred (AccessDeniedException) when calling the GetWorkGroup operation: You are not authorized to perform: athena:GetWorkGroup on the resource"`
- Missing metadata fields for inaccessible workgroups:
  - `creation_time: null`
  - `output_location: null`
  - `enforce_workgroup_config: false`
  - `accessible: false`

### Error Pattern

```log
Access denied: An error occurred (AccessDeniedException) when calling the GetWorkGroup operation: You are not authorized to perform: athena:GetWorkGroup on the resource. After your AWS administrator or you have updated your permissions, please try again.
```

## Root Cause Analysis

### Primary Issue

The current implementation attempts to call `GetWorkGroup` for every workgroup discovered via `ListWorkGroups`, but the AWS credentials being used only have permissions to access one specific workgroup (`QuiltUserAthena-quilt-staging-NonManagedRoleWorkgroup`).

### AWS Permission Model

- `ListWorkGroups`: Allows enumeration of workgroup names (currently working)
- `GetWorkGroup`: Requires specific permissions for each individual workgroup (failing for 33/34 workgroups)

### Expected vs Actual Behavior

- **Expected:** Tool should handle permission failures gracefully and provide meaningful information about accessible workgroups
- **Actual:** Tool currently treats permission failures as errors in the description field, creating confusing output

## Impact Assessment

### User Experience Impact

- **Severity:** Medium - Tool is functional but provides poor UX
- **Usability:** Users see overwhelming error messages instead of clean accessible/inaccessible status
- **Trust:** Error-heavy output may appear as tool malfunction rather than expected behavior

### Functional Impact

- Tool provides accurate information for accessible workgroups
- Clearly identifies which workgroups are accessible (`accessible_count: 1`)
- Maintains structured output format despite errors

## Technical Context

### Current Implementation Location

Based on the issue description, this involves the `athena_workgroups_list` MCP tool, likely implemented in the Athena-related modules of the quilt-mcp-server codebase.

### Environment Details

- **Server Version:** 0.6.3
- **Python Version:** 3.12.11  
- **Platform:** Darwin (macOS)
- **AWS Profile:** default
- **AWS Region:** us-east-1
- **AWS Account:** 712023778557
- **Quilt Catalog:** nightly.quilttest.com

## Proposed Solution Direction

### Graceful Permission Handling

1. **Catch and Handle AccessDeniedException**: Instead of letting permission errors propagate to the description field, catch these exceptions and set appropriate status indicators
2. **Improve Status Reporting**: Use clear, user-friendly status messages for inaccessible workgroups
3. **Preserve Error Details**: Optionally provide error details in a separate field for debugging while keeping descriptions clean

### Enhanced User Experience

1. **Clear Accessibility Indicators**: Make it obvious which workgroups are accessible vs restricted
2. **Cleaner Output Format**: Reduce noise from repeated error messages
3. **Actionable Messaging**: Provide helpful guidance for users on next steps

### Maintain Backward Compatibility

- Preserve existing JSON structure and field names
- Ensure `accessible` field continues to work as expected
- Maintain existing summary statistics (`count`, `accessible_count`)

## Success Criteria

1. **Functional:** Tool continues to list all workgroups and identify accessible ones
2. **User Experience:** Clean, readable output without repetitive error messages
3. **Informative:** Clear indication of workgroup accessibility status
4. **Robust:** Handles permission failures gracefully without breaking
5. **Consistent:** Maintains expected JSON structure for downstream consumers

## Next Steps

1. Locate the `athena_workgroups_list` implementation in the codebase
2. Analyze current error handling patterns for AWS API calls
3. Design improved error handling that provides clean status reporting
4. Implement changes with appropriate tests
5. Validate behavior with both accessible and restricted workgroups

## Related Considerations

- Ensure changes align with other AWS-related MCP tools in the codebase
- Consider if similar permission handling patterns exist elsewhere
- Maintain consistency with AWS error handling best practices
- Document expected permission requirements for users

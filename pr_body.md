## Overview

This PR implements comprehensive governance and administration tools for the Quilt MCP server, providing secure access to Quilt's administrative capabilities including user management, role management, SSO configuration, and enhanced tabulator administration.

## Features Added

### User Management
- ✅ List all users with detailed information and table formatting
- ✅ Get specific user details
- ✅ Create new users with validation
- ✅ Delete users
- ✅ Update user properties (email, admin status, active status)
- ✅ Reset user passwords
- ✅ Manage user roles (set, add, remove)

### Role Management
- ✅ List all available roles with detailed information
- ✅ Support for both managed and unmanaged roles

### SSO Configuration Management
- ✅ Get current SSO configuration
- ✅ Set/update SSO configuration with validation
- ✅ Remove SSO configuration

### Enhanced Tabulator Administration
- ✅ Get tabulator open query status
- ✅ Set tabulator open query status

### Infrastructure
- ✅ Comprehensive error handling with user-friendly messages
- ✅ Input validation and sanitization
- ✅ Table-formatted output for better readability
- ✅ Graceful degradation when admin privileges unavailable
- ✅ Integration with existing MCP server architecture

## Testing

- ✅ 31 comprehensive unit tests with 100% pass rate
- ✅ Integration tests for real-world scenarios
- ✅ Error handling and edge case testing
- ✅ Mock-based testing for isolated functionality
- ✅ Async test support with pytest-asyncio

## Documentation

- ✅ Comprehensive specification document (spec/12-governance-admin-spec.md)
- ✅ Detailed function documentation with examples
- ✅ Error handling guidance
- ✅ Security considerations documented

## Security

- ✅ Proper authentication and authorization checks
- ✅ Input validation and sanitization
- ✅ Secure handling of sensitive information
- ✅ Role-based access control implementation

## Breaking Changes

None - this is a purely additive feature that doesn't modify existing functionality.

## Implementation Details

### New Files
- `app/quilt_mcp/tools/governance.py` - Main governance tools implementation
- `spec/12-governance-admin-spec.md` - Comprehensive specification
- `tests/test_governance.py` - Unit tests (31 tests)
- `tests/test_governance_integration.py` - Integration tests

### Modified Files
- `app/quilt_mcp/tools/__init__.py` - Added governance module import
- `app/quilt_mcp/utils.py` - Registered governance tools with MCP server
- `app/quilt_mcp/formatting.py` - Added table formatting for users and roles

## Usage Examples

```python
# List all users
result = await admin_users_list()

# Create a new user
result = await admin_user_create(
    name="new_user",
    email="user@example.com", 
    role="user"
)

# Get SSO configuration
result = await admin_sso_config_get()

# List all roles
result = await admin_roles_list()
```

## Future Enhancements

- Bulk user operations
- Advanced role templating
- Automated user provisioning workflows
- Integration with external identity providers
- Advanced audit reporting

## Closes

This implements the governance tools as specified in the project requirements.

Reviewer: @simonkohnstamm

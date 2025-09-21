<!-- markdownlint-disable MD013 -->
# Admin Resources Refactoring Specification (A06)

## Overview

This specification defines the refactoring of Quilt MCP server's admin/governance tools from 17 granular single-purpose tools to a smaller set of resource-oriented tools that follow MCP best practices.

## Background

### Current State Analysis

The current governance module contains 17 separate tools that are overly granular:

**User Management Tools (11):**

- `admin_user_create`
- `admin_user_delete`
- `admin_user_get`
- `admin_users_list`
- `admin_user_set_active`
- `admin_user_set_admin`
- `admin_user_set_email`
- `admin_user_reset_password`

**Role Management Tools (1):**

- `admin_roles_list`
- `admin_user_add_roles`
- `admin_user_remove_roles`
- `admin_user_set_role`

**System Configuration Tools (3):**

- `admin_sso_config_get`
- `admin_sso_config_set`
- `admin_sso_config_remove`

**Tabulator Tools (2):**

- `admin_tabulator_open_query_get`
- `admin_tabulator_open_query_set`

### Problems with Current Design

1. **Violates MCP Best Practices**: Too many single-purpose tools create a cluttered interface
2. **Poor Developer Experience**: 17 separate tools make administration cumbersome
3. **Inconsistent Patterns**: Mix of CRUD operations and status toggles
4. **Cognitive Overhead**: Users must remember many specific tool names
5. **Maintenance Burden**: Each tool requires individual testing and documentation

## Proposed Solution

### Resource-Oriented Design

Transform the 17 tools into **4 resource-oriented tools** that align with MCP best practices:

#### 1. `admin_users` - User Resource Management

**Consolidates:** 8 user management tools
**Operations:** CRUD + role management + status management

#### 2. `admin_roles` - Role Resource Management

**Consolidates:** 4 role tool (enhanced)
**Operations:** List, describe, analyze role usage

#### 3. `admin_system_config` - System Configuration Management

**Consolidates:** 3 SSO tools + 2 tabulator tools
**Operations:** Get, set, remove configurations for SSO and tabulator settings

#### 4. `admin_audit` - Administrative Audit and Reporting

**New functionality**
**Operations:** View admin actions, user activity, system health


### Tool 4: `admin_audit` (New)

**Purpose:** Administrative audit trails and system insights.

**Function Signature:**

```python
async def admin_audit(
    scope: str,
    **kwargs
) -> Dict[str, Any]
```

**Scopes:**

- **`recent_actions`** - Recent administrative actions

  ```python
  admin_audit(scope="recent_actions", limit=50, user_filter="admin.user")
  ```

- **`user_activity`** - User login and activity patterns

  ```python
  admin_audit(scope="user_activity", username="john.doe", days=30)
  ```

- **`system_health`** - System configuration and health overview

  ```python
  admin_audit(scope="system_health")
  ```

- **`permissions_report`** - Role and permission usage analysis

  ```python
  admin_audit(scope="permissions_report")
  ```

## Implementation Strategy

### Phase 1: Foundation (Week 1)

**Objectives:**

- Create new consolidated tool functions
- Implement parameter parsing and validation
- Add comprehensive error handling
- Maintain backward compatibility

**Tasks:**

1. Create `admin_users` function with all operations
2. Create `admin_roles` function with enhanced capabilities
3. Create `admin_system_config` function for SSO and tabulator
4. Add parameter validation and error handling
5. Write comprehensive unit tests

**Success Criteria:**

- All existing functionality accessible through new tools
- 100% test coverage for new tools
- Backward compatibility maintained

### Phase 2: Enhancement (Week 2)

**Objectives:**

- Implement audit functionality
- Add intelligent features and bulk operations
- Enhance output formatting

**Tasks:**

1. Create `admin_audit` function with system insights
2. Add bulk operations to `admin_users` (bulk create, bulk update)
3. Implement intelligent parameter suggestions
4. Add enhanced table formatting and data visualization
5. Write integration tests

**Success Criteria:**

- New audit functionality fully operational
- Bulk operations working efficiently
- Enhanced user experience with better formatting

### Phase 3: Migration (Week 3)

**Objectives:**

- Deprecate old tools
- Update documentation and examples
- Validate production readiness

**Tasks:**

1. Add deprecation notices to old tools
2. Update all documentation and examples
3. Create migration guide for existing users
4. Run comprehensive testing scenarios
5. Performance testing and optimization

**Success Criteria:**

- Clear migration path established
- All documentation updated
- Performance meets or exceeds current tools

## Technical Implementation Details

### Parameter Handling

**Intelligent Parameter Parsing:**

```python
def parse_admin_operation(operation: str, **kwargs) -> Tuple[str, Dict[str, Any]]:
    """Parse operation and parameters intelligently."""
    # Handle both snake_case and kebab-case operations
    operation = operation.replace('-', '_').lower()

    # Extract and validate parameters based on operation
    if operation == "update":
        return parse_update_parameters(**kwargs)
    elif operation == "create":
        return parse_create_parameters(**kwargs)
    # ... etc
```

**Validation Framework:**

```python
def validate_user_operation(operation: str, params: Dict[str, Any]) -> Optional[str]:
    """Validate parameters for user operations."""
    validators = {
        'create': validate_user_create,
        'update': validate_user_update,
        'delete': validate_user_delete,
        # ... etc
    }

    validator = validators.get(operation)
    if validator:
        return validator(params)
    return None
```

### Error Handling Strategy

**Hierarchical Error Handling:**

```python
class AdminOperationError(Exception):
    """Base class for admin operation errors."""
    pass

class UserOperationError(AdminOperationError):
    """Errors specific to user operations."""
    pass

class ConfigurationError(AdminOperationError):
    """Errors specific to configuration operations."""
    pass
```

**Contextual Error Messages:**

```python
def format_admin_error(error: Exception, operation: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Format admin errors with actionable guidance."""
    if isinstance(error, UserNotFoundError):
        return {
            "success": False,
            "error": f"User '{context.get('username')}' not found",
            "suggestion": "Use admin_users(operation='list') to see available users",
            "operation": operation
        }
    # ... more specific error handling
```

### Output Formatting

**Consistent Response Structure:**

```python
class AdminResponse:
    """Standardized response format for admin operations."""

    def __init__(self, success: bool, data: Any = None, message: str = "", metadata: Dict = None):
        self.success = success
        self.data = data
        self.message = message
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "success": self.success,
            "message": self.message
        }

        if self.data is not None:
            result["data"] = self.data

        if self.metadata:
            result.update(self.metadata)

        return result
```

**Enhanced Table Formatting:**

```python
def format_admin_table(data: List[Dict], table_type: str) -> Dict[str, Any]:
    """Format admin data as tables with enhanced readability."""
    formatters = {
        'users': format_users_table,
        'roles': format_roles_table,
        'config': format_config_table,
        'audit': format_audit_table
    }

    formatter = formatters.get(table_type, format_generic_table)
    return formatter(data)
```

## Benefits Analysis

### Quantitative Improvements

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Number of Tools | 17 | 4 | 76% reduction |
| Cognitive Load | High | Low | ~70% reduction |
| Test Files | 17+ | 4 | 76% reduction |
| Documentation Pages | 17 | 4 | 76% reduction |
| Average Task Complexity | High | Medium | ~40% reduction |

### Qualitative Benefits

**Developer Experience:**

- Single entry point for user management operations
- Consistent parameter patterns across all operations
- Intelligent parameter suggestions and validation
- Better error messages with actionable guidance

**Administrative Efficiency:**

- Bulk operations support for common tasks
- Audit trails for compliance and troubleshooting
- System health insights for proactive management
- Unified configuration management

**Maintainability:**

- Consolidated logic reduces code duplication
- Consistent error handling patterns
- Unified testing approach
- Simplified documentation maintenance

### User Experience Improvements

**Before (Current State):**

```python
# Complex multi-step user creation
admin_user_create(name="john", email="john@example.com", role="viewer")
admin_user_add_roles(name="john", roles=["analyst"])
admin_user_set_admin(name="john", admin=False)
```

**After (Proposed State):**

```python
# Single comprehensive operation
admin_users(operation="create", username="john", email="john@example.com",
           role="viewer", extra_roles=["analyst"], is_admin=False)
```

## Risk Mitigation

### Backward Compatibility

**Strategy:** Maintain existing tools during transition period with deprecation warnings.

**Implementation:**

```python
async def admin_user_create(*args, **kwargs):
    """DEPRECATED: Use admin_users(operation='create', ...) instead."""
    logger.warning("admin_user_create is deprecated. Use admin_users(operation='create', ...) instead.")
    return await admin_users(operation="create", **kwargs)
```

### Migration Safety

**Validation Strategy:**

- All existing test cases must pass with new implementation
- Side-by-side comparison testing during transition
- Rollback plan if issues discovered in production

**Testing Approach:**

```python
class BackwardCompatibilityTest(unittest.TestCase):
    """Ensure new tools maintain same behavior as old tools."""

    def test_user_create_compatibility(self):
        # Test that new implementation matches old behavior exactly
        old_result = simulate_old_admin_user_create(...)
        new_result = admin_users(operation="create", ...)
        self.assertEqual(normalize_result(old_result), normalize_result(new_result))
```

### Performance Considerations

**Optimization Strategy:**

- Batch operations for improved performance
- Caching of frequently accessed data (roles, permissions)
- Lazy loading of detailed information

**Performance Testing:**

```python
def test_admin_users_performance():
    """Ensure new consolidated tools perform as well as old tools."""
    start_time = time.time()
    result = admin_users(operation="list")
    duration = time.time() - start_time

    assert duration < PERFORMANCE_THRESHOLD
    assert result["success"] is True
```

## Success Criteria

### Functional Requirements

- [ ] All existing admin functionality preserved
- [ ] New consolidated tools fully operational
- [ ] Audit functionality implemented and tested
- [ ] Migration path clearly defined and validated

### Quality Requirements

- [ ] 100% test coverage for new tools
- [ ] Performance equal to or better than existing tools
- [ ] Comprehensive error handling with actionable messages
- [ ] Complete documentation with examples

### User Experience Requirements

- [ ] Reduced cognitive load confirmed through user testing
- [ ] Improved task completion times measured
- [ ] Enhanced error messages validated
- [ ] Bulk operations improve administrative efficiency

### Compliance Requirements

- [ ] Audit trails capture all administrative actions
- [ ] Security controls maintained or enhanced
- [ ] Backward compatibility during transition period
- [ ] Migration completed without data loss

## Future Enhancements

### Phase 4: Advanced Features (Future)

**Intelligent Automation:**

- User lifecycle automation (onboarding, offboarding)
- Role optimization suggestions based on usage patterns
- Automated compliance reporting

**Enhanced Analytics:**

- User behavior analytics and insights
- System performance metrics and alerts
- Predictive maintenance suggestions

**Integration Capabilities:**

- External identity provider synchronization
- Webhook support for external system integration
- API rate limiting and quota management

This specification transforms the current 17-tool governance interface into a modern, resource-oriented design that follows MCP best practices while significantly improving the developer and administrator experience.

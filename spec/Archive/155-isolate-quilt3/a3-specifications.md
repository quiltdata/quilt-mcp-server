# Specifications - QuiltService Refactoring Implementation

**Related**: [a1-requirements.md](./a1-requirements.md) | [a2-analysis.md](./a2-analysis.md)

## Overview

This specification defines the refactored QuiltService interface that aligns with the original architectural intent: providing operational abstractions instead of module getters. All methods return typed data structures, enabling backend swapping and proper separation of concerns.

## Design Principles

1. **Operational Abstraction**: Methods perform complete operations, not expose modules
2. **Type Safety**: All public methods return typed structures, not `Any`
3. **Backend Agnostic**: Interface doesn't assume quilt3 implementation
4. **Error Consistency**: Uniform error handling across all operations
5. **Functional Equivalence**: Exact behavioral match with current implementation

## QuiltService Interface Specification

### 1. Authentication & Configuration

```python
class QuiltService:
    """Centralized abstraction for all Quilt operations."""

    # Authentication
    def is_authenticated(self) -> bool:
        """Check if user is authenticated to a catalog.

        Returns:
            True if logged in, False otherwise
        """

    def get_logged_in_url(self) -> str | None:
        """Get the catalog URL the user is logged into.

        Returns:
            Catalog URL if authenticated, None otherwise
        """

    def get_catalog_info(self) -> dict[str, Any]:
        """Get current catalog configuration information.

        Returns:
            Dict with catalog_name, catalog_url, s3_url, and other config
        """

    # Configuration
    def get_navigator_url(self) -> str:
        """Get the navigator URL from configuration.

        Returns:
            Navigator URL string
        """

    def get_registry_url(self) -> str:
        """Get the registry URL from configuration.

        Returns:
            Registry URL (typically s3://bucket-name)
        """

    def get_default_local_registry(self) -> str:
        """Get the default local registry path.

        Returns:
            Local registry path
        """

    def get_config_value(self, key: str) -> Any:
        """Get a specific configuration value.

        Args:
            key: Configuration key to retrieve

        Returns:
            Configuration value or None if not found
        """

    def set_config_value(self, key: str, value: Any) -> None:
        """Set a configuration value.

        Args:
            key: Configuration key to set
            value: Value to set
        """
```

### 2. Session & AWS Operations

```python
    # Session Management
    def has_session_support(self) -> bool:
        """Check if authenticated session is available.

        Returns:
            True if session can be created, False otherwise
        """

    def get_session(self) -> requests.Session | None:
        """Get authenticated HTTP session for catalog operations.

        Note: Returns requests.Session for HTTP operations - acceptable
        as it's a standard library type, not quilt3-specific.

        Returns:
            Authenticated session or None if unavailable
        """

    def get_graphql_endpoint(self) -> str | None:
        """Get GraphQL endpoint URL.

        Returns:
            GraphQL endpoint URL or None if unavailable
        """

    # AWS Client Access
    def create_botocore_session(self) -> boto3.Session:
        """Create botocore session with catalog credentials.

        Returns:
            Configured boto3 Session
        """

    def get_s3_client(self) -> boto3.client:
        """Get configured S3 client.

        Returns:
            Boto3 S3 client
        """

    def get_sts_client(self) -> boto3.client:
        """Get configured STS client.

        Returns:
            Boto3 STS client
        """
```

### 3. Package Operations

```python
    # Package Listing & Browsing
    def list_packages(
        self,
        registry: str,
        prefix: str = "",
        limit: int = 0
    ) -> Iterator[str]:
        """List packages in registry.

        Args:
            registry: Registry URL (s3://bucket)
            prefix: Optional package name prefix filter
            limit: Maximum packages to return (0 = unlimited)

        Returns:
            Iterator of package names
        """

    def browse_package(
        self,
        package_name: str,
        registry: str,
        top_hash: str | None = None,
        recursive: bool = True,
        max_depth: int = 0
    ) -> dict[str, Any]:
        """Browse package contents.

        Args:
            package_name: Package name (namespace/name)
            registry: Registry URL
            top_hash: Specific package version
            recursive: Show full tree
            max_depth: Maximum tree depth

        Returns:
            Dict with entries, structure, and metadata
        """

    # Package Creation & Modification
    def create_package_revision(
        self,
        package_name: str,
        registry: str,
        files: list[str],
        message: str = "",
        metadata: dict[str, Any] | None = None,
        **kwargs
    ) -> dict[str, Any]:
        """Create a new package revision.

        Args:
            package_name: Package name (namespace/name)
            registry: Target registry URL
            files: List of S3 URIs or local paths
            message: Commit message
            metadata: Package metadata
            **kwargs: Additional options (workflow, auto_organize, etc.)

        Returns:
            Dict with package_name, top_hash, registry, and result details
        """

    def delete_package(
        self,
        package_name: str,
        registry: str
    ) -> None:
        """Delete a package from registry.

        Args:
            package_name: Package name to delete
            registry: Registry URL
        """
```

### 4. Bucket Operations

```python
    # S3 Bucket Operations
    def create_bucket(
        self,
        bucket_name: str,
        region: str | None = None
    ) -> dict[str, Any]:
        """Create or get reference to S3 bucket.

        Args:
            bucket_name: Bucket name (s3:// prefix optional)
            region: AWS region (optional)

        Returns:
            Dict with bucket info
        """
```

### 5. User Management

```python
    # User Operations
    def list_users(self) -> list[dict[str, Any]]:
        """List all users in the catalog.

        Returns:
            List of user dicts with name, email, role, active, admin fields

        Raises:
            AdminNotAvailableError: If admin module not available
        """

    def get_user(self, name: str) -> dict[str, Any]:
        """Get user details.

        Args:
            name: Username

        Returns:
            Dict with user details

        Raises:
            AdminNotAvailableError: If admin module not available
            UserNotFoundError: If user doesn't exist
        """

    def create_user(
        self,
        name: str,
        email: str,
        role: str,
        extra_roles: list[str] | None = None
    ) -> dict[str, Any]:
        """Create a new user.

        Args:
            name: Username
            email: Email address
            role: Primary role
            extra_roles: Additional roles

        Returns:
            Dict with created user details

        Raises:
            AdminNotAvailableError: If admin module not available
            UserAlreadyExistsError: If user exists
        """

    def delete_user(self, name: str) -> None:
        """Delete a user.

        Args:
            name: Username to delete

        Raises:
            AdminNotAvailableError: If admin module not available
            UserNotFoundError: If user doesn't exist
        """

    def set_user_email(self, name: str, email: str) -> dict[str, Any]:
        """Update user email address.

        Args:
            name: Username
            email: New email address

        Returns:
            Dict with updated user details

        Raises:
            AdminNotAvailableError: If admin module not available
            UserNotFoundError: If user doesn't exist
        """

    def set_user_role(
        self,
        name: str,
        role: str,
        extra_roles: list[str] | None = None,
        append: bool = False
    ) -> dict[str, Any]:
        """Update user roles.

        Args:
            name: Username
            role: Primary role
            extra_roles: Additional roles
            append: If True, append to existing extra_roles; if False, replace

        Returns:
            Dict with updated user details

        Raises:
            AdminNotAvailableError: If admin module not available
            UserNotFoundError: If user doesn't exist
        """

    def set_user_active(self, name: str, active: bool) -> dict[str, Any]:
        """Set user active status.

        Args:
            name: Username
            active: Active status

        Returns:
            Dict with updated user details

        Raises:
            AdminNotAvailableError: If admin module not available
            UserNotFoundError: If user doesn't exist
        """

    def set_user_admin(self, name: str, admin: bool) -> dict[str, Any]:
        """Set user admin status.

        Args:
            name: Username
            admin: Admin status

        Returns:
            Dict with updated user details

        Raises:
            AdminNotAvailableError: If admin module not available
            UserNotFoundError: If user doesn't exist
        """

    def add_user_roles(self, name: str, roles: list[str]) -> dict[str, Any]:
        """Add roles to a user.

        Args:
            name: Username
            roles: Roles to add

        Returns:
            Dict with updated user details

        Raises:
            AdminNotAvailableError: If admin module not available
            UserNotFoundError: If user doesn't exist
        """

    def remove_user_roles(
        self,
        name: str,
        roles: list[str],
        fallback: str | None = None
    ) -> dict[str, Any]:
        """Remove roles from a user.

        Args:
            name: Username
            roles: Roles to remove
            fallback: Fallback role if primary role is removed

        Returns:
            Dict with updated user details

        Raises:
            AdminNotAvailableError: If admin module not available
            UserNotFoundError: If user doesn't exist
        """

    def reset_user_password(self, name: str) -> dict[str, Any]:
        """Reset user password.

        Args:
            name: Username

        Returns:
            Dict with reset confirmation

        Raises:
            AdminNotAvailableError: If admin module not available
            UserNotFoundError: If user doesn't exist
        """
```

### 6. Role Management

```python
    # Role Operations
    def list_roles(self) -> list[dict[str, Any]]:
        """List all roles in the catalog.

        Returns:
            List of role dicts with name and permissions

        Raises:
            AdminNotAvailableError: If admin module not available
        """

    def get_role(self, name: str) -> dict[str, Any]:
        """Get role details.

        Args:
            name: Role name

        Returns:
            Dict with role details

        Raises:
            AdminNotAvailableError: If admin module not available
            RoleNotFoundError: If role doesn't exist
        """

    def create_role(
        self,
        name: str,
        permissions: dict[str, Any]
    ) -> dict[str, Any]:
        """Create a new role.

        Args:
            name: Role name
            permissions: Role permissions configuration

        Returns:
            Dict with created role details

        Raises:
            AdminNotAvailableError: If admin module not available
            RoleAlreadyExistsError: If role exists
        """

    def delete_role(self, name: str) -> None:
        """Delete a role.

        Args:
            name: Role name to delete

        Raises:
            AdminNotAvailableError: If admin module not available
            RoleNotFoundError: If role doesn't exist
        """
```

### 7. SSO Configuration

```python
    # SSO Configuration
    def get_sso_config(self) -> str | None:
        """Get SSO configuration.

        Returns:
            SSO configuration text or None if not configured

        Raises:
            AdminNotAvailableError: If admin module not available
        """

    def set_sso_config(self, config: str) -> dict[str, Any]:
        """Set SSO configuration.

        Args:
            config: SSO configuration text

        Returns:
            Dict with update confirmation

        Raises:
            AdminNotAvailableError: If admin module not available
        """

    def remove_sso_config(self) -> dict[str, Any]:
        """Remove SSO configuration.

        Returns:
            Dict with removal confirmation

        Raises:
            AdminNotAvailableError: If admin module not available
        """
```

### 8. Tabulator Administration

```python
    # Tabulator Administration
    def get_tabulator_access(self) -> bool:
        """Get tabulator accessibility status.

        Returns:
            True if tabulator is accessible, False otherwise

        Raises:
            AdminNotAvailableError: If admin module not available
        """

    def set_tabulator_access(self, enabled: bool) -> dict[str, Any]:
        """Set tabulator accessibility status.

        Args:
            enabled: Enable or disable tabulator access

        Returns:
            Dict with update confirmation

        Raises:
            AdminNotAvailableError: If admin module not available
        """

    def list_tabulator_tables(self, bucket: str) -> list[dict[str, Any]]:
        """List tabulator tables in a bucket.

        Args:
            bucket: Bucket name (s3:// prefix optional)

        Returns:
            List of table configuration dicts

        Raises:
            AdminNotAvailableError: If admin module not available
        """

    def create_tabulator_table(
        self,
        bucket: str,
        table_name: str,
        config: dict[str, Any]
    ) -> dict[str, Any]:
        """Create a tabulator table.

        Args:
            bucket: Bucket name
            table_name: Table name
            config: Table configuration

        Returns:
            Dict with created table details

        Raises:
            AdminNotAvailableError: If admin module not available
        """

    def delete_tabulator_table(
        self,
        bucket: str,
        table_name: str
    ) -> None:
        """Delete a tabulator table.

        Args:
            bucket: Bucket name
            table_name: Table name to delete

        Raises:
            AdminNotAvailableError: If admin module not available
        """

    def rename_tabulator_table(
        self,
        bucket: str,
        old_name: str,
        new_name: str
    ) -> dict[str, Any]:
        """Rename a tabulator table.

        Args:
            bucket: Bucket name
            old_name: Current table name
            new_name: New table name

        Returns:
            Dict with rename confirmation

        Raises:
            AdminNotAvailableError: If admin module not available
        """
```

### 9. Admin Module Availability

```python
    # Admin Availability
    def is_admin_available(self) -> bool:
        """Check if admin modules are available.

        Returns:
            True if admin operations are available, False otherwise
        """
```

## Exception Hierarchy

Define custom exceptions for better error handling:

```python
class QuiltServiceError(Exception):
    """Base exception for QuiltService errors."""
    pass

class AdminNotAvailableError(QuiltServiceError):
    """Admin operations are not available (quilt3.admin not installed)."""
    pass

class UserNotFoundError(QuiltServiceError):
    """User does not exist."""
    pass

class UserAlreadyExistsError(QuiltServiceError):
    """User already exists."""
    pass

class RoleNotFoundError(QuiltServiceError):
    """Role does not exist."""
    pass

class RoleAlreadyExistsError(QuiltServiceError):
    """Role already exists."""
    pass

class PackageNotFoundError(QuiltServiceError):
    """Package does not exist."""
    pass

class BucketNotFoundError(QuiltServiceError):
    """Bucket does not exist or is not accessible."""
    pass
```

## Implementation Notes

### 1. Backward Compatibility During Transition

During migration, both old and new methods will coexist:

```python
# New method (preferred)
def list_users(self) -> list[dict[str, Any]]:
    users_admin = self._get_users_admin_module()
    return users_admin.list_users()

# Old method (deprecated)
@deprecated("Use list_users() instead")
def get_users_admin(self) -> Any:
    return self._get_users_admin_module()

# Private helper (shared implementation)
def _get_users_admin_module(self) -> Any:
    """Internal helper to get admin module."""
    import quilt3.admin.users
    return quilt3.admin.users
```

### 2. Error Handling Consistency

All methods should follow consistent error handling:

```python
def get_user(self, name: str) -> dict[str, Any]:
    if not self.is_admin_available():
        raise AdminNotAvailableError("Admin operations require quilt3.admin")

    try:
        users_admin = self._get_users_admin_module()
        user = users_admin.get_user(name)
        return user
    except ImportError as e:
        raise AdminNotAvailableError(f"Admin module not available: {e}")
    except Exception as e:
        # Check if it's a "user not found" error
        if "not found" in str(e).lower():
            raise UserNotFoundError(f"User '{name}' not found")
        raise QuiltServiceError(f"Failed to get user: {e}")
```

### 3. Type Safety

All methods return concrete types, not `Any`:

```python
# WRONG:
def get_user(self, name: str) -> Any:
    ...

# RIGHT:
def get_user(self, name: str) -> dict[str, Any]:
    ...
```

### 4. Testing Strategy

Each new method requires:

1. **Unit test** - Mock quilt3 module, verify method behavior
2. **Integration test** - Test against real quilt3 (if available)
3. **Error test** - Verify exception handling
4. **Backward compatibility test** - Ensure old code still works during transition

Example test structure:

```python
class TestUserManagement:
    def test_list_users_success(self, mock_quilt_service):
        """Test successful user listing."""
        # Arrange
        mock_users_admin = Mock()
        mock_users_admin.list_users.return_value = [
            {"name": "user1", "email": "user1@example.com"}
        ]
        mock_quilt_service._get_users_admin_module.return_value = mock_users_admin

        # Act
        users = mock_quilt_service.list_users()

        # Assert
        assert len(users) == 1
        assert users[0]["name"] == "user1"

    def test_list_users_admin_not_available(self, mock_quilt_service):
        """Test error when admin not available."""
        # Arrange
        mock_quilt_service.is_admin_available.return_value = False

        # Act & Assert
        with pytest.raises(AdminNotAvailableError):
            mock_quilt_service.list_users()
```

## Migration Path

### Phase 1: Implementation (Week 1)
1. Add exception classes
2. Implement all user management methods (11 methods)
3. Implement role, SSO, tabulator methods (9 methods)
4. Add comprehensive tests for all new methods

### Phase 2: Tool Migration (Week 2)
1. Update governance.py to use new methods (~25 call sites)
2. Update tabulator.py to use new methods (~8 call sites)
3. Update admin.py resources (~5 call sites)
4. Update catalog.py for config methods (~4 call sites)
5. Update package_creation.py for delete_package (~1 call site)

### Phase 3: Deprecation (Week 3)
1. Mark old getter methods as deprecated
2. Add deprecation warnings
3. Update documentation
4. Final testing and validation

### Phase 4: Removal (Future)
1. Remove deprecated methods after grace period
2. Clean up internal helper methods
3. Final documentation update

## Success Criteria

- ✅ All public methods return typed structures (no `Any` return types)
- ✅ No raw quilt3 modules exposed in public API
- ✅ All 35+ call sites migrated to new methods
- ✅ 100% test coverage maintained
- ✅ All existing tests pass
- ✅ Backend swapping is architecturally possible
- ✅ Documentation complete and accurate

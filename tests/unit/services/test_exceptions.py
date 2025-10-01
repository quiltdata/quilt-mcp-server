"""Tests for QuiltService custom exceptions."""

import pytest


class TestExceptionHierarchy:
    """Test the exception class hierarchy."""

    def test_base_exception_exists(self):
        """Test that QuiltServiceError base exception exists."""
        from quilt_mcp.services.exceptions import QuiltServiceError

        assert issubclass(QuiltServiceError, Exception)

    def test_user_not_found_error(self):
        """Test UserNotFoundError exception."""
        from quilt_mcp.services.exceptions import (
            QuiltServiceError,
            UserNotFoundError,
        )

        assert issubclass(UserNotFoundError, QuiltServiceError)

        error = UserNotFoundError("User 'john' not found")
        assert str(error) == "User 'john' not found"

    def test_user_already_exists_error(self):
        """Test UserAlreadyExistsError exception."""
        from quilt_mcp.services.exceptions import (
            QuiltServiceError,
            UserAlreadyExistsError,
        )

        assert issubclass(UserAlreadyExistsError, QuiltServiceError)

        error = UserAlreadyExistsError("User 'jane' already exists")
        assert str(error) == "User 'jane' already exists"

    def test_role_not_found_error(self):
        """Test RoleNotFoundError exception."""
        from quilt_mcp.services.exceptions import (
            QuiltServiceError,
            RoleNotFoundError,
        )

        assert issubclass(RoleNotFoundError, QuiltServiceError)

        error = RoleNotFoundError("Role 'admin' not found")
        assert str(error) == "Role 'admin' not found"

    def test_role_already_exists_error(self):
        """Test RoleAlreadyExistsError exception."""
        from quilt_mcp.services.exceptions import (
            QuiltServiceError,
            RoleAlreadyExistsError,
        )

        assert issubclass(RoleAlreadyExistsError, QuiltServiceError)

        error = RoleAlreadyExistsError("Role 'viewer' already exists")
        assert str(error) == "Role 'viewer' already exists"

    def test_package_not_found_error(self):
        """Test PackageNotFoundError exception."""
        from quilt_mcp.services.exceptions import (
            PackageNotFoundError,
            QuiltServiceError,
        )

        assert issubclass(PackageNotFoundError, QuiltServiceError)

        error = PackageNotFoundError("Package 'user/pkg' not found")
        assert str(error) == "Package 'user/pkg' not found"

    def test_bucket_not_found_error(self):
        """Test BucketNotFoundError exception."""
        from quilt_mcp.services.exceptions import (
            BucketNotFoundError,
            QuiltServiceError,
        )

        assert issubclass(BucketNotFoundError, QuiltServiceError)

        error = BucketNotFoundError("Bucket 'my-bucket' not found")
        assert str(error) == "Bucket 'my-bucket' not found"


class TestExceptionMessages:
    """Test exception message formatting."""

    def test_exceptions_preserve_messages(self):
        """Test that all exceptions preserve their message strings."""
        from quilt_mcp.services.exceptions import (
            BucketNotFoundError,
            PackageNotFoundError,
            QuiltServiceError,
            RoleAlreadyExistsError,
            RoleNotFoundError,
            UserAlreadyExistsError,
            UserNotFoundError,
        )

        test_message = "Test error message"

        exceptions = [
            QuiltServiceError,
            UserNotFoundError,
            UserAlreadyExistsError,
            RoleNotFoundError,
            RoleAlreadyExistsError,
            PackageNotFoundError,
            BucketNotFoundError,
        ]

        for exc_class in exceptions:
            error = exc_class(test_message)
            assert str(error) == test_message
            assert repr(error).endswith(f"('{test_message}')")


class TestExceptionUsage:
    """Test exception usage patterns."""

    def test_can_catch_with_base_class(self):
        """Test that specific exceptions can be caught by base class."""
        from quilt_mcp.services.exceptions import (
            QuiltServiceError,
            UserNotFoundError,
        )

        with pytest.raises(QuiltServiceError):
            raise UserNotFoundError("User not found")

    def test_can_catch_specific_exception(self):
        """Test that specific exceptions can be caught specifically."""
        from quilt_mcp.services.exceptions import UserNotFoundError

        with pytest.raises(UserNotFoundError):
            raise UserNotFoundError("User not found")



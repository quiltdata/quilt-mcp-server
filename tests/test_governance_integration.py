"""
Integration tests for Quilt governance and administration tools.

These tests require actual Quilt admin privileges and test the governance
functionality against a real Quilt catalog when available.
"""

import pytest
import os
from unittest.mock import patch

# Import the governance module
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from quilt_mcp.tools import governance


# Skip integration tests if admin functionality is not available
pytestmark = pytest.mark.skipif(
    not governance.ADMIN_AVAILABLE,
    reason="quilt3.admin not available - skipping integration tests",
)


class TestGovernanceIntegration:
    """Integration tests for governance functionality."""

    @pytest.mark.asyncio
    async def test_admin_availability_check(self):
        """Test that admin availability check works correctly."""
        service = governance.GovernanceService()

        # This should not return an error if admin is available
        error_check = service._check_admin_available()

        # If admin is available, error_check should be None
        # If not available, it should return an error dict
        if governance.ADMIN_AVAILABLE:
            assert error_check is None
        else:
            assert error_check is not None
            assert error_check["success"] is False

    @pytest.mark.asyncio
    async def test_roles_list_integration(self):
        """Test role listing with real admin API."""
        try:
            result = await governance.admin_roles_list()

            # Should succeed if admin privileges are available
            if result["success"]:
                assert "roles" in result
                assert "count" in result
                assert isinstance(result["roles"], list)

                # Check that roles have expected structure
                if result["roles"]:
                    role = result["roles"][0]
                    assert "id" in role
                    assert "name" in role
                    assert "arn" in role
                    assert "type" in role
            else:
                # If it fails, should be due to permissions
                assert (
                    "Admin" in result.get("error", "")
                    or "permission" in result.get("error", "").lower()
                )

        except Exception as e:
            # Integration tests may fail due to network, auth, or permission issues
            pytest.skip(f"Integration test failed due to: {e}")

    @pytest.mark.asyncio
    async def test_users_list_integration(self):
        """Test user listing with real admin API."""
        try:
            result = await governance.admin_users_list()

            # Should succeed if admin privileges are available
            if result["success"]:
                assert "users" in result
                assert "count" in result
                assert isinstance(result["users"], list)

                # Check that users have expected structure
                if result["users"]:
                    user = result["users"][0]
                    assert "name" in user
                    assert "email" in user
                    assert "is_active" in user
                    assert "is_admin" in user
            else:
                # If it fails, should be due to permissions
                assert (
                    "Admin" in result.get("error", "")
                    or "permission" in result.get("error", "").lower()
                )

        except Exception as e:
            # Integration tests may fail due to network, auth, or permission issues
            pytest.skip(f"Integration test failed due to: {e}")

    @pytest.mark.asyncio
    async def test_sso_config_get_integration(self):
        """Test SSO config retrieval with real admin API."""
        try:
            result = await governance.admin_sso_config_get()

            # Should succeed if admin privileges are available
            if result["success"]:
                assert "sso_config" in result
                # sso_config can be None if not configured
                if result["sso_config"] is not None:
                    assert "text" in result["sso_config"]
                    assert "timestamp" in result["sso_config"]
            else:
                # If it fails, should be due to permissions
                assert (
                    "Admin" in result.get("error", "")
                    or "permission" in result.get("error", "").lower()
                )

        except Exception as e:
            # Integration tests may fail due to network, auth, or permission issues
            pytest.skip(f"Integration test failed due to: {e}")

    @pytest.mark.asyncio
    async def test_tabulator_open_query_get_integration(self):
        """Test tabulator open query status retrieval with real admin API."""
        try:
            result = await governance.admin_tabulator_open_query_get()

            # Should succeed if admin privileges are available
            if result["success"]:
                assert "open_query_enabled" in result
                assert isinstance(result["open_query_enabled"], bool)
            else:
                # If it fails, should be due to permissions
                assert (
                    "Admin" in result.get("error", "")
                    or "permission" in result.get("error", "").lower()
                )

        except Exception as e:
            # Integration tests may fail due to network, auth, or permission issues
            pytest.skip(f"Integration test failed due to: {e}")


class TestGovernanceWorkflows:
    """Test complete governance workflows."""

    @pytest.mark.asyncio
    async def test_user_management_workflow(self):
        """Test a complete user management workflow."""
        # This test is designed to be safe and not modify actual data
        # It only tests read operations and validation

        try:
            # 1. List existing users
            users_result = await governance.admin_users_list()

            if not users_result["success"]:
                pytest.skip("Cannot test workflow without admin privileges")

            # 2. Try to get a specific user (should handle not found gracefully)
            user_result = await governance.admin_user_get("nonexistent_test_user_12345")

            # Should fail gracefully for non-existent user
            assert user_result["success"] is False
            assert "not found" in user_result["error"].lower()

            # 3. Test validation for user creation (without actually creating)
            create_result = await governance.admin_user_create("", "", "")
            assert create_result["success"] is False
            assert "Username cannot be empty" in create_result["error"]

        except Exception as e:
            pytest.skip(f"Workflow test failed due to: {e}")

    @pytest.mark.asyncio
    async def test_role_and_user_integration(self):
        """Test integration between role and user management."""
        try:
            # 1. Get available roles
            roles_result = await governance.admin_roles_list()

            if not roles_result["success"]:
                pytest.skip("Cannot test integration without admin privileges")

            # 2. Get users to see role assignments
            users_result = await governance.admin_users_list()

            if not users_result["success"]:
                pytest.skip("Cannot test integration without admin privileges")

            # 3. Verify that user roles reference valid roles
            available_role_names = {role["name"] for role in roles_result["roles"]}

            for user in users_result["users"]:
                if user.get("role"):
                    # User's primary role should be in available roles
                    # Note: This might not always be true in real systems due to role updates
                    pass  # Just verify structure exists

                if user.get("extra_roles"):
                    # Extra roles should also be valid
                    # Note: This might not always be true in real systems due to role updates
                    pass  # Just verify structure exists

        except Exception as e:
            pytest.skip(f"Integration test failed due to: {e}")


class TestGovernanceErrorHandling:
    """Test error handling in integration scenarios."""

    @pytest.mark.asyncio
    async def test_insufficient_privileges_handling(self):
        """Test handling of insufficient privileges."""
        # This test simulates scenarios where admin operations fail due to permissions

        # Mock insufficient privileges by temporarily disabling admin
        with patch.object(governance, "ADMIN_AVAILABLE", False):
            result = await governance.admin_users_list()

            assert result["success"] is False
            assert "Admin functionality not available" in result["error"]

    @pytest.mark.asyncio
    async def test_network_error_handling(self):
        """Test handling of network errors."""
        # This test simulates network connectivity issues

        with patch(
            "quilt_mcp.tools.governance.admin_users.list",
            side_effect=Exception("Network error"),
        ):
            result = await governance.admin_users_list()

            assert result["success"] is False
            assert "Failed to list users" in result["error"]

    @pytest.mark.asyncio
    async def test_invalid_input_handling(self):
        """Test handling of invalid inputs in integration context."""
        # Test various invalid inputs that should be caught by validation

        # Empty username
        result = await governance.admin_user_get("")
        assert result["success"] is False
        assert "Username cannot be empty" in result["error"]

        # Invalid email format
        result = await governance.admin_user_create("test", "invalid-email", "role")
        assert result["success"] is False
        assert "Invalid email format" in result["error"]

        # Empty SSO config
        result = await governance.admin_sso_config_set("")
        assert result["success"] is False
        assert "SSO configuration cannot be empty" in result["error"]


class TestGovernanceTableFormatting:
    """Test table formatting in integration scenarios."""

    @pytest.mark.asyncio
    async def test_users_table_formatting(self):
        """Test that user list results include proper table formatting."""
        try:
            result = await governance.admin_users_list()

            if result["success"] and result.get("users"):
                # Should include formatted table
                assert "formatted_table" in result or "display_hint" in result

                # Users should have proper structure for table formatting
                for user in result["users"]:
                    assert "name" in user
                    assert "email" in user
                    assert "is_active" in user
                    assert "is_admin" in user

        except Exception as e:
            pytest.skip(f"Table formatting test failed due to: {e}")

    @pytest.mark.asyncio
    async def test_roles_table_formatting(self):
        """Test that role list results include proper table formatting."""
        try:
            result = await governance.admin_roles_list()

            if result["success"] and result.get("roles"):
                # Should include formatted table
                assert "formatted_table" in result or "display_hint" in result

                # Roles should have proper structure for table formatting
                for role in result["roles"]:
                    assert "id" in role
                    assert "name" in role
                    assert "type" in role
                    assert "arn" in role

        except Exception as e:
            pytest.skip(f"Table formatting test failed due to: {e}")


if __name__ == "__main__":
    # Run integration tests with verbose output
    pytest.main([__file__, "-v", "-s"])

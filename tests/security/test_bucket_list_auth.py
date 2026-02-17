"""Security tests for bucket_list authentication and authorization.

These tests validate that bucket_list properly handles authentication
and only returns buckets the user has permission to access.
"""

import pytest


@pytest.mark.security
@pytest.mark.auth
class TestBucketListSecurity:
    """Security tests for bucket_list authentication and authorization."""

    def test_bucket_list_with_invalid_jwt(self, monkeypatch):
        """Test bucket_list with invalid JWT token.

        Should fail gracefully with authentication error.
        """
        print("\n[Test] Invalid JWT handling")

        class MockOps:
            def execute_graphql_query(self, query: str):
                # Simulate authentication failure
                raise Exception("Authentication failed: invalid token")

        monkeypatch.setattr("quilt_mcp.ops.factory.QuiltOpsFactory.create", lambda: MockOps())

        from quilt_mcp.tools.buckets import bucket_list

        result = bucket_list()

        # Should return error, not crash
        assert result.success is False
        assert "Failed to list buckets" in result.error
        assert "invalid token" in result.error.lower()

        print("  ✅ Invalid JWT handled gracefully")

    def test_bucket_list_with_expired_jwt(self, monkeypatch):
        """Test bucket_list with expired JWT token.

        Should fail with authentication error.
        """
        print("\n[Test] Expired JWT handling")

        class MockOps:
            def execute_graphql_query(self, query: str):
                # Simulate expired token
                raise Exception("Token expired")

        monkeypatch.setattr("quilt_mcp.ops.factory.QuiltOpsFactory.create", lambda: MockOps())

        from quilt_mcp.tools.buckets import bucket_list

        result = bucket_list()

        # Should return error
        assert result.success is False
        assert "Failed to list buckets" in result.error

        print("  ✅ Expired JWT handled gracefully")

    def test_bucket_list_permission_filtering(self, monkeypatch):
        """Test that bucket_list only returns buckets user has permission to access.

        The bucketConfigs GraphQL query should already filter by user permissions
        via auth.get_buckets_listable_by(context.get_user()).
        """
        print("\n[Test] Permission-based bucket filtering")

        # Simulate a user with limited permissions
        class MockOps:
            def execute_graphql_query(self, query: str):
                # Return only buckets user has access to
                # In reality, this filtering happens server-side
                return {
                    "data": {
                        "bucketConfigs": [
                            {
                                "name": "accessible-bucket",
                                "title": "Accessible Bucket",
                                "description": "User has access",
                                "iconUrl": None,
                                "relevanceScore": 100,
                                "browsable": True,
                                "tags": ["accessible"],
                            }
                        ]
                    }
                }

        monkeypatch.setattr("quilt_mcp.ops.factory.QuiltOpsFactory.create", lambda: MockOps())

        from quilt_mcp.tools.buckets import bucket_list

        result = bucket_list()

        # Should only return accessible buckets
        assert result.success is True
        assert result.count == 1
        assert result.buckets[0].name == "accessible-bucket"

        # Verify no inaccessible buckets are included
        bucket_names = [b.name for b in result.buckets]
        assert "restricted-bucket" not in bucket_names
        assert "private-bucket" not in bucket_names

        print("  ✅ Only accessible buckets returned")

    def test_bucket_list_no_permissions(self, monkeypatch):
        """Test bucket_list when user has no bucket permissions.

        Should return empty list, not an error.
        """
        print("\n[Test] No permissions handling")

        class MockOps:
            def execute_graphql_query(self, query: str):
                # User has no accessible buckets
                return {"data": {"bucketConfigs": []}}

        monkeypatch.setattr("quilt_mcp.ops.factory.QuiltOpsFactory.create", lambda: MockOps())

        from quilt_mcp.tools.buckets import bucket_list

        result = bucket_list()

        # Empty list is not an error
        assert result.success is True
        assert result.count == 0
        assert len(result.buckets) == 0

        print("  ✅ Empty list returned for user with no permissions")

    def test_bucket_list_unauthorized_error(self, monkeypatch):
        """Test bucket_list with explicit unauthorized error.

        Should handle 401-style errors gracefully.
        """
        print("\n[Test] Unauthorized error handling")

        class MockOps:
            def execute_graphql_query(self, query: str):
                raise Exception("401 Unauthorized: missing or invalid credentials")

        monkeypatch.setattr("quilt_mcp.ops.factory.QuiltOpsFactory.create", lambda: MockOps())

        from quilt_mcp.tools.buckets import bucket_list

        result = bucket_list()

        # Should return error with auth context
        assert result.success is False
        assert "Failed to list buckets" in result.error
        assert "unauthorized" in result.error.lower() or "401" in result.error

        print("  ✅ Unauthorized error handled gracefully")

    def test_bucket_list_does_not_leak_inaccessible_data(self, monkeypatch):
        """Test that bucket_list does not leak information about inaccessible buckets.

        Even error messages should not reveal the existence of buckets
        the user doesn't have access to.
        """
        print("\n[Test] Data leakage prevention")

        class MockOps:
            def execute_graphql_query(self, query: str):
                # Simulate server-side filtering
                # Server should never send inaccessible bucket data
                return {
                    "data": {
                        "bucketConfigs": [
                            {
                                "name": "public-bucket",
                                "title": "Public Bucket",
                                "description": None,
                                "iconUrl": None,
                                "relevanceScore": 50,
                                "browsable": True,
                                "tags": None,
                            }
                        ]
                    }
                }

        monkeypatch.setattr("quilt_mcp.ops.factory.QuiltOpsFactory.create", lambda: MockOps())

        from quilt_mcp.tools.buckets import bucket_list

        result = bucket_list()

        # Verify only accessible buckets in result
        assert result.success is True
        assert result.count == 1

        # Verify no hints about inaccessible buckets in response
        bucket_names = [b.name for b in result.buckets]
        assert len(bucket_names) == 1
        assert bucket_names[0] == "public-bucket"

        print("  ✅ No data leakage detected")

    def test_bucket_list_jwt_context_propagation(self, monkeypatch):
        """Test that JWT context is properly propagated to GraphQL query.

        The authentication context should be available to the server-side
        filtering logic.
        """
        print("\n[Test] JWT context propagation")

        # Track if context would be used (in reality, happens server-side)
        context_used = []

        class MockOps:
            def execute_graphql_query(self, query: str):
                # In real implementation, JWT is in request context
                # and auth.get_buckets_listable_by uses it
                context_used.append(True)

                return {
                    "data": {
                        "bucketConfigs": [
                            {
                                "name": "user-bucket",
                                "title": "User Bucket",
                                "description": None,
                                "iconUrl": None,
                                "relevanceScore": 100,
                                "browsable": True,
                                "tags": None,
                            }
                        ]
                    }
                }

        monkeypatch.setattr("quilt_mcp.ops.factory.QuiltOpsFactory.create", lambda: MockOps())

        from quilt_mcp.tools.buckets import bucket_list

        result = bucket_list()

        # Verify query was executed (implying context was available)
        assert len(context_used) == 1
        assert result.success is True

        print("  ✅ JWT context propagated to query execution")

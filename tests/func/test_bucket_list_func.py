"""Functional tests for bucket_list with mocked QuiltOps integration.

These tests validate the integration between the bucket_list tool and QuiltOps,
with mocked GraphQL responses to test the complete flow without hitting real services.
"""

import pytest


@pytest.mark.func
class TestBucketListFunctional:
    """Functional tests for bucket_list tool with mocked QuiltOps."""

    def test_bucket_list_quilt_ops_integration(self, monkeypatch):
        """Test bucket_list integration with QuiltOpsFactory.

        Validates:
        - QuiltOpsFactory is called correctly
        - GraphQL query is constructed properly
        - Response is mapped to result objects correctly
        """
        print("\n[Test] bucket_list QuiltOps integration")

        # Track calls to QuiltOpsFactory
        factory_calls = []
        execute_calls = []

        class MockOps:
            def execute_graphql_query(self, query: str):
                execute_calls.append(query)

                # Verify query structure
                assert "bucketConfigs" in query, "Query should include bucketConfigs"
                assert "name" in query, "Query should request name field"
                assert "title" in query, "Query should request title field"
                assert "description" in query, "Query should request description field"
                assert "iconUrl" in query, "Query should request iconUrl field"
                assert "relevanceScore" in query, "Query should request relevanceScore field"
                assert "browsable" in query, "Query should request browsable field"
                assert "tags" in query, "Query should request tags field"

                # Return mock response
                return {
                    "data": {
                        "bucketConfigs": [
                            {
                                "name": "test-bucket",
                                "title": "Test Bucket",
                                "description": "A test bucket",
                                "iconUrl": "https://example.com/icon.png",
                                "relevanceScore": 100,
                                "browsable": True,
                                "tags": ["test", "demo"],
                            }
                        ]
                    }
                }

        def mock_factory_create():
            factory_calls.append("create")
            return MockOps()

        monkeypatch.setattr("quilt_mcp.ops.factory.QuiltOpsFactory.create", mock_factory_create)

        # Call bucket_list
        from quilt_mcp.tools.buckets import bucket_list

        result = bucket_list()

        # Verify factory was called
        assert len(factory_calls) == 1, "QuiltOpsFactory.create should be called once"
        assert len(execute_calls) == 1, "execute_graphql_query should be called once"

        # Verify result
        assert result.success is True
        assert result.count == 1
        assert len(result.buckets) == 1

        bucket = result.buckets[0]
        assert bucket.name == "test-bucket"
        assert bucket.title == "Test Bucket"
        assert bucket.description == "A test bucket"
        assert bucket.iconUrl == "https://example.com/icon.png"
        assert bucket.relevanceScore == 100
        assert bucket.browsable is True
        assert bucket.tags == ["test", "demo"]

        print("  ✅ QuiltOps integration validated")

    def test_bucket_list_graphql_query_construction(self, monkeypatch):
        """Test that GraphQL query is correctly constructed."""
        print("\n[Test] GraphQL query construction")

        captured_query = None

        class MockOps:
            def execute_graphql_query(self, query: str):
                nonlocal captured_query
                captured_query = query
                return {"data": {"bucketConfigs": []}}

        monkeypatch.setattr("quilt_mcp.ops.factory.QuiltOpsFactory.create", lambda: MockOps())

        from quilt_mcp.tools.buckets import bucket_list

        result = bucket_list()

        # Verify query was captured
        assert captured_query is not None, "GraphQL query should be captured"
        assert result.success is True

        # Verify query structure - should match the bucketConfigs query
        # from ~/GitHub/enterprise/registry/quilt_server/graphql/buckets.py
        assert "query" in captured_query or "bucketConfigs" in captured_query
        assert "{" in captured_query  # Should have GraphQL structure

        print("  ✅ GraphQL query construction validated")
        print(f"  Query: {captured_query[:100]}...")

    def test_bucket_list_error_propagation(self, monkeypatch):
        """Test that GraphQL errors are properly propagated."""
        print("\n[Test] Error propagation")

        class MockOps:
            def execute_graphql_query(self, query: str):
                raise Exception("GraphQL connection failed")

        monkeypatch.setattr("quilt_mcp.ops.factory.QuiltOpsFactory.create", lambda: MockOps())

        from quilt_mcp.tools.buckets import bucket_list

        result = bucket_list()

        # Should handle error gracefully
        assert result.success is False
        assert "Failed to list buckets" in result.error
        assert "GraphQL connection failed" in result.error

        print("  ✅ Error propagation validated")

    def test_bucket_list_response_mapping(self, monkeypatch):
        """Test mapping of GraphQL response to result objects."""
        print("\n[Test] Response mapping")

        class MockOps:
            def execute_graphql_query(self, query: str):
                return {
                    "data": {
                        "bucketConfigs": [
                            {
                                "name": "bucket1",
                                "title": "Bucket 1",
                                "description": None,  # Test None handling
                                "iconUrl": None,
                                "relevanceScore": 50,
                                "browsable": False,
                                "tags": None,
                            },
                            {
                                "name": "bucket2",
                                "title": "Bucket 2",
                                "description": "Second bucket",
                                "iconUrl": "https://example.com/icon2.png",
                                "relevanceScore": 75,
                                "browsable": True,
                                "tags": ["prod"],
                            },
                        ]
                    }
                }

        monkeypatch.setattr("quilt_mcp.ops.factory.QuiltOpsFactory.create", lambda: MockOps())

        from quilt_mcp.tools.buckets import bucket_list

        result = bucket_list()

        # Verify mapping
        assert result.success is True
        assert result.count == 2

        # First bucket with None fields
        bucket1 = result.buckets[0]
        assert bucket1.name == "bucket1"
        assert bucket1.description is None
        assert bucket1.iconUrl is None
        assert bucket1.tags is None

        # Second bucket with all fields
        bucket2 = result.buckets[1]
        assert bucket2.name == "bucket2"
        assert bucket2.description == "Second bucket"
        assert bucket2.iconUrl == "https://example.com/icon2.png"
        assert bucket2.tags == ["prod"]

        print("  ✅ Response mapping validated")

    def test_bucket_list_missing_data_field(self, monkeypatch):
        """Test handling of response with missing data field."""
        print("\n[Test] Missing data field handling")

        class MockOps:
            def execute_graphql_query(self, query: str):
                # Return response without data field
                return {"errors": [{"message": "Some error"}]}

        monkeypatch.setattr("quilt_mcp.ops.factory.QuiltOpsFactory.create", lambda: MockOps())

        from quilt_mcp.tools.buckets import bucket_list

        result = bucket_list()

        # Should handle gracefully with empty list
        assert result.success is True
        assert result.count == 0
        assert len(result.buckets) == 0

        print("  ✅ Missing data field handled gracefully")

    def test_bucket_list_null_bucket_configs(self, monkeypatch):
        """Test handling of null bucketConfigs in response."""
        print("\n[Test] Null bucketConfigs handling")

        class MockOps:
            def execute_graphql_query(self, query: str):
                return {"data": {"bucketConfigs": None}}

        monkeypatch.setattr("quilt_mcp.ops.factory.QuiltOpsFactory.create", lambda: MockOps())

        from quilt_mcp.tools.buckets import bucket_list

        result = bucket_list()

        # Should handle gracefully with empty list
        assert result.success is True
        assert result.count == 0
        assert len(result.buckets) == 0

        print("  ✅ Null bucketConfigs handled gracefully")

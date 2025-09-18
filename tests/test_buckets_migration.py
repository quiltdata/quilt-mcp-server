"""Migration validation tests for buckets.py to QuiltService.

This file validates that buckets.py behavior remains identical
after migrating from direct quilt3 imports to QuiltService.
"""

from __future__ import annotations

import pytest
from unittest.mock import Mock, patch

from quilt_mcp.tools.buckets import (
    bucket_objects_search,
    bucket_objects_search_graphql,
)


class TestBucketsMigrationValidation:
    """Validate that buckets.py functions work identically with QuiltService."""

    def test_bucket_objects_search_uses_quilt_service(self):
        """Test bucket_objects_search calls QuiltService.create_bucket."""
        mock_service = Mock()
        mock_bucket = Mock()
        mock_bucket.search.return_value = [{"key": "test.txt"}]
        mock_service.create_bucket.return_value = mock_bucket

        with patch('quilt_mcp.tools.buckets.QuiltService', return_value=mock_service), \
             patch('quilt_mcp.utils.suppress_stdout'):
            result = bucket_objects_search('test-bucket', 'query')

        mock_service.create_bucket.assert_called_once_with('s3://test-bucket')
        mock_bucket.search.assert_called_once_with('query', limit=10)
        assert result['bucket'] == 'test-bucket'
        assert result['query'] == 'query'
        assert result['results'] == [{"key": "test.txt"}]

    def test_bucket_objects_search_graphql_uses_quilt_service_for_session(self):
        """Test bucket_objects_search_graphql calls QuiltService session methods."""
        mock_service = Mock()
        mock_session_obj = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "objects": {
                    "edges": [
                        {
                            "node": {
                                "key": "test.txt",
                                "size": 1024,
                                "updated": "2023-01-01",
                                "contentType": "text/plain",
                                "extension": "txt",
                                "package": {"name": "user/pkg", "topHash": "abc123"}
                            }
                        }
                    ],
                    "pageInfo": {"endCursor": "cursor123", "hasNextPage": False}
                }
            }
        }
        mock_session_obj.post.return_value = mock_response
        mock_service.has_session_support.return_value = True
        mock_service.get_session.return_value = mock_session_obj
        mock_service.get_registry_url.return_value = 'https://registry.example.com'

        with patch('quilt_mcp.tools.buckets.QuiltService', return_value=mock_service):
            result = bucket_objects_search_graphql('test-bucket')

        mock_service.has_session_support.assert_called_once()
        mock_service.get_session.assert_called_once()
        mock_service.get_registry_url.assert_called_once()
        assert result['success'] is True
        assert result['bucket'] == 'test-bucket'
        assert len(result['objects']) == 1
        assert result['objects'][0]['key'] == 'test.txt'

    def test_bucket_objects_search_graphql_handles_no_session_support(self):
        """Test bucket_objects_search_graphql handles missing session support."""
        mock_service = Mock()
        mock_service.has_session_support.return_value = False

        with patch('quilt_mcp.tools.buckets.QuiltService', return_value=mock_service):
            result = bucket_objects_search_graphql('test-bucket')

        mock_service.has_session_support.assert_called_once()
        assert result['success'] is False
        assert 'quilt3 session not available' in result['error']
        assert result['bucket'] == 'test-bucket'
        assert result['objects'] == []

    def test_bucket_objects_search_graphql_handles_no_registry_url(self):
        """Test bucket_objects_search_graphql handles missing registry URL."""
        mock_service = Mock()
        mock_service.has_session_support.return_value = True
        mock_service.get_session.return_value = Mock()
        mock_service.get_registry_url.return_value = None

        with patch('quilt_mcp.tools.buckets.QuiltService', return_value=mock_service):
            result = bucket_objects_search_graphql('test-bucket')

        mock_service.has_session_support.assert_called_once()
        mock_service.get_session.assert_called_once()
        mock_service.get_registry_url.assert_called_once()
        assert result['success'] is False
        assert 'Registry URL not configured' in result['error']
        assert result['bucket'] == 'test-bucket'
        assert result['objects'] == []
"""BDD tests for AWS S3 operations utilities.

These tests follow the Given/When/Then pattern and test behavior, not implementation.
All tests are written to fail initially (RED phase of TDD).
"""

from __future__ import annotations

import io
from unittest.mock import Mock, patch, MagicMock
import pytest

from quilt_mcp.utilities.aws.s3 import (
    create_client,
    list_objects,
    get_object,
    put_object,
    delete_object,
    object_exists,
)


class TestS3ClientCreation:
    """Test S3 client creation from sessions."""

    def test_given_valid_session_when_creating_s3_client_then_client_returned(self):
        """Given valid session, When creating S3 client, Then client returned."""
        # Given: A valid session
        mock_session = Mock()
        mock_client = Mock()
        mock_session.client.return_value = mock_client

        # When: Creating S3 client
        client = create_client(mock_session)

        # Then: S3 client is returned
        assert client == mock_client
        mock_session.client.assert_called_once_with('s3')

    def test_given_session_and_region_when_creating_s3_client_then_client_created_with_region(self):
        """Given session and region, When creating S3 client, Then client created with region."""
        # Given: A session and specific region
        mock_session = Mock()
        mock_client = Mock()
        mock_session.client.return_value = mock_client
        region = 'us-west-2'

        # When: Creating S3 client with region
        client = create_client(mock_session, region=region)

        # Then: Client is created with specified region
        assert client == mock_client
        mock_session.client.assert_called_once_with('s3', region_name=region)


class TestS3ListObjects:
    """Test S3 object listing functionality."""

    def test_given_valid_s3_client_when_listing_objects_with_prefix_then_correct_objects_returned(self):
        """Given valid S3 client, When listing objects with prefix, Then correct objects returned."""
        # Given: A valid S3 client and bucket with objects
        mock_client = Mock()
        mock_client.list_objects_v2.return_value = {
            'Contents': [
                {
                    'Key': 'test/file1.txt',
                    'Size': 1024,
                    'LastModified': '2025-01-08',
                    'ETag': '"abc123"',
                    'StorageClass': 'STANDARD',
                }
            ],
            'IsTruncated': False,
            'KeyCount': 1,
        }

        # When: Listing objects with prefix
        result = list_objects(mock_client, 'test-bucket', prefix='test/')

        # Then: Correct objects are returned
        assert result['objects']
        assert len(result['objects']) == 1
        assert result['objects'][0]['key'] == 'test/file1.txt'
        assert result['bucket'] == 'test-bucket'
        assert result['prefix'] == 'test/'
        mock_client.list_objects_v2.assert_called_once()

    def test_given_s3_client_and_pagination_params_when_listing_objects_then_pagination_handled_correctly(self):
        """Given S3 client and pagination params, When listing objects, Then pagination handled correctly."""
        # Given: S3 client and pagination parameters
        mock_client = Mock()
        mock_client.list_objects_v2.return_value = {
            'Contents': [],
            'IsTruncated': True,
            'NextContinuationToken': 'next-token-123',
            'KeyCount': 0,
        }

        # When: Listing objects with pagination
        result = list_objects(mock_client, 'test-bucket', max_keys=50, continuation_token='prev-token')

        # Then: Pagination is handled correctly
        assert result['truncated'] is True
        assert result['next_token'] == 'next-token-123'
        mock_client.list_objects_v2.assert_called_once_with(
            Bucket='test-bucket', MaxKeys=50, ContinuationToken='prev-token'
        )


class TestS3GetObject:
    """Test S3 object retrieval functionality."""

    def test_given_existing_s3_object_when_getting_object_then_object_data_retrieved_correctly(self):
        """Given existing S3 object, When getting object, Then object data retrieved correctly."""
        # Given: An existing S3 object
        mock_client = Mock()
        mock_body = Mock()
        mock_body.read.return_value = b'test content'
        mock_client.get_object.return_value = {
            'Body': mock_body,
            'ContentLength': 12,
            'ContentType': 'text/plain',
            'ETag': '"abc123"',
            'LastModified': '2025-01-08',
        }

        # When: Getting the object
        result = get_object(mock_client, 'test-bucket', 'test-key')

        # Then: Object data is retrieved correctly
        assert result['data'] == b'test content'
        assert result['content_length'] == 12
        assert result['content_type'] == 'text/plain'
        mock_client.get_object.assert_called_once_with(Bucket='test-bucket', Key='test-key')

    def test_given_large_object_over_1gb_when_streaming_object_then_memory_usage_remains_constant(self):
        """Given large object (>1GB), When streaming object, Then memory usage remains constant."""
        # Given: A large object and streaming parameters
        mock_client = Mock()
        mock_body = Mock()
        # Simulate streaming by yielding chunks
        mock_body.iter_chunks.return_value = [b'chunk1', b'chunk2', b'chunk3']
        mock_client.get_object.return_value = {
            'Body': mock_body,
            'ContentLength': 1024 * 1024 * 1024 * 2,  # 2GB
        }

        # When: Streaming the object (this would be implemented)
        result = list(get_object(mock_client, 'test-bucket', 'large-key', stream=True))

        # Then: Object is streamed in chunks (memory usage constant)
        assert len(result) == 3
        mock_client.get_object.assert_called_once()


class TestS3PutObject:
    """Test S3 object upload functionality."""

    def test_given_object_data_when_putting_object_then_object_stored_successfully_in_s3(self):
        """Given object data, When putting object, Then object stored successfully in S3."""
        # Given: Object data to upload
        mock_client = Mock()
        mock_client.put_object.return_value = {'ETag': '"def456"', 'VersionId': 'version123'}
        data = b'test upload content'

        # When: Putting the object
        result = put_object(mock_client, 'test-bucket', 'upload-key', data)

        # Then: Object is stored successfully
        assert result['etag'] == '"def456"'
        assert result['success'] is True
        mock_client.put_object.assert_called_once_with(Bucket='test-bucket', Key='upload-key', Body=data)

    def test_given_object_data_and_metadata_when_putting_object_then_metadata_included(self):
        """Given object data and metadata, When putting object, Then metadata included."""
        # Given: Object data and metadata
        mock_client = Mock()
        mock_client.put_object.return_value = {'ETag': '"def456"'}
        data = b'content with metadata'
        metadata = {'author': 'test-user', 'version': '1.0'}

        # When: Putting object with metadata
        result = put_object(mock_client, 'test-bucket', 'meta-key', data, content_type='text/plain', metadata=metadata)

        # Then: Object is stored with metadata
        assert result['success'] is True
        mock_client.put_object.assert_called_once_with(
            Bucket='test-bucket', Key='meta-key', Body=data, ContentType='text/plain', Metadata=metadata
        )


class TestS3DeleteObject:
    """Test S3 object deletion functionality."""

    def test_given_existing_s3_object_when_deleting_object_then_object_removed_from_s3(self):
        """Given existing S3 object, When deleting object, Then object removed from S3."""
        # Given: An existing S3 object
        mock_client = Mock()
        mock_client.delete_object.return_value = {'DeleteMarker': False, 'VersionId': 'version123'}

        # When: Deleting the object
        result = delete_object(mock_client, 'test-bucket', 'delete-key')

        # Then: Object is removed from S3
        assert result['deleted'] is True
        mock_client.delete_object.assert_called_once_with(Bucket='test-bucket', Key='delete-key')


class TestS3ObjectExists:
    """Test S3 object existence checking."""

    def test_given_existing_s3_object_when_checking_existence_then_returns_true(self):
        """Given existing S3 object, When checking existence, Then returns True."""
        # Given: An existing S3 object
        mock_client = Mock()
        mock_client.head_object.return_value = {'ContentLength': 1024, 'ETag': '"abc123"'}

        # When: Checking if object exists
        exists = object_exists(mock_client, 'test-bucket', 'existing-key')

        # Then: Returns True
        assert exists is True
        mock_client.head_object.assert_called_once_with(Bucket='test-bucket', Key='existing-key')

    def test_given_non_existing_s3_object_when_checking_existence_then_returns_false(self):
        """Given non-existing S3 object, When checking existence, Then returns False."""
        # Given: A non-existing S3 object (head_object raises 404)
        mock_client = Mock()
        mock_client.head_object.side_effect = Exception("404 Not Found")

        # When: Checking if object exists
        exists = object_exists(mock_client, 'test-bucket', 'missing-key')

        # Then: Returns False
        assert exists is False
        mock_client.head_object.assert_called_once_with(Bucket='test-bucket', Key='missing-key')


class TestS3RetryLogic:
    """Test S3 retry logic and error handling."""

    def test_given_network_failure_when_performing_s3_operation_then_retry_with_exponential_backoff(self):
        """Given network failure, When performing S3 operation, Then retry with exponential backoff."""
        # Given: Network failure scenario
        mock_client = Mock()
        # First call fails, second succeeds
        mock_client.get_object.side_effect = [Exception("Network timeout"), {'Body': Mock(), 'ContentLength': 100}]

        # When: Performing S3 operation with retry logic
        with patch('time.sleep') as mock_sleep:  # Mock sleep to speed up test
            result = get_object(mock_client, 'test-bucket', 'retry-key', max_retries=2)

        # Then: Operation succeeds after retry
        assert result is not None
        assert mock_client.get_object.call_count == 2
        mock_sleep.assert_called()  # Verify backoff delay occurred

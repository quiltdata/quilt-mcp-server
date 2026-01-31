"""
Tests for Quilt3_Backend bucket operations.

This module tests bucket-related operations including bucket retrieval,
transformations, and error handling for the Quilt3_Backend implementation.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime
from typing import List, Optional

from quilt_mcp.ops.exceptions import AuthenticationError, BackendError, ValidationError
from quilt_mcp.domain.package_info import Package_Info
from quilt_mcp.domain.content_info import Content_Info
from quilt_mcp.domain.bucket_info import Bucket_Info


class TestQuilt3BackendBucketOperations:
    """Test bucket listing operations."""

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_list_buckets_with_mocked_quilt3_calls(self, mock_quilt3):
        """Test list_buckets() with mocked quilt3 calls."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock bucket listing response
        mock_bucket_data = {
            'test-bucket-1': {
                'region': 'us-east-1',
                'access_level': 'read-write',
                'created_date': '2024-01-01T00:00:00Z'
            },
            'test-bucket-2': {
                'region': 'us-west-2',
                'access_level': 'read-only',
                'created_date': '2024-01-02T00:00:00Z'
            }
        }

        mock_quilt3.list_buckets.return_value = mock_bucket_data

        # Execute
        result = backend.list_buckets()

        # Verify
        assert len(result) == 2
        assert all(isinstance(bucket, Bucket_Info) for bucket in result)

        bucket1 = next(b for b in result if b.name == 'test-bucket-1')
        assert bucket1.region == 'us-east-1'
        assert bucket1.access_level == 'read-write'

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_list_buckets_bucket_metadata_extraction_comprehensive(self, mock_quilt3):
        """Test comprehensive bucket metadata extraction from various quilt3 response formats."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock comprehensive bucket data with various metadata scenarios
        mock_bucket_data = {
            'complete-metadata-bucket': {
                'region': 'us-east-1',
                'access_level': 'read-write',
                'created_date': '2024-01-15T10:30:00Z'
            },
            'minimal-metadata-bucket': {
                'region': 'eu-west-1',
                'access_level': 'admin'
                # No created_date
            },
            'null-created-date-bucket': {
                'region': 'ap-southeast-1',
                'access_level': 'public-read',
                'created_date': None
            },
            'extra-fields-bucket': {
                'region': 'ap-southeast-1',
                'access_level': 'public-read',
                'created_date': '2023-12-01T00:00:00Z',
                'extra_field': 'should_be_ignored',
                'another_extra': 12345,
                'nested_extra': {'key': 'value'}
            }
        }

        mock_quilt3.list_buckets.return_value = mock_bucket_data

        # Execute
        result = backend.list_buckets()

        # Verify extraction results
        assert len(result) == 4
        assert all(isinstance(bucket, Bucket_Info) for bucket in result)

        # Verify complete metadata extraction
        complete_bucket = next(b for b in result if b.name == 'complete-metadata-bucket')
        assert complete_bucket.region == 'us-east-1'
        assert complete_bucket.access_level == 'read-write'
        assert complete_bucket.created_date == '2024-01-15T10:30:00Z'

        # Verify minimal metadata extraction
        minimal_bucket = next(b for b in result if b.name == 'minimal-metadata-bucket')
        assert minimal_bucket.region == 'eu-west-1'
        assert minimal_bucket.access_level == 'admin'
        assert minimal_bucket.created_date is None

        # Verify null created_date is handled
        null_date_bucket = next(b for b in result if b.name == 'null-created-date-bucket')
        assert null_date_bucket.region == 'ap-southeast-1'
        assert null_date_bucket.access_level == 'public-read'
        assert null_date_bucket.created_date is None

        # Verify extra fields are ignored during extraction
        extra_bucket = next(b for b in result if b.name == 'extra-fields-bucket')
        assert extra_bucket.region == 'ap-southeast-1'
        assert extra_bucket.access_level == 'public-read'
        assert extra_bucket.created_date == '2023-12-01T00:00:00Z'
        # Extra fields should not appear in Bucket_Info object
        assert not hasattr(extra_bucket, 'extra_field')
        assert not hasattr(extra_bucket, 'another_extra')
        assert not hasattr(extra_bucket, 'nested_extra')

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_bucket_metadata_extraction_with_missing_required_fields_error_handling(self, mock_quilt3):
        """Test bucket metadata extraction error handling when required fields are missing or empty."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test scenarios that should cause validation errors
        error_scenarios = [
            # Empty strings for required fields
            {
                'empty-region-bucket': {
                    'region': '',
                    'access_level': 'read-write',
                    'created_date': '2024-01-01T00:00:00Z'
                }
            },
            {
                'empty-access-level-bucket': {
                    'region': 'us-east-1',
                    'access_level': '',
                    'created_date': '2024-01-01T00:00:00Z'
                }
            },
            # None values for required fields
            {
                'none-region-bucket': {
                    'region': None,
                    'access_level': 'read-write',
                    'created_date': '2024-01-01T00:00:00Z'
                }
            },
            {
                'none-access-level-bucket': {
                    'region': 'us-east-1',
                    'access_level': None,
                    'created_date': '2024-01-01T00:00:00Z'
                }
            },
            # Missing required fields
            {
                'missing-region-bucket': {
                    'access_level': 'read-write',
                    'created_date': '2024-01-01T00:00:00Z'
                }
            },
            {
                'missing-access-level-bucket': {
                    'region': 'us-east-1',
                    'created_date': '2024-01-01T00:00:00Z'
                }
            }
        ]

        for scenario in error_scenarios:
            mock_quilt3.list_buckets.return_value = scenario

            with pytest.raises(BackendError) as exc_info:
                backend.list_buckets()

            error_message = str(exc_info.value)
            assert "quilt3" in error_message.lower()
            assert "list_buckets failed" in error_message.lower()

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_bucket_metadata_extraction_with_various_date_formats(self, mock_quilt3):
        """Test bucket metadata extraction handles various date formats correctly."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock bucket data with various date formats
        mock_bucket_data = {
            'iso-date-bucket': {
                'region': 'us-east-1',
                'access_level': 'read-write',
                'created_date': '2024-01-15T10:30:00Z'
            },
            'iso-date-no-z-bucket': {
                'region': 'us-west-2',
                'access_level': 'admin',
                'created_date': '2024-01-15T10:30:00'
            },
            'simple-date-bucket': {
                'region': 'eu-central-1',
                'access_level': 'public-read',
                'created_date': '2024-01-15'
            },
            'datetime-object-bucket': {
                'region': 'ap-northeast-1',
                'access_level': 'private',
                'created_date': datetime(2024, 1, 15, 10, 30, 0)
            },
            'empty-date-bucket': {
                'region': 'ca-central-1',
                'access_level': 'read-only',
                'created_date': ''
            },
            'none-date-bucket': {
                'region': 'sa-east-1',
                'access_level': 'read-write',
                'created_date': None
            }
        }

        mock_quilt3.list_buckets.return_value = mock_bucket_data

        # Execute
        result = backend.list_buckets()

        # Verify date extraction and normalization
        assert len(result) == 6

        iso_bucket = next(b for b in result if b.name == 'iso-date-bucket')
        assert iso_bucket.created_date == '2024-01-15T10:30:00Z'

        iso_no_z_bucket = next(b for b in result if b.name == 'iso-date-no-z-bucket')
        assert iso_no_z_bucket.created_date == '2024-01-15T10:30:00'

        simple_bucket = next(b for b in result if b.name == 'simple-date-bucket')
        assert simple_bucket.created_date == '2024-01-15'

        datetime_bucket = next(b for b in result if b.name == 'datetime-object-bucket')
        assert datetime_bucket.created_date == '2024-01-15T10:30:00'

        empty_bucket = next(b for b in result if b.name == 'empty-date-bucket')
        assert empty_bucket.created_date == ''

        none_bucket = next(b for b in result if b.name == 'none-date-bucket')
        assert none_bucket.created_date is None

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_bucket_metadata_extraction_with_various_access_levels(self, mock_quilt3):
        """Test bucket metadata extraction handles various access level configurations."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock bucket data with various access levels
        mock_bucket_data = {
            'public-read-bucket': {
                'region': 'us-east-1',
                'access_level': 'public-read',
                'created_date': '2024-01-01T00:00:00Z'
            },
            'public-read-write-bucket': {
                'region': 'us-west-2',
                'access_level': 'public-read-write',
                'created_date': '2024-01-02T00:00:00Z'
            },
            'private-bucket': {
                'region': 'eu-west-1',
                'access_level': 'private',
                'created_date': '2024-01-03T00:00:00Z'
            },
            'authenticated-read-bucket': {
                'region': 'ap-southeast-1',
                'access_level': 'authenticated-read',
                'created_date': '2024-01-04T00:00:00Z'
            },
            'bucket-owner-read-bucket': {
                'region': 'ca-central-1',
                'access_level': 'bucket-owner-read',
                'created_date': '2024-01-05T00:00:00Z'
            },
            'bucket-owner-full-control-bucket': {
                'region': 'sa-east-1',
                'access_level': 'bucket-owner-full-control',
                'created_date': '2024-01-06T00:00:00Z'
            },
            'admin-bucket': {
                'region': 'eu-central-1',
                'access_level': 'admin',
                'created_date': '2024-01-07T00:00:00Z'
            },
            'read-only-bucket': {
                'region': 'ap-northeast-1',
                'access_level': 'read-only',
                'created_date': '2024-01-08T00:00:00Z'
            },
            'read-write-bucket': {
                'region': 'us-east-2',
                'access_level': 'read-write',
                'created_date': '2024-01-09T00:00:00Z'
            }
        }

        mock_quilt3.list_buckets.return_value = mock_bucket_data

        # Execute
        result = backend.list_buckets()

        # Verify access level extraction
        assert len(result) == 9

        # Verify each access level is correctly extracted
        expected_access_levels = {
            'public-read-bucket': 'public-read',
            'public-read-write-bucket': 'public-read-write',
            'private-bucket': 'private',
            'authenticated-read-bucket': 'authenticated-read',
            'bucket-owner-read-bucket': 'bucket-owner-read',
            'bucket-owner-full-control-bucket': 'bucket-owner-full-control',
            'admin-bucket': 'admin',
            'read-only-bucket': 'read-only',
            'read-write-bucket': 'read-write'
        }

        for bucket in result:
            expected_access_level = expected_access_levels[bucket.name]
            assert bucket.access_level == expected_access_level, f"Bucket {bucket.name} should have access_level {expected_access_level}, got {bucket.access_level}"

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_bucket_metadata_extraction_with_various_regions(self, mock_quilt3):
        """Test bucket metadata extraction handles various AWS region configurations."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock bucket data with various AWS regions
        mock_bucket_data = {
            'us-east-1-bucket': {
                'region': 'us-east-1',
                'access_level': 'read-write',
                'created_date': '2024-01-01T00:00:00Z'
            },
            'us-west-2-bucket': {
                'region': 'us-west-2',
                'access_level': 'read-write',
                'created_date': '2024-01-02T00:00:00Z'
            },
            'eu-west-1-bucket': {
                'region': 'eu-west-1',
                'access_level': 'read-write',
                'created_date': '2024-01-03T00:00:00Z'
            },
            'ap-southeast-1-bucket': {
                'region': 'ap-southeast-1',
                'access_level': 'read-write',
                'created_date': '2024-01-04T00:00:00Z'
            },
            'ca-central-1-bucket': {
                'region': 'ca-central-1',
                'access_level': 'read-write',
                'created_date': '2024-01-05T00:00:00Z'
            },
            'sa-east-1-bucket': {
                'region': 'sa-east-1',
                'access_level': 'read-write',
                'created_date': '2024-01-06T00:00:00Z'
            },
            'ap-northeast-1-bucket': {
                'region': 'ap-northeast-1',
                'access_level': 'read-write',
                'created_date': '2024-01-07T00:00:00Z'
            },
            'eu-central-1-bucket': {
                'region': 'eu-central-1',
                'access_level': 'read-write',
                'created_date': '2024-01-08T00:00:00Z'
            }
        }

        mock_quilt3.list_buckets.return_value = mock_bucket_data

        # Execute
        result = backend.list_buckets()

        # Verify region extraction
        assert len(result) == 8

        # Verify each region is correctly extracted
        expected_regions = {
            'us-east-1-bucket': 'us-east-1',
            'us-west-2-bucket': 'us-west-2',
            'eu-west-1-bucket': 'eu-west-1',
            'ap-southeast-1-bucket': 'ap-southeast-1',
            'ca-central-1-bucket': 'ca-central-1',
            'sa-east-1-bucket': 'sa-east-1',
            'ap-northeast-1-bucket': 'ap-northeast-1',
            'eu-central-1-bucket': 'eu-central-1'
        }

        for bucket in result:
            expected_region = expected_regions[bucket.name]
            assert bucket.region == expected_region, f"Bucket {bucket.name} should have region {expected_region}, got {bucket.region}"

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_bucket_metadata_extraction_error_handling_malformed_data(self, mock_quilt3):
        """Test bucket metadata extraction error handling for malformed metadata."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test various malformed data scenarios
        malformed_scenarios = [
            # Scenario 1: Non-dict bucket data
            {
                'string-bucket': 'not-a-dict',
                'valid-bucket': {'region': 'us-east-1', 'access_level': 'read-write'}
            },
            # Scenario 2: List instead of dict
            {
                'list-bucket': ['region', 'access_level'],
                'valid-bucket': {'region': 'us-east-1', 'access_level': 'read-write'}
            },
            # Scenario 3: Number instead of dict
            {
                'number-bucket': 12345,
                'valid-bucket': {'region': 'us-east-1', 'access_level': 'read-write'}
            },
            # Scenario 4: None bucket data
            {
                'none-bucket': None,
                'valid-bucket': {'region': 'us-east-1', 'access_level': 'read-write'}
            }
        ]

        for scenario in malformed_scenarios:
            mock_quilt3.list_buckets.return_value = scenario

            with pytest.raises(BackendError) as exc_info:
                backend.list_buckets()

            error_message = str(exc_info.value)
            assert "quilt3" in error_message.lower()
            assert "list_buckets failed" in error_message.lower()

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_bucket_metadata_extraction_edge_cases(self, mock_quilt3):
        """Test bucket metadata extraction handles edge cases and boundary conditions."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock edge case bucket data
        mock_bucket_data = {
            'very-long-name-bucket-with-many-dashes-and-numbers-123456789': {
                'region': 'us-east-1',
                'access_level': 'read-write',
                'created_date': '2024-01-01T00:00:00Z'
            },
            'a': {  # Single character bucket name
                'region': 'us-west-2',
                'access_level': 'admin',
                'created_date': '2024-01-02T00:00:00Z'
            },
            'bucket.with.dots': {
                'region': 'eu-west-1',
                'access_level': 'public-read',
                'created_date': '2024-01-03T00:00:00Z'
            },
            'bucket_with_underscores': {
                'region': 'ap-southeast-1',
                'access_level': 'private',
                'created_date': '2024-01-04T00:00:00Z'
            },
            'UPPERCASE-BUCKET': {
                'region': 'ca-central-1',
                'access_level': 'read-only',
                'created_date': '2024-01-05T00:00:00Z'
            },
            'bucket123numbers456': {
                'region': 'sa-east-1',
                'access_level': 'read-write',
                'created_date': '2024-01-06T00:00:00Z'
            },
            'unicode-bucket-测试': {
                'region': 'ap-northeast-1',
                'access_level': 'admin',
                'created_date': '2024-01-07T00:00:00Z'
            }
        }

        mock_quilt3.list_buckets.return_value = mock_bucket_data

        # Execute
        result = backend.list_buckets()

        # Verify edge cases are handled correctly
        assert len(result) == 7

        # Verify each edge case bucket is correctly extracted
        bucket_names = {bucket.name for bucket in result}
        expected_names = {
            'very-long-name-bucket-with-many-dashes-and-numbers-123456789',
            'a',
            'bucket.with.dots',
            'bucket_with_underscores',
            'UPPERCASE-BUCKET',
            'bucket123numbers456',
            'unicode-bucket-测试'
        }
        assert bucket_names == expected_names

        # Verify metadata is correctly extracted for edge case names
        long_name_bucket = next(b for b in result if b.name == 'very-long-name-bucket-with-many-dashes-and-numbers-123456789')
        assert long_name_bucket.region == 'us-east-1'
        assert long_name_bucket.access_level == 'read-write'

        single_char_bucket = next(b for b in result if b.name == 'a')
        assert single_char_bucket.region == 'us-west-2'
        assert single_char_bucket.access_level == 'admin'

        unicode_bucket = next(b for b in result if b.name == 'unicode-bucket-测试')
        assert unicode_bucket.region == 'ap-northeast-1'
        assert unicode_bucket.access_level == 'admin'

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_bucket_metadata_extraction_with_missing_optional_fields(self, mock_quilt3):
        """Test bucket metadata extraction gracefully handles missing optional fields."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock bucket data with various missing optional fields (only created_date is optional)
        mock_bucket_data = {
            'no-created-date-bucket': {
                'region': 'us-east-1',
                'access_level': 'read-write'
                # No created_date - this is the only optional field
            },
            'null-created-date-bucket': {
                'region': 'eu-west-1',
                'access_level': 'admin',
                'created_date': None
            },
            'empty-created-date-bucket': {
                'region': 'ap-southeast-1',
                'access_level': 'private',
                'created_date': ''
            }
        }

        mock_quilt3.list_buckets.return_value = mock_bucket_data

        # Execute
        result = backend.list_buckets()

        # Verify missing optional fields are handled gracefully
        assert len(result) == 3

        # Verify bucket with no created_date
        no_date_bucket = next(b for b in result if b.name == 'no-created-date-bucket')
        assert no_date_bucket.region == 'us-east-1'
        assert no_date_bucket.access_level == 'read-write'
        assert no_date_bucket.created_date is None

        # Verify bucket with null created_date
        null_date_bucket = next(b for b in result if b.name == 'null-created-date-bucket')
        assert null_date_bucket.region == 'eu-west-1'
        assert null_date_bucket.access_level == 'admin'
        assert null_date_bucket.created_date is None

        # Verify bucket with empty created_date
        empty_date_bucket = next(b for b in result if b.name == 'empty-created-date-bucket')
        assert empty_date_bucket.region == 'ap-southeast-1'
        assert empty_date_bucket.access_level == 'private'
        assert empty_date_bucket.created_date == ''

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_bucket_metadata_extraction_preserves_field_types(self, mock_quilt3):
        """Test bucket metadata extraction preserves correct data types for all fields."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock bucket data with various field types
        mock_bucket_data = {
            'string-fields-bucket': {
                'region': 'us-east-1',
                'access_level': 'read-write',
                'created_date': '2024-01-01T00:00:00Z'
            },
            'datetime-object-bucket': {
                'region': 'us-west-2',
                'access_level': 'admin',
                'created_date': datetime(2024, 1, 2, 10, 30, 0)
            },
            'mixed-types-bucket': {
                'region': 'eu-west-1',
                'access_level': 'public-read',
                'created_date': datetime(2024, 1, 3, 15, 45, 30)
            }
        }

        mock_quilt3.list_buckets.return_value = mock_bucket_data

        # Execute
        result = backend.list_buckets()

        # Verify field types are preserved correctly
        assert len(result) == 3

        for bucket in result:
            # All bucket names should be strings
            assert isinstance(bucket.name, str)
            
            # All regions should be strings (normalized)
            assert isinstance(bucket.region, str)
            
            # All access_levels should be strings (normalized)
            assert isinstance(bucket.access_level, str)
            
            # created_date should be string or None
            assert bucket.created_date is None or isinstance(bucket.created_date, str)

        # Verify specific type conversions
        string_bucket = next(b for b in result if b.name == 'string-fields-bucket')
        assert string_bucket.created_date == '2024-01-01T00:00:00Z'

        datetime_bucket = next(b for b in result if b.name == 'datetime-object-bucket')
        assert datetime_bucket.created_date == '2024-01-02T10:30:00'  # Converted from datetime object

        mixed_bucket = next(b for b in result if b.name == 'mixed-types-bucket')
        assert mixed_bucket.created_date == '2024-01-03T15:45:30'  # Converted from datetime object

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_list_buckets_calls_quilt3_correctly(self, mock_quilt3):
        """Test that list_buckets() correctly calls quilt3.list_buckets with proper parameters."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock bucket data
        mock_bucket_data = {
            'test-bucket': {
                'region': 'us-east-1',
                'access_level': 'read-write',
                'created_date': '2024-01-01T00:00:00Z'
            }
        }

        mock_quilt3.list_buckets.return_value = mock_bucket_data

        # Execute
        result = backend.list_buckets()

        # Verify quilt3.list_buckets was called correctly
        mock_quilt3.list_buckets.assert_called_once_with()

        # Verify result is properly transformed
        assert len(result) == 1
        assert isinstance(result[0], Bucket_Info)
        assert result[0].name == 'test-bucket'
        assert result[0].region == 'us-east-1'
        assert result[0].access_level == 'read-write'
        assert result[0].created_date == '2024-01-01T00:00:00Z'

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_list_buckets_with_empty_response(self, mock_quilt3):
        """Test list_buckets() handles empty bucket list response."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock empty bucket data
        mock_quilt3.list_buckets.return_value = {}

        # Execute
        result = backend.list_buckets()

        # Verify
        assert isinstance(result, list)
        assert len(result) == 0
        mock_quilt3.list_buckets.assert_called_once_with()

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_list_buckets_with_multiple_bucket_configurations(self, mock_quilt3):
        """Test list_buckets() with various bucket configurations and access levels."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock diverse bucket configurations
        mock_bucket_data = {
            'public-bucket': {
                'region': 'us-east-1',
                'access_level': 'public-read',
                'created_date': '2023-01-01T00:00:00Z'
            },
            'private-bucket': {
                'region': 'us-west-2',
                'access_level': 'private',
                'created_date': '2023-06-15T12:30:45Z'
            },
            'admin-bucket': {
                'region': 'eu-central-1',
                'access_level': 'admin',
                'created_date': '2024-01-01T00:00:00Z'
            },
            'read-only-bucket': {
                'region': 'ap-southeast-1',
                'access_level': 'read-only'
                # No created_date
            },
            'bucket-with-dashes': {
                'region': 'ca-central-1',
                'access_level': 'read-write',
                'created_date': '2024-03-15T14:22:33Z'
            }
        }

        mock_quilt3.list_buckets.return_value = mock_bucket_data

        # Execute
        result = backend.list_buckets()

        # Verify
        assert len(result) == 5
        assert all(isinstance(bucket, Bucket_Info) for bucket in result)

        # Verify specific bucket configurations
        bucket_names = {bucket.name for bucket in result}
        expected_names = {'public-bucket', 'private-bucket', 'admin-bucket', 'read-only-bucket', 'bucket-with-dashes'}
        assert bucket_names == expected_names

        # Verify specific bucket details
        public_bucket = next(b for b in result if b.name == 'public-bucket')
        assert public_bucket.region == 'us-east-1'
        assert public_bucket.access_level == 'public-read'
        assert public_bucket.created_date == '2023-01-01T00:00:00Z'

        read_only_bucket = next(b for b in result if b.name == 'read-only-bucket')
        assert read_only_bucket.region == 'ap-southeast-1'
        assert read_only_bucket.access_level == 'read-only'
        assert read_only_bucket.created_date is None

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_list_buckets_error_handling(self, mock_quilt3):
        """Test list_buckets() error handling for various failure scenarios."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test various error scenarios
        error_scenarios = [
            (Exception("Network timeout"), "network timeout"),
            (Exception("Access denied"), "access denied"),
            (Exception("Invalid credentials"), "invalid credentials"),
            (PermissionError("Insufficient permissions"), "insufficient permissions"),
            (ConnectionError("Connection failed"), "connection failed"),
            (ValueError("Invalid response format"), "invalid response"),
        ]

        for error, expected_context in error_scenarios:
            mock_quilt3.list_buckets.side_effect = error

            with pytest.raises(BackendError) as exc_info:
                backend.list_buckets()

            error_message = str(exc_info.value)
            assert "quilt3" in error_message.lower()
            assert "list_buckets failed" in error_message.lower()
            assert expected_context.lower() in error_message.lower()

            # Reset for next test
            mock_quilt3.list_buckets.side_effect = None

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_list_buckets_transformation_to_bucket_info(self, mock_quilt3):
        """Test that list_buckets() properly transforms quilt3 responses to Bucket_Info domain objects."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock comprehensive bucket data
        mock_bucket_data = {
            'comprehensive-bucket': {
                'region': 'us-east-1',
                'access_level': 'read-write',
                'created_date': '2024-01-15T10:30:45Z'
            }
        }

        mock_quilt3.list_buckets.return_value = mock_bucket_data

        # Execute
        result = backend.list_buckets()

        # Verify result is Bucket_Info domain object
        assert len(result) == 1
        bucket = result[0]
        assert isinstance(bucket, Bucket_Info)

        # Verify all fields are correctly transformed
        assert bucket.name == 'comprehensive-bucket'
        assert bucket.region == 'us-east-1'
        assert bucket.access_level == 'read-write'
        assert bucket.created_date == '2024-01-15T10:30:45Z'

        # Verify it's a proper dataclass that can be serialized
        from dataclasses import asdict
        bucket_dict = asdict(bucket)
        assert isinstance(bucket_dict, dict)
        assert bucket_dict['name'] == 'comprehensive-bucket'
        assert bucket_dict['region'] == 'us-east-1'
        assert bucket_dict['access_level'] == 'read-write'
        assert bucket_dict['created_date'] == '2024-01-15T10:30:45Z'

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_list_buckets_with_malformed_response_data(self, mock_quilt3):
        """Test list_buckets() handles malformed response data gracefully."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test various malformed response scenarios
        malformed_scenarios = [
            # Missing required fields
            {
                'malformed-bucket-1': {
                    'access_level': 'read-write'
                    # Missing region
                }
            },
            # Empty bucket data
            {
                'malformed-bucket-2': {}
            },
            # None values
            {
                'malformed-bucket-3': {
                    'region': None,
                    'access_level': 'read-write'
                }
            }
        ]

        for i, malformed_data in enumerate(malformed_scenarios):
            mock_quilt3.list_buckets.return_value = malformed_data

            with pytest.raises(BackendError) as exc_info:
                backend.list_buckets()

            error_message = str(exc_info.value)
            assert "transformation failed" in error_message.lower() or "list_buckets failed" in error_message.lower()

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_list_buckets_logging_behavior(self, mock_quilt3):
        """Test that list_buckets() logs appropriate debug information."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock bucket data
        mock_bucket_data = {
            'logging-test-bucket': {
                'region': 'us-east-1',
                'access_level': 'read-write'
            }
        }

        mock_quilt3.list_buckets.return_value = mock_bucket_data

        # Capture log messages
        with patch('quilt_mcp.backends.quilt3_backend.logger') as mock_logger:
            result = backend.list_buckets()

            # Verify debug logging
            mock_logger.debug.assert_any_call("Listing buckets")
            mock_logger.debug.assert_any_call("Found 1 buckets")

            # Should have exactly 2 debug calls from list_buckets
            assert mock_logger.debug.call_count >= 2

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_list_buckets_with_large_number_of_buckets(self, mock_quilt3):
        """Test list_buckets() handles large numbers of buckets efficiently."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Create large number of mock buckets
        mock_bucket_data = {}
        for i in range(100):
            mock_bucket_data[f'bucket-{i:03d}'] = {
                'region': f'us-east-{(i % 2) + 1}',
                'access_level': 'read-write' if i % 2 == 0 else 'read-only',
                'created_date': f'2024-01-{(i % 28) + 1:02d}T00:00:00Z'
            }

        mock_quilt3.list_buckets.return_value = mock_bucket_data

        # Execute
        result = backend.list_buckets()

        # Verify
        assert len(result) == 100
        assert all(isinstance(bucket, Bucket_Info) for bucket in result)

        # Verify bucket names are correctly processed
        bucket_names = {bucket.name for bucket in result}
        expected_names = {f'bucket-{i:03d}' for i in range(100)}
        assert bucket_names == expected_names

        # Verify some specific buckets
        bucket_000 = next(b for b in result if b.name == 'bucket-000')
        assert bucket_000.region == 'us-east-1'
        assert bucket_000.access_level == 'read-write'

        bucket_099 = next(b for b in result if b.name == 'bucket-099')
        assert bucket_099.region == 'us-east-2'
        assert bucket_099.access_level == 'read-only'

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_list_buckets_with_special_bucket_names(self, mock_quilt3):
        """Test list_buckets() handles buckets with special characters and naming patterns."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock buckets with various naming patterns
        mock_bucket_data = {
            'bucket-with-dashes': {
                'region': 'us-east-1',
                'access_level': 'read-write'
            },
            'bucket.with.dots': {
                'region': 'us-west-2',
                'access_level': 'read-only'
            },
            'bucketwithverylongnametotesthandling': {
                'region': 'eu-west-1',
                'access_level': 'admin'
            },
            '123numeric-bucket': {
                'region': 'ap-southeast-1',
                'access_level': 'public-read'
            },
            'a': {  # Single character bucket name
                'region': 'ca-central-1',
                'access_level': 'private'
            }
        }

        mock_quilt3.list_buckets.return_value = mock_bucket_data

        # Execute
        result = backend.list_buckets()

        # Verify
        assert len(result) == 5
        assert all(isinstance(bucket, Bucket_Info) for bucket in result)

        # Verify specific bucket names are preserved
        bucket_names = {bucket.name for bucket in result}
        expected_names = {
            'bucket-with-dashes',
            'bucket.with.dots',
            'bucketwithverylongnametotesthandling',
            '123numeric-bucket',
            'a'
        }
        assert bucket_names == expected_names

        # Verify specific bucket details
        dash_bucket = next(b for b in result if b.name == 'bucket-with-dashes')
        assert dash_bucket.region == 'us-east-1'
        assert dash_bucket.access_level == 'read-write'

        single_char_bucket = next(b for b in result if b.name == 'a')
        assert single_char_bucket.region == 'ca-central-1'
        assert single_char_bucket.access_level == 'private'


class TestQuilt3BackendBucketTransformation:
    """Test bucket transformation methods in isolation."""

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_with_complete_data(self, mock_quilt3):
        """Test _transform_bucket() method with complete quilt3 bucket object."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Create complete bucket data
        bucket_name = "test-bucket"
        bucket_data = {
            'region': 'us-east-1',
            'access_level': 'read-write',
            'created_date': '2024-01-01T00:00:00Z'
        }

        # Execute transformation
        result = backend._transform_bucket(bucket_name, bucket_data)

        # Verify
        assert isinstance(result, Bucket_Info)
        assert result.name == "test-bucket"
        assert result.region == "us-east-1"
        assert result.access_level == "read-write"
        assert result.created_date == "2024-01-01T00:00:00Z"

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_with_missing_fields(self, mock_quilt3):
        """Test _transform_bucket() handles missing/null fields in quilt3 objects."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Create minimal bucket data
        bucket_name = "minimal-bucket"
        bucket_data = {
            'region': 'us-west-2',
            'access_level': 'read-only'
            # created_date missing
        }

        # Execute transformation
        result = backend._transform_bucket(bucket_name, bucket_data)

        # Verify
        assert result.name == "minimal-bucket"
        assert result.region == "us-west-2"
        assert result.access_level == "read-only"
        assert result.created_date is None

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_error_handling(self, mock_quilt3):
        """Test _transform_bucket() error handling in transformation logic."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Create invalid bucket data
        bucket_name = None  # Invalid name
        bucket_data = {'region': 'us-east-1'}

        with pytest.raises(BackendError):
            backend._transform_bucket(bucket_name, bucket_data)

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_error_wrapping_and_context(self, mock_quilt3):
        """Test that bucket transformation errors are properly wrapped in BackendError with context."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test various error scenarios for bucket transformation
        error_scenarios = [
            # Missing bucket name
            {
                'bucket_name': None,
                'bucket_data': {'region': 'us-east-1', 'access_level': 'read-write'},
                'expected_message': 'missing name',
                'description': 'None bucket name'
            },
            # Empty bucket name
            {
                'bucket_name': '',
                'bucket_data': {'region': 'us-east-1', 'access_level': 'read-write'},
                'expected_message': 'missing name',
                'description': 'empty bucket name'
            },
            # None bucket data
            {
                'bucket_name': 'test-bucket',
                'bucket_data': None,
                'expected_message': 'bucket_data is none',
                'description': 'None bucket data'
            },
            # Empty bucket data (will fail domain validation)
            {
                'bucket_name': 'test-bucket',
                'bucket_data': {},
                'expected_message': 'region field cannot be empty',
                'description': 'empty bucket data'
            },
            # Missing required fields in bucket data
            {
                'bucket_name': 'test-bucket',
                'bucket_data': {'region': '', 'access_level': 'read-write'},
                'expected_message': 'region field cannot be empty',
                'description': 'empty region field'
            },
            {
                'bucket_name': 'test-bucket',
                'bucket_data': {'region': 'us-east-1', 'access_level': ''},
                'expected_message': 'access_level field cannot be empty',
                'description': 'empty access_level field'
            }
        ]

        for scenario in error_scenarios:
            # Test that error is wrapped in BackendError
            with pytest.raises(BackendError) as exc_info:
                backend._transform_bucket(scenario['bucket_name'], scenario['bucket_data'])

            error = exc_info.value
            error_message = str(error)

            # Verify error message contains expected content
            assert scenario['expected_message'].lower() in error_message.lower(), \
                f"Expected '{scenario['expected_message']}' in error message for {scenario['description']}: {error_message}"

            # Verify error is properly wrapped as BackendError
            assert isinstance(error, BackendError), f"Error should be BackendError for {scenario['description']}"

            # Verify error context is provided
            assert hasattr(error, 'context'), f"Error should have context for {scenario['description']}"
            if error.context:
                assert 'bucket_name' in error.context or 'bucket_data_keys' in error.context, \
                    f"Error context should contain bucket info for {scenario['description']}"

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_error_message_clarity(self, mock_quilt3):
        """Test that bucket transformation error messages are clear and actionable."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test error message clarity for different failure types
        clarity_tests = [
            {
                'name': 'missing_bucket_name',
                'bucket_name': None,
                'bucket_data': {'region': 'us-east-1', 'access_level': 'read-write'},
                'expected_keywords': ['missing', 'name', 'bucket']
            },
            {
                'name': 'none_bucket_data',
                'bucket_name': 'test-bucket',
                'bucket_data': None,
                'expected_keywords': ['bucket_data', 'none', 'invalid']
            },
            {
                'name': 'empty_region',
                'bucket_name': 'test-bucket',
                'bucket_data': {'region': '', 'access_level': 'read-write'},
                'expected_keywords': ['region', 'field', 'empty']
            }
        ]

        for test_case in clarity_tests:
            with pytest.raises(BackendError) as exc_info:
                backend._transform_bucket(test_case['bucket_name'], test_case['bucket_data'])

            error_message = str(exc_info.value).lower()

            # Verify error message contains expected keywords for clarity
            for keyword in test_case['expected_keywords']:
                assert keyword.lower() in error_message, \
                    f"Error message should contain '{keyword}' for {test_case['name']}: {error_message}"

            # Verify error message mentions the backend type
            assert 'quilt3' in error_message, \
                f"Error message should mention backend type for {test_case['name']}: {error_message}"

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_error_propagation_from_helpers(self, mock_quilt3):
        """Test that errors from bucket transformation helper methods are properly propagated."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test error propagation from validation helper
        with pytest.raises(BackendError) as exc_info:
            backend._transform_bucket(None, {'region': 'us-east-1'})

        # Verify the validation error is properly propagated
        assert "missing name" in str(exc_info.value).lower()

        # Test error propagation from domain object creation (Bucket_Info validation)
        with pytest.raises(BackendError) as exc_info:
            backend._transform_bucket('test-bucket', {'region': '', 'access_level': 'read-write'})

        # Verify the domain validation error is properly propagated
        assert "region field cannot be empty" in str(exc_info.value).lower()

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_various_transformation_failures(self, mock_quilt3):
        """Test various types of bucket transformation failures and their error handling."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test different types of transformation failures
        failure_scenarios = [
            {
                'name': 'bucket_info_creation_failure',
                'mock_target': 'quilt_mcp.backends.quilt3_backend.Bucket_Info',
                'mock_side_effect': ValueError("Bucket_Info creation failed"),
                'expected_error': 'transformation failed'
            },
            {
                'name': 'normalization_helper_failure',
                'mock_target': None,  # We'll mock a helper method
                'mock_side_effect': None,
                'expected_error': 'transformation failed'
            }
        ]

        for scenario in failure_scenarios:
            if scenario['mock_target']:
                with patch(scenario['mock_target'], side_effect=scenario['mock_side_effect']):
                    bucket_name = "test-bucket"
                    bucket_data = {'region': 'us-east-1', 'access_level': 'read-write'}

                    with pytest.raises(BackendError) as exc_info:
                        backend._transform_bucket(bucket_name, bucket_data)

                    assert scenario['expected_error'] in str(exc_info.value).lower()
            else:
                # Test normalization helper failure
                with patch.object(backend, '_normalize_string_field', side_effect=Exception("Normalization failed")):
                    bucket_name = "test-bucket"
                    bucket_data = {'region': 'us-east-1', 'access_level': 'read-write'}

                    with pytest.raises(BackendError) as exc_info:
                        backend._transform_bucket(bucket_name, bucket_data)

                    assert 'transformation failed' in str(exc_info.value).lower()
                    assert 'normalization failed' in str(exc_info.value).lower()

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_edge_case_error_scenarios(self, mock_quilt3):
        """Test edge case error scenarios in bucket transformation."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test edge cases that should cause errors
        edge_case_scenarios = [
            {
                'name': 'bucket_data_wrong_type',
                'bucket_name': 'test-bucket',
                'bucket_data': "not-a-dict",  # String instead of dict
                'expected_error': 'transformation failed'
            },
            {
                'name': 'bucket_data_list_type',
                'bucket_name': 'test-bucket',
                'bucket_data': ['region', 'access_level'],  # List instead of dict
                'expected_error': 'transformation failed'
            }
        ]

        for scenario in edge_case_scenarios:
            with pytest.raises(BackendError) as exc_info:
                backend._transform_bucket(scenario['bucket_name'], scenario['bucket_data'])

            error_message = str(exc_info.value).lower()
            assert scenario['expected_error'] in error_message, \
                f"Expected '{scenario['expected_error']}' in error message for {scenario['name']}: {error_message}"

            # Verify error context includes useful debugging information
            error = exc_info.value
            assert hasattr(error, 'context'), f"Error should have context for {scenario['name']}"
            if error.context:
                assert 'bucket_name' in error.context, f"Error context should contain bucket_name for {scenario['name']}"
                assert 'bucket_data_type' in error.context, f"Error context should contain bucket_data_type for {scenario['name']}"

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_with_various_bucket_names(self, mock_quilt3):
        """Test _transform_bucket() handles various bucket name formats."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        bucket_names = [
            "simple-bucket",
            "bucket-with-dashes",
            "bucket.with.dots",
            "bucket_with_underscores",
            "123numeric-bucket",
            "very-long-bucket-name-with-many-characters-and-dashes-for-testing",
            "a",  # Single character
            "bucket123",  # Alphanumeric
        ]

        for bucket_name in bucket_names:
            bucket_data = {
                'region': 'us-east-1',
                'access_level': 'read-write',
                'created_date': '2024-01-01T00:00:00Z'
            }

            result = backend._transform_bucket(bucket_name, bucket_data)

            assert isinstance(result, Bucket_Info)
            assert result.name == bucket_name
            assert result.region == 'us-east-1'
            assert result.access_level == 'read-write'
            assert result.created_date == '2024-01-01T00:00:00Z'

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_with_various_regions(self, mock_quilt3):
        """Test _transform_bucket() handles various AWS regions correctly."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        regions = [
            'us-east-1',
            'us-west-2',
            'eu-west-1',
            'eu-central-1',
            'ap-southeast-1',
            'ap-northeast-1',
            'sa-east-1',
            'ca-central-1',
            'us-gov-west-1',
        ]

        for region in regions:
            bucket_data = {
                'region': region,
                'access_level': 'read-only'
            }

            result = backend._transform_bucket("test-bucket", bucket_data)

            assert result.region == region

        # Test empty region (should cause error due to validation)
        bucket_data = {
            'region': '',  # Empty region
            'access_level': 'read-only'
        }

        with pytest.raises(BackendError) as exc_info:
            backend._transform_bucket("test-bucket", bucket_data)

        assert "transformation failed" in str(exc_info.value).lower()

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_with_various_access_levels(self, mock_quilt3):
        """Test _transform_bucket() handles various access levels correctly."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        access_levels = [
            'read-only',
            'read-write',
            'admin',
            'full-control',
            'write-only',
            'list-only',
            'custom-permission-level',
        ]

        for access_level in access_levels:
            bucket_data = {
                'region': 'us-east-1',
                'access_level': access_level
            }

            result = backend._transform_bucket("test-bucket", bucket_data)

            assert result.access_level == access_level

        # Test empty access level (should cause error due to validation)
        bucket_data = {
            'region': 'us-east-1',
            'access_level': ''  # Empty access level
        }

        with pytest.raises(BackendError) as exc_info:
            backend._transform_bucket("test-bucket", bucket_data)

        assert "transformation failed" in str(exc_info.value).lower()

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_with_various_date_formats(self, mock_quilt3):
        """Test _transform_bucket() handles various created_date formats."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        date_formats = [
            '2024-01-01T00:00:00Z',  # ISO format with Z
            '2024-01-01T00:00:00+00:00',  # ISO format with timezone
            '2024-01-01T00:00:00',  # ISO format without timezone
            '2024-01-01',  # Date only
            '2024-12-31T23:59:59.999Z',  # With milliseconds
            None,  # No created date
            '',  # Empty string
        ]

        for created_date in date_formats:
            bucket_data = {
                'region': 'us-east-1',
                'access_level': 'read-write'
            }
            if created_date is not None:
                bucket_data['created_date'] = created_date

            result = backend._transform_bucket("test-bucket", bucket_data)

            if created_date is None:
                assert result.created_date is None
            else:
                assert result.created_date == created_date

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_with_minimal_data(self, mock_quilt3):
        """Test _transform_bucket() works with minimal bucket data."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test with minimal valid bucket data (non-empty required fields)
        minimal_data = {
            'region': 'us-west-2',
            'access_level': 'read-only'
        }
        result = backend._transform_bucket("minimal-bucket", minimal_data)

        assert result.name == "minimal-bucket"
        assert result.region == "us-west-2"
        assert result.access_level == "read-only"
        assert result.created_date is None

        # Test with only some fields
        partial_data = {
            'region': 'us-west-2',
            'access_level': 'admin'
        }
        result = backend._transform_bucket("partial-bucket", partial_data)

        assert result.name == "partial-bucket"
        assert result.region == "us-west-2"
        assert result.access_level == "admin"
        assert result.created_date is None

        # Test with empty bucket data (should cause error due to missing required fields)
        with pytest.raises(BackendError) as exc_info:
            backend._transform_bucket("empty-bucket", {})

        assert "transformation failed" in str(exc_info.value).lower()

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_with_extra_fields(self, mock_quilt3):
        """Test _transform_bucket() ignores extra fields in bucket data."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test with extra fields that should be ignored
        bucket_data_with_extras = {
            'region': 'us-east-1',
            'access_level': 'read-write',
            'created_date': '2024-01-01T00:00:00Z',
            'extra_field_1': 'should_be_ignored',
            'extra_field_2': 12345,
            'nested_extra': {'key': 'value'},
            'list_extra': ['item1', 'item2']
        }

        result = backend._transform_bucket("extra-fields-bucket", bucket_data_with_extras)

        # Verify only expected fields are used
        assert result.name == "extra-fields-bucket"
        assert result.region == "us-east-1"
        assert result.access_level == "read-write"
        assert result.created_date == "2024-01-01T00:00:00Z"

        # Verify extra fields don't affect the result
        assert not hasattr(result, 'extra_field_1')
        assert not hasattr(result, 'extra_field_2')
        assert not hasattr(result, 'nested_extra')
        assert not hasattr(result, 'list_extra')


class TestQuilt3BackendBucketTransformationIsolated:
    """Test _transform_bucket() method in complete isolation with focus on transformation logic."""

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_isolated_with_minimal_mock_data(self, mock_quilt3):
        """Test _transform_bucket() method in isolation with minimal mock bucket data."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Create minimal mock bucket data with only required fields
        bucket_name = "isolated-test-bucket"
        bucket_data = {
            'region': 'us-east-1',
            'access_level': 'read-write'
            # created_date intentionally omitted to test optional field handling
        }

        # Execute transformation in isolation
        result = backend._transform_bucket(bucket_name, bucket_data)

        # Verify transformation produces correct Bucket_Info
        assert isinstance(result, Bucket_Info)
        assert result.name == "isolated-test-bucket"
        assert result.region == "us-east-1"
        assert result.access_level == "read-write"
        assert result.created_date is None  # Optional field should be None

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_isolated_with_complete_mock_data(self, mock_quilt3):
        """Test _transform_bucket() method in isolation with complete mock bucket data."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Create complete mock bucket data with all fields
        bucket_name = "complete-isolated-bucket"
        bucket_data = {
            'region': 'us-west-2',
            'access_level': 'read-only',
            'created_date': '2024-03-15T14:30:45Z'
        }

        # Execute transformation in isolation
        result = backend._transform_bucket(bucket_name, bucket_data)

        # Verify complete transformation
        assert isinstance(result, Bucket_Info)
        assert result.name == "complete-isolated-bucket"
        assert result.region == "us-west-2"
        assert result.access_level == "read-only"
        assert result.created_date == "2024-03-15T14:30:45Z"

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_isolated_validation_logic(self, mock_quilt3):
        """Test _transform_bucket() validation logic in isolation."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test validation of required bucket_name field
        with pytest.raises(BackendError) as exc_info:
            backend._transform_bucket(None, {'region': 'us-east-1', 'access_level': 'read-write'})
        assert "missing name" in str(exc_info.value).lower()

        # Test validation of empty bucket_name
        with pytest.raises(BackendError) as exc_info:
            backend._transform_bucket("", {'region': 'us-east-1', 'access_level': 'read-write'})
        assert "missing name" in str(exc_info.value).lower()

        # Test validation of None bucket_data
        with pytest.raises(BackendError) as exc_info:
            backend._transform_bucket("test-bucket", None)
        assert "bucket_data is none" in str(exc_info.value).lower()

        # Test validation of empty region field
        with pytest.raises(BackendError) as exc_info:
            backend._transform_bucket("test-bucket", {'region': '', 'access_level': 'read-write'})
        assert "region field cannot be empty" in str(exc_info.value).lower()

        # Test validation of empty access_level field
        with pytest.raises(BackendError) as exc_info:
            backend._transform_bucket("test-bucket", {'region': 'us-east-1', 'access_level': ''})
        assert "access_level field cannot be empty" in str(exc_info.value).lower()

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_isolated_with_null_optional_fields(self, mock_quilt3):
        """Test _transform_bucket() handles null/None values in optional fields."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test various null/None scenarios for optional fields
        null_scenarios = [
            {
                'region': 'us-east-1',
                'access_level': 'read-write',
                'created_date': None  # Explicit None
            },
            {
                'region': 'us-west-1',
                'access_level': 'read-only'
                # created_date missing entirely
            }
        ]

        for i, bucket_data in enumerate(null_scenarios):
            bucket_name = f"null-test-bucket-{i}"
            
            result = backend._transform_bucket(bucket_name, bucket_data)
            
            assert isinstance(result, Bucket_Info)
            assert result.name == bucket_name
            assert result.region == bucket_data['region']
            assert result.access_level == bucket_data['access_level']
            assert result.created_date is None

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_isolated_helper_method_integration(self, mock_quilt3):
        """Test _transform_bucket() integration with helper methods in isolation."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Create bucket data that exercises all helper methods
        bucket_name = "helper-integration-bucket"
        bucket_data = {
            'region': '  us-central-1  ',  # Tests _normalize_string_field (preserves whitespace)
            'access_level': 'READ-WRITE',  # Tests _normalize_string_field (case)
            'created_date': '2024-01-15T10:30:00.000Z'  # Tests _normalize_datetime
        }

        # Execute transformation
        result = backend._transform_bucket(bucket_name, bucket_data)

        # Verify helper method integration
        assert isinstance(result, Bucket_Info)
        assert result.name == "helper-integration-bucket"
        assert result.region == "  us-central-1  "  # Whitespace should be preserved
        assert result.access_level == "READ-WRITE"  # Case should be preserved
        assert result.created_date == "2024-01-15T10:30:00.000Z"  # Datetime should be normalized

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_isolated_edge_case_bucket_names(self, mock_quilt3):
        """Test _transform_bucket() with edge case bucket names in isolation."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test various edge case bucket names
        edge_case_names = [
            "a",  # Single character
            "bucket-with-dashes",  # Dashes
            "bucket.with.dots",  # Dots
            "bucket123numbers",  # Numbers
            "a" * 63,  # Maximum AWS bucket name length
            "my-test-bucket-2024",  # Common pattern
        ]

        base_bucket_data = {
            'region': 'us-east-1',
            'access_level': 'read-write',
            'created_date': '2024-01-01T00:00:00Z'
        }

        for bucket_name in edge_case_names:
            result = backend._transform_bucket(bucket_name, base_bucket_data)
            
            assert isinstance(result, Bucket_Info)
            assert result.name == bucket_name
            assert result.region == "us-east-1"
            assert result.access_level == "read-write"
            assert result.created_date == "2024-01-01T00:00:00Z"

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_isolated_edge_case_regions(self, mock_quilt3):
        """Test _transform_bucket() with edge case AWS regions in isolation."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test various AWS regions
        edge_case_regions = [
            "us-east-1",  # Standard US region
            "us-west-2",  # Standard US region
            "eu-west-1",  # European region
            "ap-southeast-1",  # Asia Pacific region
            "ca-central-1",  # Canada region
            "sa-east-1",  # South America region
            "af-south-1",  # Africa region
            "me-south-1",  # Middle East region
        ]

        base_bucket_data = {
            'access_level': 'read-write',
            'created_date': '2024-01-01T00:00:00Z'
        }

        for region in edge_case_regions:
            bucket_data = {**base_bucket_data, 'region': region}
            
            result = backend._transform_bucket("test-bucket", bucket_data)
            
            assert isinstance(result, Bucket_Info)
            assert result.name == "test-bucket"
            assert result.region == region
            assert result.access_level == "read-write"
            assert result.created_date == "2024-01-01T00:00:00Z"

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_isolated_edge_case_access_levels(self, mock_quilt3):
        """Test _transform_bucket() with edge case access levels in isolation."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test various access levels
        edge_case_access_levels = [
            "read-only",
            "read-write",
            "write-only",
            "admin",
            "public-read",
            "private",
            "READ-ONLY",  # Case variation
            "Read-Write",  # Case variation
        ]

        base_bucket_data = {
            'region': 'us-east-1',
            'created_date': '2024-01-01T00:00:00Z'
        }

        for access_level in edge_case_access_levels:
            bucket_data = {**base_bucket_data, 'access_level': access_level}
            
            result = backend._transform_bucket("test-bucket", bucket_data)
            
            assert isinstance(result, Bucket_Info)
            assert result.name == "test-bucket"
            assert result.region == "us-east-1"
            assert result.access_level == access_level  # Should preserve original case
            assert result.created_date == "2024-01-01T00:00:00Z"

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_isolated_error_context_and_wrapping(self, mock_quilt3):
        """Test _transform_bucket() error context and wrapping in isolation."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test error context for various failure scenarios
        error_scenarios = [
            {
                'bucket_name': None,
                'bucket_data': {'region': 'us-east-1', 'access_level': 'read-write'},
                'expected_context_keys': ['bucket_name', 'bucket_data_keys', 'bucket_data_type']
            },
            {
                'bucket_name': 'test-bucket',
                'bucket_data': None,
                'expected_context_keys': ['bucket_name', 'bucket_data_keys', 'bucket_data_type']
            },
            {
                'bucket_name': 'test-bucket',
                'bucket_data': {'region': '', 'access_level': 'read-write'},
                'expected_context_keys': ['bucket_name', 'bucket_data_keys', 'bucket_data_type']
            }
        ]

        for scenario in error_scenarios:
            with pytest.raises(BackendError) as exc_info:
                backend._transform_bucket(scenario['bucket_name'], scenario['bucket_data'])

            error = exc_info.value
            
            # Verify error is properly wrapped as BackendError
            assert isinstance(error, BackendError)
            
            # Verify error message mentions backend type
            assert "quilt3" in str(error).lower()
            
            # Verify error context is provided
            assert hasattr(error, 'context')
            if error.context:
                for expected_key in scenario['expected_context_keys']:
                    assert expected_key in error.context, f"Missing context key: {expected_key}"

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_isolated_transformation_logic_only(self, mock_quilt3):
        """Test _transform_bucket() pure transformation logic without side effects."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test that transformation is pure (no side effects)
        bucket_name = "pure-transformation-test"
        bucket_data = {
            'region': 'us-east-1',
            'access_level': 'read-write',
            'created_date': '2024-01-01T00:00:00Z'
        }

        # Execute transformation multiple times
        result1 = backend._transform_bucket(bucket_name, bucket_data)
        result2 = backend._transform_bucket(bucket_name, bucket_data)

        # Verify results are identical (pure function)
        assert result1.name == result2.name
        assert result1.region == result2.region
        assert result1.access_level == result2.access_level
        assert result1.created_date == result2.created_date

        # Verify original bucket_data is not modified (no side effects)
        assert bucket_data['region'] == 'us-east-1'
        assert bucket_data['access_level'] == 'read-write'
        assert bucket_data['created_date'] == '2024-01-01T00:00:00Z'

        # Verify results are separate objects
        assert result1 is not result2
        assert id(result1) != id(result2)


class TestQuilt3BackendBucketTransformationFromQuilt3Responses:
    """Test transformation from quilt3 bucket responses to Bucket_Info domain objects.
    
    This test class focuses specifically on testing the transformation logic from
    quilt3-specific bucket responses to our Bucket_Info domain objects, covering
    various response configurations and edge cases.
    """

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_from_typical_quilt3_response(self, mock_quilt3):
        """Test _transform_bucket() with typical quilt3 bucket response format."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Simulate typical quilt3 bucket response format
        bucket_name = "production-data-bucket"
        quilt3_bucket_response = {
            'region': 'us-west-2',
            'access_level': 'read-write',
            'created_date': '2024-03-15T14:30:45.123456Z',
            'bucket_policy': 'private',  # Extra field from quilt3
            'versioning': True,  # Extra field from quilt3
            'encryption': 'AES256'  # Extra field from quilt3
        }

        result = backend._transform_bucket(bucket_name, quilt3_bucket_response)

        # Verify transformation to Bucket_Info domain object
        assert isinstance(result, Bucket_Info)
        assert result.name == "production-data-bucket"
        assert result.region == "us-west-2"
        assert result.access_level == "read-write"
        assert result.created_date == "2024-03-15T14:30:45.123456Z"

        # Verify it's a proper dataclass that can be serialized
        from dataclasses import asdict
        result_dict = asdict(result)
        assert isinstance(result_dict, dict)
        assert result_dict['name'] == "production-data-bucket"
        assert result_dict['region'] == "us-west-2"
        assert result_dict['access_level'] == "read-write"
        assert result_dict['created_date'] == "2024-03-15T14:30:45.123456Z"

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_from_minimal_quilt3_response(self, mock_quilt3):
        """Test _transform_bucket() with minimal quilt3 bucket response."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Simulate minimal quilt3 bucket response with only required fields
        bucket_name = "minimal-bucket"
        minimal_quilt3_response = {
            'region': 'eu-west-1',
            'access_level': 'read-only'
            # No created_date or other optional fields
        }

        result = backend._transform_bucket(bucket_name, minimal_quilt3_response)

        # Verify transformation handles missing optional fields
        assert isinstance(result, Bucket_Info)
        assert result.name == "minimal-bucket"
        assert result.region == "eu-west-1"
        assert result.access_level == "read-only"
        assert result.created_date is None  # Should default to None for missing field

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_from_quilt3_response_with_null_fields(self, mock_quilt3):
        """Test _transform_bucket() handles null/None values in quilt3 bucket responses."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test various null/None scenarios in quilt3 responses
        null_scenarios = [
            {
                'name': 'null_created_date',
                'bucket_name': 'null-date-bucket',
                'response': {
                    'region': 'us-east-1',
                    'access_level': 'read-write',
                    'created_date': None
                },
                'expected_created_date': None
            },
            {
                'name': 'empty_created_date',
                'bucket_name': 'empty-date-bucket',
                'response': {
                    'region': 'ap-southeast-1',
                    'access_level': 'admin',
                    'created_date': ''
                },
                'expected_created_date': ''  # Empty string should be preserved
            },
            {
                'name': 'missing_created_date',
                'bucket_name': 'missing-date-bucket',
                'response': {
                    'region': 'ca-central-1',
                    'access_level': 'list-only'
                    # created_date key missing entirely
                },
                'expected_created_date': None
            }
        ]

        for scenario in null_scenarios:
            result = backend._transform_bucket(scenario['bucket_name'], scenario['response'])

            assert isinstance(result, Bucket_Info)
            assert result.name == scenario['bucket_name']
            assert result.region == scenario['response']['region']
            assert result.access_level == scenario['response']['access_level']
            assert result.created_date == scenario['expected_created_date']

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_from_quilt3_response_with_invalid_required_fields(self, mock_quilt3):
        """Test _transform_bucket() properly fails when quilt3 responses have invalid required fields."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test scenarios that should fail due to invalid required fields
        invalid_scenarios = [
            {
                'name': 'null_region',
                'bucket_name': 'test-bucket',
                'response': {
                    'region': None,  # Invalid: region cannot be None
                    'access_level': 'read-write'
                },
                'expected_error': 'region field cannot be empty'
            },
            {
                'name': 'empty_region',
                'bucket_name': 'test-bucket',
                'response': {
                    'region': '',  # Invalid: region cannot be empty
                    'access_level': 'read-write'
                },
                'expected_error': 'region field cannot be empty'
            },
            {
                'name': 'null_access_level',
                'bucket_name': 'test-bucket',
                'response': {
                    'region': 'us-east-1',
                    'access_level': None  # Invalid: access_level cannot be None
                },
                'expected_error': 'access_level field cannot be empty'
            },
            {
                'name': 'empty_access_level',
                'bucket_name': 'test-bucket',
                'response': {
                    'region': 'us-east-1',
                    'access_level': ''  # Invalid: access_level cannot be empty
                },
                'expected_error': 'access_level field cannot be empty'
            },
            {
                'name': 'missing_region',
                'bucket_name': 'test-bucket',
                'response': {
                    'access_level': 'read-write'
                    # region key missing entirely
                },
                'expected_error': 'region field cannot be empty'
            },
            {
                'name': 'missing_access_level',
                'bucket_name': 'test-bucket',
                'response': {
                    'region': 'us-east-1'
                    # access_level key missing entirely
                },
                'expected_error': 'access_level field cannot be empty'
            }
        ]

        for scenario in invalid_scenarios:
            with pytest.raises(BackendError) as exc_info:
                backend._transform_bucket(scenario['bucket_name'], scenario['response'])

            error_message = str(exc_info.value)
            assert scenario['expected_error'].lower() in error_message.lower(), \
                f"Expected '{scenario['expected_error']}' in error message for {scenario['name']}: {error_message}"

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_from_various_quilt3_response_configurations(self, mock_quilt3):
        """Test _transform_bucket() with various quilt3 bucket response configurations."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test different response configurations that might come from quilt3
        response_configurations = [
            {
                'name': 'aws_standard_bucket',
                'bucket_name': 'aws-standard-bucket',
                'response': {
                    'region': 'us-east-1',
                    'access_level': 'read-write',
                    'created_date': '2024-01-15T10:30:00Z',
                    'storage_class': 'STANDARD',  # Extra quilt3 field
                    'lifecycle_policy': 'enabled'  # Extra quilt3 field
                }
            },
            {
                'name': 'aws_glacier_bucket',
                'bucket_name': 'glacier-archive-bucket',
                'response': {
                    'region': 'us-west-2',
                    'access_level': 'read-only',
                    'created_date': '2023-12-01T00:00:00Z',
                    'storage_class': 'GLACIER',  # Extra quilt3 field
                    'transition_days': 30  # Extra quilt3 field
                }
            },
            {
                'name': 'multi_region_bucket',
                'bucket_name': 'multi-region-bucket',
                'response': {
                    'region': 'eu-central-1',
                    'access_level': 'admin',
                    'created_date': '2024-02-29T23:59:59.999Z',
                    'cross_region_replication': True,  # Extra quilt3 field
                    'replicated_regions': ['us-east-1', 'ap-southeast-1']  # Extra quilt3 field
                }
            },
            {
                'name': 'government_cloud_bucket',
                'bucket_name': 'gov-cloud-bucket',
                'response': {
                    'region': 'us-gov-west-1',
                    'access_level': 'full-control',
                    'created_date': '2024-03-01T12:00:00Z',
                    'compliance_level': 'FedRAMP',  # Extra quilt3 field
                    'encryption_type': 'KMS'  # Extra quilt3 field
                }
            }
        ]

        for config in response_configurations:
            result = backend._transform_bucket(config['bucket_name'], config['response'])

            # Verify transformation extracts only the domain-relevant fields
            assert isinstance(result, Bucket_Info)
            assert result.name == config['bucket_name']
            assert result.region == config['response']['region']
            assert result.access_level == config['response']['access_level']
            assert result.created_date == config['response']['created_date']

            # Verify extra quilt3-specific fields are not included in domain object
            from dataclasses import asdict
            result_dict = asdict(result)
            quilt3_specific_fields = [
                'storage_class', 'lifecycle_policy', 'transition_days',
                'cross_region_replication', 'replicated_regions',
                'compliance_level', 'encryption_type'
            ]
            for field in quilt3_specific_fields:
                assert field not in result_dict, f"Domain object should not contain quilt3-specific field: {field}"

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_from_quilt3_response_edge_cases(self, mock_quilt3):
        """Test _transform_bucket() handles edge cases in quilt3 bucket responses."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test edge cases that might occur in real quilt3 responses
        edge_cases = [
            {
                'name': 'very_long_bucket_name',
                'bucket_name': 'a' * 63,  # AWS bucket name limit
                'response': {
                    'region': 'us-east-1',
                    'access_level': 'read-write',
                    'created_date': '2024-01-01T00:00:00Z'
                }
            },
            {
                'name': 'single_char_bucket_name',
                'bucket_name': 'a',
                'response': {
                    'region': 'us-west-2',
                    'access_level': 'read-only'
                }
            },
            {
                'name': 'bucket_with_special_chars',
                'bucket_name': 'bucket-with.dots_and-dashes123',
                'response': {
                    'region': 'eu-west-1',
                    'access_level': 'admin',
                    'created_date': '2024-12-31T23:59:59.999999Z'
                }
            },
            {
                'name': 'very_long_region',
                'bucket_name': 'test-bucket',
                'response': {
                    'region': 'custom-very-long-region-name-for-testing-purposes',
                    'access_level': 'read-write'
                }
            },
            {
                'name': 'custom_access_level',
                'bucket_name': 'custom-access-bucket',
                'response': {
                    'region': 'us-east-1',
                    'access_level': 'custom-permission-level-with-specific-rules',
                    'created_date': '1970-01-01T00:00:00Z'  # Unix epoch
                }
            },
            {
                'name': 'future_date',
                'bucket_name': 'future-bucket',
                'response': {
                    'region': 'us-east-1',
                    'access_level': 'read-write',
                    'created_date': '2099-12-31T23:59:59Z'  # Future date
                }
            }
        ]

        for case in edge_cases:
            result = backend._transform_bucket(case['bucket_name'], case['response'])

            assert isinstance(result, Bucket_Info)
            assert result.name == case['bucket_name']
            assert result.region == case['response']['region']
            assert result.access_level == case['response']['access_level']

            if 'created_date' in case['response']:
                assert result.created_date == case['response']['created_date']
            else:
                assert result.created_date is None

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_from_malformed_quilt3_responses(self, mock_quilt3):
        """Test _transform_bucket() handles malformed quilt3 bucket responses appropriately."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test malformed responses that should cause errors
        malformed_scenarios = [
            {
                'name': 'none_response',
                'bucket_name': 'test-bucket',
                'response': None,
                'expected_error': 'bucket_data is none'
            },
            {
                'name': 'string_response',
                'bucket_name': 'test-bucket',
                'response': "not-a-dict",
                'expected_error': 'transformation failed'
            },
            {
                'name': 'list_response',
                'bucket_name': 'test-bucket',
                'response': ['region', 'access_level'],
                'expected_error': 'transformation failed'
            },
            {
                'name': 'number_response',
                'bucket_name': 'test-bucket',
                'response': 12345,
                'expected_error': 'transformation failed'
            }
        ]

        for scenario in malformed_scenarios:
            with pytest.raises(BackendError) as exc_info:
                backend._transform_bucket(scenario['bucket_name'], scenario['response'])

            error_message = str(exc_info.value)
            assert scenario['expected_error'].lower() in error_message.lower(), \
                f"Expected '{scenario['expected_error']}' in error message for {scenario['name']}: {error_message}"

            # Verify error context includes debugging information
            error = exc_info.value
            assert hasattr(error, 'context'), f"Error should have context for {scenario['name']}"
            if error.context:
                assert 'bucket_name' in error.context, f"Error context should contain bucket_name for {scenario['name']}"
                assert 'bucket_data_type' in error.context, f"Error context should contain bucket_data_type for {scenario['name']}"

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_from_quilt3_response_with_unexpected_field_types(self, mock_quilt3):
        """Test _transform_bucket() handles unexpected field types in quilt3 responses."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test responses with unexpected field types
        unexpected_type_scenarios = [
            {
                'name': 'numeric_region',
                'bucket_name': 'numeric-region-bucket',
                'response': {
                    'region': 12345,  # Number instead of string
                    'access_level': 'read-write'
                },
                'should_succeed': True,  # Should be converted to string
                'expected_region': '12345'
            },
            {
                'name': 'boolean_access_level',
                'bucket_name': 'boolean-access-bucket',
                'response': {
                    'region': 'us-east-1',
                    'access_level': True  # Boolean instead of string
                },
                'should_succeed': True,  # Should be converted to string
                'expected_access_level': 'True'
            },
            {
                'name': 'list_region',
                'bucket_name': 'list-region-bucket',
                'response': {
                    'region': ['us-east-1', 'us-west-2'],  # List instead of string
                    'access_level': 'read-write'
                },
                'should_succeed': True,  # Should be converted to string
                'expected_region': "['us-east-1', 'us-west-2']"
            },
            {
                'name': 'dict_created_date',
                'bucket_name': 'dict-date-bucket',
                'response': {
                    'region': 'us-east-1',
                    'access_level': 'read-write',
                    'created_date': {'year': 2024, 'month': 1, 'day': 1}  # Dict instead of string
                },
                'should_succeed': True,  # Should be converted to string
                'expected_created_date': "{'year': 2024, 'month': 1, 'day': 1}"
            }
        ]

        for scenario in unexpected_type_scenarios:
            if scenario['should_succeed']:
                result = backend._transform_bucket(scenario['bucket_name'], scenario['response'])

                assert isinstance(result, Bucket_Info)
                assert result.name == scenario['bucket_name']

                if 'expected_region' in scenario:
                    assert result.region == scenario['expected_region']
                else:
                    assert result.region == str(scenario['response']['region'])

                if 'expected_access_level' in scenario:
                    assert result.access_level == scenario['expected_access_level']
                else:
                    assert result.access_level == str(scenario['response']['access_level'])

                if 'expected_created_date' in scenario:
                    assert result.created_date == scenario['expected_created_date']
                elif 'created_date' in scenario['response']:
                    assert result.created_date == str(scenario['response']['created_date'])
            else:
                with pytest.raises(BackendError):
                    backend._transform_bucket(scenario['bucket_name'], scenario['response'])

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_ensures_bucket_info_object_correctness(self, mock_quilt3):
        """Test _transform_bucket() ensures Bucket_Info objects are created correctly with all required fields."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test comprehensive bucket response
        comprehensive_response = {
            'region': 'eu-central-1',
            'access_level': 'full-control',
            'created_date': '2024-06-15T14:30:45.123456Z',
            'extra_field_1': 'ignored',
            'extra_field_2': {'nested': 'ignored'},
            'extra_field_3': ['list', 'ignored']
        }

        result = backend._transform_bucket("comprehensive-bucket", comprehensive_response)

        # Verify Bucket_Info object structure and correctness
        assert isinstance(result, Bucket_Info)

        # Verify all required fields are present and correct
        assert hasattr(result, 'name')
        assert hasattr(result, 'region')
        assert hasattr(result, 'access_level')
        assert hasattr(result, 'created_date')

        assert result.name == "comprehensive-bucket"
        assert result.region == "eu-central-1"
        assert result.access_level == "full-control"
        assert result.created_date == "2024-06-15T14:30:45.123456Z"

        # Verify it's a proper dataclass
        from dataclasses import is_dataclass, fields, asdict
        assert is_dataclass(result)

        # Verify dataclass fields match expected structure
        field_names = {field.name for field in fields(result)}
        expected_fields = {'name', 'region', 'access_level', 'created_date'}
        assert field_names == expected_fields

        # Verify dataclass can be serialized
        result_dict = asdict(result)
        assert isinstance(result_dict, dict)
        assert len(result_dict) == 4  # Only the 4 expected fields
        assert result_dict['name'] == "comprehensive-bucket"
        assert result_dict['region'] == "eu-central-1"
        assert result_dict['access_level'] == "full-control"
        assert result_dict['created_date'] == "2024-06-15T14:30:45.123456Z"

        # Verify no extra fields from quilt3 response are included
        for key in comprehensive_response:
            if key not in expected_fields:
                assert key not in result_dict

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_method_isolation_and_direct_testing(self, mock_quilt3):
        """Test _transform_bucket() method directly in isolation without other dependencies."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test direct method call with various inputs
        test_cases = [
            {
                'name': 'standard_case',
                'bucket_name': 'standard-bucket',
                'bucket_data': {
                    'region': 'us-east-1',
                    'access_level': 'read-write',
                    'created_date': '2024-01-01T00:00:00Z'
                }
            },
            {
                'name': 'minimal_case',
                'bucket_name': 'minimal-bucket',
                'bucket_data': {
                    'region': 'us-west-2',
                    'access_level': 'read-only'
                }
            },
            {
                'name': 'complex_case',
                'bucket_name': 'complex-bucket-name-with-dashes-and-numbers-123',
                'bucket_data': {
                    'region': 'ap-southeast-1',
                    'access_level': 'admin',
                    'created_date': '2024-12-31T23:59:59.999999Z'
                }
            }
        ]

        for case in test_cases:
            # Call _transform_bucket directly
            result = backend._transform_bucket(case['bucket_name'], case['bucket_data'])

            # Verify direct method call produces correct Bucket_Info object
            assert isinstance(result, Bucket_Info)
            assert result.name == case['bucket_name']
            assert result.region == case['bucket_data']['region']
            assert result.access_level == case['bucket_data']['access_level']

            if 'created_date' in case['bucket_data']:
                assert result.created_date == case['bucket_data']['created_date']
            else:
                assert result.created_date is None

            # Verify the method is truly isolated (no side effects)
            # Call it again with the same inputs
            result2 = backend._transform_bucket(case['bucket_name'], case['bucket_data'])
            assert result.name == result2.name
            assert result.region == result2.region
            assert result.access_level == result2.access_level
            assert result.created_date == result2.created_date

        # Include extra fields that should be ignored
        bucket_data = {
            'region': 'us-east-1',
            'access_level': 'read-write',
            'created_date': '2024-01-01T00:00:00Z',
            'extra_field_1': 'should_be_ignored',
            'extra_field_2': 12345,
            'nested_extra': {'key': 'value'},
            'list_extra': [1, 2, 3]
        }

        result = backend._transform_bucket("extra-fields-bucket", bucket_data)

        # Should only include the expected fields
        assert result.name == "extra-fields-bucket"
        assert result.region == "us-east-1"
        assert result.access_level == "read-write"
        assert result.created_date == "2024-01-01T00:00:00Z"

        # Verify it's a proper Bucket_Info object
        assert isinstance(result, Bucket_Info)

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_preserves_field_types(self, mock_quilt3):
        """Test _transform_bucket() preserves correct data types for all fields."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        bucket_data = {
            'region': 'us-east-1',
            'access_level': 'read-write',
            'created_date': '2024-01-01T00:00:00Z'
        }

        result = backend._transform_bucket("type-test-bucket", bucket_data)

        # Verify all field types
        assert isinstance(result.name, str)
        assert isinstance(result.region, str)
        assert isinstance(result.access_level, str)
        assert isinstance(result.created_date, str) or result.created_date is None

        # Verify specific values
        assert result.name == "type-test-bucket"
        assert result.region == "us-east-1"
        assert result.access_level == "read-write"
        assert result.created_date == "2024-01-01T00:00:00Z"


class TestQuilt3BackendMockBucketTransformation:
    """Test transformation with mock quilt3 bucket objects with various configurations.
    
    This test class focuses specifically on testing the _transform_bucket() method
    with mock quilt3 bucket objects, testing transformation logic with different
    configurations, edge cases, and error handling scenarios.
    """

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_with_complete_mock_configuration(self, mock_quilt3):
        """Test _transform_bucket() with complete mock quilt3 bucket configuration."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Create comprehensive mock bucket configuration
        bucket_name = "comprehensive-test-bucket"
        bucket_data = {
            'region': 'us-west-2',
            'access_level': 'read-write',
            'created_date': '2024-01-15T10:30:45Z',
            'owner': 'test-user',
            'versioning': 'enabled',
            'encryption': 'AES256',
            'tags': {'Environment': 'test', 'Project': 'quilt-mcp'}
        }

        # Execute transformation
        result = backend._transform_bucket(bucket_name, bucket_data)

        # Verify complete transformation
        assert isinstance(result, Bucket_Info)
        assert result.name == "comprehensive-test-bucket"
        assert result.region == "us-west-2"
        assert result.access_level == "read-write"
        assert result.created_date == "2024-01-15T10:30:45Z"

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_with_minimal_mock_configuration(self, mock_quilt3):
        """Test _transform_bucket() with minimal mock quilt3 bucket configuration."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Create minimal mock bucket configuration (only required fields)
        bucket_name = "minimal-test-bucket"
        bucket_data = {
            'region': 'us-east-1',
            'access_level': 'read-only'
            # created_date is optional and missing
        }

        # Execute transformation
        result = backend._transform_bucket(bucket_name, bucket_data)

        # Verify minimal transformation handles defaults correctly
        assert isinstance(result, Bucket_Info)
        assert result.name == "minimal-test-bucket"
        assert result.region == "us-east-1"
        assert result.access_level == "read-only"
        assert result.created_date is None  # Should default to None for missing field

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_with_various_region_configurations(self, mock_quilt3):
        """Test _transform_bucket() with various AWS region configurations."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test different AWS regions
        region_configurations = [
            'us-east-1',      # US East (N. Virginia)
            'us-west-2',      # US West (Oregon)
            'eu-west-1',      # Europe (Ireland)
            'ap-southeast-1', # Asia Pacific (Singapore)
            'ca-central-1',   # Canada (Central)
            'sa-east-1',      # South America (São Paulo)
            'af-south-1',     # Africa (Cape Town)
            'me-south-1',     # Middle East (Bahrain)
            'ap-east-1',      # Asia Pacific (Hong Kong)
            'eu-north-1',     # Europe (Stockholm)
        ]

        for region in region_configurations:
            bucket_name = f"test-bucket-{region.replace('-', '')}"
            bucket_data = {
                'region': region,
                'access_level': 'read-write',
                'created_date': '2024-01-01T12:00:00Z'
            }

            result = backend._transform_bucket(bucket_name, bucket_data)

            assert result.region == region, f"Failed for region: {region}"
            assert result.name == bucket_name
            assert result.access_level == "read-write"

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_with_various_access_level_configurations(self, mock_quilt3):
        """Test _transform_bucket() with various access level configurations."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test different access levels
        access_level_configurations = [
            'read-only',
            'read-write',
            'write-only',
            'admin',
            'full-control',
            'list-only',
            'public-read',
            'public-read-write',
            'authenticated-read',
            'bucket-owner-read',
            'bucket-owner-full-control',
        ]

        for access_level in access_level_configurations:
            bucket_name = f"test-bucket-{access_level.replace('-', '')}"
            bucket_data = {
                'region': 'us-east-1',
                'access_level': access_level,
                'created_date': '2024-01-01T12:00:00Z'
            }

            result = backend._transform_bucket(bucket_name, bucket_data)

            assert result.access_level == access_level, f"Failed for access level: {access_level}"
            assert result.name == bucket_name
            assert result.region == "us-east-1"

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_with_various_date_format_configurations(self, mock_quilt3):
        """Test _transform_bucket() with various created_date format configurations."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test different date formats
        date_format_configurations = [
            (None, None),  # None date
            ('', ''),      # Empty string date -> _normalize_datetime returns str('') = ''
            ('2024-01-01T12:00:00Z', '2024-01-01T12:00:00Z'),  # ISO format with Z
            ('2024-01-01T12:00:00', '2024-01-01T12:00:00'),    # ISO format without Z
            ('2024-01-01 12:00:00', '2024-01-01 12:00:00'),    # Space-separated format
            ('2024-01-01', '2024-01-01'),                      # Date only
            ('1640995200', '1640995200'),                      # Unix timestamp string
            ('custom_date_string', 'custom_date_string'),      # Custom string
            (1640995200, '1640995200'),                        # Numeric timestamp
            (datetime(2024, 1, 1, 12, 0, 0), '2024-01-01T12:00:00'),  # datetime object
        ]

        for input_date, expected_date in date_format_configurations:
            bucket_name = f"test-bucket-date"
            bucket_data = {
                'region': 'us-east-1',
                'access_level': 'read-write',
                'created_date': input_date
            }

            result = backend._transform_bucket(bucket_name, bucket_data)

            assert result.created_date == expected_date, f"Failed for input date: {input_date}"
            assert result.name == bucket_name

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_with_various_bucket_name_configurations(self, mock_quilt3):
        """Test _transform_bucket() with various bucket name configurations."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test different bucket name formats (following AWS S3 naming rules)
        bucket_name_configurations = [
            'simple-bucket',                    # Simple name with dash
            'bucket.with.dots',                 # Name with dots
            'bucket-with-multiple-dashes',      # Multiple dashes
            'bucket123',                        # Alphanumeric
            '123bucket',                        # Starting with number
            'a' * 63,                          # Maximum length (63 chars)
            'a',                               # Minimum length (1 char)
            'my-test-bucket-2024',             # Common pattern
            'data.backup.bucket',              # Dot notation
            'user-uploads-prod',               # Descriptive name
        ]

        for bucket_name in bucket_name_configurations:
            bucket_data = {
                'region': 'us-east-1',
                'access_level': 'read-write',
                'created_date': '2024-01-01T12:00:00Z'
            }

            result = backend._transform_bucket(bucket_name, bucket_data)

            assert result.name == bucket_name, f"Failed for bucket name: {bucket_name}"
            assert result.region == "us-east-1"
            assert result.access_level == "read-write"

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_with_partial_mock_configurations(self, mock_quilt3):
        """Test _transform_bucket() with partial mock configurations (some fields missing)."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test various partial configurations
        partial_configurations = [
            {
                'name': 'partial-bucket-1',
                'data': {'region': 'us-east-1'},  # Missing access_level and created_date
                'expected_access_level': '',  # Should default to empty string
                'expected_created_date': None
            },
            {
                'name': 'partial-bucket-2',
                'data': {'access_level': 'read-only'},  # Missing region and created_date
                'expected_region': '',  # Should default to empty string
                'expected_created_date': None
            },
            {
                'name': 'partial-bucket-3',
                'data': {'created_date': '2024-01-01T12:00:00Z'},  # Missing region and access_level
                'expected_region': '',
                'expected_access_level': ''
            },
            {
                'name': 'partial-bucket-4',
                'data': {},  # Empty data - all fields missing
                'expected_region': '',
                'expected_access_level': '',
                'expected_created_date': None
            }
        ]

        for config in partial_configurations:
            bucket_name = config['name']
            bucket_data = config['data']

            # Most of these should fail due to Bucket_Info validation (empty region/access_level)
            # Only test the ones that should succeed
            if bucket_data.get('region') and bucket_data.get('access_level'):
                result = backend._transform_bucket(bucket_name, bucket_data)
                assert result.name == bucket_name
                assert result.region == bucket_data['region']
                assert result.access_level == bucket_data['access_level']
            else:
                # Should fail due to domain validation
                with pytest.raises(BackendError) as exc_info:
                    backend._transform_bucket(bucket_name, bucket_data)
                
                error_message = str(exc_info.value).lower()
                assert "transformation failed" in error_message

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_with_edge_case_mock_configurations(self, mock_quilt3):
        """Test _transform_bucket() with edge case mock configurations."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test edge cases that should succeed
        edge_case_configurations = [
            {
                'name': 'edge-case-1',
                'data': {
                    'region': 'us-east-1',
                    'access_level': 'read-write',
                    'created_date': None,  # Explicit None
                    'extra_field': 'ignored'  # Extra fields should be ignored
                }
            },
            {
                'name': 'edge-case-2',
                'data': {
                    'region': 'eu-west-1',
                    'access_level': 'admin',
                    'created_date': '',  # Empty string
                    'nested': {'data': 'ignored'}  # Nested data should be ignored
                }
            },
            {
                'name': 'edge-case-3',
                'data': {
                    'region': 'ap-southeast-1',
                    'access_level': 'read-only',
                    'created_date': 0,  # Zero timestamp
                    'list_field': ['ignored', 'data']  # List data should be ignored
                }
            }
        ]

        for config in edge_case_configurations:
            bucket_name = config['name']
            bucket_data = config['data']

            result = backend._transform_bucket(bucket_name, bucket_data)

            assert result.name == bucket_name
            assert result.region == bucket_data['region']
            assert result.access_level == bucket_data['access_level']
            
            # Verify created_date handling
            expected_date = bucket_data['created_date']
            if expected_date is None:
                assert result.created_date is None
            elif expected_date == '':
                assert result.created_date == ''  # _normalize_datetime returns str('') = ''
            else:
                assert result.created_date == str(expected_date)

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_with_invalid_mock_configurations(self, mock_quilt3):
        """Test _transform_bucket() error handling with invalid mock configurations."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test configurations that should fail
        invalid_configurations = [
            {
                'name': None,  # None bucket name
                'data': {'region': 'us-east-1', 'access_level': 'read-write'},
                'expected_error': 'missing name'
            },
            {
                'name': '',  # Empty bucket name
                'data': {'region': 'us-east-1', 'access_level': 'read-write'},
                'expected_error': 'missing name'
            },
            {
                'name': 'valid-bucket',
                'data': None,  # None bucket data
                'expected_error': 'bucket_data is none'
            },
            {
                'name': 'invalid-region-bucket',
                'data': {'region': '', 'access_level': 'read-write'},  # Empty region
                'expected_error': 'region field cannot be empty'
            },
            {
                'name': 'invalid-access-bucket',
                'data': {'region': 'us-east-1', 'access_level': ''},  # Empty access level
                'expected_error': 'access_level field cannot be empty'
            },
            {
                'name': 'missing-region-bucket',
                'data': {'access_level': 'read-write'},  # Missing region
                'expected_error': 'region field cannot be empty'
            },
            {
                'name': 'missing-access-bucket',
                'data': {'region': 'us-east-1'},  # Missing access_level
                'expected_error': 'access_level field cannot be empty'
            }
        ]

        for config in invalid_configurations:
            bucket_name = config['name']
            bucket_data = config['data']
            expected_error = config['expected_error']

            with pytest.raises(BackendError) as exc_info:
                backend._transform_bucket(bucket_name, bucket_data)

            error_message = str(exc_info.value).lower()
            assert expected_error.lower() in error_message, \
                f"Expected error '{expected_error}' not found in: {error_message}"

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_with_mock_aws_response_format(self, mock_quilt3):
        """Test _transform_bucket() with mock configurations mimicking AWS API responses."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock AWS S3 API response format
        aws_response_format = {
            'Name': 'aws-response-bucket',  # AWS uses 'Name' key
            'Region': 'us-west-2',          # AWS uses 'Region' key
            'CreationDate': '2024-01-15T10:30:45.000Z',  # AWS datetime format
            'BucketPolicy': {
                'Version': '2012-10-17',
                'Statement': [
                    {
                        'Effect': 'Allow',
                        'Principal': '*',
                        'Action': 's3:GetObject',
                        'Resource': 'arn:aws:s3:::aws-response-bucket/*'
                    }
                ]
            },
            'Versioning': {'Status': 'Enabled'},
            'Encryption': {
                'Rules': [
                    {
                        'ApplyServerSideEncryptionByDefault': {
                            'SSEAlgorithm': 'AES256'
                        }
                    }
                ]
            },
            'Tags': [
                {'Key': 'Environment', 'Value': 'production'},
                {'Key': 'Owner', 'Value': 'data-team'}
            ]
        }

        # Transform AWS-style response to our expected format
        bucket_name = "aws-response-bucket"
        bucket_data = {
            'region': aws_response_format.get('Region', 'us-east-1'),
            'access_level': 'read-write',  # Derived from policy analysis
            'created_date': aws_response_format.get('CreationDate')
        }

        result = backend._transform_bucket(bucket_name, bucket_data)

        assert result.name == "aws-response-bucket"
        assert result.region == "us-west-2"
        assert result.access_level == "read-write"
        assert result.created_date == "2024-01-15T10:30:45.000Z"

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_with_mock_quilt3_response_format(self, mock_quilt3):
        """Test _transform_bucket() with mock configurations mimicking quilt3 library responses."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock quilt3 library response format
        quilt3_response_format = {
            'bucket_name': 'quilt3-response-bucket',
            'region': 'eu-central-1',
            'permissions': {
                'read': True,
                'write': True,
                'delete': False,
                'admin': False
            },
            'metadata': {
                'created': '2024-02-20T14:15:30Z',
                'owner': 'quilt-user',
                'description': 'Quilt3 managed bucket'
            },
            'configuration': {
                'versioning': True,
                'lifecycle_rules': [],
                'cors_rules': []
            }
        }

        # Transform quilt3-style response to our expected format
        bucket_name = quilt3_response_format['bucket_name']
        
        # Derive access level from permissions
        permissions = quilt3_response_format['permissions']
        if permissions.get('admin'):
            access_level = 'admin'
        elif permissions.get('write'):
            access_level = 'read-write'
        elif permissions.get('read'):
            access_level = 'read-only'
        else:
            access_level = 'no-access'

        bucket_data = {
            'region': quilt3_response_format['region'],
            'access_level': access_level,
            'created_date': quilt3_response_format['metadata']['created']
        }

        result = backend._transform_bucket(bucket_name, bucket_data)

        assert result.name == "quilt3-response-bucket"
        assert result.region == "eu-central-1"
        assert result.access_level == "read-write"
        assert result.created_date == "2024-02-20T14:15:30Z"

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_with_unicode_and_special_characters(self, mock_quilt3):
        """Test _transform_bucket() handles unicode and special characters in configurations."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test unicode and special characters (where valid for S3 bucket names)
        # Note: S3 bucket names have strict rules, so we test within those constraints
        unicode_configurations = [
            {
                'name': 'unicode-test-bucket',  # S3 names must be ASCII
                'data': {
                    'region': 'us-east-1',
                    'access_level': 'read-write',
                    'created_date': '2024-01-01T12:00:00Z',
                    'description': '测试存储桶',  # Unicode in metadata
                    'owner': 'пользователь',     # Cyrillic in metadata
                    'tags': {'名前': '値', 'ключ': 'значение'}  # Unicode in tags
                }
            },
            {
                'name': 'special-chars-bucket',
                'data': {
                    'region': 'eu-west-1',
                    'access_level': 'admin',
                    'created_date': '2024-01-01T12:00:00Z',
                    'metadata': {
                        'special': '!@#$%^&*()_+-=[]{}|;:,.<>?',
                        'quotes': '"single" and \'double\' quotes',
                        'newlines': 'line1\nline2\nline3'
                    }
                }
            }
        ]

        for config in unicode_configurations:
            bucket_name = config['name']
            bucket_data = config['data']

            result = backend._transform_bucket(bucket_name, bucket_data)

            assert result.name == bucket_name
            assert result.region == bucket_data['region']
            assert result.access_level == bucket_data['access_level']
            assert result.created_date == bucket_data['created_date']

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_error_context_preservation(self, mock_quilt3):
        """Test _transform_bucket() error handling and context preservation."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test validation errors (raised directly from _validate_bucket_fields)
        with pytest.raises(BackendError) as exc_info:
            backend._transform_bucket(None, {'region': 'us-east-1', 'access_level': 'read-write'})

        error = exc_info.value
        error_message = str(error)

        # Verify error message for validation errors
        assert "quilt3 backend bucket validation failed" in error_message.lower()
        assert "missing name" in error_message.lower()

        # Validation errors have empty context (raised directly from _validate_bucket_fields)
        assert hasattr(error, 'context')
        context = error.context
        assert context == {}  # Empty context for validation errors

        # Test general transformation errors (wrapped with context)
        # Mock Bucket_Info to fail during creation to trigger general error handling
        with patch('quilt_mcp.backends.quilt3_backend.Bucket_Info', side_effect=ValueError("Domain validation failed")):
            with pytest.raises(BackendError) as exc_info:
                backend._transform_bucket("test-bucket", {'region': 'us-east-1', 'access_level': 'read-write'})

            error = exc_info.value
            error_message = str(error)

            # Verify error message for general transformation errors
            assert "quilt3 backend bucket transformation failed" in error_message.lower()
            assert "domain validation failed" in error_message.lower()

            # General transformation errors have context
            assert hasattr(error, 'context')
            context = error.context
            assert 'bucket_name' in context
            assert 'bucket_data_keys' in context
            assert 'bucket_data_type' in context
            assert context['bucket_name'] == "test-bucket"
            assert context['bucket_data_type'] == "dict"

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_logging_behavior(self, mock_quilt3):
        """Test _transform_bucket() logging behavior during transformation."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        bucket_name = "logging-test-bucket"
        bucket_data = {
            'region': 'us-east-1',
            'access_level': 'read-write',
            'created_date': '2024-01-01T12:00:00Z'
        }

        # Capture log messages
        with patch('quilt_mcp.backends.quilt3_backend.logger') as mock_logger:
            result = backend._transform_bucket(bucket_name, bucket_data)

            # Verify debug logging
            mock_logger.debug.assert_any_call("Transforming bucket: logging-test-bucket")
            mock_logger.debug.assert_any_call("Successfully transformed bucket: logging-test-bucket in us-east-1")

            # Should have exactly 2 debug calls
            assert mock_logger.debug.call_count == 2

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_performance_with_large_mock_data(self, mock_quilt3):
        """Test _transform_bucket() performance with large mock data structures."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Create mock with very large metadata
        large_bucket_name = "performance-test-bucket"
        large_bucket_data = {
            'region': 'us-west-2',
            'access_level': 'read-write',
            'created_date': '2024-01-01T12:00:00Z',
            'large_metadata': {
                'description': 'A' * 100000,  # Very long description
                'tags': {f'tag{i}': f'value{i}' for i in range(10000)},  # Many tags
                'policies': ['policy' + str(i) for i in range(1000)],  # Many policies
                'large_nested': {
                    'level1': {
                        'level2': {
                            'level3': {
                                'data': 'X' * 50000  # Deep nesting with large data
                            }
                        }
                    }
                }
            }
        }

        # Should handle large data without issues
        result = backend._transform_bucket(large_bucket_name, large_bucket_data)

        assert result.name == "performance-test-bucket"
        assert result.region == "us-west-2"
        assert result.access_level == "read-write"
        assert result.created_date == "2024-01-01T12:00:00Z"

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_with_different_mock_data_types(self, mock_quilt3):
        """Test _transform_bucket() works with different types of mock data structures."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test with different data structure types
        data_type_configurations = [
            {
                'name': 'dict-data-bucket',
                'data': dict(region='us-east-1', access_level='read-write'),  # Standard dict
            },
            {
                'name': 'ordered-dict-bucket',
                'data': {'region': 'us-west-2', 'access_level': 'admin', 'created_date': '2024-01-01T12:00:00Z'},  # Dict with specific order
            },
            {
                'name': 'mixed-types-bucket',
                'data': {
                    'region': 'eu-west-1',
                    'access_level': 'read-only',
                    'created_date': 1640995200,  # Numeric timestamp
                    'numeric_field': 42,
                    'boolean_field': True,
                    'list_field': ['item1', 'item2'],
                    'nested_dict': {'key': 'value'}
                }
            }
        ]

        for config in data_type_configurations:
            bucket_name = config['name']
            bucket_data = config['data']

            result = backend._transform_bucket(bucket_name, bucket_data)

            assert isinstance(result, Bucket_Info)
            assert result.name == bucket_name
            assert result.region == bucket_data['region']
            assert result.access_level == bucket_data['access_level']

            # Verify created_date handling for different types
            if 'created_date' in bucket_data:
                expected_date = str(bucket_data['created_date']) if bucket_data['created_date'] is not None else None
                assert result.created_date == expected_date

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_helper_method_integration(self, mock_quilt3):
        """Test _transform_bucket() integration with helper methods."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Create mock that exercises all helper methods
        bucket_name = "helper-integration-bucket"
        bucket_data = {
            'region': '  us-east-1  ',  # String that needs normalization (whitespace)
            'access_level': '  read-write  ',  # String that needs normalization
            'created_date': datetime(2024, 1, 15, 10, 30, 45),  # Datetime that needs normalization
            'extra_field': 'ignored'  # Extra field that should be ignored
        }

        result = backend._transform_bucket(bucket_name, bucket_data)

        # Verify helper methods worked correctly
        assert result.name == "helper-integration-bucket"
        assert result.region == "  us-east-1  "  # _normalize_string_field doesn't trim whitespace, just converts to string
        assert result.access_level == "  read-write  "  # _normalize_string_field doesn't trim whitespace
        assert result.created_date == "2024-01-15T10:30:45"  # _normalize_datetime converted to ISO

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_comprehensive_mock_scenarios(self, mock_quilt3):
        """Test _transform_bucket() with comprehensive mock scenarios covering all edge cases."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Comprehensive test scenarios
        comprehensive_scenarios = [
            {
                'description': 'Production-like configuration',
                'name': 'prod-data-bucket',
                'data': {
                    'region': 'us-east-1',
                    'access_level': 'read-write',
                    'created_date': '2024-01-15T10:30:45.123Z',
                    'environment': 'production',
                    'team': 'data-engineering',
                    'cost_center': 'engineering-001'
                }
            },
            {
                'description': 'Development configuration',
                'name': 'dev-test-bucket',
                'data': {
                    'region': 'us-west-2',
                    'access_level': 'admin',
                    'created_date': None,
                    'temporary': True,
                    'auto_delete': '30d'
                }
            },
            {
                'description': 'Archive configuration',
                'name': 'archive-storage-bucket',
                'data': {
                    'region': 'us-west-1',
                    'access_level': 'read-only',
                    'created_date': '2020-01-01T00:00:00Z',
                    'storage_class': 'GLACIER',
                    'retention_policy': '7y'
                }
            },
            {
                'description': 'Public dataset configuration',
                'name': 'public-dataset-bucket',
                'data': {
                    'region': 'us-east-1',
                    'access_level': 'public-read',
                    'created_date': '2023-06-15T14:22:33Z',
                    'public': True,
                    'dataset_type': 'research'
                }
            }
        ]

        for scenario in comprehensive_scenarios:
            bucket_name = scenario['name']
            bucket_data = scenario['data']

            result = backend._transform_bucket(bucket_name, bucket_data)

            # Verify basic transformation
            assert isinstance(result, Bucket_Info)
            assert result.name == bucket_name
            assert result.region == bucket_data['region']
            assert result.access_level == bucket_data['access_level']
            
            # Verify created_date handling
            expected_date = bucket_data['created_date']
            if expected_date is None:
                assert result.created_date is None
            else:
                assert result.created_date == expected_date

            # Verify the transformation succeeded for this scenario
            print(f"✓ Scenario '{scenario['description']}' passed")

    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_mock_object_attribute_access_patterns(self, mock_quilt3):
        """Test _transform_bucket() handles various mock object attribute access patterns."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test with mock object that has dynamic attribute access
        class DynamicBucketData:
            def __init__(self, data):
                self._data = data

            def get(self, key, default=None):
                return self._data.get(key, default)

            def keys(self):
                return self._data.keys()

            def __getitem__(self, key):
                return self._data[key]

            def __contains__(self, key):
                return key in self._data

        dynamic_data = DynamicBucketData({
            'region': 'ap-southeast-1',
            'access_level': 'read-write',
            'created_date': '2024-01-01T12:00:00Z'
        })

        result = backend._transform_bucket("dynamic-bucket", dynamic_data)

        assert result.name == "dynamic-bucket"
        assert result.region == "ap-southeast-1"
        assert result.access_level == "read-write"
        assert result.created_date == "2024-01-01T12:00:00Z"

        # Test with standard dictionary
        standard_dict = {
            'region': 'ca-central-1',
            'access_level': 'admin',
            'created_date': '2024-02-01T12:00:00Z'
        }

        result = backend._transform_bucket("standard-bucket", standard_dict)

        assert result.name == "standard-bucket"
        assert result.region == "ca-central-1"
        assert result.access_level == "admin"
        assert result.created_date == "2024-02-01T12:00:00Z"



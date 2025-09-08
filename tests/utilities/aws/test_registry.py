"""BDD tests for AWS registry operations utilities.

These tests follow the Given/When/Then pattern and test behavior, not implementation.
All tests are written to fail initially (RED phase of TDD).
"""

from __future__ import annotations

from unittest.mock import Mock, patch
import pytest

from quilt_mcp.utilities.aws.registry import (
    get_registry_url,
    list_packages,
    get_package_metadata,
    validate_registry_access,
    RegistryError,
)


class TestRegistryURL:
    """Test registry URL generation and validation."""

    def test_given_registry_name_when_getting_registry_url_then_correct_url_returned(self):
        """Given registry name, When getting registry URL, Then correct URL returned."""
        # Given: A registry name
        registry_name = "test-registry"

        # When: Getting registry URL
        result = get_registry_url(registry_name)

        # Then: Correct S3 URL is returned
        assert result == f"s3://{registry_name}"

    def test_given_s3_url_registry_name_when_getting_registry_url_then_url_returned_unchanged(self):
        """Given S3 URL as registry name, When getting registry URL, Then URL returned unchanged."""
        # Given: A registry name that's already an S3 URL
        registry_name = "s3://test-registry"

        # When: Getting registry URL
        result = get_registry_url(registry_name)

        # Then: URL is returned unchanged
        assert result == registry_name

    def test_given_empty_registry_name_when_getting_registry_url_then_error_raised(self):
        """Given empty registry name, When getting registry URL, Then error raised."""
        # Given: An empty registry name
        registry_name = ""

        # When/Then: Getting registry URL raises error
        with pytest.raises(RegistryError) as exc_info:
            get_registry_url(registry_name)

        assert "empty" in str(exc_info.value).lower()


class TestPackageListing:
    """Test package listing with pagination support."""

    def test_given_valid_registry_when_listing_packages_then_package_list_retrieved(self):
        """Given valid registry, When listing packages, Then package list retrieved."""
        # Given: Valid S3 client and registry URL
        mock_s3_client = Mock()
        registry_url = "s3://test-registry"

        # Mock S3 response
        mock_s3_client.list_objects_v2.return_value = {
            'Contents': [
                {'Key': 'package1/.quilt/packages/manifest_hash1'},
                {'Key': 'package2/.quilt/packages/manifest_hash2'},
                {'Key': 'some-file.txt'},  # Non-package file
            ],
            'IsTruncated': False,
        }

        # When: Listing packages
        result = list_packages(mock_s3_client, registry_url)

        # Then: Package list is retrieved correctly
        assert 'packages' in result
        assert len(result['packages']) == 2
        assert 'package1' in [pkg['name'] for pkg in result['packages']]
        assert 'package2' in [pkg['name'] for pkg in result['packages']]

    def test_given_large_registry_when_listing_packages_then_pagination_works_correctly(self):
        """Given large registry, When listing packages, Then pagination works correctly."""
        # Given: Large registry with pagination needed
        mock_s3_client = Mock()
        registry_url = "s3://test-registry"

        # Mock paginated S3 response
        mock_s3_client.list_objects_v2.return_value = {
            'Contents': [{'Key': f'package{i}/.quilt/packages/hash{i}'} for i in range(100)],
            'IsTruncated': True,
            'NextContinuationToken': 'next-token',
        }

        # When: Listing packages with pagination
        result = list_packages(mock_s3_client, registry_url, max_keys=100)

        # Then: Pagination information is included
        assert result['truncated'] is True
        assert result['next_token'] == 'next-token'
        assert len(result['packages']) == 100

    def test_given_empty_registry_when_listing_packages_then_empty_list_returned(self):
        """Given empty registry, When listing packages, Then empty list returned."""
        # Given: Empty registry
        mock_s3_client = Mock()
        registry_url = "s3://empty-registry"

        # Mock empty S3 response
        mock_s3_client.list_objects_v2.return_value = {'Contents': [], 'IsTruncated': False}

        # When: Listing packages
        result = list_packages(mock_s3_client, registry_url)

        # Then: Empty package list is returned
        assert result['packages'] == []
        assert result['truncated'] is False

    def test_given_inaccessible_registry_when_listing_packages_then_registry_error_raised(self):
        """Given inaccessible registry, When listing packages, Then RegistryError raised."""
        # Given: Inaccessible registry
        mock_s3_client = Mock()
        registry_url = "s3://inaccessible-registry"

        # Mock S3 access denied error
        from botocore.exceptions import ClientError

        mock_s3_client.list_objects_v2.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access Denied'}}, 'list_objects_v2'
        )

        # When/Then: Listing packages raises RegistryError
        with pytest.raises(RegistryError) as exc_info:
            list_packages(mock_s3_client, registry_url)

        assert "access" in str(exc_info.value).lower()


class TestPackageMetadata:
    """Test package metadata retrieval."""

    def test_given_package_name_when_getting_package_metadata_then_metadata_retrieved_correctly(self):
        """Given package name, When getting package metadata, Then metadata retrieved correctly."""
        # Given: Valid package name and S3 client
        mock_s3_client = Mock()
        registry_url = "s3://test-registry"
        package_name = "test/package"

        # Mock S3 response for package metadata
        mock_s3_client.list_objects_v2.return_value = {
            'Contents': [
                {'Key': 'test/package/.quilt/packages/latest', 'LastModified': '2024-01-01T00:00:00Z', 'Size': 100}
            ]
        }

        # When: Getting package metadata
        result = get_package_metadata(mock_s3_client, registry_url, package_name)

        # Then: Metadata is retrieved correctly
        assert result['package_name'] == package_name
        assert result['registry_url'] == registry_url
        assert 'latest_version' in result

    def test_given_nonexistent_package_when_getting_package_metadata_then_error_raised(self):
        """Given nonexistent package, When getting package metadata, Then error raised."""
        # Given: Nonexistent package
        mock_s3_client = Mock()
        registry_url = "s3://test-registry"
        package_name = "nonexistent/package"

        # Mock empty S3 response
        mock_s3_client.list_objects_v2.return_value = {'Contents': []}

        # When/Then: Getting package metadata raises error
        with pytest.raises(RegistryError) as exc_info:
            get_package_metadata(mock_s3_client, registry_url, package_name)

        assert "not found" in str(exc_info.value).lower()

    def test_given_invalid_package_name_when_getting_package_metadata_then_error_raised(self):
        """Given invalid package name, When getting package metadata, Then error raised."""
        # Given: Invalid package name
        mock_s3_client = Mock()
        registry_url = "s3://test-registry"
        package_name = ""

        # When/Then: Getting package metadata raises error
        with pytest.raises(RegistryError) as exc_info:
            get_package_metadata(mock_s3_client, registry_url, package_name)

        assert "invalid" in str(exc_info.value).lower()


class TestRegistryAccess:
    """Test registry access validation."""

    def test_given_valid_registry_when_validating_registry_access_then_validation_succeeds(self):
        """Given valid registry, When validating access, Then validation succeeds."""
        # Given: Valid registry and S3 client
        mock_s3_client = Mock()
        registry_url = "s3://accessible-registry"

        # Mock successful S3 operations
        mock_s3_client.head_bucket.return_value = {}
        mock_s3_client.list_objects_v2.return_value = {'Contents': []}

        # When: Validating registry access
        result = validate_registry_access(mock_s3_client, registry_url)

        # Then: Validation succeeds
        assert result['accessible'] is True
        assert result['can_list'] is True

    def test_given_invalid_registry_when_validating_registry_access_then_appropriate_error_raised(self):
        """Given invalid registry, When validating access, Then appropriate error raised."""
        # Given: Invalid registry
        mock_s3_client = Mock()
        registry_url = "s3://nonexistent-registry"

        # Mock S3 NoSuchBucket error
        from botocore.exceptions import ClientError

        mock_s3_client.head_bucket.side_effect = ClientError(
            {'Error': {'Code': 'NoSuchBucket', 'Message': 'The specified bucket does not exist'}}, 'head_bucket'
        )

        # When/Then: Validating registry access raises error
        with pytest.raises(RegistryError) as exc_info:
            validate_registry_access(mock_s3_client, registry_url)

        assert "not exist" in str(exc_info.value).lower()

    def test_given_read_only_registry_when_validating_registry_access_then_limited_access_reported(self):
        """Given read-only registry, When validating access, Then limited access reported."""
        # Given: Read-only registry
        mock_s3_client = Mock()
        registry_url = "s3://readonly-registry"

        # Mock read-only access (can list but not write)
        mock_s3_client.head_bucket.return_value = {}
        mock_s3_client.list_objects_v2.return_value = {'Contents': []}

        from botocore.exceptions import ClientError

        mock_s3_client.put_object.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access Denied'}}, 'put_object'
        )
        
        # Mock get_bucket_acl to also deny access (this is what the function actually checks)
        mock_s3_client.get_bucket_acl.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access Denied'}}, 'get_bucket_acl'
        )
        
        # Mock the alternative write permission test methods to also fail
        mock_s3_client.get_bucket_versioning.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access Denied'}}, 'get_bucket_versioning'
        )

        # When: Validating registry access
        result = validate_registry_access(mock_s3_client, registry_url)

        # Then: Limited access is reported
        assert result['accessible'] is True
        assert result['can_list'] is True
        assert result['can_write'] is False

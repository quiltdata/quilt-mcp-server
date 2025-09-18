"""Tests for QuiltService - Test-Driven Development Implementation."""

from __future__ import annotations

import pytest
from unittest.mock import Mock, patch

from quilt_mcp.services.quilt_service import QuiltService


class TestQuiltServiceAuthentication:
    """Test authentication and configuration methods."""

    def test_get_logged_in_url_when_not_authenticated(self):
        """Test get_logged_in_url returns None when not authenticated."""
        service = QuiltService()
        with patch('quilt3.logged_in', return_value=None):
            result = service.get_logged_in_url()
            assert result is None

    def test_get_logged_in_url_when_authenticated(self):
        """Test get_logged_in_url returns URL when authenticated."""
        service = QuiltService()
        # This test will fail initially - that's the RED phase
        with patch('quilt3.logged_in', return_value='https://example.quiltdata.com'):
            result = service.get_logged_in_url()
            assert result == 'https://example.quiltdata.com'

    def test_is_authenticated_when_not_logged_in(self):
        """Test is_authenticated returns False when not logged in."""
        service = QuiltService()
        with patch('quilt3.logged_in', return_value=None):
            result = service.is_authenticated()
            assert result is False

    def test_is_authenticated_when_logged_in(self):
        """Test is_authenticated returns True when logged in."""
        service = QuiltService()
        with patch('quilt3.logged_in', return_value='https://example.quiltdata.com'):
            result = service.is_authenticated()
            assert result is True

    def test_get_config_returns_none_when_no_config(self):
        """Test get_config returns None when no configuration available."""
        service = QuiltService()
        with patch('quilt3.config', return_value=None):
            result = service.get_config()
            assert result is None

    def test_get_config_returns_config_when_available(self):
        """Test get_config returns configuration when available."""
        service = QuiltService()
        expected_config = {
            'navigator_url': 'https://example.quiltdata.com',
            'registryUrl': 's3://example-bucket'
        }
        with patch('quilt3.config', return_value=expected_config):
            result = service.get_config()
            assert result == expected_config


class TestQuiltServicePackageOperations:
    """Test package operation methods."""

    def test_create_package_returns_package_instance(self):
        """Test create_package returns a Package instance."""
        service = QuiltService()
        mock_package = Mock()
        with patch('quilt3.Package', return_value=mock_package):
            result = service.create_package()
            assert result == mock_package

    def test_list_packages_returns_package_list(self):
        """Test list_packages returns iterator of package names."""
        service = QuiltService()
        expected_packages = ['user/package1', 'user/package2']
        with patch('quilt3.list_packages', return_value=iter(expected_packages)):
            result = list(service.list_packages('s3://test-bucket'))
            assert result == expected_packages

    def test_get_catalog_info_when_authenticated(self):
        """Test get_catalog_info returns comprehensive info when authenticated."""
        service = QuiltService()
        with patch('quilt3.logged_in', return_value='https://example.quiltdata.com'), \
             patch('quilt3.config', return_value={
                 'navigator_url': 'https://example.quiltdata.com',
                 'registryUrl': 's3://example-bucket'
             }):
            result = service.get_catalog_info()
            assert result['is_authenticated'] is True
            assert result['catalog_name'] == 'example.quiltdata.com'
            assert result['logged_in_url'] == 'https://example.quiltdata.com'
            assert result['navigator_url'] == 'https://example.quiltdata.com'
            assert result['registry_url'] == 's3://example-bucket'

    def test_set_config_calls_quilt3_config(self):
        """Test set_config calls quilt3.config with catalog URL."""
        service = QuiltService()
        with patch('quilt3.config') as mock_config:
            service.set_config('https://example.quiltdata.com')
            mock_config.assert_called_once_with('https://example.quiltdata.com')

    def test_browse_package_without_hash(self):
        """Test browse_package calls Package.browse without top_hash."""
        service = QuiltService()
        mock_package = Mock()
        with patch('quilt3.Package.browse', return_value=mock_package) as mock_browse:
            result = service.browse_package('user/package', 's3://test-bucket')
            assert result == mock_package
            mock_browse.assert_called_once_with('user/package', registry='s3://test-bucket')

    def test_browse_package_with_hash(self):
        """Test browse_package calls Package.browse with top_hash."""
        service = QuiltService()
        mock_package = Mock()
        with patch('quilt3.Package.browse', return_value=mock_package) as mock_browse:
            result = service.browse_package('user/package', 's3://test-bucket', top_hash='abc123')
            assert result == mock_package
            mock_browse.assert_called_once_with('user/package', registry='s3://test-bucket', top_hash='abc123')

    def test_create_bucket_returns_bucket_instance(self):
        """Test create_bucket returns a Bucket instance."""
        service = QuiltService()
        mock_bucket = Mock()
        with patch('quilt3.Bucket', return_value=mock_bucket) as mock_bucket_class:
            result = service.create_bucket('s3://test-bucket')
            assert result == mock_bucket
            mock_bucket_class.assert_called_once_with('s3://test-bucket')

    def test_get_search_api_returns_search_module(self):
        """Test get_search_api returns the search_util.search_api module."""
        service = QuiltService()
        mock_search_api = Mock()
        with patch('quilt3.search_util.search_api', mock_search_api):
            result = service.get_search_api()
            assert result == mock_search_api

    def test_has_session_support_when_available(self):
        """Test has_session_support returns True when session is available."""
        service = QuiltService()
        mock_session = Mock()
        mock_session.get_session = Mock()
        with patch('quilt3.session', mock_session):
            result = service.has_session_support()
            assert result is True

    def test_has_session_support_when_not_available(self):
        """Test has_session_support returns False when session is not available."""
        service = QuiltService()
        with patch('quilt3.session', None):
            result = service.has_session_support()
            assert result is False

    def test_get_session_when_available(self):
        """Test get_session returns session object when available."""
        service = QuiltService()
        mock_session_obj = Mock()
        mock_session = Mock()
        mock_session.get_session = Mock(return_value=mock_session_obj)
        with patch('quilt3.session', mock_session):
            result = service.get_session()
            assert result == mock_session_obj
            mock_session.get_session.assert_called_once()

    def test_get_registry_url_when_available(self):
        """Test get_registry_url returns URL when available."""
        service = QuiltService()
        mock_session = Mock()
        mock_session.get_registry_url = Mock(return_value='s3://test-registry')
        with patch('quilt3.session', mock_session):
            result = service.get_registry_url()
            assert result == 's3://test-registry'

    def test_get_registry_url_when_not_available(self):
        """Test get_registry_url returns None when not available."""
        service = QuiltService()
        mock_session = Mock()
        del mock_session.get_registry_url  # Simulate missing method
        with patch('quilt3.session', mock_session):
            result = service.get_registry_url()
            assert result is None
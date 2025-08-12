from unittest.mock import Mock, patch

from quilt_mcp import (
    auth_status,
    catalog_info,
    catalog_name,
    catalog_url,
    catalog_uri,
    package_browse,
    package_contents_search,
    packages_list,
    packages_search,
)


class TestQuiltTools:
    """Test suite for Quilt MCP tools."""

    def test_auth_status_authenticated(self):
        """Test auth_status when user is authenticated."""
        with patch('quilt3.logged_in', return_value='https://open.quiltdata.com'):
            result = auth_status()

            assert result['status'] == 'authenticated'
            assert result['catalog_url'] == 'https://open.quiltdata.com'
            assert result['search_available'] is True

    def test_auth_status_not_authenticated(self):
        """Test auth_status when user is not authenticated."""
        with patch('quilt3.logged_in', return_value=None):
            result = auth_status()

            assert result['status'] == 'not_authenticated'
            assert result['search_available'] is False
            assert 'setup_instructions' in result

    def test_auth_status_error(self):
        """Test auth_status when an error occurs."""
        with patch('quilt3.logged_in', side_effect=Exception('Test error')):
            result = auth_status()

            assert result['status'] == 'error'
            assert 'Failed to check authentication' in result['error']
            assert 'setup_instructions' in result

    def test_packages_list_success(self):
        """Test packages_list with successful response."""
        mock_packages = ['user/package1', 'user/package2']
        mock_package = Mock()
        mock_package.meta = {'description': 'Test package'}

        with patch('quilt3.list_packages', return_value=mock_packages), \
             patch('quilt3.Package.browse', return_value=mock_package):

            result = packages_list()

            # Result now has packages structure
            assert isinstance(result, dict)
            assert 'packages' in result

            packages = result['packages']
            assert len(packages) == 2
            assert packages[0] == 'user/package1'
            assert packages[1] == 'user/package2'

    def test_packages_list_with_prefix(self):
        """Test packages_list with prefix filter."""
        mock_packages = ['user/package1', 'user/package2', 'other/package3']
        mock_package = Mock()
        mock_package.meta = {}

        with patch('quilt3.list_packages', return_value=mock_packages), \
             patch('quilt3.Package.browse', return_value=mock_package):

            result = packages_list(prefix='user/')

            # Result now has packages structure
            assert isinstance(result, dict)
            assert 'packages' in result

            packages = result['packages']
            assert len(packages) == 2
            assert all(pkg.startswith('user/') for pkg in packages)


    def test_packages_list_error(self):
        """Test packages_list with error."""
        with patch('quilt3.list_packages', side_effect=Exception('Test error')):
            try:
                result = packages_list()
                assert False, "Expected exception"
            except Exception as e:
                assert 'Test error' in str(e)

    def test_package_browse_success(self):
        """Test package_browse with successful response."""
        mock_package = Mock()
        mock_package.keys.return_value = ['file1.txt', 'file2.csv']

        with patch('quilt3.Package.browse', return_value=mock_package):
            result = package_browse('user/test-package')

            assert isinstance(result, dict)
            assert 'contents' in result
            assert len(result['contents']) == 2
            assert 'file1.txt' in result['contents']
            assert 'file2.csv' in result['contents']

    def test_package_browse_error(self):
        """Test package_browse with error."""
        with patch('quilt3.Package.browse', side_effect=Exception('Package not found')):
            try:
                result = package_browse('user/nonexistent')
                assert False, "Expected exception"
            except Exception as e:
                assert 'Package not found' in str(e)

    def test_package_contents_search_success(self):
        """Test package_contents_search with matches."""
        mock_package = Mock()
        mock_package.keys.return_value = ['test_file.txt', 'data.csv']

        with patch('quilt3.Package.browse', return_value=mock_package):
            result = package_contents_search('user/test-package', 'test')

            assert isinstance(result, dict)
            assert 'matches' in result
            assert 'count' in result
            assert len(result['matches']) == 1  # Only 'test_file.txt' matches 'test'
            assert 'test_file.txt' in result['matches']

    def test_packages_search_authentication_error(self):
        """Test packages_search with authentication error."""
        with patch('quilt3.search', side_effect=Exception('401 Unauthorized')):
            try:
                result = packages_search('test query')
                assert False, "Expected exception"
            except Exception as e:
                assert '401 Unauthorized' in str(e)

    def test_packages_search_config_error(self):
        """Test packages_search with configuration error."""
        with patch('quilt3.search', side_effect=Exception('Invalid URL - No scheme supplied')):
            try:
                result = packages_search('test query')
                assert False, "Expected exception"
            except Exception as e:
                assert 'Invalid URL - No scheme supplied' in str(e)

    def test_packages_search_success(self):
        """Test packages_search with successful results."""
        mock_results = [
            {'name': 'user/package1', 'description': 'Test package 1'},
            {'name': 'user/package2', 'description': 'Test package 2'}
        ]

        with patch('quilt3.config'), \
             patch('quilt3.search', return_value=mock_results):

            result = packages_search('test query')

            assert isinstance(result, dict)
            assert 'results' in result
            assert len(result['results']) == 2
            assert result['results'][0]['name'] == 'user/package1'
            assert result['results'][1]['name'] == 'user/package2'

    def test_catalog_info_success(self):
        """Test catalog_info with successful response."""
        with patch('quilt3.logged_in', return_value='https://test.catalog.com'), \
             patch('quilt3.config', return_value={'navigator_url': 'https://test.catalog.com', 'registryUrl': 'https://registry.test.com'}):

            result = catalog_info()

            assert isinstance(result, dict)
            assert result['status'] == 'success'
            assert result['catalog_name'] == 'test.catalog.com'
            assert result['is_authenticated'] is True
            assert 'navigator_url' in result
            assert 'registry_url' in result

    def test_catalog_info_not_authenticated(self):
        """Test catalog_info when not authenticated."""
        with patch('quilt3.logged_in', return_value=None), \
             patch('quilt3.config', return_value={'navigator_url': 'https://test.catalog.com'}):

            result = catalog_info()

            assert isinstance(result, dict)
            assert result['status'] == 'success'
            assert result['catalog_name'] == 'test.catalog.com'
            assert result['is_authenticated'] is False

    def test_catalog_name_from_authentication(self):
        """Test catalog_name when detected from authentication."""
        with patch('quilt3.logged_in', return_value='https://test.catalog.com'), \
             patch('quilt3.config', return_value={}):

            result = catalog_name()

            assert isinstance(result, dict)
            assert result['status'] == 'success'
            assert result['catalog_name'] == 'test.catalog.com'
            assert result['detection_method'] == 'authentication'
            assert result['is_authenticated'] is True

    def test_catalog_name_from_config(self):
        """Test catalog_name when detected from config."""
        with patch('quilt3.logged_in', return_value=None), \
             patch('quilt3.config', return_value={'navigator_url': 'https://config.catalog.com'}):

            result = catalog_name()

            assert isinstance(result, dict)
            assert result['status'] == 'success'
            assert result['catalog_name'] == 'config.catalog.com'
            assert result['detection_method'] == 'navigator_config'
            assert result['is_authenticated'] is False

    def test_catalog_url_package_view(self):
        """Test catalog_url for package view."""
        with patch('quilt3.logged_in', return_value='https://test.catalog.com'):
            result = catalog_url(
                registry='s3://test-bucket',
                package_name='user/package',
                path='data.csv'
            )

            assert isinstance(result, dict)
            assert result['status'] == 'success'
            assert result['view_type'] == 'package'
            assert result['catalog_url'] == 'https://test.catalog.com/b/test-bucket/packages/user/package/tree/latest/data.csv'
            assert result['bucket'] == 'test-bucket'

    def test_catalog_url_bucket_view(self):
        """Test catalog_url for bucket view."""
        with patch('quilt3.logged_in', return_value='https://test.catalog.com'):
            result = catalog_url(
                registry='s3://test-bucket',
                path='data/file.csv'
            )

            assert isinstance(result, dict)
            assert result['status'] == 'success'
            assert result['view_type'] == 'bucket'
            assert result['catalog_url'] == 'https://test.catalog.com/b/test-bucket/tree/data/file.csv'
            assert result['bucket'] == 'test-bucket'

    def test_catalog_uri_basic(self):
        """Test catalog_uri with basic parameters."""
        with patch('quilt3.logged_in', return_value='https://test.catalog.com'):
            result = catalog_uri(
                registry='s3://test-bucket',
                package_name='user/package',
                path='data.csv'
            )

            assert isinstance(result, dict)
            assert result['status'] == 'success'
            assert result['quilt_plus_uri'] == 'quilt+s3://test-bucket#package=user/package&path=data.csv&catalog=test.catalog.com'
            assert result['bucket'] == 'test-bucket'

    def test_catalog_uri_with_version(self):
        """Test catalog_uri with version hash."""
        with patch('quilt3.logged_in', return_value='https://test.catalog.com'):
            result = catalog_uri(
                registry='s3://test-bucket',
                package_name='user/package',
                top_hash='abc123def456'
            )

            assert isinstance(result, dict)
            assert result['status'] == 'success'
            assert 'package=user/package@abc123def456' in result['quilt_plus_uri']
            assert result['top_hash'] == 'abc123def456'

    def test_catalog_uri_with_tag(self):
        """Test catalog_uri with version tag."""
        with patch('quilt3.logged_in', return_value='https://test.catalog.com'):
            result = catalog_uri(
                registry='s3://test-bucket',
                package_name='user/package',
                tag='v1.0'
            )

            assert isinstance(result, dict)
            assert result['status'] == 'success'
            assert 'package=user/package:v1.0' in result['quilt_plus_uri']
            assert result['tag'] == 'v1.0'

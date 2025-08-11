import pytest
import json
from unittest.mock import Mock, patch, MagicMock

from quilt import (
    auth_check,
    packages_list,
    package_browse,
    package_contents_search,
    packages_search
)

class TestQuiltTools:
    """Test suite for Quilt MCP tools."""
    
    def test_auth_check_authenticated(self):
        """Test auth_check when user is authenticated."""
        with patch('quilt3.logged_in', return_value='https://open.quiltdata.com'):
            result = auth_check()
            
            assert result['status'] == 'authenticated'
            assert result['catalog_url'] == 'https://open.quiltdata.com'
            assert result['search_available'] is True

    def test_auth_check_not_authenticated(self):
        """Test auth_check when user is not authenticated."""
        with patch('quilt3.logged_in', return_value=None):
            result = auth_check()
            
            assert result['status'] == 'not_authenticated'
            assert result['search_available'] is False
            assert 'setup_instructions' in result

    def test_auth_check_error(self):
        """Test auth_check when an error occurs."""
        with patch('quilt3.logged_in', side_effect=Exception('Test error')):
            result = auth_check()
            
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
            
            # Result now has pagination structure
            assert len(result) == 1
            assert 'packages' in result[0]
            assert 'pagination' in result[0]
            
            packages = result[0]['packages']
            assert len(packages) == 2
            assert packages[0]['name'] == 'user/package1'
            assert packages[0]['registry'] == 's3://quilt-example'
            assert packages[0]['metadata'] == {'description': 'Test package'}
            
            # Check pagination info
            pagination = result[0]['pagination']
            assert pagination['total'] == 2
            assert pagination['offset'] == 0
            assert pagination['limit'] == 12
            assert pagination['returned'] == 2
            assert pagination['has_more'] is False

    def test_packages_list_with_prefix(self):
        """Test packages_list with prefix filter."""
        mock_packages = ['user/package1', 'user/package2', 'other/package3']
        mock_package = Mock()
        mock_package.meta = {}
        
        with patch('quilt3.list_packages', return_value=mock_packages), \
             patch('quilt3.Package.browse', return_value=mock_package):
            
            result = packages_list(prefix='user/')
            
            # Result now has pagination structure
            assert len(result) == 1
            assert 'packages' in result[0]
            assert 'pagination' in result[0]
            
            packages = result[0]['packages']
            assert len(packages) == 2
            assert all(pkg['name'].startswith('user/') for pkg in packages)
            
            # Check pagination info
            pagination = result[0]['pagination']
            assert pagination['total'] == 2
            assert pagination['returned'] == 2

    def test_packages_list_error(self):
        """Test packages_list with error."""
        with patch('quilt3.list_packages', side_effect=Exception('Test error')):
            result = packages_list()
            
            assert len(result) == 1
            assert 'error' in result[0]
            assert 'Failed to list packages' in result[0]['error']

    def test_package_browse_success(self):
        """Test package_browse with successful response."""
        mock_package = Mock()
        mock_package.meta = {'description': 'Test package'}
        mock_package.top_hash = 'abc123'
        mock_package.__iter__ = Mock(return_value=iter(['file1.txt', 'file2.csv']))
        
        mock_entry = Mock()
        mock_entry.size = 1024
        mock_entry.hash = 'def456'
        mock_entry.meta = {}
        mock_package.__getitem__ = Mock(return_value=mock_entry)
        
        with patch('quilt3.Package.browse', return_value=mock_package):
            result = package_browse('user/test-package')
            
            assert result['name'] == 'user/test-package'
            assert result['hash'] == 'abc123'
            assert result['metadata'] == {'description': 'Test package'}
            assert len(result['files']) == 2

    def test_package_browse_error(self):
        """Test package_browse with error."""
        with patch('quilt3.Package.browse', side_effect=Exception('Package not found')):
            result = package_browse('user/nonexistent')
            
            assert 'error' in result
            assert 'Failed to browse package' in result['error']

    def test_package_contents_search_success(self):
        """Test package_contents_search with matches."""
        mock_package = Mock()
        mock_package.meta = {'description': 'Contains test data'}
        mock_package.__iter__ = Mock(return_value=iter(['test_file.txt', 'data.csv']))
        
        mock_entry = Mock()
        mock_entry.size = 512
        mock_entry.hash = 'xyz789'
        mock_entry.meta = {'type': 'test'}
        mock_package.__getitem__ = Mock(return_value=mock_entry)
        
        with patch('quilt3.Package.browse', return_value=mock_package):
            result = package_contents_search('user/test-package', 'test')
            
            # Should find matches in package metadata, file path, and file metadata
            assert len(result) >= 2
            assert any(match['match_type'] == 'metadata' for match in result)
            assert any(match['match_type'] == 'path' for match in result)

    def test_packages_search_authentication_error(self):
        """Test packages_search with authentication error."""
        with patch('quilt3.search', side_effect=Exception('401 Unauthorized')):
            result = packages_search('test query')
            
            assert len(result) == 1
            assert result[0]['error'] == 'Search failed: Authentication required'
            assert 'quilt3 login' in result[0]['solution']

    def test_packages_search_config_error(self):
        """Test packages_search with configuration error."""
        with patch('quilt3.search', side_effect=Exception('Invalid URL - No scheme supplied')):
            result = packages_search('test query')
            
            assert len(result) == 1
            assert result[0]['error'] == 'Search failed: Quilt catalog not configured'
            assert 'quilt3 config' in result[0]['solution']

    def test_packages_search_success(self):
        """Test packages_search with successful results."""
        mock_results = [
            {'name': 'user/package1', 'description': 'Test package 1'},
            {'name': 'user/package2', 'description': 'Test package 2'}
        ]
        
        with patch('quilt3.config'), \
             patch('quilt3.search', return_value=mock_results):
            
            result = packages_search('test query')
            
            assert len(result) == 2
            assert result[0]['name'] == 'user/package1'
            assert result[1]['name'] == 'user/package2'
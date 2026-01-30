"""End-to-end integration tests for complete QuiltOps workflows."""

import pytest
from unittest.mock import patch, MagicMock

from quilt_mcp.ops.factory import QuiltOpsFactory
from quilt_mcp.domain.package_info import Package_Info
from quilt_mcp.domain.content_info import Content_Info
from quilt_mcp.domain.bucket_info import Bucket_Info


@pytest.mark.integration
class TestEndToEndWorkflows:
    """Integration tests for complete package search and browsing workflows."""

    def test_complete_package_search_workflow(self):
        """Test complete workflow: search packages -> get package info -> browse content."""
        mock_session = MagicMock()
        
        with patch('quilt3.logged_in', return_value=True):
            with patch('quilt3.session.get_session', return_value=mock_session):
                with patch('quilt3.session.get_registry_url', return_value='s3://test-registry'):
                    quilt_ops = QuiltOpsFactory.create()
                    
                    # Mock search results
                    mock_package = MagicMock()
                    mock_package.name = "test/package"
                    mock_package.description = "Test package"
                    mock_package.tags = ["test"]
                    mock_package.modified = MagicMock()
                    mock_package.modified.isoformat.return_value = "2024-01-01T00:00:00Z"
                    mock_package.registry = "s3://test-registry"
                    mock_package.bucket = "test-bucket"
                    mock_package.top_hash = "abc123"
                    
                    with patch('quilt3.search', return_value=[mock_package]):
                        # Step 1: Search for packages
                        packages = quilt_ops.search_packages("test", "s3://test-registry")
                        assert len(packages) == 1
                        assert isinstance(packages[0], Package_Info)
                        assert packages[0].name == "test/package"
                        
                        # Step 2: Get detailed package info
                        with patch('quilt3.Package.browse', return_value=mock_package):
                            package_info = quilt_ops.get_package_info("test/package", "s3://test-registry")
                            assert isinstance(package_info, Package_Info)
                            assert package_info.name == "test/package"
                            
                            # Step 3: Browse package content
                            mock_content = MagicMock()
                            mock_content.name = "data.csv"
                            mock_content.size = 1024
                            mock_content.is_dir = False
                            mock_content.modified = MagicMock()
                            mock_content.modified.isoformat.return_value = "2024-01-01T00:00:00Z"
                            
                            with patch.object(mock_package, '__iter__', return_value=iter([mock_content])):
                                content = quilt_ops.browse_content("test/package", "s3://test-registry")
                                assert len(content) == 1
                                assert isinstance(content[0], Content_Info)
                                assert content[0].path == "data.csv"
                                assert content[0].type == "file"

    def test_complete_bucket_and_content_workflow(self):
        """Test complete workflow: browse content -> get content URL."""
        mock_session = MagicMock()
        
        with patch('quilt3.logged_in', return_value=True):
            with patch('quilt3.session.get_session', return_value=mock_session):
                with patch('quilt3.session.get_registry_url', return_value='s3://test-registry'):
                    quilt_ops = QuiltOpsFactory.create()
                    
                    # Step 1: Browse content in a package
                    mock_package = MagicMock()
                    mock_content = MagicMock()
                    mock_content.name = "important-data.csv"
                    mock_content.size = 2048
                    mock_content.is_dir = False
                    mock_content.modified = MagicMock()
                    mock_content.modified.isoformat.return_value = "2024-01-01T00:00:00Z"
                    
                    with patch('quilt3.Package.browse', return_value=mock_package):
                        with patch.object(mock_package, '__iter__', return_value=iter([mock_content])):
                            content = quilt_ops.browse_content("test/package", "s3://test-registry")
                            assert len(content) == 1
                            assert content[0].path == "important-data.csv"
                            
                            # Step 2: Get download URL for specific content
                            test_url = "https://s3.amazonaws.com/test-bucket/important-data.csv"
                            with patch.object(mock_package, 'get_url', return_value=test_url):
                                url = quilt_ops.get_content_url("test/package", "s3://test-registry", "important-data.csv")
                                assert url == test_url

    def test_error_recovery_in_workflow(self):
        """Test that workflows handle errors gracefully and provide useful information."""
        mock_session = MagicMock()
        
        with patch('quilt3.logged_in', return_value=True):
            with patch('quilt3.session.get_session', return_value=mock_session):
                with patch('quilt3.session.get_registry_url', return_value='s3://test-registry'):
                    quilt_ops = QuiltOpsFactory.create()
                    
                    # Test search failure with meaningful error
                    with patch('quilt3.search', side_effect=Exception("Network timeout")):
                        try:
                            quilt_ops.search_packages("test", "s3://test-registry")
                            assert False, "Should have raised BackendError"
                        except Exception as e:
                            assert "Quilt3 backend" in str(e)
                            assert "Network timeout" in str(e)
                    
                    # Test package info failure with context
                    with patch('quilt3.Package.browse', side_effect=Exception("Package not found")):
                        try:
                            quilt_ops.get_package_info("nonexistent/package", "s3://test-registry")
                            assert False, "Should have raised BackendError"
                        except Exception as e:
                            assert "Quilt3 backend" in str(e)
                            assert "Package not found" in str(e)

    def test_workflow_with_empty_results(self):
        """Test workflows handle empty results gracefully."""
        mock_session = MagicMock()
        
        with patch('quilt3.logged_in', return_value=True):
            with patch('quilt3.session.get_session', return_value=mock_session):
                with patch('quilt3.session.get_registry_url', return_value='s3://test-registry'):
                    quilt_ops = QuiltOpsFactory.create()
                    
                    # Test empty search results
                    with patch('quilt3.search', return_value=[]):
                        packages = quilt_ops.search_packages("nonexistent", "s3://test-registry")
                        assert len(packages) == 0
                        assert isinstance(packages, list)
                    
                    # Test empty content browsing
                    mock_package = MagicMock()
                    with patch('quilt3.Package.browse', return_value=mock_package):
                        with patch.object(mock_package, '__iter__', return_value=iter([])):
                            content = quilt_ops.browse_content("empty/package", "s3://test-registry")
                            assert len(content) == 0
                            assert isinstance(content, list)

    def test_workflow_data_consistency(self):
        """Test that data remains consistent throughout the workflow."""
        mock_session = MagicMock()
        
        with patch('quilt3.logged_in', return_value=True):
            with patch('quilt3.session.get_session', return_value=mock_session):
                with patch('quilt3.session.get_registry_url', return_value='s3://test-registry'):
                    quilt_ops = QuiltOpsFactory.create()
                    
                    # Create consistent mock data
                    package_name = "consistent/test-package"
                    registry = "s3://test-registry"
                    
                    mock_package = MagicMock()
                    mock_package.name = package_name
                    mock_package.description = "Consistent test package"
                    mock_package.tags = ["consistency", "test"]
                    mock_package.modified = MagicMock()
                    mock_package.modified.isoformat.return_value = "2024-01-01T12:00:00Z"
                    mock_package.registry = registry
                    mock_package.bucket = "test-bucket"
                    mock_package.top_hash = "consistent123"
                    
                    # Test search returns consistent data
                    with patch('quilt3.search', return_value=[mock_package]):
                        packages = quilt_ops.search_packages("consistent", registry)
                        found_package = packages[0]
                        
                        # Test get_package_info returns same data
                        with patch('quilt3.Package.browse', return_value=mock_package):
                            package_info = quilt_ops.get_package_info(package_name, registry)
                            
                            # Verify consistency
                            assert found_package.name == package_info.name
                            assert found_package.description == package_info.description
                            assert found_package.tags == package_info.tags
                            assert found_package.modified_date == package_info.modified_date
                            assert found_package.registry == package_info.registry
                            assert found_package.bucket == package_info.bucket
                            assert found_package.top_hash == package_info.top_hash

    def test_workflow_performance_characteristics(self):
        """Test that workflows complete in reasonable time and handle large datasets."""
        mock_session = MagicMock()
        
        with patch('quilt3.logged_in', return_value=True):
            with patch('quilt3.session.get_session', return_value=mock_session):
                with patch('quilt3.session.get_registry_url', return_value='s3://test-registry'):
                    quilt_ops = QuiltOpsFactory.create()
                    
                    # Test with large number of packages
                    large_package_list = []
                    for i in range(100):
                        mock_package = MagicMock()
                        mock_package.name = f"test/package-{i}"
                        mock_package.description = f"Test package {i}"
                        mock_package.tags = ["test", f"batch-{i//10}"]
                        mock_package.modified = MagicMock()
                        mock_package.modified.isoformat.return_value = f"2024-01-{(i%30)+1:02d}T00:00:00Z"
                        mock_package.registry = "s3://test-registry"
                        mock_package.bucket = "test-bucket"
                        mock_package.top_hash = f"hash{i}"
                        large_package_list.append(mock_package)
                    
                    with patch('quilt3.search', return_value=large_package_list):
                        import time
                        start_time = time.time()
                        packages = quilt_ops.search_packages("test", "s3://test-registry")
                        end_time = time.time()
                        
                        # Should complete quickly even with many packages
                        assert (end_time - start_time) < 1.0  # Less than 1 second
                        assert len(packages) == 100
                        assert all(isinstance(pkg, Package_Info) for pkg in packages)
                    
                    # Test with large content list
                    mock_package = MagicMock()
                    large_content_list = []
                    for i in range(50):
                        mock_content = MagicMock()
                        mock_content.name = f"data/file-{i}.csv"
                        mock_content.size = 1024 * (i + 1)
                        mock_content.is_dir = False
                        mock_content.modified = MagicMock()
                        mock_content.modified.isoformat.return_value = f"2024-01-01T{i%24:02d}:00:00Z"
                        large_content_list.append(mock_content)
                    
                    with patch('quilt3.Package.browse', return_value=mock_package):
                        with patch.object(mock_package, '__iter__', return_value=iter(large_content_list)):
                            start_time = time.time()
                            content = quilt_ops.browse_content("test/large-package", "s3://test-registry")
                            end_time = time.time()
                            
                            # Should complete quickly even with many files
                            assert (end_time - start_time) < 1.0  # Less than 1 second
                            assert len(content) == 50
                            assert all(isinstance(item, Content_Info) for item in content)
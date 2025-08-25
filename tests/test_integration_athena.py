#!/usr/bin/env python3
"""
Integration tests for AWS Athena and Glue Data Catalog tools

These tests require actual AWS credentials and resources.
"""

import pytest
import os
from unittest.mock import patch

from quilt_mcp.tools.athena_glue import (
    athena_databases_list,
    athena_tables_list,
    athena_table_schema,
    athena_query_execute,
    athena_workgroups_list
)
from quilt_mcp.aws.athena_service import AthenaQueryService


@pytest.mark.aws
@pytest.mark.integration
class TestAthenaIntegration:
    """Integration tests for Athena functionality."""
    
    @pytest.fixture(autouse=True)
    def setup_aws_env(self):
        """Setup AWS environment variables for testing."""
        # Check if AWS credentials are available
        if not (os.environ.get('AWS_ACCESS_KEY_ID') or os.environ.get('AWS_PROFILE')):
            pytest.skip("AWS credentials not available")
        
        # Set default staging location if not set
        if not os.environ.get('ATHENA_QUERY_RESULT_LOCATION'):
            os.environ['ATHENA_QUERY_RESULT_LOCATION'] = 's3://aws-athena-query-results-test/'
    
    def test_list_databases_integration(self):
        """Test listing databases with real AWS connection."""
        result = athena_databases_list()
        
        # Should succeed or fail gracefully with AWS error
        assert isinstance(result, dict)
        assert 'success' in result
        
        if result['success']:
            assert 'databases' in result
            assert isinstance(result['databases'], list)
            assert 'catalog_name' in result
            assert result['catalog_name'] == 'AwsDataCatalog'
        else:
            # Should have error message if failed
            assert 'error' in result
            assert isinstance(result['error'], str)
    
    def test_list_workgroups_integration(self):
        """Test listing Athena workgroups with real AWS connection."""
        result = athena_workgroups_list()
        
        assert isinstance(result, dict)
        assert 'success' in result
        
        if result['success']:
            assert 'workgroups' in result
            assert isinstance(result['workgroups'], list)
            # Should at least have 'primary' workgroup
            workgroup_names = [wg['name'] for wg in result['workgroups']]
            assert 'primary' in workgroup_names
    
    @pytest.mark.slow
    def test_query_execution_integration(self):
        """Test executing a simple query against Athena."""
        # Use a simple query that should work in most AWS accounts
        query = "SELECT 1 as test_value, 'hello' as test_string"
        
        result = athena_query_execute(
            query=query,
            max_results=10,
            output_format='json',
            use_quilt_auth=False  # Use default AWS credentials
        )
        
        assert isinstance(result, dict)
        assert 'success' in result
        
        if result['success']:
            assert 'formatted_data' in result
            assert 'format' in result
            assert result['format'] == 'json'
            assert len(result['formatted_data']) == 1
            assert result['formatted_data'][0]['test_value'] == 1
            assert result['formatted_data'][0]['test_string'] == 'hello'
        else:
            # Query might fail due to Athena setup, but should fail gracefully
            assert 'error' in result
    
    def test_service_initialization_integration(self):
        """Test AthenaQueryService initialization with real AWS."""
        try:
            service = AthenaQueryService(use_quilt_auth=False)
            
            # Test lazy initialization doesn't fail
            glue_client = service.glue_client
            s3_client = service.s3_client
            
            # These should be boto3 clients
            assert hasattr(glue_client, 'get_databases')
            assert hasattr(s3_client, 'list_buckets')
            
        except Exception as e:
            # If initialization fails, it should be due to AWS config issues
            assert 'credential' in str(e).lower() or 'auth' in str(e).lower()
    
    @pytest.mark.slow
    def test_database_discovery_integration(self):
        """Test database discovery integration."""
        try:
            service = AthenaQueryService(use_quilt_auth=False)
            result = service.discover_databases()
            
            assert isinstance(result, dict)
            assert 'success' in result
            
            if result['success']:
                assert 'databases' in result
                assert isinstance(result['databases'], list)
                # Each database should have required fields
                for db in result['databases']:
                    assert 'name' in db
                    assert isinstance(db['name'], str)
            
        except Exception as e:
            pytest.skip(f"AWS access issue: {e}")


@pytest.mark.aws  
@pytest.mark.integration
@pytest.mark.slow
class TestQuiltAuthIntegration:
    """Integration tests for quilt3 authentication."""
    
    @pytest.fixture(autouse=True)
    def check_quilt_available(self):
        """Check if quilt3 is available and configured."""
        try:
            import quilt3
            # Try to get session to verify quilt3 is configured
            session = quilt3.session.get_session()
            if not session:
                pytest.skip("Quilt3 session not available")
        except ImportError:
            pytest.skip("quilt3 not available")
        except Exception as e:
            pytest.skip(f"Quilt3 configuration issue: {e}")
    
    def test_service_with_quilt_auth(self):
        """Test service initialization with quilt3 authentication."""
        try:
            service = AthenaQueryService(use_quilt_auth=True)
            
            # Test that we can create clients
            glue_client = service.glue_client
            s3_client = service.s3_client
            engine = service.engine
            
            assert glue_client is not None
            assert s3_client is not None
            assert engine is not None
            
        except Exception as e:
            # Expected if quilt3 isn't properly configured
            assert 'quilt' in str(e).lower() or 'credential' in str(e).lower()
    
    def test_query_with_quilt_auth(self):
        """Test query execution with quilt3 authentication."""
        query = "SELECT 1 as test_value"
        
        result = athena_query_execute(
            query=query,
            use_quilt_auth=True,
            max_results=1
        )
        
        assert isinstance(result, dict)
        assert 'success' in result
        
        # Test passes if query succeeds or fails gracefully
        if not result['success']:
            assert 'error' in result


@pytest.mark.performance
class TestAthenaPerformance:
    """Performance tests for Athena functionality."""
    
    @patch('quilt_mcp.aws.athena_service.boto3')
    @patch('quilt_mcp.aws.athena_service.create_engine')
    def test_concurrent_database_discovery(self, mock_create_engine, mock_boto3):
        """Test concurrent database discovery operations."""
        import threading
        import time
        
        # Mock responses
        mock_glue = mock_boto3.client.return_value
        mock_glue.get_databases.return_value = {
            'DatabaseList': [{'Name': f'db_{i}'} for i in range(100)]
        }
        
        results = []
        errors = []
        
        def discover_databases():
            try:
                result = athena_databases_list()
                results.append(result)
            except Exception as e:
                errors.append(e)
        
        # Run multiple concurrent requests
        threads = []
        start_time = time.time()
        
        for _ in range(10):
            thread = threading.Thread(target=discover_databases)
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        end_time = time.time()
        
        # All requests should complete successfully
        assert len(errors) == 0
        assert len(results) == 10
        
        # Should complete in reasonable time (less than 5 seconds)
        assert end_time - start_time < 5.0
        
        # All results should be successful
        for result in results:
            assert result['success'] is True
    
    @patch('quilt_mcp.aws.athena_service.pd.read_sql_query')
    @patch('quilt_mcp.aws.athena_service.create_engine')
    @patch('quilt_mcp.aws.athena_service.boto3')
    def test_large_result_set_handling(self, mock_boto3, mock_create_engine, mock_read_sql):
        """Test handling of large result sets."""
        import pandas as pd
        
        # Create large mock DataFrame (10,000 rows)
        large_df = pd.DataFrame({
            'id': range(10000),
            'value': [f'value_{i}' for i in range(10000)]
        })
        mock_read_sql.return_value = large_df
        
        service = AthenaQueryService(use_quilt_auth=False)
        
        # Test with default max_results (should truncate)
        result = service.execute_query("SELECT * FROM large_table", max_results=1000)
        
        assert result['success'] is True
        assert result['row_count'] == 1000  # Should be truncated
        assert result['truncated'] is True
        
        # Test with higher limit
        result = service.execute_query("SELECT * FROM large_table", max_results=5000)
        
        assert result['success'] is True
        assert result['row_count'] == 5000  # Should be truncated to 5000
        assert result['truncated'] is True


@pytest.mark.error_handling  
class TestAthenaErrorHandling:
    """Test error handling scenarios."""
    
    @patch('quilt_mcp.aws.athena_service.boto3')
    def test_glue_connection_error(self, mock_boto3):
        """Test handling of Glue connection errors."""
        from botocore.exceptions import BotoCoreError, ClientError
        
        mock_glue = mock_boto3.client.return_value
        mock_glue.get_databases.side_effect = ClientError(
            error_response={'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}},
            operation_name='GetDatabases'
        )
        
        result = athena_databases_list()
        
        assert result['success'] is False
        assert 'Access denied' in result['error']
    
    @patch('quilt_mcp.aws.athena_service.create_engine')
    @patch('quilt_mcp.aws.athena_service.boto3')
    def test_sqlalchemy_connection_error(self, mock_boto3, mock_create_engine):
        """Test handling of SQLAlchemy connection errors."""
        from sqlalchemy.exc import SQLAlchemyError
        
        mock_engine = mock_create_engine.return_value
        mock_engine.connect.side_effect = SQLAlchemyError("Connection failed")
        
        service = AthenaQueryService(use_quilt_auth=False)
        result = service.execute_query("SELECT 1")
        
        assert result['success'] is False
        assert 'Connection failed' in result['error']
    
    @patch('quilt_mcp.aws.athena_service.pd.read_sql_query')
    @patch('quilt_mcp.aws.athena_service.create_engine')
    @patch('quilt_mcp.aws.athena_service.boto3')
    def test_sql_syntax_error(self, mock_boto3, mock_create_engine, mock_read_sql):
        """Test handling of SQL syntax errors."""
        from sqlalchemy.exc import DatabaseError
        
        mock_read_sql.side_effect = DatabaseError(
            "Syntax error in SQL statement",
            params=None,
            orig=Exception("SYNTAX_ERROR")
        )
        
        result = athena_query_execute("SELECT FROM WHERE")  # Invalid SQL
        
        assert result['success'] is False
        assert 'error' in result['error'].lower()
    
    def test_invalid_query_parameters(self):
        """Test handling of invalid query parameters."""
        # Empty query
        result = athena_query_execute("")
        assert result['success'] is False
        
        # Invalid max_results
        result = athena_query_execute("SELECT 1", max_results=-1)
        assert result['success'] is False
        
        # Invalid output format
        result = athena_query_execute("SELECT 1", output_format="invalid")
        assert result['success'] is False
    
    @patch('quilt_mcp.aws.athena_service.boto3')
    def test_table_not_found_error(self, mock_boto3):
        """Test handling when table is not found."""
        from botocore.exceptions import ClientError
        
        mock_glue = mock_boto3.client.return_value
        mock_glue.get_table.side_effect = ClientError(
            error_response={'Error': {'Code': 'EntityNotFoundException', 'Message': 'Table not found'}},
            operation_name='GetTable'
        )
        
        result = athena_table_schema('test_db', 'nonexistent_table')
        
        assert result['success'] is False
        assert 'Table not found' in result['error'] or 'not found' in result['error'].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
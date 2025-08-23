#!/usr/bin/env python3
"""
Tests for AWS Athena and Glue Data Catalog tools
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
from datetime import datetime

from quilt_mcp.tools.athena_glue import (
    athena_databases_list,
    athena_tables_list,
    athena_table_schema,
    athena_query_execute,
    athena_query_history,
    athena_workgroups_list,
    athena_query_validate
)
from quilt_mcp.aws.athena_service import AthenaQueryService


class TestAthenaDatabasesList:
    """Test athena_databases_list function."""
    
    @patch('quilt_mcp.tools.athena_glue.AthenaQueryService')
    def test_list_databases_success(self, mock_service_class):
        """Test successful database listing."""
        # Mock the service
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        
        # Mock response
        mock_service.discover_databases.return_value = {
            'success': True,
            'databases': [
                {
                    'name': 'analytics_db',
                    'description': 'Analytics database',
                    'location_uri': 's3://analytics-data/',
                    'create_time': '2024-01-01T00:00:00',
                    'parameters': {}
                }
            ],
            'catalog_name': 'AwsDataCatalog',
            'count': 1
        }
        
        result = athena_databases_list()
        
        assert result['success'] is True
        assert len(result['databases']) == 1
        assert result['databases'][0]['name'] == 'analytics_db'
        mock_service.discover_databases.assert_called_once_with('AwsDataCatalog')
    
    @patch('quilt_mcp.tools.athena_glue.AthenaQueryService')
    def test_list_databases_with_custom_catalog(self, mock_service_class):
        """Test database listing with custom catalog."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.discover_databases.return_value = {'success': True, 'databases': []}
        
        athena_databases_list(catalog_name="custom-catalog")
        
        mock_service.discover_databases.assert_called_once_with('custom-catalog')
    
    @patch('quilt_mcp.tools.athena_glue.AthenaQueryService')
    def test_list_databases_error(self, mock_service_class):
        """Test database listing error handling."""
        mock_service_class.side_effect = Exception("Connection failed")
        
        result = athena_databases_list()
        
        assert result['success'] is False
        assert 'Connection failed' in result['error']


class TestAthenaTablesList:
    """Test athena_tables_list function."""
    
    @patch('quilt_mcp.tools.athena_glue.AthenaQueryService')
    def test_list_tables_success(self, mock_service_class):
        """Test successful table listing."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        
        mock_service.discover_tables.return_value = {
            'success': True,
            'tables': [
                {
                    'name': 'customer_events',
                    'database_name': 'analytics_db',
                    'description': 'Customer event data',
                    'table_type': 'EXTERNAL_TABLE',
                    'storage_descriptor': {
                        'location': 's3://data/customer_events/',
                        'input_format': 'org.apache.hadoop.mapred.TextInputFormat'
                    }
                }
            ],
            'database_name': 'analytics_db',
            'catalog_name': 'AwsDataCatalog',
            'count': 1
        }
        
        result = athena_tables_list('analytics_db')
        
        assert result['success'] is True
        assert len(result['tables']) == 1
        assert result['tables'][0]['name'] == 'customer_events'
        mock_service.discover_tables.assert_called_once_with('analytics_db', 'AwsDataCatalog', None)
    
    @patch('quilt_mcp.tools.athena_glue.AthenaQueryService')
    def test_list_tables_with_pattern(self, mock_service_class):
        """Test table listing with pattern filter."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.discover_tables.return_value = {'success': True, 'tables': []}
        
        athena_tables_list('analytics_db', table_pattern='customer_*')
        
        mock_service.discover_tables.assert_called_once_with('analytics_db', 'AwsDataCatalog', 'customer_*')


class TestAthenaTableSchema:
    """Test athena_table_schema function."""
    
    @patch('quilt_mcp.tools.athena_glue.AthenaQueryService')
    def test_get_table_schema_success(self, mock_service_class):
        """Test successful table schema retrieval."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        
        mock_service.get_table_metadata.return_value = {
            'success': True,
            'table_name': 'customer_events',
            'database_name': 'analytics_db',
            'columns': [
                {'name': 'customer_id', 'type': 'bigint', 'comment': 'Customer identifier'},
                {'name': 'event_type', 'type': 'string', 'comment': 'Type of event'}
            ],
            'partitions': [
                {'name': 'date', 'type': 'string', 'comment': 'Event date'}
            ],
            'storage_descriptor': {
                'location': 's3://data/customer_events/',
                'input_format': 'parquet'
            }
        }
        
        result = athena_table_schema('analytics_db', 'customer_events')
        
        assert result['success'] is True
        assert result['table_name'] == 'customer_events'
        assert len(result['columns']) == 2
        assert len(result['partitions']) == 1


class TestAthenaQueryExecute:
    """Test athena_query_execute function."""
    
    @patch('quilt_mcp.tools.athena_glue.AthenaQueryService')
    def test_query_execute_success(self, mock_service_class):
        """Test successful query execution."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        
        # Mock query result
        mock_df = pd.DataFrame({
            'event_type': ['page_view', 'purchase', 'cart_add'],
            'count': [125432, 23891, 45123]
        })
        
        mock_service.execute_query.return_value = {
            'success': True,
            'data': mock_df,
            'row_count': 3,
            'truncated': False,
            'columns': ['event_type', 'count'],
            'dtypes': {'event_type': 'object', 'count': 'int64'},
            'query': 'SELECT event_type, COUNT(*) FROM table GROUP BY event_type'
        }
        
        mock_service.format_results.return_value = {
            'success': True,
            'formatted_data': [
                {'event_type': 'page_view', 'count': 125432},
                {'event_type': 'purchase', 'count': 23891},
                {'event_type': 'cart_add', 'count': 45123}
            ],
            'format': 'json',
            'row_count': 3,
            'truncated': False
        }
        
        query = "SELECT event_type, COUNT(*) FROM customer_events GROUP BY event_type"
        result = athena_query_execute(query)
        
        assert result['success'] is True
        assert len(result['formatted_data']) == 3
        assert result['format'] == 'json'
        mock_service.execute_query.assert_called_once_with(query, None, 1000)
        mock_service.format_results.assert_called_once()
    
    def test_query_execute_empty_query(self):
        """Test query execution with empty query."""
        result = athena_query_execute("")
        
        assert result['success'] is False
        assert 'empty' in result['error'].lower()
    
    def test_query_execute_invalid_max_results(self):
        """Test query execution with invalid max_results."""
        result = athena_query_execute("SELECT * FROM table", max_results=0)
        
        assert result['success'] is False
        assert 'max_results must be between' in result['error']
    
    def test_query_execute_invalid_format(self):
        """Test query execution with invalid output format."""
        result = athena_query_execute("SELECT * FROM table", output_format="xml")
        
        assert result['success'] is False
        assert 'output_format must be one of' in result['error']


class TestAthenaQueryHistory:
    """Test athena_query_history function."""
    
    @patch('boto3.client')
    @patch('quilt_mcp.tools.athena_glue.AthenaQueryService')
    def test_query_history_success(self, mock_service_class, mock_boto3_client):
        """Test successful query history retrieval."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        
        mock_athena_client = Mock()
        mock_boto3_client.return_value = mock_athena_client
        
        # Mock list_query_executions response
        mock_athena_client.list_query_executions.return_value = {
            'QueryExecutionIds': ['query-1', 'query-2']
        }
        
        # Mock batch_get_query_execution response
        mock_execution_time = datetime.utcnow()
        mock_athena_client.batch_get_query_execution.return_value = {
            'QueryExecutions': [
                {
                    'QueryExecutionId': 'query-1',
                    'Query': 'SELECT * FROM table1',
                    'Status': {
                        'State': 'SUCCEEDED',
                        'SubmissionDateTime': mock_execution_time,
                        'CompletionDateTime': mock_execution_time
                    },
                    'Statistics': {
                        'TotalExecutionTimeInMillis': 2300,
                        'DataScannedInBytes': 1024000
                    },
                    'ResultConfiguration': {
                        'OutputLocation': 's3://results/query-1'
                    },
                    'WorkGroup': 'primary',
                    'QueryExecutionContext': {
                        'Database': 'analytics_db'
                    }
                }
            ]
        }
        
        result = athena_query_history()
        
        assert result['success'] is True
        assert len(result['query_history']) == 1
        assert result['query_history'][0]['query_execution_id'] == 'query-1'
        assert result['query_history'][0]['status'] == 'SUCCEEDED'
    
    @patch('boto3.client')
    @patch('quilt_mcp.tools.athena_glue.AthenaQueryService')
    def test_query_history_no_executions(self, mock_service_class, mock_boto3_client):
        """Test query history with no executions."""
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        
        mock_athena_client = Mock()
        mock_boto3_client.return_value = mock_athena_client
        mock_athena_client.list_query_executions.return_value = {'QueryExecutionIds': []}
        
        result = athena_query_history()
        
        assert result['success'] is True
        assert len(result['query_history']) == 0
        assert result['count'] == 0


class TestAthenaWorkgroupsList:
    """Test athena_workgroups_list function."""
    
    @patch('boto3.client')
    def test_list_workgroups_success(self, mock_boto3_client):
        """Test successful workgroups listing."""
        mock_athena_client = Mock()
        mock_boto3_client.return_value = mock_athena_client
        
        mock_time = datetime.utcnow()
        mock_athena_client.list_work_groups.return_value = {
            'WorkGroups': [
                {
                    'Name': 'primary',
                    'Description': 'Primary workgroup',
                    'State': 'ENABLED',
                    'CreationTime': mock_time
                },
                {
                    'Name': 'analytics',
                    'Description': 'Analytics workgroup',
                    'State': 'ENABLED',
                    'CreationTime': mock_time
                }
            ]
        }
        
        result = athena_workgroups_list()
        
        assert result['success'] is True
        assert len(result['workgroups']) == 2
        assert result['workgroups'][0]['name'] == 'primary'
        assert result['workgroups'][1]['name'] == 'analytics'


class TestAthenaQueryValidate:
    """Test athena_query_validate function."""
    
    def test_validate_empty_query(self):
        """Test validation of empty query."""
        result = athena_query_validate("")
        
        assert result['success'] is False
        assert 'empty' in result['error'].lower()
    
    def test_validate_valid_select_query(self):
        """Test validation of valid SELECT query."""
        query = "SELECT event_type, COUNT(*) FROM customer_events WHERE date >= '2024-01-01' GROUP BY event_type"
        result = athena_query_validate(query)
        
        assert result['success'] is True
        assert result['valid'] is True
        assert result['query_type'] == 'SELECT'
    
    def test_validate_dangerous_query(self):
        """Test validation of dangerous query."""
        query = "DROP TABLE customer_events"
        result = athena_query_validate(query)
        
        assert result['success'] is False
        assert result['valid'] is False
        assert 'dangerous' in result['error'].lower()
    
    def test_validate_select_without_from(self):
        """Test validation of SELECT without FROM."""
        query = "SELECT 1, 2, 3"
        result = athena_query_validate(query)
        
        assert result['success'] is False
        assert result['valid'] is False
        assert 'FROM clause' in result['error']
    
    def test_validate_mismatched_parentheses(self):
        """Test validation of query with mismatched parentheses."""
        query = "SELECT COUNT((event_type) FROM customer_events"
        result = athena_query_validate(query)
        
        assert result['success'] is False
        assert result['valid'] is False
        assert 'parentheses' in result['error'].lower()
    
    def test_validate_show_query(self):
        """Test validation of SHOW query."""
        query = "SHOW TABLES"
        result = athena_query_validate(query)
        
        assert result['success'] is True
        assert result['valid'] is True
        assert result['query_type'] == 'SHOW'
    
    def test_validate_describe_query(self):
        """Test validation of DESCRIBE query."""
        query = "DESCRIBE analytics_db.customer_events"
        result = athena_query_validate(query)
        
        assert result['success'] is True
        assert result['valid'] is True
        assert result['query_type'] == 'DESCRIBE'


class TestAthenaQueryService:
    """Test AthenaQueryService class."""
    
    @patch('quilt_mcp.aws.athena_service.create_engine')
    @patch('quilt_mcp.aws.athena_service.boto3')
    def test_service_initialization(self, mock_boto3, mock_create_engine):
        """Test service initialization."""
        service = AthenaQueryService(use_quilt_auth=False)
        
        assert service.use_quilt_auth is False
        assert service.query_cache.maxsize == 100
    
    @patch('quilt_mcp.aws.athena_service.create_engine')
    @patch('quilt_mcp.aws.athena_service.boto3')
    def test_discover_databases(self, mock_boto3, mock_create_engine):
        """Test database discovery."""
        service = AthenaQueryService(use_quilt_auth=False)
        
        # Mock Glue client
        mock_glue_client = Mock()
        service._glue_client = mock_glue_client
        
        mock_glue_client.get_databases.return_value = {
            'DatabaseList': [
                {
                    'Name': 'analytics_db',
                    'Description': 'Analytics database',
                    'LocationUri': 's3://analytics-data/',
                    'CreateTime': datetime.utcnow(),
                    'Parameters': {'key': 'value'}
                }
            ]
        }
        
        result = service.discover_databases()
        
        assert result['success'] is True
        assert len(result['databases']) == 1
        assert result['databases'][0]['name'] == 'analytics_db'
    
    @patch('quilt_mcp.aws.athena_service.pd.read_sql_query')
    @patch('quilt_mcp.aws.athena_service.create_engine')
    @patch('quilt_mcp.aws.athena_service.boto3')
    def test_execute_query(self, mock_boto3, mock_create_engine, mock_read_sql):
        """Test query execution."""
        service = AthenaQueryService(use_quilt_auth=False)
        
        # Mock pandas DataFrame result
        mock_df = pd.DataFrame({
            'event_type': ['page_view', 'purchase'],
            'count': [125432, 23891]
        })
        mock_read_sql.return_value = mock_df
        
        result = service.execute_query("SELECT event_type, COUNT(*) FROM events GROUP BY event_type")
        
        assert result['success'] is True
        assert result['row_count'] == 2
        assert result['columns'] == ['event_type', 'count']
        assert result['truncated'] is False
    
    @patch('quilt_mcp.aws.athena_service.create_engine')
    @patch('quilt_mcp.aws.athena_service.boto3')  
    def test_format_results_json(self, mock_boto3, mock_create_engine):
        """Test result formatting to JSON."""
        service = AthenaQueryService(use_quilt_auth=False)
        
        # Mock result data
        df = pd.DataFrame({
            'event_type': ['page_view', 'purchase'],
            'count': [125432, 23891]
        })
        
        result_data = {
            'success': True,
            'data': df,
            'row_count': 2,
            'truncated': False
        }
        
        formatted = service.format_results(result_data, 'json')
        
        assert formatted['success'] is True
        assert formatted['format'] == 'json'
        assert len(formatted['formatted_data']) == 2
        assert formatted['formatted_data'][0]['event_type'] == 'page_view'
    
    @patch('quilt_mcp.aws.athena_service.create_engine')
    @patch('quilt_mcp.aws.athena_service.boto3')
    def test_format_results_csv(self, mock_boto3, mock_create_engine):
        """Test result formatting to CSV."""
        service = AthenaQueryService(use_quilt_auth=False)
        
        df = pd.DataFrame({
            'event_type': ['page_view', 'purchase'],
            'count': [125432, 23891]
        })
        
        result_data = {
            'success': True,
            'data': df,
            'row_count': 2,
            'truncated': False
        }
        
        formatted = service.format_results(result_data, 'csv')
        
        assert formatted['success'] is True
        assert formatted['format'] == 'csv'
        assert 'event_type,count' in formatted['formatted_data']
        assert 'page_view,125432' in formatted['formatted_data']


if __name__ == "__main__":
    pytest.main([__file__])
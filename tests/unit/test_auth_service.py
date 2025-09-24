"""Tests for the authentication service."""

import json
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import boto3
from botocore.exceptions import ClientError

from quilt_mcp.services.auth_service import (
    AuthenticationService,
    AuthMethod,
    AuthStatus,
    get_auth_service,
    initialize_auth,
)


class TestAuthenticationService:
    """Test cases for AuthenticationService."""

    def test_auth_service_initialization(self):
        """Test that authentication service initializes correctly."""
        service = AuthenticationService()
        assert service._auth_status == AuthStatus.UNAUTHENTICATED
        assert service._auth_method is None
        assert service._boto3_session is None

    def test_iam_role_authentication_success(self):
        """Test successful IAM role authentication."""
        service = AuthenticationService()
        
        # Mock boto3 session and STS client
        mock_session = Mock()
        mock_sts_client = Mock()
        mock_identity = {
            "Account": "123456789012",
            "UserId": "test-user",
            "Arn": "arn:aws:sts::123456789012:assumed-role/test-role/test-session"
        }
        mock_sts_client.get_caller_identity.return_value = mock_identity
        mock_session.client.return_value = mock_sts_client
        
        with patch('boto3.Session', return_value=mock_session):
            status = service._try_iam_role_auth()
            
            assert status == AuthStatus.AUTHENTICATED
            assert service._auth_method == AuthMethod.IAM_ROLE
            assert service._aws_credentials == {
                "account_id": "123456789012",
                "user_id": "test-user",
                "arn": "arn:aws:sts::123456789012:assumed-role/test-role/test-session"
            }

    def test_iam_role_authentication_failure(self):
        """Test IAM role authentication failure."""
        service = AuthenticationService()
        
        # Mock boto3 session that raises exception
        with patch('boto3.Session') as mock_boto3:
            mock_boto3.side_effect = ClientError(
                {'Error': {'Code': 'NoCredentialsError'}}, 'GetCallerIdentity'
            )
            
            status = service._try_iam_role_auth()
            assert status == AuthStatus.UNAUTHENTICATED

    def test_environment_authentication_success(self):
        """Test successful environment variable authentication."""
        service = AuthenticationService()
        
        # Mock environment variables
        env_vars = {
            'AWS_ACCESS_KEY_ID': 'test-access-key',
            'AWS_SECRET_ACCESS_KEY': 'test-secret-key',
            'AWS_SESSION_TOKEN': 'test-session-token',
            'AWS_DEFAULT_REGION': 'us-east-1'
        }
        
        mock_session = Mock()
        mock_sts_client = Mock()
        mock_identity = {
            "Account": "123456789012",
            "UserId": "test-user",
            "Arn": "arn:aws:sts::123456789012:user/test-user"
        }
        mock_sts_client.get_caller_identity.return_value = mock_identity
        mock_session.client.return_value = mock_sts_client
        
        with patch.dict('os.environ', env_vars), \
             patch('boto3.Session', return_value=mock_session):
            
            status = service._try_environment_auth()
            
            assert status == AuthStatus.AUTHENTICATED
            assert service._auth_method == AuthMethod.ENVIRONMENT
            assert service._aws_credentials == {
                "account_id": "123456789012",
                "user_id": "test-user",
                "arn": "arn:aws:sts::123456789012:user/test-user"
            }

    def test_quilt_registry_authentication_success(self):
        """Test successful Quilt registry authentication."""
        service = AuthenticationService()
        
        # Create temporary credentials file
        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock platformdirs to use our temp directory
            with patch('platformdirs.user_data_dir', return_value=temp_dir):
                credentials_path = Path(temp_dir) / 'Quilt' / 'QuiltData' / 'credentials.json'
                credentials_path.parent.mkdir(parents=True)
                
                # Create valid credentials
                credentials = {
                    'access_key': 'test-access-key',
                    'secret_key': 'test-secret-key',
                    'token': 'test-session-token',
                    'expiry_time': time.time() + 3600  # Valid for 1 hour
                }
                
                with open(credentials_path, 'w') as f:
                    json.dump(credentials, f)
                
                # Mock boto3 session
                mock_session = Mock()
                mock_sts_client = Mock()
                mock_identity = {
                    "Account": "123456789012",
                    "UserId": "test-user",
                    "Arn": "arn:aws:sts::123456789012:assumed-role/quilt-role/test-session"
                }
                mock_sts_client.get_caller_identity.return_value = mock_identity
                mock_session.client.return_value = mock_sts_client
                
                with patch('boto3.Session', return_value=mock_session):
                    status = service._try_quilt_registry_auth()
                    
                    assert status == AuthStatus.AUTHENTICATED
                    assert service._auth_method == AuthMethod.QUILT3

    def test_quilt_registry_authentication_expired_credentials(self):
        """Test Quilt registry authentication with expired credentials."""
        service = AuthenticationService()
        
        # Create temporary credentials file with expired credentials
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('platformdirs.user_data_dir', return_value=temp_dir):
                credentials_path = Path(temp_dir) / 'Quilt' / 'QuiltData' / 'credentials.json'
                credentials_path.parent.mkdir(parents=True)
                
                # Create expired credentials
                credentials = {
                    'access_key': 'test-access-key',
                    'secret_key': 'test-secret-key',
                    'token': 'test-session-token',
                    'expiry_time': time.time() - 3600  # Expired 1 hour ago
                }
                
                with open(credentials_path, 'w') as f:
                    json.dump(credentials, f)
                
                status = service._try_quilt_registry_auth()
                assert status == AuthStatus.UNAUTHENTICATED

    def test_get_auth_status(self):
        """Test getting authentication status."""
        service = AuthenticationService()
        service._auth_status = AuthStatus.AUTHENTICATED
        service._auth_method = AuthMethod.IAM_ROLE
        service._catalog_url = "https://demo.quiltdata.com"
        service._catalog_name = "demo"
        service._aws_credentials = {"account_id": "123456789012"}
        
        status = service.get_auth_status()
        
        assert status["status"] == "authenticated"
        assert status["method"] == "iam_role"
        assert status["catalog_url"] == "https://demo.quiltdata.com"
        assert status["catalog_name"] == "demo"
        assert status["aws_credentials"]["account_id"] == "123456789012"
        assert status["is_authenticated"] is True

    def test_get_quilt_compatible_session(self):
        """Test getting Quilt-compatible session."""
        service = AuthenticationService()
        
        # Test with existing session
        mock_session = Mock()
        service._boto3_session = mock_session
        
        session = service.get_quilt_compatible_session()
        assert session == mock_session
        
        # Test fallback to default session
        service._boto3_session = None
        with patch('boto3.Session') as mock_boto3:
            mock_default_session = Mock()
            mock_boto3.return_value = mock_default_session
            
            session = service.get_quilt_compatible_session()
            assert session == mock_default_session

    def test_global_auth_service(self):
        """Test global authentication service functions."""
        # Clear global instance
        import quilt_mcp.services.auth_service
        quilt_mcp.services.auth_service._auth_service = None
        
        # Test get_auth_service
        service = get_auth_service()
        assert isinstance(service, AuthenticationService)
        
        # Test that it's the same instance
        service2 = get_auth_service()
        assert service is service2


class TestAuthenticationIntegration:
    """Integration tests for authentication service."""

    def test_authentication_priority_order(self):
        """Test that authentication methods are tried in correct priority order."""
        service = AuthenticationService()
        
        # Mock all authentication methods to return UNAUTHENTICATED
        with patch.object(service, '_try_quilt3_auth', return_value=AuthStatus.UNAUTHENTICATED), \
             patch.object(service, '_try_quilt_registry_auth', return_value=AuthStatus.UNAUTHENTICATED), \
             patch.object(service, '_try_iam_role_auth', return_value=AuthStatus.UNAUTHENTICATED), \
             patch.object(service, '_try_environment_auth', return_value=AuthStatus.UNAUTHENTICATED):
            
            # Mock IAM role to succeed
            with patch.object(service, '_try_iam_role_auth', return_value=AuthStatus.AUTHENTICATED):
                status = service.authenticate()
                assert status == AuthStatus.AUTHENTICATED
                assert service._auth_method == AuthMethod.IAM_ROLE

    def test_authentication_with_mixed_methods(self):
        """Test authentication when some methods fail and others succeed."""
        service = AuthenticationService()
        
        # Mock quilt3 to fail, IAM role to succeed
        with patch.object(service, '_try_quilt3_auth', return_value=AuthStatus.UNAUTHENTICATED), \
             patch.object(service, '_try_quilt_registry_auth', return_value=AuthStatus.UNAUTHENTICATED), \
             patch.object(service, '_try_iam_role_auth', return_value=AuthStatus.AUTHENTICATED):
            
            status = service.authenticate()
            assert status == AuthStatus.AUTHENTICATED
            assert service._auth_method == AuthMethod.IAM_ROLE

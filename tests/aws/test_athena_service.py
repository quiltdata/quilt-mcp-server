"""Tests for AthenaQueryService dependency injection."""

from __future__ import annotations

import pytest
from unittest.mock import Mock, patch, MagicMock

from quilt_mcp.aws.athena_service import AthenaQueryService
from quilt_mcp.services.quilt_service import QuiltService


class TestAthenaQueryServiceDependencyInjection:
    """Test AthenaQueryService dependency injection with QuiltService."""

    def test_athena_service_accepts_quilt_service_dependency(self):
        """Test that AthenaQueryService can accept QuiltService as dependency."""
        mock_quilt_service = Mock(spec=QuiltService)

        # This test will fail initially until we implement dependency injection
        service = AthenaQueryService(use_quilt_auth=True, quilt_service=mock_quilt_service)

        # Verify the service was created with the dependency
        assert hasattr(service, 'quilt_service')
        assert service.quilt_service == mock_quilt_service

    def test_athena_service_uses_quilt_service_for_botocore_session(self):
        """Test that AthenaQueryService uses QuiltService.create_botocore_session()."""
        mock_quilt_service = Mock(spec=QuiltService)
        mock_botocore_session = Mock()
        mock_credentials = Mock()
        mock_credentials.access_key = "test_access_key"
        mock_credentials.secret_key = "test_secret_key"
        mock_credentials.token = None
        mock_botocore_session.get_credentials.return_value = mock_credentials
        mock_quilt_service.create_botocore_session.return_value = mock_botocore_session

        service = AthenaQueryService(use_quilt_auth=True, quilt_service=mock_quilt_service)

        with patch.object(service, '_discover_workgroup', return_value='test-workgroup'):
            with patch('quilt_mcp.aws.athena_service.create_engine') as mock_create_engine:
                mock_engine = Mock()
                mock_create_engine.return_value = mock_engine

                # This should trigger the SQLAlchemy engine creation
                engine = service.engine

                # Verify QuiltService was used instead of direct quilt3 calls
                mock_quilt_service.create_botocore_session.assert_called_once()
                mock_botocore_session.get_credentials.assert_called_once()
                mock_create_engine.assert_called_once()

    def test_athena_service_backwards_compatible_without_quilt_service(self):
        """Test that AthenaQueryService remains backwards compatible without QuiltService."""
        # This should still work for existing code that doesn't pass quilt_service
        service = AthenaQueryService(use_quilt_auth=True)

        # Should not have quilt_service attribute initially
        assert not hasattr(service, 'quilt_service') or service.quilt_service is None

    def test_athena_service_uses_fallback_when_no_quilt_service_provided(self):
        """Test that AthenaQueryService falls back to direct quilt3 when no QuiltService provided."""
        service = AthenaQueryService(use_quilt_auth=True)

        with patch('quilt3.session.create_botocore_session') as mock_create_session:
            mock_botocore_session = Mock()
            mock_credentials = Mock()
            mock_credentials.access_key = "test_access_key"
            mock_credentials.secret_key = "test_secret_key"
            mock_credentials.token = None
            mock_botocore_session.get_credentials.return_value = mock_credentials
            mock_create_session.return_value = mock_botocore_session

            with patch.object(service, '_discover_workgroup', return_value='test-workgroup'):
                with patch('quilt_mcp.aws.athena_service.create_engine') as mock_create_engine:
                    mock_engine = Mock()
                    mock_create_engine.return_value = mock_engine

                    # This should trigger the SQLAlchemy engine creation
                    engine = service.engine

                    # Verify direct quilt3 was used as fallback
                    mock_create_session.assert_called_once()
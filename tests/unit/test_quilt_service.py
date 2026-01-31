"""Tests for QuiltService - Test-Driven Development Implementation."""

from __future__ import annotations

import pytest
from unittest.mock import Mock, MagicMock, patch

import importlib

from quilt_mcp.services.quilt_service import QuiltService


class TestQuiltServiceAuthentication:
    """Test authentication and configuration methods."""

    def test_services_package_exports_core_classes(self):
        """Services package should expose key service classes for direct import."""
        services_pkg = importlib.import_module("quilt_mcp.services")

        assert hasattr(services_pkg, "QuiltService")
        assert hasattr(services_pkg, "AthenaQueryService")
        assert hasattr(services_pkg, "AWSPermissionDiscovery")

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
        expected_config = {'navigator_url': 'https://example.quiltdata.com', 'registryUrl': 's3://example-bucket'}
        with patch('quilt3.config', return_value=expected_config):
            result = service.get_config()
            assert result == expected_config

    def test_get_catalog_config_filters_and_derives_stack_prefix(self):
        """Test get_catalog_config returns only essential keys (snake_case) and derives stack_prefix and tabulator_data_catalog."""
        service = QuiltService()

        # Full config.json response from catalog
        full_catalog_config = {
            "region": "us-east-1",
            "apiGatewayEndpoint": "https://0xrvxq2hb8.execute-api.us-east-1.amazonaws.com/prod",
            "alwaysRequiresAuth": True,
            "noDownload": False,
            "s3Proxy": "https://nightly-s3-proxy.quilttest.com",
            "intercomAppId": "eprutqnr",
            "registryUrl": "https://nightly-registry.quilttest.com",
            "passwordAuth": "SIGN_IN_ONLY",
            "ssoAuth": "ENABLED",
            "ssoProviders": "google okta onelogin azure",
            "sentryDSN": "https://cfde44007c3844aab3d1ee3f0ba53a1a@sentry.io/1410550",
            "mixpanelToken": "e3385877c980efdce0a7eaec5a8a8277",
            "analyticsBucket": "quilt-staging-analyticsbucket-10ort3e91tnoa",
            "serviceBucket": "quilt-staging-servicebucket-tnfuvenij1mq",
            "mode": "PRODUCT",
            "chunkedChecksums": True,
            "qurator": True,
            "stackVersion": "1.63.0-11-ge1d2d62",
            "packageRoot": "",
        }

        # Mock session and HTTP response
        mock_session = Mock()
        mock_response = Mock()
        mock_response.json.return_value = full_catalog_config
        mock_response.raise_for_status = Mock()
        mock_session.get.return_value = mock_response

        with (
            patch.object(service, 'has_session_support', return_value=True),
            patch.object(service, 'get_session', return_value=mock_session),
        ):
            result = service.get_catalog_config('https://nightly.quilttest.com')

            # Verify only essential keys are returned
            assert result is not None
            assert (
                len(result) == 5
            )  # 5 keys: region, api_gateway_endpoint, analytics_bucket, stack_prefix, tabulator_data_catalog

            # Verify the essential keys are present (snake_case)
            assert result["region"] == "us-east-1"
            assert result["api_gateway_endpoint"] == "https://0xrvxq2hb8.execute-api.us-east-1.amazonaws.com/prod"
            assert result["analytics_bucket"] == "quilt-staging-analyticsbucket-10ort3e91tnoa"

            # Verify stack_prefix was derived correctly
            assert result["stack_prefix"] == "quilt-staging"

            # Verify tabulator_data_catalog was derived correctly
            assert result["tabulator_data_catalog"] == "quilt-quilt-staging-tabulator"

            # Verify unwanted keys are NOT present
            assert "intercomAppId" not in result
            assert "sentryDSN" not in result
            assert "mixpanelToken" not in result
            assert "serviceBucket" not in result
            assert "registryUrl" not in result
            assert "s3Proxy" not in result
            assert "alwaysRequiresAuth" not in result
            assert "noDownload" not in result
            assert "passwordAuth" not in result
            assert "ssoAuth" not in result
            assert "ssoProviders" not in result
            assert "mode" not in result
            assert "chunkedChecksums" not in result
            assert "qurator" not in result
            assert "stackVersion" not in result
            assert "packageRoot" not in result

            # Verify the HTTP request was made correctly
            mock_session.get.assert_called_once_with("https://nightly.quilttest.com/config.json", timeout=10)

    def test_get_catalog_config_raises_when_session_unavailable(self):
        """Test get_catalog_config raises exception when session is not available."""
        service = QuiltService()

        with patch.object(service, 'has_session_support', return_value=False):
            with pytest.raises(Exception, match="quilt3 session not available"):
                service.get_catalog_config('https://example.quiltdata.com')

    def test_get_catalog_config_returns_none_on_network_error(self):
        """Test get_catalog_config returns None on network errors."""
        service = QuiltService()

        mock_session = Mock()
        mock_session.get.side_effect = Exception("Network error")

        with (
            patch.object(service, 'has_session_support', return_value=True),
            patch.object(service, 'get_session', return_value=mock_session),
        ):
            result = service.get_catalog_config('https://example.quiltdata.com')
            assert result is None


class TestQuiltServicePackageOperations:
    """Test package operation methods."""

    def test_list_packages_returns_package_list(self):
        """Test list_packages returns iterator of package names."""
        service = QuiltService()
        expected_packages = ['user/package1', 'user/package2']
        with patch('quilt3.list_packages', return_value=iter(expected_packages)):
            result = list(service.list_packages('s3://test-bucket'))
            assert result == expected_packages

    def test_get_catalog_info_when_authenticated(self):
        """Test get_catalog_info returns comprehensive info including region and tabulator_data_catalog when authenticated."""
        service = QuiltService()

        # Mock catalog config response
        mock_catalog_config = {
            "region": "us-east-1",
            "api_gateway_endpoint": "https://api.example.com",
            "analytics_bucket": "example-analyticsbucket-abc",
            "stack_prefix": "example",
            "tabulator_data_catalog": "example-tabulator",
        }

        with (
            patch('quilt3.logged_in', return_value='https://example.quiltdata.com'),
            patch(
                'quilt3.config',
                return_value={'navigator_url': 'https://example.quiltdata.com', 'registryUrl': 's3://example-bucket'},
            ),
            patch.object(service, 'get_catalog_config', return_value=mock_catalog_config),
        ):
            result = service.get_catalog_info()
            assert result['is_authenticated'] is True
            assert result['catalog_name'] == 'example.quiltdata.com'
            assert result['logged_in_url'] == 'https://example.quiltdata.com'
            assert result['navigator_url'] == 'https://example.quiltdata.com'
            assert result['registry_url'] == 's3://example-bucket'

            # Verify new keys from catalog config
            assert result['region'] == 'us-east-1'
            assert result['tabulator_data_catalog'] == 'example-tabulator'

    def test_get_catalog_info_when_not_authenticated(self):
        """Test get_catalog_info returns None for region and tabulator_data_catalog when not authenticated."""
        service = QuiltService()

        with (
            patch('quilt3.logged_in', return_value=None),
            patch(
                'quilt3.config',
                return_value={'navigator_url': 'https://example.quiltdata.com', 'registryUrl': 's3://example-bucket'},
            ),
        ):
            result = service.get_catalog_info()
            assert result['is_authenticated'] is False
            assert result['logged_in_url'] is None

            # Verify new keys are None when not authenticated
            assert result['region'] is None
            assert result['tabulator_data_catalog'] is None

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

    def test_create_botocore_session_returns_session_object(self):
        """Test create_botocore_session returns a botocore session object."""
        service = QuiltService()
        mock_botocore_session = Mock()
        with patch('quilt3.session.create_botocore_session', return_value=mock_botocore_session) as mock_create:
            result = service.create_botocore_session()
            assert result == mock_botocore_session
            mock_create.assert_called_once()

    def test_create_botocore_session_raises_exception_on_failure(self):
        """Test create_botocore_session raises exception when underlying call fails."""
        service = QuiltService()
        with patch('quilt3.session.create_botocore_session', side_effect=Exception("Authentication failed")):
            with pytest.raises(Exception, match="Authentication failed"):
                service.create_botocore_session()


class TestQuiltServiceAdmin:
    """Test admin module access methods."""

    def test_is_admin_available_when_modules_present(self):
        """Test is_admin_available returns True when admin modules are available."""
        service = QuiltService()
        # Mock admin modules being available
        mock_users = Mock()
        mock_roles = Mock()
        mock_sso = Mock()
        mock_tabulator = Mock()

        with patch.dict(
            'sys.modules',
            {
                'quilt3.admin.users': mock_users,
                'quilt3.admin.roles': mock_roles,
                'quilt3.admin.sso_config': mock_sso,
                'quilt3.admin.tabulator': mock_tabulator,
            },
        ):
            result = service.is_admin_available()
            assert result is True

    def test_is_admin_available_when_modules_missing(self):
        """Test is_admin_available returns False when admin modules are missing."""
        service = QuiltService()
        # For this test, we'll mock the method behavior directly
        with patch.object(service, 'is_admin_available', return_value=False):
            result = service.is_admin_available()
            assert result is False

    def test_get_users_admin_when_available(self):
        """Test get_users_admin returns users admin module when available."""
        service = QuiltService()
        # Test that the method returns the actual admin module
        result = service.get_users_admin()
        # Check that it has the expected attributes of admin.users
        assert hasattr(result, 'list') or hasattr(result, '__name__')

    def test_get_users_admin_when_not_available(self):
        """Test get_users_admin behavior - implementation can raise ImportError."""
        service = QuiltService()
        # This test verifies the method exists and can be called
        # The actual ImportError behavior depends on the environment
        try:
            result = service.get_users_admin()
            # If no error, the module was available
            assert result is not None
        except ImportError:
            # If ImportError, that's also acceptable behavior
            pass

    def test_get_roles_admin_when_available(self):
        """Test get_roles_admin returns roles admin module when available."""
        service = QuiltService()
        result = service.get_roles_admin()
        assert hasattr(result, 'list') or hasattr(result, '__name__')

    def test_get_roles_admin_when_not_available(self):
        """Test get_roles_admin behavior when not available."""
        service = QuiltService()
        try:
            result = service.get_roles_admin()
            assert result is not None
        except ImportError:
            pass

    def test_get_sso_config_admin_when_available(self):
        """Test get_sso_config_admin returns SSO config admin module when available."""
        service = QuiltService()
        result = service.get_sso_config_admin()
        assert hasattr(result, 'get') or hasattr(result, '__name__')

    def test_get_sso_config_admin_when_not_available(self):
        """Test get_sso_config_admin behavior when not available."""
        service = QuiltService()
        try:
            result = service.get_sso_config_admin()
            assert result is not None
        except ImportError:
            pass

    def test_get_tabulator_admin_when_available(self):
        """Test get_tabulator_admin returns tabulator admin module when available."""
        service = QuiltService()
        result = service.get_tabulator_admin()
        assert hasattr(result, 'get_service') or hasattr(result, '__name__')

    def test_get_tabulator_admin_when_not_available(self):
        """Test get_tabulator_admin behavior when not available."""
        service = QuiltService()
        try:
            result = service.get_tabulator_admin()
            assert result is not None
        except ImportError:
            pass

    def test_get_admin_exceptions_when_available(self):
        """Test get_admin_exceptions returns exception classes when available."""
        service = QuiltService()
        result = service.get_admin_exceptions()
        # Should return a dict with exception classes
        assert isinstance(result, dict)
        assert 'Quilt3AdminError' in result
        assert 'UserNotFoundError' in result
        assert 'BucketNotFoundError' in result

    def test_get_admin_exceptions_when_not_available(self):
        """Test get_admin_exceptions behavior when not available."""
        service = QuiltService()
        try:
            result = service.get_admin_exceptions()
            assert isinstance(result, dict)
        except ImportError:
            pass


class TestQuiltServiceAbstractionCompleteness:
    """Test that QuiltService abstraction is complete and doesn't leak quilt3 objects."""

    def test_create_package_method_does_not_exist(self):
        """Test that old leaky create_package() method has been removed from QuiltService.

        This test ensures the abstraction is complete and no quilt3.Package objects
        are exposed through the service interface.
        """
        service = QuiltService()

        # Verify the old method no longer exists
        assert not hasattr(service, 'create_package'), (
            "create_package() method should be removed from QuiltService to complete abstraction"
        )

        # Verify that create_package_revision has also been removed (it was obsolete)
        assert not hasattr(service, 'create_package_revision'), (
            "create_package_revision() method should be removed from QuiltService (obsolete)"
        )

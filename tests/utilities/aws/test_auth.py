"""BDD tests for AWS authentication utilities.

These tests follow the Given/When/Then pattern and test behavior, not implementation.
All tests are written to fail initially (RED phase of TDD).
"""

from __future__ import annotations

from unittest.mock import Mock, patch, MagicMock
import pytest

from quilt_mcp.utilities.aws.auth import (
    get_credentials,
    validate_credentials,
    get_caller_identity,
    is_quilt_authenticated,
    get_credential_type,
    AuthError,
    _credential_cache,
)


class TestCredentialRetrieval:
    """Test credential retrieval with dual credential support."""

    def setup_method(self):
        """Clear credential cache before each test."""
        _credential_cache.clear()

    def test_given_quilt_catalog_login_when_getting_credentials_with_prefer_quilt_true_then_quilt3_credentials_returned(
        self,
    ):
        """Given Quilt catalog login, When getting credentials with prefer_quilt=True, Then Quilt3 credentials returned."""
        # Given: Quilt3 is logged in and available
        with (
            patch('quilt3.logged_in', return_value='https://example.quiltdata.com'),
            patch('quilt3.get_boto3_session') as mock_get_session,
        ):
            mock_session = Mock()
            mock_credentials = Mock()
            mock_session.get_credentials.return_value = mock_credentials
            mock_get_session.return_value = mock_session

            # When: Getting credentials with prefer_quilt=True
            credentials = get_credentials(prefer_quilt=True)

            # Then: Quilt3 credentials are returned
            assert credentials == mock_credentials
            mock_get_session.assert_called_once()

    def test_given_aws_profile_when_getting_credentials_with_prefer_quilt_false_then_profile_credentials_returned(
        self,
    ):
        """Given AWS profile, When getting credentials with prefer_quilt=False, Then profile credentials returned."""
        # Given: AWS profile is configured
        profile_name = 'test-profile'

        with patch('boto3.Session') as mock_boto3_session:
            mock_session = Mock()
            mock_credentials = Mock()
            mock_session.get_credentials.return_value = mock_credentials
            mock_boto3_session.return_value = mock_session

            # When: Getting credentials with prefer_quilt=False and profile
            credentials = get_credentials(prefer_quilt=False, profile_name=profile_name)

            # Then: Profile credentials are returned
            assert credentials == mock_credentials
            mock_boto3_session.assert_called_once_with(profile_name=profile_name)

    def test_given_both_credential_types_available_when_getting_credentials_with_default_settings_then_quilt3_credentials_preferred(
        self,
    ):
        """Given both credential types available, When getting credentials with default settings, Then Quilt3 credentials preferred."""
        # Given: Both Quilt3 and native AWS credentials are available
        with (
            patch('quilt3.logged_in', return_value='https://example.quiltdata.com'),
            patch('quilt3.get_boto3_session') as mock_quilt_session,
            patch('boto3.Session') as mock_boto3_session,
        ):
            mock_quilt_session_obj = Mock()
            mock_quilt_credentials = Mock()
            mock_quilt_session_obj.get_credentials.return_value = mock_quilt_credentials
            mock_quilt_session.return_value = mock_quilt_session_obj

            # When: Getting credentials with default settings
            credentials = get_credentials()

            # Then: Quilt3 credentials are preferred
            assert credentials is mock_quilt_credentials
            mock_quilt_session.assert_called_once()
            mock_boto3_session.assert_not_called()

    def test_given_no_credentials_available_when_getting_credentials_then_auth_error_with_guidance_raised(self):
        """Given no credentials available, When getting credentials, Then AuthError with guidance raised."""
        # Given: No credentials are available
        with (
            patch('quilt3.logged_in', return_value=False),
            patch('boto3.Session') as mock_boto3_session,
        ):
            # Configure boto3.Session to return None credentials
            mock_boto3_session.return_value.get_credentials.return_value = None
            # When/Then: Getting credentials raises AuthError with guidance
            with pytest.raises(AuthError) as exc_info:
                get_credentials()

            error_message = str(exc_info.value)
            assert "credentials" in error_message.lower()
            assert any(term in error_message.lower() for term in ["quilt3", "aws", "configure"])


class TestCredentialValidation:
    """Test credential validation functionality."""

    def test_given_valid_quilt3_credentials_when_validating_then_validation_succeeds_with_quilt3_identity(self):
        """Given valid Quilt3 credentials, When validating, Then validation succeeds with Quilt3 identity."""
        # Given: Valid Quilt3 credentials
        mock_credentials = Mock()
        mock_credentials.access_key = "AKIATEST"
        mock_credentials.secret_key = "secret"
        mock_credentials.token = "token"

        with patch('boto3.Session') as mock_session_class:
            mock_session = Mock()
            mock_sts_client = Mock()
            mock_session.client.return_value = mock_sts_client
            mock_session_class.return_value = mock_session

            mock_sts_client.get_caller_identity.return_value = {
                'Account': '123456789012',
                'Arn': 'arn:aws:sts::123456789012:assumed-role/quilt-role/user',
                'UserId': 'AIDACKCEVSQ6C2EXAMPLE',
            }

            # When: Validating Quilt3 credentials
            result = validate_credentials(mock_credentials, credential_type="quilt3")

            # Then: Validation succeeds with Quilt3 identity
            assert result['valid'] is True
            assert result['credential_type'] == 'quilt3'
            assert 'identity' in result

    def test_given_valid_native_aws_credentials_when_validating_then_validation_succeeds_with_native_aws_identity(
        self,
    ):
        """Given valid native AWS credentials, When validating, Then validation succeeds with native AWS identity."""
        # Given: Valid native AWS credentials
        mock_credentials = Mock()
        mock_credentials.access_key = "AKIATEST"
        mock_credentials.secret_key = "secret"
        mock_credentials.token = None

        with patch('boto3.Session') as mock_session_class:
            mock_session = Mock()
            mock_sts_client = Mock()
            mock_session.client.return_value = mock_sts_client
            mock_session_class.return_value = mock_session

            mock_sts_client.get_caller_identity.return_value = {
                'Account': '123456789012',
                'Arn': 'arn:aws:iam::123456789012:user/test-user',
                'UserId': 'AIDACKCEVSQ6C2EXAMPLE',
            }

            # When: Validating native AWS credentials
            result = validate_credentials(mock_credentials, credential_type="native_aws")

            # Then: Validation succeeds with native AWS identity
            assert result['valid'] is True
            assert result['credential_type'] == 'native_aws'
            assert 'identity' in result

    def test_given_invalid_credentials_when_validating_then_validation_fails_with_credential_type_specific_error(self):
        """Given invalid credentials, When validating, Then validation fails with credential-type-specific error."""
        # Given: Invalid credentials
        mock_credentials = Mock()
        mock_credentials.access_key = "INVALID"
        mock_credentials.secret_key = "invalid"
        mock_credentials.token = None

        with patch('boto3.Session') as mock_session_class:
            mock_session = Mock()
            mock_sts_client = Mock()
            mock_session.client.return_value = mock_sts_client
            mock_session_class.return_value = mock_session

            from botocore.exceptions import ClientError

            mock_sts_client.get_caller_identity.side_effect = ClientError(
                {'Error': {'Code': 'InvalidUserID.NotFound', 'Message': 'Invalid credentials'}}, 'get_caller_identity'
            )

            # When: Validating invalid credentials
            result = validate_credentials(mock_credentials)

            # Then: Validation fails with appropriate error
            assert result['valid'] is False
            assert 'error' in result
            assert 'invalid' in result['error'].lower()

    def test_given_expired_credentials_when_validating_then_validation_fails_with_refresh_guidance(self):
        """Given expired credentials, When validating, Then validation fails with refresh guidance."""
        # Given: Expired credentials
        mock_credentials = Mock()

        with patch('boto3.Session') as mock_session_class:
            mock_session = Mock()
            mock_sts_client = Mock()
            mock_session.client.return_value = mock_sts_client
            mock_session_class.return_value = mock_session

            from botocore.exceptions import ClientError

            mock_sts_client.get_caller_identity.side_effect = ClientError(
                {'Error': {'Code': 'TokenRefreshRequired', 'Message': 'Token has expired'}}, 'get_caller_identity'
            )

            # When: Validating expired credentials
            result = validate_credentials(mock_credentials)

            # Then: Validation fails with refresh guidance
            assert result['valid'] is False
            assert 'refresh' in result.get('guidance', '').lower()


class TestCallerIdentity:
    """Test caller identity retrieval for both session types."""

    def test_given_quilt3_session_when_getting_caller_identity_then_quilt3_identity_returned(self):
        """Given Quilt3 session, When getting caller identity, Then Quilt3 identity returned."""
        # Given: Quilt3 session
        mock_session = Mock()
        mock_sts_client = Mock()
        mock_session.client.return_value = mock_sts_client

        mock_sts_client.get_caller_identity.return_value = {
            'Account': '123456789012',
            'Arn': 'arn:aws:sts::123456789012:assumed-role/quilt-role/user',
            'UserId': 'AIDACKCEVSQ6C2EXAMPLE',
        }

        # When: Getting caller identity
        identity = get_caller_identity(mock_session)

        # Then: Quilt3 identity is returned
        assert identity['account'] == '123456789012'
        assert 'quilt' in identity['arn'].lower()

    def test_given_native_aws_session_when_getting_caller_identity_then_native_identity_returned(self):
        """Given native AWS session, When getting caller identity, Then native identity returned."""
        # Given: Native AWS session
        mock_session = Mock()
        mock_sts_client = Mock()
        mock_session.client.return_value = mock_sts_client

        mock_sts_client.get_caller_identity.return_value = {
            'Account': '123456789012',
            'Arn': 'arn:aws:iam::123456789012:user/test-user',
            'UserId': 'AIDACKCEVSQ6C2EXAMPLE',
        }

        # When: Getting caller identity
        identity = get_caller_identity(mock_session)

        # Then: Native AWS identity is returned
        assert identity['account'] == '123456789012'
        assert 'user/test-user' in identity['arn']

    def test_given_invalid_session_when_getting_caller_identity_then_auth_error_raised(self):
        """Given invalid session, When getting caller identity, Then AuthError raised."""
        # Given: Invalid session
        mock_session = Mock()
        mock_session.client.side_effect = Exception("Invalid session")

        # When/Then: Getting caller identity raises AuthError
        with pytest.raises(AuthError):
            get_caller_identity(mock_session)


class TestAuthenticationStatus:
    """Test authentication status checking."""

    def test_given_active_quilt3_login_when_checking_quilt_authentication_then_true_returned(self):
        """Given active Quilt3 login, When checking Quilt authentication, Then True returned."""
        # Given: Active Quilt3 login
        with patch('quilt3.logged_in', return_value='https://example.quiltdata.com'):
            # When: Checking if Quilt is authenticated
            result = is_quilt_authenticated()

            # Then: True is returned
            assert result is True

    def test_given_no_quilt3_login_when_checking_quilt_authentication_then_false_returned(self):
        """Given no Quilt3 login, When checking Quilt authentication, Then False returned."""
        # Given: No Quilt3 login
        with patch('quilt3.logged_in', return_value=None):
            # When: Checking if Quilt is authenticated
            result = is_quilt_authenticated()

            # Then: False is returned
            assert result is False

    def test_given_quilt3_error_when_checking_quilt_authentication_then_false_returned_gracefully(self):
        """Given Quilt3 error, When checking Quilt authentication, Then False returned gracefully."""
        # Given: Quilt3 raises an error
        with patch('quilt3.logged_in', side_effect=Exception("Quilt3 error")):
            # When: Checking if Quilt is authenticated
            result = is_quilt_authenticated()

            # Then: False is returned gracefully
            assert result is False


class TestCredentialTypeDetection:
    """Test credential type detection."""

    def test_given_quilt3_backed_session_when_getting_credential_type_then_quilt3_returned(self):
        """Given Quilt3-backed session, When getting credential type, Then 'quilt3' returned."""
        # Given: Quilt3-backed session (with session token indicating STS)
        mock_session = Mock()

        with (
            patch('quilt3.logged_in', return_value='https://example.quiltdata.com'),
            patch('quilt3.get_boto3_session', return_value=mock_session),
        ):
            # When: Getting credential type
            cred_type = get_credential_type(mock_session)

            # Then: 'quilt3' is returned
            assert cred_type == 'quilt3'

    def test_given_native_aws_session_when_getting_credential_type_then_native_aws_returned(self):
        """Given native AWS session, When getting credential type, Then 'native_aws' returned."""
        # Given: Native AWS session
        mock_session = Mock()

        with patch('quilt3.logged_in', return_value=None):
            # When: Getting credential type
            cred_type = get_credential_type(mock_session)

            # Then: 'native_aws' is returned
            assert cred_type == 'native_aws'

    def test_given_ambiguous_session_when_getting_credential_type_then_native_aws_returned(self):
        """Given ambiguous session, When getting credential type, Then 'native_aws' returned (fallback)."""
        # Given: Ambiguous session that can't be clearly identified
        mock_session = Mock()

        with patch('quilt3.logged_in', side_effect=Exception("Cannot determine")):
            # When: Getting credential type
            cred_type = get_credential_type(mock_session)

            # Then: 'native_aws' is returned (fallback behavior)
            assert cred_type == 'native_aws'

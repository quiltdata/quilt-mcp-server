"""BDD tests for AWS session management utilities.

These tests follow the Given/When/Then pattern and test behavior, not implementation.
All tests are written to fail initially (RED phase of TDD).
"""

from __future__ import annotations

import os
from unittest.mock import Mock, patch, MagicMock
import pytest

from quilt_mcp.utilities.aws.session import (
    create_session,
    get_session_credentials,
    validate_session,
)


class TestSessionCreation:
    """Test session creation with dual credential support."""

    def test_given_quilt_catalog_login_active_when_creating_session_with_prefer_quilt_true_then_quilt3_backed_session_used(
        self,
    ):
        """Given Quilt catalog login active, When creating session with prefer_quilt=True, Then Quilt3-backed session used."""
        # Given: Quilt3 is logged in and available
        with (
            patch('quilt3.logged_in', return_value='https://example.quiltdata.com'),
            patch('quilt3.get_boto3_session') as mock_get_session,
        ):
            mock_session = Mock()
            mock_get_session.return_value = mock_session

            # When: Creating session with prefer_quilt=True (default)
            session = create_session(prefer_quilt=True)

            # Then: Quilt3-backed session is used
            assert session == mock_session
            mock_get_session.assert_called_once()

    def test_given_native_aws_credentials_configured_when_creating_session_with_prefer_quilt_false_then_standard_boto3_session_used(
        self,
    ):
        """Given native AWS credentials configured, When creating session with prefer_quilt=False, Then standard boto3 session used."""
        # Given: Native AWS credentials are available
        with patch('boto3.Session') as mock_boto3_session:
            mock_session = Mock()
            mock_boto3_session.return_value = mock_session

            # When: Creating session with prefer_quilt=False
            session = create_session(prefer_quilt=False)

            # Then: Standard boto3 session is used
            assert session == mock_session
            mock_boto3_session.assert_called_once()

    def test_given_both_credential_types_available_when_creating_session_with_default_settings_then_quilt3_session_preferred(
        self,
    ):
        """Given both credential types available, When creating session with default settings, Then Quilt3 session preferred."""
        # Given: Both Quilt3 and native AWS credentials are available
        with (
            patch('quilt3.logged_in', return_value='https://example.quiltdata.com'),
            patch('quilt3.get_boto3_session') as mock_quilt_session,
            patch('boto3.Session') as mock_boto3_session,
        ):
            mock_quilt_session_obj = Mock()
            mock_quilt_session.return_value = mock_quilt_session_obj

            # When: Creating session with default settings (prefer_quilt defaults to True)
            session = create_session()

            # Then: Quilt3 session is preferred
            assert session == mock_quilt_session_obj
            mock_quilt_session.assert_called_once()
            mock_boto3_session.assert_not_called()

    def test_given_quilt_disable_quilt3_session_env_var_when_creating_session_then_native_aws_credentials_used(self):
        """Given QUILT_DISABLE_QUILT3_SESSION=1 environment variable, When creating session, Then native AWS credentials used."""
        # Given: Environment variable disables Quilt3 sessions
        with (
            patch.dict(os.environ, {'QUILT_DISABLE_QUILT3_SESSION': '1'}),
            patch('quilt3.logged_in', return_value='https://example.quiltdata.com'),
            patch('boto3.Session') as mock_boto3_session,
        ):
            mock_session = Mock()
            mock_boto3_session.return_value = mock_session

            # When: Creating session (even with prefer_quilt=True)
            session = create_session(prefer_quilt=True)

            # Then: Native AWS credentials are used despite preference
            assert session == mock_session
            mock_boto3_session.assert_called_once()

    def test_given_aws_profile_name_provided_when_creating_session_then_session_uses_specified_profile_native_aws_only(
        self,
    ):
        """Given AWS profile name provided, When creating session, Then session uses specified profile (native AWS only)."""
        # Given: AWS profile name is provided
        profile_name = 'test-profile'

        with patch('boto3.Session') as mock_boto3_session:
            mock_session = Mock()
            mock_boto3_session.return_value = mock_session

            # When: Creating session with profile name
            session = create_session(profile_name=profile_name)

            # Then: Native AWS session is created with specified profile
            assert session == mock_session
            mock_boto3_session.assert_called_once_with(profile_name=profile_name, region_name=None)

    def test_given_invalid_quilt3_credentials_when_creating_session_then_fallback_to_native_aws_credentials_attempted(
        self,
    ):
        """Given invalid Quilt3 credentials, When creating session, Then fallback to native AWS credentials attempted."""
        # Given: Quilt3 credentials are invalid/expired
        with patch('quilt3.logged_in', return_value=None), patch('boto3.Session') as mock_boto3_session:
            mock_session = Mock()
            mock_boto3_session.return_value = mock_session

            # When: Creating session with prefer_quilt=True
            session = create_session(prefer_quilt=True)

            # Then: Fallback to native AWS credentials occurs
            assert session == mock_session
            mock_boto3_session.assert_called_once()

    def test_given_no_credentials_configured_when_creating_session_then_appropriate_error_with_setup_guidance_for_both_credential_types(
        self,
    ):
        """Given no credentials configured, When creating session, Then appropriate error with setup guidance for both credential types."""
        # Given: No credentials are available
        with (
            patch('quilt3.logged_in', return_value=None),
            patch('boto3.Session', side_effect=Exception("No credentials found")),
        ):
            # When/Then: Creating session raises error with guidance
            with pytest.raises(Exception) as exc_info:
                create_session()

            error_message = str(exc_info.value)
            assert "credentials" in error_message.lower()
            assert "quilt3" in error_message.lower() or "aws" in error_message.lower()

    def test_given_session_timeout_when_validating_session_then_session_refresh_is_handled_appropriately_for_session_type(
        self,
    ):
        """Given session timeout, When validating session, Then session refresh is handled appropriately for session type."""
        # Given: A session that has timed out
        mock_session = Mock()
        mock_session.client.side_effect = Exception("Token expired")

        # When/Then: Validating session handles timeout appropriately
        result = validate_session(mock_session)

        # Then: Validation should indicate session needs refresh
        assert result is False or "expired" in str(result).lower()


class TestSessionCredentials:
    """Test session credential extraction and validation."""

    def test_given_valid_quilt3_session_when_getting_session_credentials_then_quilt3_credentials_returned(self):
        """Given valid Quilt3 session, When getting session credentials, Then Quilt3 credentials returned."""
        # Given: A valid Quilt3-backed session
        mock_session = Mock()
        mock_credentials = Mock()
        mock_session.get_credentials.return_value = mock_credentials

        # When: Getting session credentials
        credentials = get_session_credentials(mock_session)

        # Then: Credentials are returned
        assert credentials == mock_credentials
        mock_session.get_credentials.assert_called_once()

    def test_given_valid_native_aws_session_when_getting_session_credentials_then_native_credentials_returned(self):
        """Given valid native AWS session, When getting session credentials, Then native credentials returned."""
        # Given: A valid native AWS session
        mock_session = Mock()
        mock_credentials = Mock()
        mock_session.get_credentials.return_value = mock_credentials

        # When: Getting session credentials
        credentials = get_session_credentials(mock_session)

        # Then: Native AWS credentials are returned
        assert credentials == mock_credentials
        mock_session.get_credentials.assert_called_once()


class TestSessionValidation:
    """Test session validation functionality."""

    def test_given_valid_quilt3_session_when_validating_session_then_validation_succeeds(self):
        """Given valid Quilt3 session, When validating session, Then validation succeeds."""
        # Given: A valid Quilt3 session
        mock_session = Mock()
        mock_sts_client = Mock()
        mock_session.client.return_value = mock_sts_client
        mock_sts_client.get_caller_identity.return_value = {
            'Account': '123456789012',
            'Arn': 'arn:aws:sts::123456789012:assumed-role/test-role/test-user',
            'UserId': 'AIDACKCEVSQ6C2EXAMPLE',
        }

        # When: Validating the session
        result = validate_session(mock_session)

        # Then: Validation succeeds
        assert result is True
        mock_session.client.assert_called_once_with('sts')
        mock_sts_client.get_caller_identity.assert_called_once()

    def test_given_invalid_session_when_validating_session_then_validation_fails_with_clear_error(self):
        """Given invalid session, When validating session, Then validation fails with clear error."""
        # Given: An invalid session
        mock_session = Mock()
        mock_session.client.side_effect = Exception("Invalid credentials")

        # When: Validating the session
        result = validate_session(mock_session)

        # Then: Validation fails with clear error
        assert result is False

#!/usr/bin/env python3
"""
Tests for post_release_status.py script.

Tests both the new release notes update functionality and existing PR comment functionality.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock, call
import requests
import sys
import os
from io import StringIO

# Add scripts directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import post_release_status


class TestGenerateReleaseComment:
    """Test release comment generation."""

    def test_generate_production_release_comment(self):
        """Test generating comment for production release."""
        version = "1.0.0"
        release_url = "https://github.com/owner/repo/releases/tag/v1.0.0"
        pypi_url = "https://pypi.org/project/quilt-mcp-server/1.0.0/"
        docker_image = "123456789.dkr.ecr.us-east-1.amazonaws.com/quilt-mcp-server:1.0.0"

        comment = post_release_status.generate_release_comment(
            version=version,
            release_url=release_url,
            pypi_url=pypi_url,
            docker_image=docker_image
        )

        # Verify structure and content
        assert "## 🚀 Release Status for v1.0.0" in comment
        assert "### 📦 Package Locations" in comment
        assert release_url in comment
        assert pypi_url in comment
        assert "### 🐳 Docker Pull Command" in comment
        assert f"docker pull {docker_image}" in comment
        assert "### 📥 Installation" in comment
        assert "pip install quilt-mcp-server==1.0.0" in comment
        assert "uv add quilt-mcp-server==1.0.0" in comment
        # Should NOT contain TestPyPI instructions
        assert "test.pypi.org" not in comment

    def test_generate_development_release_comment(self):
        """Test generating comment for development release."""
        version = "1.0.0-dev-20250101"
        release_url = "https://github.com/owner/repo/releases/tag/v1.0.0-dev-20250101"
        pypi_url = "https://test.pypi.org/project/quilt-mcp-server/1.0.0-dev-20250101/"
        docker_image = None  # Dev releases might not have Docker

        comment = post_release_status.generate_release_comment(
            version=version,
            release_url=release_url,
            pypi_url=pypi_url,
            docker_image=docker_image
        )

        # Verify development-specific content
        assert "## 🚀 Release Status for v1.0.0-dev-20250101" in comment
        assert release_url in comment
        assert pypi_url in comment
        assert "### 🐳 Docker Pull Command" not in comment  # No docker section
        assert "pip install -i https://test.pypi.org/simple/ quilt-mcp-server==1.0.0-dev-20250101" in comment
        assert "uv add --index https://test.pypi.org/simple/ quilt-mcp-server==1.0.0-dev-20250101" in comment

    def test_generate_comment_with_unknown_docker_image(self):
        """Test graceful handling of unknown/placeholder Docker image."""
        version = "1.0.0"
        release_url = "https://github.com/owner/repo/releases/tag/v1.0.0"
        pypi_url = "https://pypi.org/project/quilt-mcp-server/1.0.0/"
        docker_image = "unknown/quilt-mcp-server:1.0.0"  # Placeholder value

        comment = post_release_status.generate_release_comment(
            version=version,
            release_url=release_url,
            pypi_url=pypi_url,
            docker_image=docker_image
        )

        # Should not include Docker section for unknown image
        assert "### 🐳 Docker Pull Command" not in comment
        assert docker_image not in comment


class TestUpdateReleaseNotes:
    """Test GitHub release notes update functionality (new primary feature)."""

    @patch('post_release_status.requests')
    def test_update_release_notes_success(self, mock_requests):
        """Test successful release notes update."""
        # Mock GET request to fetch current release
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {
            "body": "## What's Changed\n\n* Existing release notes"
        }
        mock_get_response.raise_for_status.return_value = None

        # Mock PATCH request to update release
        mock_patch_response = Mock()
        mock_patch_response.status_code = 200
        mock_patch_response.raise_for_status.return_value = None

        mock_requests.get.return_value = mock_get_response
        mock_requests.patch.return_value = mock_patch_response

        github_token = "test-token"
        repo = "owner/repo"
        release_id = "12345"
        additional_content = "\n---\n\n## 📦 Release Status\n\nTest content"

        result = post_release_status.update_release_notes(
            github_token=github_token,
            repo=repo,
            release_id=release_id,
            additional_content=additional_content
        )

        assert result is True

        # Verify GET request
        mock_requests.get.assert_called_once_with(
            f"https://api.github.com/repos/{repo}/releases/{release_id}",
            headers={
                "Authorization": f"token {github_token}",
                "Accept": "application/vnd.github.v3+json"
            }
        )

        # Verify PATCH request
        expected_body = "## What's Changed\n\n* Existing release notes\n---\n\n## 📦 Release Status\n\nTest content"
        mock_requests.patch.assert_called_once_with(
            f"https://api.github.com/repos/{repo}/releases/{release_id}",
            headers={
                "Authorization": f"token {github_token}",
                "Accept": "application/vnd.github.v3+json"
            },
            json={"body": expected_body}
        )

    @patch('post_release_status.requests')
    def test_update_release_notes_get_failure(self, mock_requests):
        """Test release notes update when GET fails."""
        mock_get_response = Mock()
        mock_get_response.raise_for_status.side_effect = requests.RequestException("Not found")
        mock_requests.get.return_value = mock_get_response

        result = post_release_status.update_release_notes(
            github_token="test-token",
            repo="owner/repo",
            release_id="12345",
            additional_content="test content"
        )

        assert result is False
        # Should not attempt PATCH if GET fails
        mock_requests.patch.assert_not_called()

    @patch('post_release_status.requests')
    def test_update_release_notes_patch_failure(self, mock_requests):
        """Test release notes update when PATCH fails."""
        # Mock successful GET
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {"body": "existing"}
        mock_get_response.raise_for_status.return_value = None

        # Mock failed PATCH
        mock_patch_response = Mock()
        mock_patch_response.raise_for_status.side_effect = requests.RequestException("Update failed")

        mock_requests.get.return_value = mock_get_response
        mock_requests.patch.return_value = mock_patch_response

        result = post_release_status.update_release_notes(
            github_token="test-token",
            repo="owner/repo",
            release_id="12345",
            additional_content="test content"
        )

        assert result is False

    @patch('post_release_status.requests')
    def test_update_release_notes_empty_existing_body(self, mock_requests):
        """Test release notes update with empty existing body."""
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {"body": None}  # GitHub can return null
        mock_get_response.raise_for_status.return_value = None

        mock_patch_response = Mock()
        mock_patch_response.status_code = 200
        mock_patch_response.raise_for_status.return_value = None

        mock_requests.get.return_value = mock_get_response
        mock_requests.patch.return_value = mock_patch_response

        additional_content = "## New Content"
        result = post_release_status.update_release_notes(
            github_token="test-token",
            repo="owner/repo",
            release_id="12345",
            additional_content=additional_content
        )

        assert result is True
        # Should handle None body gracefully
        mock_requests.patch.assert_called_once()
        call_args = mock_requests.patch.call_args
        assert call_args[1]["json"]["body"] == additional_content


class TestFindPrForSha:
    """Test PR finding functionality (refactored from find_pr_for_tag)."""

    @patch('post_release_status.requests')
    def test_find_pr_for_sha_success(self, mock_requests):
        """Test successful PR finding."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"number": 123, "title": "Test PR"},
            {"number": 456, "title": "Another PR"}
        ]
        mock_response.raise_for_status.return_value = None
        mock_requests.get.return_value = mock_response

        pr_number = post_release_status.find_pr_for_sha(
            github_token="test-token",
            repo="owner/repo",
            sha="abc123def456"
        )

        assert pr_number == 123  # Should return first (most recent) PR

        mock_requests.get.assert_called_once_with(
            "https://api.github.com/repos/owner/repo/commits/abc123def456/pulls",
            headers={
                "Authorization": "token test-token",
                "Accept": "application/vnd.github.v3+json"
            }
        )

    @patch('post_release_status.requests')
    def test_find_pr_for_sha_no_prs(self, mock_requests):
        """Test PR finding when no PRs exist."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_response.raise_for_status.return_value = None
        mock_requests.get.return_value = mock_response

        pr_number = post_release_status.find_pr_for_sha(
            github_token="test-token",
            repo="owner/repo",
            sha="abc123def456"
        )

        assert pr_number is None

    @patch('post_release_status.requests')
    def test_find_pr_for_sha_api_error(self, mock_requests):
        """Test PR finding when API returns error."""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.RequestException("API Error")
        mock_requests.get.return_value = mock_response

        pr_number = post_release_status.find_pr_for_sha(
            github_token="test-token",
            repo="owner/repo",
            sha="abc123def456"
        )

        assert pr_number is None


class TestIntegrationScenarios:
    """Test complete workflow scenarios."""

    def test_main_with_release_id_success(self):
        """Test main function with release ID - successful path."""
        with patch('post_release_status.update_release_notes') as mock_update_notes, \
             patch('post_release_status.find_pr_for_sha') as mock_find_pr, \
             patch('post_release_status.post_comment_to_pr') as mock_post_comment:

            mock_update_notes.return_value = True
            mock_find_pr.return_value = 123
            mock_post_comment.return_value = True

            test_args = [
                "post_release_status.py",
                "--version", "1.0.0",
                "--release-url", "https://github.com/owner/repo/releases/tag/v1.0.0",
                "--pypi-url", "https://pypi.org/project/quilt-mcp-server/1.0.0/",
                "--docker-image", "123456789.dkr.ecr.us-east-1.amazonaws.com/quilt-mcp-server:1.0.0",
                "--release-id", "12345",
                "--sha", "abc123def456",
                "--repo", "owner/repo",
                "--github-token", "test-token"
            ]

            with patch.object(sys, 'argv', test_args):
                result = post_release_status.main()

            assert result == 0
            mock_update_notes.assert_called_once()
            mock_find_pr.assert_called_once_with(
                github_token="test-token",
                repo="owner/repo",
                sha="abc123def456"
            )
            mock_post_comment.assert_called_once()

    def test_main_release_notes_failure_should_fail(self):
        """Test main function fails when release notes update fails."""
        with patch('post_release_status.update_release_notes') as mock_update_notes, \
             patch('post_release_status.find_pr_for_sha') as mock_find_pr:

            mock_update_notes.return_value = False  # Release notes update failed
            mock_find_pr.return_value = 123

            test_args = [
                "post_release_status.py",
                "--version", "1.0.0",
                "--release-url", "https://github.com/owner/repo/releases/tag/v1.0.0",
                "--pypi-url", "https://pypi.org/project/quilt-mcp-server/1.0.0/",
                "--release-id", "12345",
                "--repo", "owner/repo",
                "--github-token", "test-token"
            ]

            with patch.object(sys, 'argv', test_args):
                result = post_release_status.main()

            assert result == 1  # Should fail the workflow
            mock_update_notes.assert_called_once()

    def test_main_pr_comment_failure_should_continue(self):
        """Test main function continues when PR comment fails but release notes succeed."""
        with patch('post_release_status.update_release_notes') as mock_update_notes, \
             patch('post_release_status.find_pr_for_sha') as mock_find_pr, \
             patch('post_release_status.post_comment_to_pr') as mock_post_comment:

            mock_update_notes.return_value = True  # Release notes update succeeded
            mock_find_pr.return_value = 123
            mock_post_comment.return_value = False  # PR comment failed

            test_args = [
                "post_release_status.py",
                "--version", "1.0.0",
                "--release-url", "https://github.com/owner/repo/releases/tag/v1.0.0",
                "--pypi-url", "https://pypi.org/project/quilt-mcp-server/1.0.0/",
                "--release-id", "12345",
                "--sha", "abc123def456",
                "--repo", "owner/repo",
                "--github-token", "test-token"
            ]

            with patch.object(sys, 'argv', test_args):
                result = post_release_status.main()

            assert result == 0  # Should NOT fail the workflow
            mock_update_notes.assert_called_once()
            mock_post_comment.assert_called_once()

    def test_main_no_release_id_legacy_behavior(self):
        """Test main function falls back to legacy PR-only behavior without release-id."""
        with patch('post_release_status.find_pr_for_sha') as mock_find_pr:
            mock_find_pr.return_value = None  # No PR found

            test_args = [
                "post_release_status.py",
                "--version", "1.0.0",
                "--release-url", "https://github.com/owner/repo/releases/tag/v1.0.0",
                "--pypi-url", "https://pypi.org/project/quilt-mcp-server/1.0.0/",
                "--sha", "abc123def456",
                "--repo", "owner/repo",
                "--github-token", "test-token"
                # Note: no --release-id provided
            ]

            with patch.object(sys, 'argv', test_args):
                with patch('sys.stdout', new_callable=StringIO) as mock_stdout, \
                     patch('sys.stderr', new_callable=StringIO):
                    result = post_release_status.main()

            assert result == 0  # Should not fail
            output = mock_stdout.getvalue()
            assert "Release Status:" in output

    def test_main_dry_run_mode(self):
        """Test main function in dry-run mode."""
        test_args = [
            "post_release_status.py",
            "--version", "1.0.0",
            "--release-url", "https://github.com/owner/repo/releases/tag/v1.0.0",
            "--pypi-url", "https://pypi.org/project/quilt-mcp-server/1.0.0/",
            "--dry-run"
        ]

        with patch.object(sys, 'argv', test_args):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                result = post_release_status.main()

        assert result == 0
        output = mock_stdout.getvalue()
        assert "=== DRY RUN - Comment Body ===" in output
        assert "## 🚀 Release Status for v1.0.0" in output

    def test_legacy_find_pr_for_tag_alias(self):
        """Test that find_pr_for_tag is an alias for find_pr_for_sha."""
        with patch('post_release_status.find_pr_for_sha') as mock_find_pr:
            mock_find_pr.return_value = 456

            result = post_release_status.find_pr_for_tag(
                github_token="test-token",
                repo="owner/repo",
                sha="abc123"
            )

            assert result == 456
            mock_find_pr.assert_called_once_with(
                github_token="test-token",
                repo="owner/repo",
                sha="abc123"
            )
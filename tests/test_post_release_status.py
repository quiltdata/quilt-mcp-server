#!/usr/bin/env python3
"""Tests for post_release_status.py script with pure function design."""

import sys
import os
from unittest import TestCase
from unittest.mock import Mock, patch, MagicMock, call

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import post_release_status


class TestGenerateReleaseComment(TestCase):
    """Test the generate_release_comment function."""

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
            docker_image=docker_image,
            is_production=True,
            package_name="quilt-mcp-server",
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
            docker_image=docker_image,
            is_production=False,
            package_name="quilt-mcp-server",
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
            docker_image=docker_image,
            is_production=True,
            package_name="quilt-mcp-server",
        )

        # Should not include Docker section for unknown image
        assert "### 🐳 Docker Pull Command" not in comment
        assert docker_image not in comment


class TestUpdateReleaseNotes(TestCase):
    """Test GitHub release notes update functionality."""

    @patch('builtins.__import__')
    def test_update_release_notes_success(self, mock_import):
        """Test successful release notes update."""
        # Mock the requests module
        mock_requests = MagicMock()
        mock_import.return_value = mock_requests

        # Mock GET response
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {"body": "## What's Changed\n\n* Existing release notes"}
        mock_get_response.raise_for_status.return_value = None

        # Mock PATCH response
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
            github_token=github_token, repo=repo, release_id=release_id, additional_content=additional_content
        )

        assert result is True

        # Verify the API calls
        mock_requests.get.assert_called_once()
        mock_requests.patch.assert_called_once()


class TestFindPrForSha(TestCase):
    """Test PR finding functionality."""

    @patch('builtins.__import__')
    def test_find_pr_for_sha_success(self, mock_import):
        """Test finding PR from SHA successfully."""
        # Mock the requests module
        mock_requests = MagicMock()
        mock_import.return_value = mock_requests

        # Mock response with PR data
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{"number": 42, "title": "Test PR"}]
        mock_response.raise_for_status.return_value = None

        mock_requests.get.return_value = mock_response

        github_token = "test-token"
        repo = "owner/repo"
        sha = "abc123"

        result = post_release_status.find_pr_for_sha(github_token=github_token, repo=repo, sha=sha)

        assert result == 42


class TestPostCommentToPR(TestCase):
    """Test PR comment posting functionality."""

    @patch('builtins.__import__')
    def test_post_comment_success(self, mock_import):
        """Test posting comment to PR successfully."""
        # Mock the requests module
        mock_requests = MagicMock()
        mock_import.return_value = mock_requests

        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.raise_for_status.return_value = None

        mock_requests.post.return_value = mock_response

        github_token = "test-token"
        repo = "owner/repo"
        pr_number = 42
        comment_body = "Test comment"

        result = post_release_status.post_comment_to_pr(
            github_token=github_token, repo=repo, pr_number=pr_number, comment_body=comment_body
        )

        assert result is True


class TestMainFunction(TestCase):
    """Test the main function with pure function design."""

    @patch(
        'sys.argv',
        [
            'post_release_status.py',
            '--version',
            '1.0.0',
            '--release-url',
            'https://github.com/owner/repo/releases/tag/v1.0.0',
            '--pypi-url',
            'https://pypi.org/project/quilt-mcp-server/1.0.0/',
            '--docker-image',
            'registry/image:1.0.0',
            '--release-id',
            '12345',
            '--sha',
            'abc123',
            '--repo',
            'owner/repo',
            '--github-token',
            'test-token',
            '--is-production',
            'true',
            '--package-name',
            'quilt-mcp-server',
        ],
    )
    @patch('post_release_status.update_release_notes')
    @patch('post_release_status.find_pr_for_sha')
    @patch('post_release_status.post_comment_to_pr')
    def test_main_with_all_parameters(self, mock_post_comment, mock_find_pr, mock_update_notes):
        """Test main function with all parameters explicitly passed."""
        mock_update_notes.return_value = True
        mock_find_pr.return_value = 42
        mock_post_comment.return_value = True

        # Run main
        result = post_release_status.main()

        assert result == 0
        mock_update_notes.assert_called_once()
        mock_find_pr.assert_called_once()
        mock_post_comment.assert_called_once()

    @patch(
        'sys.argv',
        [
            'post_release_status.py',
            '--version',
            '1.0.0',
            '--release-url',
            'https://github.com/owner/repo/releases/tag/v1.0.0',
            '--pypi-url',
            'https://pypi.org/project/quilt-mcp-server/1.0.0/',
            '--repo',
            'owner/repo',
            '--github-token',
            'test-token',
            '--dry-run',
        ],
    )
    def test_main_dry_run(self):
        """Test dry run mode."""
        # Capture stdout
        with patch('builtins.print') as mock_print:
            result = post_release_status.main()

        assert result == 0
        # Check that dry run output was printed
        mock_print.assert_called()

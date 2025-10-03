"""Stateless packaging tool tests ensuring token enforcement and client usage."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Dict
from unittest.mock import patch

import pytest

from quilt_mcp.runtime import request_context
from quilt_mcp.tools import packaging


@contextmanager
def runtime_token(token: str | None):
    with request_context(token, metadata={"session_id": "session"} if token else None):
        yield


@pytest.fixture
def test_token():
    """Get test token from environment."""
    token = os.getenv("QUILT_TEST_TOKEN")
    if not token:
        pytest.skip("QUILT_TEST_TOKEN not set - skipping tests requiring authentication")
    return token


@pytest.fixture
def catalog_url(monkeypatch):
    """Set catalog URL to demo."""
    monkeypatch.setenv("QUILT_CATALOG_URL", "https://demo.quiltdata.com")
    return "https://demo.quiltdata.com"


class TestPackagingCoreActions:
    """Test core packaging actions (browse and create)."""

    def test_discovery_mode_no_action(self):
        """Test discovery mode returns module info (no auth needed)."""
        result = packaging.packaging()

        assert result.get("module") == "packaging"
        # discover and list removed - use search instead
        assert "discover" not in result.get("actions", [])
        assert "list" not in result.get("actions", [])
        # Core actions should be present
        assert "browse" in result.get("actions", [])
        assert "create" in result.get("actions", [])
        assert "metadata_templates" in result.get("actions", [])
        # Should have note about using search
        assert "note" in result
        assert "search" in result["note"].lower()


class TestPackagingMetadataTemplates:
    """Test metadata templates functionality."""

    def test_metadata_templates_list(self):
        """Test listing metadata templates."""
        result = packaging.packaging(action="metadata_templates")

        assert result["success"] is True
        assert "templates" in result
        assert isinstance(result["templates"], dict)
        
        # Should have standard templates
        assert "standard" in result["templates"]
        assert "dataset" in result["templates"]
        assert "model" in result["templates"]

    def test_get_metadata_template_standard(self):
        """Test getting standard metadata template."""
        result = packaging.packaging(action="get_template", params={"template_name": "standard"})

        assert result["success"] is True
        assert "template" in result
        assert result["template"]["description"] == "Standard package metadata template"
        assert "fields" in result["template"]

    def test_get_metadata_template_dataset(self):
        """Test getting dataset metadata template."""
        result = packaging.packaging(action="get_template", params={"template_name": "dataset"})

        assert result["success"] is True
        assert "template" in result
        assert result["template"]["description"] == "Dataset package metadata template"
        assert "fields" in result["template"]

    def test_get_metadata_template_invalid(self):
        """Test getting invalid metadata template."""
        result = packaging.packaging(action="get_template", params={"template_name": "invalid"})

        assert result["success"] is False
        assert "unknown" in result["error"].lower()


class TestPackagingValidation:
    """Test package validation functionality."""

    def test_validate_package_name_valid(self):
        """Test valid package name validation."""
        is_valid, error = packaging._validate_package_name("namespace/packagename")
        assert is_valid is True
        assert error is None

    def test_validate_package_name_invalid_empty(self):
        """Test invalid empty package name."""
        is_valid, error = packaging._validate_package_name("")
        assert is_valid is False
        assert "required" in error.lower()

    def test_validate_package_name_invalid_format(self):
        """Test invalid package name format."""
        is_valid, error = packaging._validate_package_name("invalid-name")
        assert is_valid is False
        assert "invalid" in error.lower()


class TestPackagingHelpers:
    """Test helper functions."""

    def test_normalize_registry_s3_uri(self):
        """Test S3 URI normalization."""
        result = packaging._normalize_registry("s3://my-bucket")
        assert result == "s3://my-bucket"

    def test_normalize_registry_bucket_name(self):
        """Test bucket name normalization."""
        result = packaging._normalize_registry("my-bucket")
        assert result == "s3://my-bucket"

    def test_normalize_registry_http_url(self):
        """Test HTTP URL normalization."""
        result = packaging._normalize_registry("https://example.com")
        assert result == "https://example.com"

    def test_get_file_extension(self):
        """Test file extension extraction."""
        assert packaging._get_file_extension("file.txt") == "txt"
        assert packaging._get_file_extension("file.tar.gz") == "gz"
        assert packaging._get_file_extension("file") == ""

    def test_organize_file_path_with_extension(self):
        """Test file path organization with known extension."""
        result = packaging._organize_file_path("data.csv", auto_organize=True)
        assert result == "data/processed/data.csv"

    def test_organize_file_path_without_organization(self):
        """Test file path organization disabled."""
        result = packaging._organize_file_path("data.csv", auto_organize=False)
        assert result == "data.csv"

    def test_organize_file_path_unknown_extension(self):
        """Test file path organization with unknown extension."""
        result = packaging._organize_file_path("data.xyz", auto_organize=True)
        assert result == "data.xyz"


class TestPackagingErrorHandling:
    """Test error handling for invalid inputs."""

    def test_invalid_action(self, test_token, catalog_url):
        """Test invalid action returns error."""
        with request_context(test_token, metadata={"path": "/packaging"}):
            result = packaging.packaging(action="totally_invalid_action")

        assert result["success"] is False
        assert "unknown" in result["error"].lower()

    def test_missing_required_params(self, test_token, catalog_url):
        """Test missing required parameters."""
        with request_context(test_token, metadata={"path": "/packaging"}):
            result = packaging.packaging(action="browse", params={})

        assert result["success"] is False
        # The error will be about GraphQL failure, not missing params, since we pass None as name
        assert "failed" in result["error"].lower()

    def test_create_propagates_catalog_errors(self, monkeypatch, catalog_url):
        """Ensure catalog failures bubble up without reporting success."""
        from quilt_mcp.clients import catalog as catalog_client

        captured: dict[str, object] = {}

        def fake_package_create(**kwargs):
            captured.update(kwargs)
            return {
                "success": False,
                "error": "Operation failed: Invalid package name: jump-csv-data.",
                "error_type": "QuiltException",
            }

        monkeypatch.setattr(catalog_client, "catalog_package_create", fake_package_create)

        with request_context("token-123", metadata={"path": "/packaging"}):
            result = packaging.packaging(
                action="create",
                params={
                    "name": "demo-team/jump-csv-data",
                    "files": ["s3://demo-bucket/path/data.csv"],
                    "description": "Demo dataset",
                },
            )

        assert result["success"] is False
        assert "invalid package name" in result["error"].lower()
        assert captured["package_name"] == "demo-team/jump-csv-data"
        assert captured["s3_uris"] == ["s3://demo-bucket/path/data.csv"]
        assert captured["flatten"] is True


class TestPackagingMetadataDefaults:
    """Test automatic metadata generation for packaging."""

    @patch("quilt_mcp.tools.packaging.catalog_client.catalog_package_create")
    @patch("quilt_mcp.tools.packaging.catalog_client.catalog_packages_list")
    def test_auto_metadata_generation(self, mock_packages_list, mock_package_create, test_token, catalog_url):
        mock_packages_list.return_value = [
            "demo-team/existing-analysis",
            "demo-team/cell-data",
        ]

        captured_kwargs: Dict[str, Any] = {}

        def fake_package_create(**kwargs):
            captured_kwargs.update(kwargs)
            return {
                "success": True,
                "package": {"bucket": "quilt-sandbox-bucket", "name": kwargs["package_name"]},
                "revision": {"hash": "abc123"},
                "message": "created",
            }

        mock_package_create.side_effect = fake_package_create

        with request_context(test_token, metadata={"path": "/packaging"}):
            result = packaging.package_create(
                name="demo-team/new-dataset",
                files=[
                    "s3://quilt-sandbox-bucket/data/file1.csv",
                    "s3://quilt-sandbox-bucket/data/file2.tsv",
                ],
            )

        metadata_sent = captured_kwargs["metadata"]
        assert sorted(metadata_sent.get("file_extensions", [])) == ["csv", "tsv"]
        assert metadata_sent.get("file_counts_by_extension", {}).get("csv") == 1
        assert "tags" in metadata_sent and metadata_sent["tags"]
        assert metadata_sent.get("source_buckets") == ["quilt-sandbox-bucket"]
        assert result["warnings"]
        assert result.get("navigation", {}).get("tool") == "navigate"
        assert result["navigation"]["params"]["route"]["params"]["bucket"] == "quilt-sandbox-bucket"
        assert result["navigation"]["params"]["route"]["params"]["name"] == "demo-team/new-dataset"

class TestPackagingIntegration:
    """Test integration with real catalog (if token available)."""

    def test_package_browse_real(self, test_token, catalog_url):
        """Test browsing a real package if available."""
        with request_context(test_token, metadata={"path": "/packaging"}):
            # First try to discover packages to see if any exist
            discover_result = packaging.packaging(action="discover")
            
            if discover_result.get("success") and discover_result.get("total_packages", 0) > 0:
                # If packages exist, try to browse the first one
                packages_list = discover_result.get("packages", [])
                if packages_list:
                    first_package = packages_list[0]
                    package_name = first_package.get("name")
                    
                    if package_name:
                        browse_result = packaging.packaging(
                            action="browse", 
                            params={"name": package_name}
                        )
                        
                        # Should succeed or fail gracefully
                        assert isinstance(browse_result, dict)
                        assert "success" in browse_result

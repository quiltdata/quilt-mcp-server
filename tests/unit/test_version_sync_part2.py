"""
BDD tests for version synchronization between pyproject.toml and manifest.json.

Tests the behavioral specifications from spec/a03-release-version.md.
"""

import json
import tempfile
import tomllib
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.version_sync import (
    read_project_version,
    generate_manifest_from_template,
    check_version_sync_required,
    sync_versions,
)


class TestBuildIntegration:
    """BS-4: Build Integration - Given pyproject.toml version is "1.2.3" and manifest.json template exists, when I run the build process, then manifest.json should be generated with version "1.2.3" and build should succeed."""

    def test_sync_versions_end_to_end_process(self):
        """Should read pyproject.toml, process template, and generate correct manifest.json."""
        pyproject_content = """
[project]
name = "integration-test"
version = "3.0.0-beta.1"
description = "Integration test project"
"""

        template_content = """
{
  "manifest_version": "0.1",
  "name": "integration-extension",
  "version": "{{ version }}",
  "description": "Integration test extension"
}
"""

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            pyproject_path = temp_path / "pyproject.toml"
            template_path = temp_path / "manifest.json.j2"
            manifest_path = temp_path / "manifest.json"

            # Create input files
            pyproject_path.write_text(pyproject_content)
            template_path.write_text(template_content)

            # Run the sync process
            sync_versions(
                pyproject_path=pyproject_path,
                template_path=template_path,
                manifest_path=manifest_path,
            )

            # Verify the result
            assert manifest_path.exists()

            with open(manifest_path, "r") as f:
                manifest = json.load(f)

            assert manifest["version"] == "3.0.0-beta.1"
            assert manifest["name"] == "integration-extension"
            assert manifest["manifest_version"] == "0.1"

    def test_sync_versions_with_real_manifest_template_structure(self):
        """Should handle the actual manifest.json structure from the project."""
        pyproject_content = """
[project]
name = "quilt-mcp-server"
version = "0.5.7"
description = "Secure MCP server for accessing Quilt data with JWT authentication"
"""

        # Based on the actual manifest.json structure
        template_content = """
{
  "manifest_version": "0.1",
  "name": "quilt-mcp",
  "version": "{{ version }}",
  "description": "Access Quilt data packages through Claude Desktop",
  "author": {
    "name": "Quilt Data, Inc.",
    "email": "support@quiltdata.com"
  },
  "license": "Apache-2.0",
  "repository": {
    "type": "git",
    "url": "https://github.com/quiltdata/quilt-mcp-server"
  },
  "icon": "icon.png",
  "server": {
    "type": "binary",
    "entry_point": "uvx",
    "mcp_config": {
      "command": "uvx",
      "args": ["quilt-mcp"],
      "env": {
        "PYTHONNOUSERSITE": "1",
        "FASTMCP_TRANSPORT": "stdio"
      }
    }
  },
  "user_config": {
    "catalog_domain": {
      "type": "string",
      "title": "Quilt Catalog Domain",
      "description": "Your Quilt catalog's DNS name (not the URL)",
      "required": true
    },
    "aws_profile": {
      "type": "string",
      "title": "AWS Profile",
      "description": "AWS profile for authentication",
      "required": false
    },
    "aws_region": {
      "type": "string",
      "title": "AWS Region",
      "description": "Region for AWS Quilt data access",
      "required": false
    },
    "log_level": {
      "type": "string",
      "title": "Log Level",
      "description": "Set logging verbosity (info, debug, error)",
      "required": false,
      "default": "info"
    }
  }
}
"""

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            pyproject_path = temp_path / "pyproject.toml"
            template_path = temp_path / "manifest.json.j2"
            manifest_path = temp_path / "manifest.json"

            pyproject_path.write_text(pyproject_content)
            template_path.write_text(template_content)

            sync_versions(
                pyproject_path=pyproject_path,
                template_path=template_path,
                manifest_path=manifest_path,
            )

            with open(manifest_path, "r") as f:
                manifest = json.load(f)

            # Verify version substitution
            assert manifest["version"] == "0.5.7"

            # Verify complex nested structure preservation
            assert manifest["server"]["mcp_config"]["env"]["PYTHONNOUSERSITE"] == "1"
            assert manifest["user_config"]["catalog_domain"]["required"] is True
            assert manifest["author"]["email"] == "support@quiltdata.com"

    def test_handles_errors_gracefully(self):
        """Should provide clear error messages for common failure scenarios."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Test missing pyproject.toml
            with pytest.raises(FileNotFoundError):
                sync_versions(
                    pyproject_path=temp_path / "missing.toml",
                    template_path=temp_path / "template.j2",
                    manifest_path=temp_path / "output.json",
                )

            # Test missing template
            pyproject_path = temp_path / "pyproject.toml"
            pyproject_path.write_text('[project]\nname="test"\nversion="1.0.0"')

            with pytest.raises(FileNotFoundError):
                sync_versions(
                    pyproject_path=pyproject_path,
                    template_path=temp_path / "missing_template.j2",
                    manifest_path=temp_path / "output.json",
                )

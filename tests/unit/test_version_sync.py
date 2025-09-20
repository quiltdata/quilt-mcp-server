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

from quilt_mcp.version_sync import (
    read_project_version,
    generate_manifest_from_template,
    check_version_sync_required,
    sync_versions,
)


class TestVersionReading:
    """BS-1: Version Reading - Given a pyproject.toml with version "1.2.3", when I read the project version, then the returned version should be "1.2.3"."""

    def test_reads_version_from_pyproject_toml(self):
        """Should extract version from pyproject.toml [project] section."""
        pyproject_content = """
[project]
name = "test-project"
version = "1.2.3"
description = "Test project"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            try:
                f.write(pyproject_content)
                f.flush()

                version = read_project_version(Path(f.name))
                assert version == "1.2.3"
            finally:
                Path(f.name).unlink(missing_ok=True)

    def test_handles_complex_version_formats(self):
        """Should handle prerelease and development versions."""
        test_cases = [
            "1.0.0-rc.1",
            "2.3.4-beta.2",
            "1.5.0-dev",
            "0.1.0-alpha.1+build.123",
        ]

        for version in test_cases:
            pyproject_content = f"""
[project]
name = "test-project"
version = "{version}"
"""
            with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
                try:
                    f.write(pyproject_content)
                    f.flush()

                    result = read_project_version(Path(f.name))
                    assert result == version
                finally:
                    Path(f.name).unlink(missing_ok=True)

    def test_raises_error_for_missing_file(self):
        """Should raise FileNotFoundError for non-existent pyproject.toml."""
        with pytest.raises(FileNotFoundError):
            read_project_version(Path("/non/existent/pyproject.toml"))

    def test_raises_error_for_missing_version_field(self):
        """Should raise KeyError when version field is missing."""
        pyproject_content = """
[project]
name = "test-project"
description = "Test project without version"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            try:
                f.write(pyproject_content)
                f.flush()

                with pytest.raises(KeyError, match="version"):
                    read_project_version(Path(f.name))
            finally:
                Path(f.name).unlink(missing_ok=True)

    def test_raises_error_for_missing_project_section(self):
        """Should raise KeyError when [project] section is missing."""
        pyproject_content = """
[build-system]
requires = ["setuptools"]
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            try:
                f.write(pyproject_content)
                f.flush()

                with pytest.raises(KeyError, match="project"):
                    read_project_version(Path(f.name))
            finally:
                Path(f.name).unlink(missing_ok=True)


class TestTemplateProcessing:
    """BS-2: Template Processing - Given a manifest.json.j2 template with "{{ version }}" placeholder and pyproject.toml version is "1.2.3", when I generate the manifest from template, then the manifest.json should contain version "1.2.3" and all other fields should remain unchanged."""

    def test_generates_manifest_from_template_with_version_substitution(self):
        """Should substitute {{ version }} placeholder with actual version."""
        template_content = """
{
  "dxt_version": "0.1",
  "name": "test-extension",
  "version": "{{ version }}",
  "description": "Test extension",
  "author": {
    "name": "Test Author",
    "email": "test@example.com"
  }
}
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".j2", delete=False) as template_file:
            try:
                template_file.write(template_content)
                template_file.flush()

                with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as output_file:
                    try:
                        generate_manifest_from_template(
                            template_path=Path(template_file.name),
                            output_path=Path(output_file.name),
                            version="1.2.3",
                        )

                        # Verify the generated file
                        with open(output_file.name, "r") as f:
                            manifest = json.load(f)

                        assert manifest["version"] == "1.2.3"
                        assert manifest["name"] == "test-extension"
                        assert manifest["dxt_version"] == "0.1"
                        assert manifest["author"]["name"] == "Test Author"
                    finally:
                        Path(output_file.name).unlink(missing_ok=True)
            finally:
                Path(template_file.name).unlink(missing_ok=True)

    def test_preserves_all_non_version_fields(self):
        """Should preserve complex nested structures and all fields except version."""
        template_content = """
{
  "dxt_version": "0.1",
  "name": "complex-extension",
  "version": "{{ version }}",
  "description": "Complex test extension",
  "author": {
    "name": "Test Author",
    "email": "test@example.com"
  },
  "server": {
    "type": "python",
    "entry_point": "bootstrap.py",
    "mcp_config": {
      "command": "python3",
      "args": ["${__dirname}/bootstrap.py"],
      "env": {
        "PYTHONNOUSERSITE": "1"
      }
    }
  },
  "user_config": {
    "catalog_domain": {
      "type": "string",
      "title": "Catalog Domain",
      "required": true
    }
  }
}
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".j2", delete=False) as template_file:
            try:
                template_file.write(template_content)
                template_file.flush()

                with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as output_file:
                    try:
                        generate_manifest_from_template(
                            template_path=Path(template_file.name),
                            output_path=Path(output_file.name),
                            version="2.0.0",
                        )

                        with open(output_file.name, "r") as f:
                            manifest = json.load(f)

                        # Check version was substituted
                        assert manifest["version"] == "2.0.0"

                        # Check all other fields preserved
                        assert manifest["server"]["mcp_config"]["env"]["PYTHONNOUSERSITE"] == "1"
                        assert manifest["user_config"]["catalog_domain"]["required"] is True
                        assert len(manifest["server"]["mcp_config"]["args"]) == 1
                    finally:
                        Path(output_file.name).unlink(missing_ok=True)
            finally:
                Path(template_file.name).unlink(missing_ok=True)

    def test_raises_error_for_missing_template(self):
        """Should raise FileNotFoundError for non-existent template."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as output_file:
            try:
                with pytest.raises(FileNotFoundError):
                    generate_manifest_from_template(
                        template_path=Path("/non/existent/template.j2"),
                        output_path=Path(output_file.name),
                        version="1.0.0",
                    )
            finally:
                Path(output_file.name).unlink(missing_ok=True)

    def test_handles_invalid_json_template(self):
        """Should raise appropriate error for malformed JSON template."""
        invalid_template = """
{
  "name": "broken-json",
  "version": "{{ version }}",
  "invalid": json content here
}
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".j2", delete=False) as template_file:
            try:
                template_file.write(invalid_template)
                template_file.flush()

                with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as output_file:
                    try:
                        with pytest.raises(json.JSONDecodeError):
                            generate_manifest_from_template(
                                template_path=Path(template_file.name),
                                output_path=Path(output_file.name),
                                version="1.0.0",
                            )
                    finally:
                        Path(output_file.name).unlink(missing_ok=True)
            finally:
                Path(template_file.name).unlink(missing_ok=True)


class TestSyncDetection:
    """BS-3: Sync Detection - Given pyproject.toml version is "1.2.3" and manifest.json version is "1.2.2", when I check version sync status, then sync should be required."""

    def test_detects_version_mismatch_requires_sync(self):
        """Should return True when versions don't match."""
        pyproject_content = """
[project]
name = "test-project"
version = "1.2.3"
"""
        manifest_content = {
            "name": "test-extension",
            "version": "1.2.2",
            "description": "Test extension",
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as pyproject_file:
            try:
                pyproject_file.write(pyproject_content)
                pyproject_file.flush()

                with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as manifest_file:
                    try:
                        json.dump(manifest_content, manifest_file)
                        manifest_file.flush()

                        result = check_version_sync_required(
                            pyproject_path=Path(pyproject_file.name),
                            manifest_path=Path(manifest_file.name),
                        )

                        assert result is True
                    finally:
                        Path(manifest_file.name).unlink(missing_ok=True)
            finally:
                Path(pyproject_file.name).unlink(missing_ok=True)

    def test_detects_versions_in_sync_no_sync_needed(self):
        """Should return False when versions match."""
        pyproject_content = """
[project]
name = "test-project"
version = "1.2.3"
"""
        manifest_content = {
            "name": "test-extension",
            "version": "1.2.3",
            "description": "Test extension",
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as pyproject_file:
            try:
                pyproject_file.write(pyproject_content)
                pyproject_file.flush()

                with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as manifest_file:
                    try:
                        json.dump(manifest_content, manifest_file)
                        manifest_file.flush()

                        result = check_version_sync_required(
                            pyproject_path=Path(pyproject_file.name),
                            manifest_path=Path(manifest_file.name),
                        )

                        assert result is False
                    finally:
                        Path(manifest_file.name).unlink(missing_ok=True)
            finally:
                Path(pyproject_file.name).unlink(missing_ok=True)

    def test_handles_missing_manifest_file(self):
        """Should return True when manifest.json doesn't exist (sync needed to create it)."""
        pyproject_content = """
[project]
name = "test-project"
version = "1.2.3"
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as pyproject_file:
            try:
                pyproject_file.write(pyproject_content)
                pyproject_file.flush()

                result = check_version_sync_required(
                    pyproject_path=Path(pyproject_file.name),
                    manifest_path=Path("/non/existent/manifest.json"),
                )

                assert result is True
            finally:
                Path(pyproject_file.name).unlink(missing_ok=True)


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
  "dxt_version": "0.1",
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
            assert manifest["dxt_version"] == "0.1"

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
  "dxt_version": "0.1",
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
    "url": "https://github.com/ernest/fast-mcp-server"
  },
  "icon": "icon.png",
  "server": {
    "type": "python",
    "entry_point": "bootstrap.py",
    "mcp_config": {
      "command": "python3",
      "args": ["${__dirname}/bootstrap.py"],
      "env": {
        "PYTHONNOUSERSITE": "1"
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

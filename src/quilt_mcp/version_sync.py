"""
Version synchronization utilities for keeping pyproject.toml and manifest.json in sync.

This module implements the functionality specified in spec/a03-release-version.md
to ensure pyproject.toml serves as the single source of truth for version information.
"""

import json
import tomllib
from pathlib import Path
from typing import Dict, Any

import jinja2


def read_project_version(pyproject_path: Path) -> str:
    """
    Read version from pyproject.toml [project] section.

    Args:
        pyproject_path: Path to pyproject.toml file

    Returns:
        Version string from pyproject.toml

    Raises:
        FileNotFoundError: If pyproject.toml doesn't exist
        KeyError: If [project] section or version field is missing
    """
    with open(pyproject_path, "rb") as f:
        pyproject_data = tomllib.load(f)

    return pyproject_data["project"]["version"]


def generate_manifest_from_template(template_path: Path, output_path: Path, version: str) -> None:
    """
    Generate manifest.json from Jinja2 template with version substitution.

    Args:
        template_path: Path to manifest.json.j2 template file
        output_path: Path where generated manifest.json should be written
        version: Version string to substitute in template

    Raises:
        FileNotFoundError: If template file doesn't exist
        json.JSONDecodeError: If template renders to invalid JSON
        jinja2.TemplateError: If template has syntax errors
    """
    with open(template_path, "r") as f:
        template_content = f.read()

    # Render template with version using safe environment
    env = jinja2.Environment(autoescape=True, undefined=jinja2.StrictUndefined)
    template = env.from_string(template_content)
    rendered_content = template.render(version=version)

    # Validate that rendered content is valid JSON
    manifest_data = json.loads(rendered_content)

    # Write the generated manifest
    with open(output_path, "w") as f:
        json.dump(manifest_data, f, indent=2)


def check_version_sync_required(pyproject_path: Path, manifest_path: Path) -> bool:
    """
    Check if version synchronization is required.

    Args:
        pyproject_path: Path to pyproject.toml file
        manifest_path: Path to manifest.json file

    Returns:
        True if sync is required (versions don't match or manifest missing)
        False if versions are already in sync

    Raises:
        FileNotFoundError: If pyproject.toml doesn't exist
        KeyError: If version fields are missing from either file
    """
    # Read version from pyproject.toml
    pyproject_version = read_project_version(pyproject_path)

    # Check if manifest exists
    if not manifest_path.exists():
        return True

    # Read version from manifest.json
    try:
        with open(manifest_path, "r") as f:
            manifest_data = json.load(f)
        manifest_version = manifest_data["version"]
    except (json.JSONDecodeError, KeyError):
        return True

    # Compare versions
    return pyproject_version != manifest_version


def sync_versions(pyproject_path: Path, template_path: Path, manifest_path: Path) -> None:
    """
    Synchronize versions by reading from pyproject.toml and generating manifest.json.

    This is the main entry point for the version sync process.

    Args:
        pyproject_path: Path to pyproject.toml file
        template_path: Path to manifest.json.j2 template
        manifest_path: Path where manifest.json should be generated

    Raises:
        FileNotFoundError: If pyproject.toml or template don't exist
        KeyError: If required fields are missing
        json.JSONDecodeError: If template renders to invalid JSON
    """
    # Read version from pyproject.toml
    version = read_project_version(pyproject_path)

    # Generate manifest from template
    generate_manifest_from_template(template_path=template_path, output_path=manifest_path, version=version)

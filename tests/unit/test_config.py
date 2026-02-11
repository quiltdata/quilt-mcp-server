"""Unit tests for mode/backend configuration resolution."""

from __future__ import annotations

import pytest

from quilt_mcp.config import ConfigurationError, DeploymentMode, ModeConfig, get_mode_config, reset_mode_config


@pytest.fixture(autouse=True)
def clean_mode_config(monkeypatch: pytest.MonkeyPatch):
    """Reset singleton and clear mode env between tests."""
    reset_mode_config()
    monkeypatch.delenv("QUILT_DEPLOYMENT", raising=False)
    monkeypatch.delenv("QUILT_MULTIUSER_MODE", raising=False)
    monkeypatch.delenv("QUILT_CATALOG_URL", raising=False)
    monkeypatch.delenv("QUILT_REGISTRY_URL", raising=False)
    yield
    reset_mode_config()


def test_default_backend_is_platform_graphql():
    mode_config = get_mode_config()

    assert mode_config.deployment_mode == DeploymentMode.LOCAL
    assert mode_config.backend_name == "platform"
    assert mode_config.backend_type == "graphql"
    assert mode_config.backend_selection_source == "default"
    assert mode_config.default_transport == "stdio"
    assert mode_config.requires_jwt is True


def test_deployment_cli_precedence_over_env_and_backend(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("QUILT_DEPLOYMENT", "legacy")
    mode_config = get_mode_config(
        deployment_mode="remote",
        backend_override="quilt3",
    )

    assert mode_config.deployment_mode == DeploymentMode.REMOTE
    assert mode_config.deployment_selection_source == "deployment-cli"
    assert mode_config.backend_name == "quilt3"
    assert mode_config.backend_selection_source == "cli"
    assert mode_config.default_transport == "http"


def test_deployment_env_precedence_over_legacy_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("QUILT_DEPLOYMENT", "remote")
    monkeypatch.setenv("QUILT_MULTIUSER_MODE", "false")

    mode_config = get_mode_config()

    assert mode_config.deployment_mode == DeploymentMode.REMOTE
    assert mode_config.deployment_selection_source == "deployment-env"
    assert mode_config.backend_name == "platform"
    assert mode_config.backend_selection_source == "deployment-env"
    assert mode_config.default_transport == "http"


def test_legacy_env_true_selects_platform(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("QUILT_MULTIUSER_MODE", "true")

    mode_config = get_mode_config()

    assert mode_config.deployment_mode == DeploymentMode.LOCAL
    assert mode_config.deployment_selection_source == "legacy-env"
    assert mode_config.backend_name == "platform"
    assert mode_config.backend_type == "graphql"
    assert mode_config.backend_selection_source == "legacy-env"


def test_legacy_env_false_selects_quilt3(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("QUILT_MULTIUSER_MODE", "false")

    mode_config = get_mode_config()

    assert mode_config.deployment_mode == DeploymentMode.LEGACY
    assert mode_config.deployment_selection_source == "legacy-env"
    assert mode_config.backend_name == "quilt3"
    assert mode_config.backend_type == "quilt3"
    assert mode_config.backend_selection_source == "legacy-env"
    assert mode_config.requires_jwt is False


def test_backend_override_precedence_over_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("QUILT_DEPLOYMENT", "legacy")

    mode_config = get_mode_config(backend_override="platform")

    assert mode_config.deployment_mode == DeploymentMode.LEGACY
    assert mode_config.backend_name == "platform"
    assert mode_config.backend_type == "graphql"
    assert mode_config.backend_selection_source == "cli"


def test_backend_override_supports_quilt3(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("QUILT_DEPLOYMENT", "remote")

    mode_config = get_mode_config(backend_override="quilt3")

    assert mode_config.deployment_mode == DeploymentMode.REMOTE
    assert mode_config.backend_name == "quilt3"
    assert mode_config.backend_type == "quilt3"
    assert mode_config.backend_selection_source == "cli"


def test_platform_validation_requires_catalog_and_registry():
    mode_config = ModeConfig(backend_override="platform")

    errors = mode_config.get_validation_errors()

    assert "Platform backend requires QUILT_CATALOG_URL environment variable" in errors
    assert "Platform backend requires QUILT_REGISTRY_URL environment variable" in errors


def test_quilt3_validation_does_not_require_catalog_registry():
    mode_config = ModeConfig(backend_override="quilt3")
    mode_config.validate()


def test_invalid_backend_override_raises_configuration_error():
    with pytest.raises(ConfigurationError, match="Invalid backend"):
        ModeConfig(backend_override="nope")


def test_invalid_deployment_override_raises_configuration_error():
    with pytest.raises(ConfigurationError, match="Invalid deployment mode"):
        ModeConfig(deployment_mode="nope")

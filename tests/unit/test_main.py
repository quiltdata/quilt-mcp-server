import os
from importlib import reload

import pytest


@pytest.fixture(autouse=True)
def reset_env(monkeypatch):
    monkeypatch.delenv("FASTMCP_TRANSPORT", raising=False)
    yield
    monkeypatch.delenv("FASTMCP_TRANSPORT", raising=False)


def call_main_with_fake_server(argv=None):
    import quilt_mcp.main as main_module
    import sys

    reload(main_module)

    called = False
    skip_banner_arg = None

    def fake_run_server(skip_banner=False):
        nonlocal called, skip_banner_arg
        called = True
        skip_banner_arg = skip_banner

    main_module.run_server = fake_run_server  # type: ignore[attr-defined]

    # Mock sys.argv if provided
    if argv is not None:
        old_argv = sys.argv
        sys.argv = argv
        try:
            main_module.main()
        finally:
            sys.argv = old_argv
    else:
        # Use empty argv (just program name) for default behavior
        old_argv = sys.argv
        sys.argv = ["quilt-mcp"]
        try:
            main_module.main()
        finally:
            sys.argv = old_argv

    return called, os.environ.get("FASTMCP_TRANSPORT"), skip_banner_arg


def test_main_preserves_existing_transport(monkeypatch):
    monkeypatch.setenv("FASTMCP_TRANSPORT", "http")

    called, transport, skip_banner = call_main_with_fake_server()

    assert called is True
    assert transport == "http"
    assert skip_banner is False  # Default


def test_main_defaults_to_stdio():
    called, transport, skip_banner = call_main_with_fake_server()

    assert called is True
    assert transport == "stdio"
    assert skip_banner is False  # Default


def test_main_imports_dotenv():
    """Test that main.py imports load_dotenv for development support."""
    import quilt_mcp.main as main_module

    # Verify that load_dotenv is imported
    assert hasattr(main_module, 'load_dotenv')

    # Verify main() calls it (by checking the function is defined)
    import inspect

    source = inspect.getsource(main_module.main)
    assert 'load_dotenv()' in source


def test_skip_banner_cli_flag():
    """Test that --skip-banner CLI flag sets skip_banner=True."""
    called, transport, skip_banner = call_main_with_fake_server(["quilt-mcp", "--skip-banner"])

    assert called is True
    assert skip_banner is True


def test_skip_banner_env_var(monkeypatch):
    """Test that MCP_SKIP_BANNER env var sets skip_banner=True."""
    monkeypatch.setenv("MCP_SKIP_BANNER", "true")

    called, transport, skip_banner = call_main_with_fake_server()

    assert called is True
    assert skip_banner is True


def test_skip_banner_cli_overrides_env(monkeypatch):
    """Test that CLI flag overrides environment variable."""
    monkeypatch.setenv("MCP_SKIP_BANNER", "false")

    called, transport, skip_banner = call_main_with_fake_server(["quilt-mcp", "--skip-banner"])

    assert called is True
    assert skip_banner is True  # CLI flag wins


def test_skip_banner_env_false(monkeypatch):
    """Test that MCP_SKIP_BANNER=false shows banner."""
    monkeypatch.setenv("MCP_SKIP_BANNER", "false")

    called, transport, skip_banner = call_main_with_fake_server()

    assert called is True
    assert skip_banner is False

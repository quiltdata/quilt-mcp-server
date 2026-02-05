import os
from importlib import reload
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def reset_env(monkeypatch):
    monkeypatch.delenv("FASTMCP_TRANSPORT", raising=False)
    # Reset ModeConfig singleton for each test
    from quilt_mcp.config import reset_mode_config

    reset_mode_config()
    yield
    monkeypatch.delenv("FASTMCP_TRANSPORT", raising=False)
    reset_mode_config()


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


def test_skip_banner_env_false(monkeypatch):
    """Test that MCP_SKIP_BANNER=false shows banner."""
    monkeypatch.setenv("MCP_SKIP_BANNER", "false")

    called, transport, skip_banner = call_main_with_fake_server()

    assert called is True
    assert skip_banner is False


def test_main_import_error_handling(monkeypatch, capsys):
    """Test that ImportError is caught and formatted with diagnostic info."""
    import quilt_mcp.main as main_module
    import sys
    from importlib import reload

    reload(main_module)

    def fake_run_server(skip_banner=False):
        raise ImportError("No module named 'fake_module'")

    main_module.run_server = fake_run_server  # type: ignore[attr-defined]

    # Mock sys.argv to avoid argparse errors
    old_argv = sys.argv
    sys.argv = ["quilt-mcp"]
    try:
        # Test that main() exits with code 1 on ImportError
        with pytest.raises(SystemExit) as exc_info:
            main_module.main()

        assert exc_info.value.code == 1

        # Check that diagnostic output was written to stderr
        captured = capsys.readouterr()
        assert "QUILT MCP SERVER STARTUP ERROR" in captured.err
        assert "Missing Dependency" in captured.err
        assert "fake_module" in captured.err
        assert "Troubleshooting:" in captured.err
    finally:
        sys.argv = old_argv


def test_main_generic_error_handling(monkeypatch, capsys):
    """Test that generic exceptions are caught and formatted."""
    import quilt_mcp.main as main_module
    import sys
    from importlib import reload

    reload(main_module)

    def fake_run_server(skip_banner=False):
        raise ValueError("Something went wrong")

    main_module.run_server = fake_run_server  # type: ignore[attr-defined]

    # Mock sys.argv to avoid argparse errors
    old_argv = sys.argv
    sys.argv = ["quilt-mcp"]
    try:
        # Test that main() exits with code 1 on generic error
        with pytest.raises(SystemExit) as exc_info:
            main_module.main()

        assert exc_info.value.code == 1

        # Check that diagnostic output was written to stderr
        captured = capsys.readouterr()
        assert "QUILT MCP SERVER STARTUP ERROR" in captured.err
        assert "Unexpected Error" in captured.err
        assert "Something went wrong" in captured.err
        assert "Traceback:" in captured.err
    finally:
        sys.argv = old_argv


def test_main_keyboard_interrupt(monkeypatch, capsys):
    """Test that KeyboardInterrupt exits cleanly."""
    import quilt_mcp.main as main_module
    import sys
    from importlib import reload

    reload(main_module)

    def fake_run_server(skip_banner=False):
        raise KeyboardInterrupt()

    main_module.run_server = fake_run_server  # type: ignore[attr-defined]

    # Mock sys.argv to avoid argparse errors
    old_argv = sys.argv
    sys.argv = ["quilt-mcp"]
    try:
        # Test that main() exits with code 0 on KeyboardInterrupt
        with pytest.raises(SystemExit) as exc_info:
            main_module.main()

        assert exc_info.value.code == 0

        # Check that clean shutdown message was printed
        captured = capsys.readouterr()
        assert "shutdown" in captured.err.lower()
        assert "user interrupt" in captured.err.lower()
    finally:
        sys.argv = old_argv


def test_transport_protocol_selection_local_mode(monkeypatch):
    """Test that local mode sets stdio transport."""
    # Ensure local mode (default)
    monkeypatch.delenv("QUILT_MULTIUSER_MODE", raising=False)

    called, transport, skip_banner = call_main_with_fake_server()

    assert called is True
    assert transport == "stdio"


def test_transport_protocol_selection_multiuser_mode(monkeypatch):
    """Test that multiuser mode sets http transport."""
    # Set multiuser mode
    monkeypatch.setenv("QUILT_MULTIUSER_MODE", "true")
    # Set required JWT config to pass validation
    monkeypatch.setenv("MCP_JWT_SECRET", "test-secret")
    monkeypatch.setenv("MCP_JWT_ISSUER", "test-issuer")
    monkeypatch.setenv("MCP_JWT_AUDIENCE", "test-audience")

    called, transport, skip_banner = call_main_with_fake_server()

    assert called is True
    assert transport == "http"


def test_transport_protocol_respects_existing_env_var(monkeypatch):
    """Test that existing FASTMCP_TRANSPORT is not overridden."""
    # Set multiuser mode (which would normally set http)
    monkeypatch.setenv("QUILT_MULTIUSER_MODE", "true")
    # Set required JWT config to pass validation
    monkeypatch.setenv("MCP_JWT_SECRET", "test-secret")
    monkeypatch.setenv("MCP_JWT_ISSUER", "test-issuer")
    monkeypatch.setenv("MCP_JWT_AUDIENCE", "test-audience")
    # Pre-set transport to a different value
    monkeypatch.setenv("FASTMCP_TRANSPORT", "sse")

    called, transport, skip_banner = call_main_with_fake_server()

    assert called is True
    assert transport == "sse"  # Should not be overridden

"""Unit tests for CLI/startup diagnostics in quilt_mcp.main."""

from __future__ import annotations

from quilt_mcp.main import print_startup_error


def test_print_startup_error_includes_selected_backend(capsys):
    print_startup_error(Exception("bad config"), "Configuration Error", selected_backend="platform")

    captured = capsys.readouterr()
    assert "Selected backend: platform" in captured.err
    assert "--backend quilt3" in captured.err


def test_print_startup_error_auth_guidance(capsys):
    print_startup_error(Exception("missing jwt"), "Authentication Error", selected_backend="platform")

    captured = capsys.readouterr()
    assert "Run 'quilt3 login'" in captured.err
    assert "--backend quilt3" in captured.err

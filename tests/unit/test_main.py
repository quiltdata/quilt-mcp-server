import os
from importlib import reload

import pytest


@pytest.fixture(autouse=True)
def reset_env(monkeypatch):
    monkeypatch.delenv("FASTMCP_TRANSPORT", raising=False)
    yield
    monkeypatch.delenv("FASTMCP_TRANSPORT", raising=False)


def call_main_with_fake_server():
    import quilt_mcp.main as main_module

    reload(main_module)

    called = False

    def fake_run_server():
        nonlocal called
        called = True

    main_module.run_server = fake_run_server  # type: ignore[attr-defined]

    main_module.main()
    return called, os.environ.get("FASTMCP_TRANSPORT")


def test_main_preserves_existing_transport(monkeypatch):
    monkeypatch.setenv("FASTMCP_TRANSPORT", "http")

    called, transport = call_main_with_fake_server()

    assert called is True
    assert transport == "http"


def test_main_defaults_to_stdio():
    called, transport = call_main_with_fake_server()

    assert called is True
    assert transport == "stdio"


def test_main_imports_dotenv():
    """Test that main.py imports load_dotenv for development support."""
    import quilt_mcp.main as main_module

    # Verify that load_dotenv is imported
    assert hasattr(main_module, 'load_dotenv')

    # Verify main() calls it (by checking the function is defined)
    import inspect

    source = inspect.getsource(main_module.main)
    assert 'load_dotenv()' in source

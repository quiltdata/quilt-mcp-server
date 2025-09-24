from pathlib import Path


def test_installation_doc_includes_docker_instructions():
    installation_path = Path("docs/user/INSTALLATION.md")
    text = installation_path.read_text()

    assert "docker pull" in text
    assert "docker run" in text


def test_installation_doc_includes_proxy_guidance():
    installation_path = Path("docs/user/INSTALLATION.md")
    text = installation_path.read_text()

    assert "FastMCP.as_proxy" in text

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
RELEASE_SCRIPT = REPO_ROOT / "bin" / "release.sh"


@pytest.mark.usefixtures("monkeypatch")
def test_python_dist_dry_run_succeeds_without_credentials(tmp_path):
    env = os.environ.copy()
    for key in ["UV_PUBLISH_TOKEN", "UV_PUBLISH_USERNAME", "UV_PUBLISH_PASSWORD"]:
        env.pop(key, None)
    env["DRY_RUN"] = "1"
    env["DIST_DIR"] = str(tmp_path / "dist")

    proc = subprocess.run(
        [str(RELEASE_SCRIPT), "python-dist"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
    )

    assert proc.returncode == 0
    assert "python-dist" in proc.stdout
    assert Path(env["DIST_DIR"]).exists()


@pytest.mark.usefixtures("monkeypatch")
def test_python_dist_logs_dry_run_command(tmp_path):
    env = os.environ.copy()
    env["DRY_RUN"] = "1"
    env["DIST_DIR"] = str(tmp_path / "dist")

    proc = subprocess.run(
        [str(RELEASE_SCRIPT), "python-dist"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
    )

    assert "Would run: uv build" in proc.stdout


@pytest.mark.usefixtures("monkeypatch")
def test_make_python_dist_delegates_to_release(tmp_path):
    env = os.environ.copy()
    env["DRY_RUN"] = "1"
    env["DIST_DIR"] = str(tmp_path / "dist")

    make_args = ["make", f"DIST_DIR={env['DIST_DIR']}", "python-dist"]

    proc = subprocess.run(
        make_args,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
    )

    assert proc.returncode == 0
    assert "python-dist" in proc.stdout
    assert Path(env["DIST_DIR"]).exists()


@pytest.mark.usefixtures("monkeypatch")
def test_python_publish_requires_credentials(tmp_path):
    env = os.environ.copy()
    for key in ["UV_PUBLISH_TOKEN", "UV_PUBLISH_USERNAME", "UV_PUBLISH_PASSWORD"]:
        env.pop(key, None)
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    (dist_dir / "dummy.whl").write_text("fake")
    env["DIST_DIR"] = str(dist_dir)
    env["DRY_RUN"] = "1"

    proc = subprocess.run(
        [str(RELEASE_SCRIPT), "python-publish"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
    )

    assert proc.returncode != 0
    assert "Missing publish credentials" in proc.stdout


@pytest.mark.usefixtures("monkeypatch")
def test_python_publish_dry_run_with_token(tmp_path):
    env = os.environ.copy()
    env["UV_PUBLISH_TOKEN"] = "token-value"
    env["DRY_RUN"] = "1"
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    (dist_dir / "dummy.whl").write_text("fake")
    env["DIST_DIR"] = str(dist_dir)
    env["PYPI_REPOSITORY_URL"] = "https://test.pypi.org/legacy/"

    proc = subprocess.run(
        [str(RELEASE_SCRIPT), "python-publish"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
    )

    assert proc.returncode == 0
    assert "uv publish" in proc.stdout
    assert "token-value" not in proc.stdout


@pytest.mark.usefixtures("monkeypatch")
def test_make_python_publish_delegates(tmp_path):
    env = os.environ.copy()
    env["UV_PUBLISH_USERNAME"] = "user"
    env["UV_PUBLISH_PASSWORD"] = "pass"
    env["DRY_RUN"] = "1"
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    (dist_dir / "dummy.tar.gz").write_text("fake")
    env["DIST_DIR"] = str(dist_dir)

    make_args = ["make", f"DIST_DIR={env['DIST_DIR']}", "python-publish"]

    proc = subprocess.run(
        make_args,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
    )

    assert proc.returncode == 0
    assert "python-publish" in proc.stdout

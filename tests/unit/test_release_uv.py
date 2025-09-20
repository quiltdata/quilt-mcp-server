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

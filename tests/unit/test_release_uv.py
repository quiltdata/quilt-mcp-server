import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
RELEASE_SCRIPT = REPO_ROOT / "bin" / "release.sh"


@pytest.mark.usefixtures("monkeypatch")
def test_uv_package_requires_credentials(tmp_path):
    env = os.environ.copy()
    for key in ["UV_PUBLISH_TOKEN", "UV_PUBLISH_USERNAME", "UV_PUBLISH_PASSWORD"]:
        env.pop(key, None)
    env["DRY_RUN"] = "1"
    env["DIST_DIR"] = str(tmp_path / "dist")

    proc = subprocess.run(
        [str(RELEASE_SCRIPT), "uv-package"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
    )

    assert proc.returncode != 0
    assert "UV_PUBLISH_TOKEN" in proc.stdout


@pytest.mark.usefixtures("monkeypatch")
def test_uv_package_accepts_token_credentials(tmp_path):
    env = os.environ.copy()
    env["UV_PUBLISH_TOKEN"] = "fake-token"
    env["DRY_RUN"] = "1"
    env["DIST_DIR"] = str(tmp_path / "dist")

    proc = subprocess.run(
        [str(RELEASE_SCRIPT), "uv-package"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
    )

    assert proc.returncode == 0
    assert "Using UV_PUBLISH_TOKEN" in proc.stdout
    assert Path(env["DIST_DIR"]).exists()


@pytest.mark.usefixtures("monkeypatch")
def test_make_package_uv_delegates_to_release(tmp_path):
    env = os.environ.copy()
    env["UV_PUBLISH_USERNAME"] = "user"
    env["UV_PUBLISH_PASSWORD"] = "pass"
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
    assert "uv-package" in proc.stdout
    assert Path(env["DIST_DIR"]).exists()

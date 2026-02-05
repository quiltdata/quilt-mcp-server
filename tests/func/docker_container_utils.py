import socket
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
IMAGE_TAG = "quilt-mcp:test"
DEFAULT_TIMEOUT = 60


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def build_test_image() -> None:
    dockerfile = REPO_ROOT / "Dockerfile"
    assert dockerfile.exists(), "Dockerfile must exist for container build"

    build_cmd = (
        "docker",
        "build",
        "--platform",
        "linux/amd64",
        "--tag",
        IMAGE_TAG,
        str(REPO_ROOT),
    )
    subprocess.run(build_cmd, check=True)

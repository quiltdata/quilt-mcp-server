"""Tests for the health check script."""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add scripts directory to path for import
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from healthcheck import check_health, main  # noqa: E402


class TestHealthCheckFunction:
    """Test the check_health function."""

    @patch("urllib.request.urlopen")
    def test_healthy_response(self, mock_urlopen):
        """Test successful health check with valid response."""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({
            "status": "ok",
            "timestamp": "2025-01-24T12:00:00Z",
            "server": {
                "name": "quilt-mcp-server",
                "version": "1.0.0",
            },
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        is_healthy, data, error = check_health()

        assert is_healthy is True
        assert error is None
        assert data["status"] == "ok"
        assert "timestamp" in data
        assert data["server"]["name"] == "quilt-mcp-server"

    @patch("urllib.request.urlopen")
    def test_unhealthy_status(self, mock_urlopen):
        """Test health check with unhealthy status."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({
            "status": "unhealthy",
            "timestamp": "2025-01-24T12:00:00Z",
            "server": {"name": "quilt-mcp-server"},
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        is_healthy, data, error = check_health()

        assert is_healthy is False
        assert error == "Status not ok: unhealthy"
        assert data["status"] == "unhealthy"

    @patch("urllib.request.urlopen")
    def test_http_error(self, mock_urlopen):
        """Test health check with HTTP error."""
        from urllib.error import HTTPError

        mock_urlopen.side_effect = HTTPError(
            "http://localhost:8080/health", 503, "Service Unavailable", {}, None
        )

        is_healthy, data, error = check_health()

        assert is_healthy is False
        assert data is None
        assert "HTTP error: 503" in error

    @patch("urllib.request.urlopen")
    def test_connection_error(self, mock_urlopen):
        """Test health check with connection error."""
        from urllib.error import URLError

        mock_urlopen.side_effect = URLError("Connection refused")

        is_healthy, data, error = check_health()

        assert is_healthy is False
        assert data is None
        assert "Connection error" in error

    @patch("urllib.request.urlopen")
    def test_invalid_json(self, mock_urlopen):
        """Test health check with invalid JSON response."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b"not json"
        mock_urlopen.return_value.__enter__.return_value = mock_response

        is_healthy, data, error = check_health()

        assert is_healthy is False
        assert data is None
        assert "Invalid JSON response" in error

    @patch("urllib.request.urlopen")
    def test_missing_required_fields(self, mock_urlopen):
        """Test health check with missing required fields."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({
            "status": "ok",
            # Missing timestamp and server
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        is_healthy, data, error = check_health()

        assert is_healthy is False
        assert "Missing required fields" in error

    @patch("urllib.request.urlopen")
    def test_wrong_server_name(self, mock_urlopen):
        """Test health check with wrong server name."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({
            "status": "ok",
            "timestamp": "2025-01-24T12:00:00Z",
            "server": {"name": "wrong-server"},
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        is_healthy, data, error = check_health()

        assert is_healthy is False
        assert "Unexpected server name: wrong-server" in error

    @patch("urllib.request.urlopen")
    def test_timeout(self, mock_urlopen):
        """Test health check with timeout."""
        mock_urlopen.side_effect = TimeoutError("Request timed out")

        is_healthy, data, error = check_health(timeout=1)

        assert is_healthy is False
        assert data is None
        assert "Request timed out" in error


class TestHealthCheckScript:
    """Test the health check script CLI."""

    def test_script_exists(self):
        """Test that the health check script exists."""
        script_path = REPO_ROOT / "scripts" / "healthcheck.py"
        assert script_path.exists(), "Health check script not found"

    def test_script_executable(self):
        """Test that the script can be executed."""
        script_path = REPO_ROOT / "scripts" / "healthcheck.py"

        # Test with --help to avoid actual network calls
        result = subprocess.run(
            [sys.executable, str(script_path), "--help"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "Health check for MCP server" in result.stdout

    @patch("healthcheck.check_health")
    def test_script_success(self, mock_check):
        """Test script with successful health check."""
        mock_check.return_value = (
            True,
            {"status": "ok", "timestamp": "2025-01-24T12:00:00Z", "server": {"name": "quilt-mcp-server"}},
            None,
        )

        with patch("sys.argv", ["healthcheck.py"]):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 0

    @patch("healthcheck.check_health")
    def test_script_failure(self, mock_check):
        """Test script with failed health check."""
        mock_check.return_value = (False, None, "Connection refused")

        with patch("sys.argv", ["healthcheck.py"]):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 1

    @patch("healthcheck.check_health")
    def test_script_json_output(self, mock_check, capsys):
        """Test script with JSON output."""
        mock_check.return_value = (
            True,
            {"status": "ok", "timestamp": "2025-01-24T12:00:00Z", "server": {"name": "quilt-mcp-server"}},
            None,
        )

        with patch("sys.argv", ["healthcheck.py", "--json"]):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 0

        captured = capsys.readouterr()
        output = json.loads(captured.out)

        assert output["healthy"] is True
        assert output["error"] is None
        assert output["response"]["status"] == "ok"

    @patch("healthcheck.check_health")
    def test_script_verbose_output(self, mock_check, capsys):
        """Test script with verbose output."""
        mock_check.return_value = (
            True,
            {"status": "ok", "timestamp": "2025-01-24T12:00:00Z", "server": {"name": "quilt-mcp-server", "version": "1.0.0"}},
            None,
        )

        with patch("sys.argv", ["healthcheck.py", "--verbose"]):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 0

        # Check that verbose was passed to check_health
        mock_check.assert_called_once_with(
            url="http://localhost:8080/health",
            timeout=5,
            verbose=True,
        )


class TestHealthCheckIntegration:
    """Integration tests for health check with Docker."""

    @pytest.mark.integration
    def test_healthcheck_in_docker_image(self):
        """Test that health check script is included in Docker image and works."""
        # This test assumes the Docker image has been built
        image_tag = "quilt-mcp:test"

        # Check if image exists
        result = subprocess.run(
            ["docker", "images", "-q", image_tag],
            capture_output=True,
            text=True,
        )

        if not result.stdout.strip():
            pytest.skip(f"Docker image {image_tag} not found")

        # Run health check script in container
        result = subprocess.run(
            [
                "docker", "run", "--rm",
                image_tag,
                "python", "/app/scripts/healthcheck.py", "--help",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "Health check for MCP server" in result.stdout
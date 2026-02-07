"""
Telemetry Transport Layer

This module handles secure transmission of telemetry data to various
endpoints while maintaining privacy and reliability.
"""

import json
import os
import time
import platform
import sys
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, wait

logger = logging.getLogger(__name__)

# Quilt3-compatible telemetry constants
TELEMETRY_URL = "https://telemetry.quiltdata.cloud/Prod/metrics"
TELEMETRY_USER_AGENT = "QuiltMCP"
TELEMETRY_CLIENT_TYPE = "quilt-mcp-server"
TELEMETRY_SCHEMA_VERSION = "mcp-usage-metrics-v1"
DISABLE_USAGE_METRICS_ENVVAR = "QUILT_DISABLE_USAGE_METRICS"
MAX_CLEANUP_WAIT_SECS = 5


class TelemetryTransport(ABC):
    """Abstract base class for telemetry transport mechanisms."""

    @abstractmethod
    def send_session(self, session_data: Any) -> bool:
        """Send session data. Returns True if successful."""
        pass

    @abstractmethod
    def send_batch(self, batch_data: List[Any]) -> bool:
        """Send a batch of session data. Returns True if successful."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if transport is available and configured."""
        pass


class LocalFileTransport(TelemetryTransport):
    """Local file-based telemetry transport."""

    def __init__(self, file_path: Optional[str] = None):
        self.file_path = Path(file_path or self._get_default_path())
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def _get_default_path(self) -> str:
        """Get default file path for telemetry data."""
        home_dir = Path.home()
        return str(home_dir / ".quilt" / "mcp_telemetry.jsonl")

    def send_session(self, session_data: Any) -> bool:
        """Write session data to local file."""
        try:
            # Convert session data to dict if needed
            if hasattr(session_data, "__dict__"):
                data = session_data.__dict__
            else:
                data = session_data

            # Add timestamp
            record = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": "session",
                "transport": "local_file",
                "data": data,
            }

            # Append to file (JSONL format)
            with open(self.file_path, "a") as f:
                f.write(json.dumps(record, default=str) + "\n")

            logger.debug(f"Wrote telemetry session to {self.file_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to write telemetry to file: {e}")
            return False

    def send_batch(self, batch_data: List[Any]) -> bool:
        """Write batch data to local file."""
        try:
            records = []
            for session_data in batch_data:
                if hasattr(session_data, "__dict__"):
                    data = session_data.__dict__
                else:
                    data = session_data

                record = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "type": "session",
                    "transport": "local_file",
                    "data": data,
                }
                records.append(record)

            # Write all records
            with open(self.file_path, "a") as f:
                for record in records:
                    f.write(json.dumps(record, default=str) + "\n")

            logger.debug(f"Wrote {len(records)} telemetry records to {self.file_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to write telemetry batch to file: {e}")
            return False

    def is_available(self) -> bool:
        """Check if file transport is available."""
        try:
            # Test write access
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            test_file = self.file_path.parent / ".test_write"
            test_file.write_text("test")
            test_file.unlink()
            return True
        except OSError:
            return False

    def read_sessions(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Read sessions from the local file."""
        sessions: list[dict[str, Any]] = []

        if not self.file_path.exists():
            return sessions

        try:
            with open(self.file_path, "r") as f:
                for line_num, line in enumerate(f):
                    if limit and len(sessions) >= limit:
                        break

                    try:
                        record = json.loads(line.strip())
                        if record.get("type") == "session":
                            sessions.append(record["data"])
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON on line {line_num + 1}")
                        continue

            return sessions

        except Exception as e:
            logger.error(f"Failed to read telemetry file: {e}")
            return sessions


class HTTPTransport(TelemetryTransport):
    """HTTP-based telemetry transport using async requests (quilt3-compatible)."""

    def __init__(self, endpoint: Optional[str] = None, api_key: Optional[str] = None, timeout: int = 30):
        from quilt_mcp.utils.common import normalize_url

        # Default to quilt3 telemetry endpoint
        self.endpoint = normalize_url(endpoint) if endpoint else TELEMETRY_URL
        self.api_key = api_key
        self.timeout = timeout
        self.session = None
        self.pending_reqs: list = []

        # Initialize HTTP session with async support (like quilt3)
        try:
            from requests_futures.sessions import FuturesSession  # type: ignore[import-untyped]

            # Use ThreadPoolExecutor with max 2 workers (same as quilt3)
            self.session = FuturesSession(executor=ThreadPoolExecutor(max_workers=2))

            # Set headers (use quilt3's user agent)
            headers = {
                "Content-Type": "application/json",
                "User-Agent": TELEMETRY_USER_AGENT,
            }

            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            self.session.headers.update(headers)

        except ImportError:
            logger.warning("requests_futures library not available, HTTP transport disabled")
            self.session = None

    def cleanup_completed_requests(self) -> None:
        """Clean up completed async requests (quilt3-compatible)."""
        if not self.session:
            return

        # Remove completed requests from pending list
        self.pending_reqs = [r for r in self.pending_reqs if not r.done()]

    def send_session(self, session_data: Any) -> bool:
        """Send session data via HTTP asynchronously (quilt3-compatible)."""
        if not self.session:
            return False

        try:
            self.cleanup_completed_requests()

            # Convert session data to dict if needed
            if hasattr(session_data, "__dict__"):
                data = session_data.__dict__
            else:
                data = session_data

            # Get navigator URL from environment (if available)
            navigator_url = os.getenv("QUILT_CATALOG_URL") or os.getenv("QUILT_NAVIGATOR_URL")

            # Format payload to match quilt3 schema
            payload = {
                "api_name": data.get("tool_name", "unknown"),
                "python_session_id": data.get("session_id", "unknown"),
                "telemetry_schema_version": TELEMETRY_SCHEMA_VERSION,
                "navigator_url": navigator_url,
                "client_type": TELEMETRY_CLIENT_TYPE,
                "client_version": self._get_mcp_version(),
                "platform": sys.platform,
                "python_implementation": platform.python_implementation(),
                "python_version_major": platform.python_version_tuple()[0],
                "python_version_minor": platform.python_version_tuple()[1],
                "python_version_patch": platform.python_version_tuple()[2],
                # MCP-specific extensions
                "mcp_data": {
                    "execution_time": data.get("execution_time"),
                    "success": data.get("success"),
                    "total_calls": data.get("total_calls"),
                    "task_type": data.get("task_type"),
                },
            }

            # Send asynchronously (non-blocking like quilt3)
            future = self.session.post(self.endpoint, json=payload, timeout=self.timeout)
            self.pending_reqs.append(future)

            logger.debug(f"Queued telemetry session to {self.endpoint}")
            return True

        except Exception as e:
            logger.error(f"Failed to send telemetry via HTTP: {e}")
            return False

    def _get_mcp_version(self) -> str:
        """Get MCP server version."""
        try:
            from quilt_mcp import __version__

            return __version__
        except ImportError:
            return "unknown"

    def send_batch(self, batch_data: List[Any]) -> bool:
        """Send batch data via HTTP asynchronously."""
        if not self.session:
            return False

        try:
            self.cleanup_completed_requests()

            # Send each session individually (matching quilt3 pattern)
            for session_data in batch_data:
                self.send_session(session_data)

            logger.debug(f"Queued {len(batch_data)} telemetry sessions to {self.endpoint}")
            return True

        except Exception as e:
            logger.error(f"Failed to send telemetry batch via HTTP: {e}")
            return False

    def wait_for_pending(self, timeout: int = MAX_CLEANUP_WAIT_SECS) -> None:
        """Wait for all pending requests to complete (quilt3-compatible)."""
        if not self.session or not self.pending_reqs:
            return

        try:
            wait(self.pending_reqs, timeout=timeout)
            logger.debug(f"Waited for {len(self.pending_reqs)} pending telemetry requests")
        except Exception as e:
            logger.warning(f"Error waiting for pending requests: {e}")

    def is_available(self) -> bool:
        """Check if HTTP transport is available."""
        # For async transport, just check if session is configured
        # (quilt3-compatible: they don't check connectivity in has_connectivity either)
        return self.session is not None


class CloudWatchTransport(TelemetryTransport):
    """AWS CloudWatch-based telemetry transport."""

    def __init__(self, log_group: str = "mcp-telemetry", log_stream: Optional[str] = None):
        self.log_group = log_group
        self.log_stream = log_stream or f"mcp-{int(time.time())}"
        self.client = None

        try:
            import boto3

            self.client = boto3.client("logs")

            # Ensure log group exists
            try:
                self.client.create_log_group(logGroupName=self.log_group)
            except self.client.exceptions.ResourceAlreadyExistsException:
                pass

            # Create log stream
            try:
                self.client.create_log_stream(logGroupName=self.log_group, logStreamName=self.log_stream)
            except self.client.exceptions.ResourceAlreadyExistsException:
                pass

        except ImportError:
            logger.warning("boto3 not available, CloudWatch transport disabled")
        except Exception as e:
            logger.warning(f"Failed to initialize CloudWatch transport: {e}")

    def send_session(self, session_data: Any) -> bool:
        """Send session data to CloudWatch."""
        if not self.client:
            return False

        try:
            # Convert session data to dict if needed
            if hasattr(session_data, "__dict__"):
                data = session_data.__dict__
            else:
                data = session_data

            log_event = {
                "timestamp": int(time.time() * 1000),  # CloudWatch expects milliseconds
                "message": json.dumps({"type": "session", "transport": "cloudwatch", "data": data}, default=str),
            }

            self.client.put_log_events(
                logGroupName=self.log_group,
                logStreamName=self.log_stream,
                logEvents=[log_event],
            )

            logger.debug(f"Sent telemetry session to CloudWatch: {self.log_group}/{self.log_stream}")
            return True

        except Exception as e:
            logger.error(f"Failed to send telemetry to CloudWatch: {e}")
            return False

    def send_batch(self, batch_data: List[Any]) -> bool:
        """Send batch data to CloudWatch."""
        if not self.client:
            return False

        try:
            log_events = []
            for session_data in batch_data:
                if hasattr(session_data, "__dict__"):
                    data = session_data.__dict__
                else:
                    data = session_data

                log_event = {
                    "timestamp": int(time.time() * 1000),
                    "message": json.dumps({"type": "session", "transport": "cloudwatch", "data": data}, default=str),
                }
                log_events.append(log_event)

            # CloudWatch has a limit of 10,000 events per batch
            batch_size = 1000
            for i in range(0, len(log_events), batch_size):
                batch = log_events[i : i + batch_size]
                self.client.put_log_events(
                    logGroupName=self.log_group,
                    logStreamName=self.log_stream,
                    logEvents=batch,
                )

            logger.debug(f"Sent {len(log_events)} telemetry events to CloudWatch")
            return True

        except Exception as e:
            logger.error(f"Failed to send telemetry batch to CloudWatch: {e}")
            return False

    def is_available(self) -> bool:
        """Check if CloudWatch transport is available."""
        if not self.client:
            return False

        try:
            # Test by describing the log group
            self.client.describe_log_groups(logGroupNamePrefix=self.log_group)
            return True
        except Exception:
            return False


def create_transport(config) -> TelemetryTransport:
    """Create appropriate transport based on configuration."""
    if config.local_only:
        return LocalFileTransport()

    if config.endpoint:
        if config.endpoint.startswith("http"):
            api_key = os.getenv("MCP_TELEMETRY_API_KEY")
            return HTTPTransport(config.endpoint, api_key)
        elif config.endpoint.startswith("cloudwatch:"):
            log_group = config.endpoint.replace("cloudwatch:", "")
            return CloudWatchTransport(log_group)

    # Default to quilt3-compatible HTTP transport
    return HTTPTransport()


# Global transport instance for atexit cleanup
_global_http_transport: Optional[HTTPTransport] = None


def register_http_transport(transport: HTTPTransport) -> None:
    """Register HTTP transport for cleanup on exit (quilt3-compatible)."""
    global _global_http_transport
    _global_http_transport = transport


# Cleanup pending requests on exit (quilt3-compatible)
import atexit


@atexit.register
def cleanup_pending_requests():
    """Finish up any pending telemetry requests on exit."""
    if _global_http_transport:
        _global_http_transport.wait_for_pending()

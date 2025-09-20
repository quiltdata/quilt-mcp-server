"""
Telemetry Transport Layer

This module handles secure transmission of telemetry data to various
endpoints while maintaining privacy and reliability.
"""

import json
import os
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


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
        sessions = []

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
    """HTTP-based telemetry transport."""

    def __init__(self, endpoint: str, api_key: Optional[str] = None, timeout: int = 30):
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.session = None

        # Initialize HTTP session
        try:
            import requests

            self.session = requests.Session()

            # Set headers
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "QuiltMCP-Telemetry/1.0",
            }

            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            self.session.headers.update(headers)

        except ImportError:
            logger.warning("requests library not available, HTTP transport disabled")
            self.session = None

    def send_session(self, session_data: Any) -> bool:
        """Send session data via HTTP."""
        if not self.session:
            return False

        try:
            # Convert session data to dict if needed
            if hasattr(session_data, "__dict__"):
                data = session_data.__dict__
            else:
                data = session_data

            payload = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": "session",
                "transport": "http",
                "data": data,
            }

            response = self.session.post(f"{self.endpoint}/telemetry/session", json=payload, timeout=self.timeout)

            if response.status_code == 200:
                logger.debug(f"Successfully sent telemetry session to {self.endpoint}")
                return True
            else:
                logger.warning(f"HTTP telemetry failed: {response.status_code} {response.text}")
                return False

        except Exception as e:
            logger.error(f"Failed to send telemetry via HTTP: {e}")
            return False

    def send_batch(self, batch_data: List[Any]) -> bool:
        """Send batch data via HTTP."""
        if not self.session:
            return False

        try:
            sessions = []
            for session_data in batch_data:
                if hasattr(session_data, "__dict__"):
                    data = session_data.__dict__
                else:
                    data = session_data
                sessions.append(data)

            payload = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": "batch",
                "transport": "http",
                "sessions": sessions,
            }

            response = self.session.post(f"{self.endpoint}/telemetry/batch", json=payload, timeout=self.timeout)

            if response.status_code == 200:
                logger.debug(f"Successfully sent telemetry batch to {self.endpoint}")
                return True
            else:
                logger.warning(f"HTTP telemetry batch failed: {response.status_code} {response.text}")
                return False

        except Exception as e:
            logger.error(f"Failed to send telemetry batch via HTTP: {e}")
            return False

    def is_available(self) -> bool:
        """Check if HTTP transport is available."""
        if not self.session:
            return False

        try:
            # Test connectivity with a simple ping
            response = self.session.get(f"{self.endpoint}/health", timeout=5)
            return response.status_code == 200
        except Exception:
            return False


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

    # Default to local file transport
    return LocalFileTransport()

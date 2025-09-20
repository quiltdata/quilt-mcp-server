"""
Telemetry Collector for MCP Tool Usage Analytics

This module collects comprehensive usage data from MCP servers while
maintaining user privacy and enabling performance optimization.
"""

import os
import time
import uuid
import hashlib
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class TelemetryLevel(Enum):
    """Telemetry collection levels."""

    DISABLED = "disabled"
    MINIMAL = "minimal"  # Only basic performance metrics
    STANDARD = "standard"  # Performance + tool usage patterns
    DETAILED = "detailed"  # Everything including context and errors


@dataclass
class TelemetryConfig:
    """Configuration for telemetry collection."""

    enabled: bool = True
    level: TelemetryLevel = TelemetryLevel.STANDARD
    local_only: bool = False
    endpoint: Optional[str] = None
    batch_size: int = 100
    flush_interval: int = 300  # seconds
    privacy_level: str = "standard"  # minimal, standard, strict
    session_timeout: int = 3600  # seconds

    @classmethod
    def from_env(cls) -> "TelemetryConfig":
        """Create config from environment variables."""
        return cls(
            enabled=os.getenv("MCP_TELEMETRY_ENABLED", "true").lower() == "true",
            level=TelemetryLevel(os.getenv("MCP_TELEMETRY_LEVEL", "standard")),
            local_only=os.getenv("MCP_TELEMETRY_LOCAL_ONLY", "false").lower() == "true",
            endpoint=os.getenv("MCP_TELEMETRY_ENDPOINT"),
            batch_size=int(os.getenv("MCP_TELEMETRY_BATCH_SIZE", "100")),
            flush_interval=int(os.getenv("MCP_TELEMETRY_FLUSH_INTERVAL", "300")),
            privacy_level=os.getenv("MCP_TELEMETRY_PRIVACY_LEVEL", "standard"),
            session_timeout=int(os.getenv("MCP_TELEMETRY_SESSION_TIMEOUT", "3600")),
        )


@dataclass
class ToolCallData:
    """Data structure for a single tool call."""

    tool_name: str
    args_hash: str
    execution_time: float
    success: bool
    timestamp: float
    sequence_position: int
    session_id: str
    error_type: Optional[str] = None
    result_size: Optional[int] = None
    context: Optional[Dict[str, Any]] = None


@dataclass
class TaskSession:
    """Data structure for a complete task session."""

    session_id: str
    start_time: float
    end_time: Optional[float] = None
    tool_calls: List[ToolCallData] = None
    task_type: Optional[str] = None
    completed: bool = False
    total_calls: int = 0
    efficiency_score: Optional[float] = None

    def __post_init__(self):
        if self.tool_calls is None:
            self.tool_calls = []


class TelemetryCollector:
    """Collects and manages MCP tool usage telemetry."""

    def __init__(self, config: Optional[TelemetryConfig] = None):
        self.config = config or TelemetryConfig.from_env()
        self.sessions: Dict[str, TaskSession] = {}
        self.current_session_id: Optional[str] = None
        self.sequence_counter = 0

        # Initialize transport if enabled
        self.transport = None
        if self.config.enabled and not self.config.local_only:
            from .transport import create_transport

            self.transport = create_transport(self.config)

        # Initialize privacy manager
        from .privacy import PrivacyManager

        self.privacy_manager = PrivacyManager(self.config.privacy_level)

        logger.info(f"TelemetryCollector initialized: enabled={self.config.enabled}, level={self.config.level.value}")

    def start_session(self, task_type: Optional[str] = None) -> str:
        """Start a new task session."""
        if not self.config.enabled:
            return "disabled"

        session_id = str(uuid.uuid4())
        self.current_session_id = session_id
        self.sequence_counter = 0

        session = TaskSession(session_id=session_id, start_time=time.time(), task_type=task_type)
        self.sessions[session_id] = session

        logger.debug(f"Started telemetry session: {session_id}")
        return session_id

    def end_session(self, session_id: Optional[str] = None, completed: bool = True) -> None:
        """End a task session."""
        if not self.config.enabled:
            return

        session_id = session_id or self.current_session_id
        if not session_id or session_id not in self.sessions:
            return

        session = self.sessions[session_id]
        session.end_time = time.time()
        session.completed = completed
        session.total_calls = len(session.tool_calls)

        # Calculate efficiency score
        if session.tool_calls:
            session.efficiency_score = self._calculate_efficiency_score(session)

        # Send session data if transport is available
        if self.transport and self.config.level != TelemetryLevel.DISABLED:
            try:
                self.transport.send_session(session)
            except Exception as e:
                logger.warning(f"Failed to send telemetry data: {e}")

        # Clean up
        if session_id == self.current_session_id:
            self.current_session_id = None

        # Keep session for a while for analysis, then clean up
        # In production, you might want to persist this data

        logger.debug(f"Ended telemetry session: {session_id}, completed={completed}")

    def record_tool_call(
        self,
        tool_name: str,
        args: Dict[str, Any],
        execution_time: float,
        success: bool,
        result: Any = None,
        error: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a tool call in the current session."""
        if not self.config.enabled or self.config.level == TelemetryLevel.DISABLED:
            return

        session_id = self.current_session_id
        if not session_id:
            # Auto-start session if none exists
            session_id = self.start_session()

        if session_id not in self.sessions:
            return

        # Anonymize and hash arguments
        args_hash = self.privacy_manager.hash_args(args)

        # Determine error type if applicable
        error_type = None
        if not success and error:
            error_type = type(error).__name__

        # Calculate result size if available
        result_size = None
        if success and result is not None:
            try:
                result_size = len(str(result))
            except Exception:
                pass

        # Filter context based on privacy level
        filtered_context = None
        if context and self.config.level in [
            TelemetryLevel.STANDARD,
            TelemetryLevel.DETAILED,
        ]:
            filtered_context = self.privacy_manager.filter_context(context)

        # Create tool call data
        call_data = ToolCallData(
            tool_name=tool_name,
            args_hash=args_hash,
            execution_time=execution_time,
            success=success,
            timestamp=time.time(),
            sequence_position=self.sequence_counter,
            session_id=session_id,
            error_type=error_type,
            result_size=result_size,
            context=filtered_context,
        )

        # Add to session
        session = self.sessions[session_id]
        session.tool_calls.append(call_data)
        self.sequence_counter += 1

        logger.debug(f"Recorded tool call: {tool_name} in session {session_id}")

    def get_session_stats(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Get statistics for a session."""
        session_id = session_id or self.current_session_id
        if not session_id or session_id not in self.sessions:
            return {}

        session = self.sessions[session_id]

        # Calculate basic stats
        total_time = (session.end_time or time.time()) - session.start_time
        success_rate = 0.0
        if session.tool_calls:
            successful_calls = sum(1 for call in session.tool_calls if call.success)
            success_rate = successful_calls / len(session.tool_calls)

        return {
            "session_id": session_id,
            "total_time": total_time,
            "total_calls": len(session.tool_calls),
            "success_rate": success_rate,
            "efficiency_score": session.efficiency_score,
            "completed": session.completed,
            "task_type": session.task_type,
        }

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get overall performance metrics across all sessions."""
        if not self.sessions:
            return {}

        # Aggregate metrics across all sessions
        total_sessions = len(self.sessions)
        completed_sessions = sum(1 for s in self.sessions.values() if s.completed)
        total_calls = sum(len(s.tool_calls) for s in self.sessions.values())

        # Calculate average metrics
        avg_calls_per_session = total_calls / total_sessions if total_sessions > 0 else 0
        completion_rate = completed_sessions / total_sessions if total_sessions > 0 else 0

        # Tool usage statistics
        tool_usage = {}
        for session in self.sessions.values():
            for call in session.tool_calls:
                tool_usage[call.tool_name] = tool_usage.get(call.tool_name, 0) + 1

        return {
            "total_sessions": total_sessions,
            "completed_sessions": completed_sessions,
            "completion_rate": completion_rate,
            "total_tool_calls": total_calls,
            "avg_calls_per_session": avg_calls_per_session,
            "tool_usage": tool_usage,
            "collection_enabled": self.config.enabled,
            "collection_level": self.config.level.value,
        }

    def _calculate_efficiency_score(self, session: TaskSession) -> float:
        """Calculate efficiency score for a session."""
        if not session.tool_calls:
            return 0.0

        # Basic efficiency metrics
        success_rate = sum(1 for call in session.tool_calls if call.success) / len(session.tool_calls)

        # Penalize for too many calls (assuming optimal is around 3-5 calls per task)
        optimal_calls = 4
        call_efficiency = min(1.0, optimal_calls / len(session.tool_calls))

        # Reward fast execution
        avg_execution_time = sum(call.execution_time for call in session.tool_calls) / len(session.tool_calls)
        time_efficiency = min(1.0, 2.0 / max(avg_execution_time, 0.1))  # Assume 2s is optimal

        # Combined score
        efficiency_score = (success_rate * 0.5) + (call_efficiency * 0.3) + (time_efficiency * 0.2)
        return round(efficiency_score, 3)

    def export_data(self, format: str = "json") -> Union[str, Dict[str, Any]]:
        """Export collected telemetry data."""
        if not self.config.enabled:
            return {} if format == "dict" else "{}"

        data = {
            "config": asdict(self.config),
            "sessions": [asdict(session) for session in self.sessions.values()],
            "performance_metrics": self.get_performance_metrics(),
            "export_timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if format == "json":
            return json.dumps(data, indent=2, default=str)
        return data

    def cleanup_old_sessions(self, max_age_seconds: int = 86400) -> int:
        """Clean up old sessions to prevent memory leaks."""
        current_time = time.time()
        old_sessions = []

        for session_id, session in self.sessions.items():
            session_age = current_time - session.start_time
            if session_age > max_age_seconds:
                old_sessions.append(session_id)

        for session_id in old_sessions:
            del self.sessions[session_id]
            if session_id == self.current_session_id:
                self.current_session_id = None

        logger.debug(f"Cleaned up {len(old_sessions)} old telemetry sessions")
        return len(old_sessions)


# Global telemetry collector instance
_global_collector: Optional[TelemetryCollector] = None


def get_telemetry_collector() -> TelemetryCollector:
    """Get or create the global telemetry collector."""
    global _global_collector
    if _global_collector is None:
        _global_collector = TelemetryCollector()
    return _global_collector


def configure_telemetry(config: TelemetryConfig) -> None:
    """Configure the global telemetry collector."""
    global _global_collector
    _global_collector = TelemetryCollector(config)

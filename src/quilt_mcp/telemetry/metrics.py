"""
Metrics calculation and performance analysis for MCP telemetry.

This module provides utilities for calculating performance metrics
and analyzing telemetry data to identify optimization opportunities.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import statistics


@dataclass
class PerformanceMetrics:
    """Container for performance metrics data."""

    response_time_ms: float
    success_rate: float
    error_count: int
    total_calls: int
    memory_usage_mb: Optional[float] = None
    cpu_usage_percent: Optional[float] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


class MetricsCalculator:
    """Calculate performance metrics from telemetry data."""

    def __init__(self):
        self.data_points: List[Dict[str, Any]] = []

    def add_data_point(self, data: Dict[str, Any]) -> None:
        """Add a telemetry data point for analysis."""
        self.data_points.append(data)

    def calculate_response_time_stats(self) -> Dict[str, float]:
        """Calculate response time statistics."""
        if not self.data_points:
            return {"mean": 0.0, "median": 0.0, "p95": 0.0, "p99": 0.0}

        response_times = [
            point.get("response_time_ms", 0.0) for point in self.data_points if "response_time_ms" in point
        ]

        if not response_times:
            return {"mean": 0.0, "median": 0.0, "p95": 0.0, "p99": 0.0}

        response_times.sort()
        return {
            "mean": statistics.mean(response_times),
            "median": statistics.median(response_times),
            "p95": self._percentile(response_times, 95),
            "p99": self._percentile(response_times, 99),
        }

    def calculate_success_rate(self) -> float:
        """Calculate overall success rate."""
        if not self.data_points:
            return 0.0

        successful = sum(1 for point in self.data_points if point.get("success", False))

        return successful / len(self.data_points) if self.data_points else 0.0

    def calculate_error_rate(self) -> float:
        """Calculate overall error rate."""
        return 1.0 - self.calculate_success_rate()

    def get_performance_metrics(self) -> PerformanceMetrics:
        """Get comprehensive performance metrics."""
        stats = self.calculate_response_time_stats()
        success_rate = self.calculate_success_rate()
        error_count = sum(1 for point in self.data_points if not point.get("success", True))

        return PerformanceMetrics(
            response_time_ms=stats["mean"],
            success_rate=success_rate,
            error_count=error_count,
            total_calls=len(self.data_points),
        )

    def identify_slow_operations(self, threshold_ms: float = 1000.0) -> List[Dict[str, Any]]:
        """Identify operations that exceed the response time threshold."""
        return [point for point in self.data_points if point.get("response_time_ms", 0.0) > threshold_ms]

    def get_tool_usage_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get usage statistics by tool name."""
        tool_stats = {}

        for point in self.data_points:
            tool_name = point.get("tool_name", "unknown")
            if tool_name not in tool_stats:
                tool_stats[tool_name] = {
                    "count": 0,
                    "total_time": 0.0,
                    "errors": 0,
                    "successes": 0,
                }

            stats = tool_stats[tool_name]
            stats["count"] += 1
            stats["total_time"] += point.get("response_time_ms", 0.0)

            if point.get("success", True):
                stats["successes"] += 1
            else:
                stats["errors"] += 1

        # Calculate averages
        for tool_name, stats in tool_stats.items():
            if stats["count"] > 0:
                stats["avg_response_time"] = stats["total_time"] / stats["count"]
                stats["success_rate"] = stats["successes"] / stats["count"]
            else:
                stats["avg_response_time"] = 0.0
                stats["success_rate"] = 0.0

        return tool_stats

    def clear_data(self) -> None:
        """Clear all collected data points."""
        self.data_points.clear()

    @staticmethod
    def _percentile(data: List[float], percentile: int) -> float:
        """Calculate the nth percentile of a sorted list."""
        if not data:
            return 0.0

        index = (percentile / 100.0) * (len(data) - 1)
        lower_index = int(index)
        upper_index = min(lower_index + 1, len(data) - 1)

        if lower_index == upper_index:
            return data[lower_index]

        # Linear interpolation
        weight = index - lower_index
        return data[lower_index] * (1 - weight) + data[upper_index] * weight

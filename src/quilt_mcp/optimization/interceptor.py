"""
Tool Call Interceptor for MCP Optimization

This module intercepts MCP tool calls to collect performance data,
analyze usage patterns, and enable optimization opportunities.
"""

import time
import functools
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass
import logging
from contextlib import contextmanager

from ..telemetry.collector import get_telemetry_collector

logger = logging.getLogger(__name__)


@dataclass
class OptimizationContext:
    """Context information for optimization analysis."""

    user_intent: Optional[str] = None
    task_type: Optional[str] = None
    expected_outcome: Optional[str] = None
    performance_target: Optional[str] = None  # "speed", "accuracy", "efficiency"
    sequence_id: Optional[str] = None
    parallel_execution: bool = False
    cache_enabled: bool = True


class ToolCallInterceptor:
    """Intercepts and analyzes MCP tool calls for optimization."""

    def __init__(self):
        self.telemetry = get_telemetry_collector()
        self.call_stack: List[Dict[str, Any]] = []
        self.current_context: Optional[OptimizationContext] = None
        self.performance_cache: Dict[str, Any] = {}

    @contextmanager
    def optimization_context(self, context: OptimizationContext):
        """Context manager for optimization analysis."""
        previous_context = self.current_context
        self.current_context = context

        # Start telemetry session if not already started
        session_id = self.telemetry.start_session(context.task_type)
        context.sequence_id = session_id

        try:
            yield context
        finally:
            # End telemetry session
            self.telemetry.end_session(session_id, completed=True)
            self.current_context = previous_context

    def intercept_tool_call(self, func: Callable) -> Callable:
        """Decorator to intercept tool calls."""

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            tool_name = func.__name__
            start_time = time.time()

            # Prepare call data
            call_data = {
                "tool_name": tool_name,
                "args": kwargs,
                "start_time": start_time,
                "context": self.current_context,
            }

            # Add to call stack
            self.call_stack.append(call_data)

            try:
                # Check for optimization opportunities before execution
                optimization = self._check_pre_execution_optimization(tool_name, kwargs)
                if optimization:
                    logger.info(f"Applying pre-execution optimization for {tool_name}: {optimization}")

                # Execute the function
                result = func(*args, **kwargs)

                # Calculate execution time
                execution_time = time.time() - start_time

                # Record successful call
                self.telemetry.record_tool_call(
                    tool_name=tool_name,
                    args=kwargs,
                    execution_time=execution_time,
                    success=True,
                    result=result,
                    context=self._get_telemetry_context(),
                )

                # Update call data
                call_data.update(
                    {
                        "success": True,
                        "execution_time": execution_time,
                        "result_size": len(str(result)) if result else 0,
                    }
                )

                # Check for post-execution optimizations
                self._check_post_execution_optimization(call_data, result)

                return result

            except Exception as e:
                execution_time = time.time() - start_time

                # Record failed call
                self.telemetry.record_tool_call(
                    tool_name=tool_name,
                    args=kwargs,
                    execution_time=execution_time,
                    success=False,
                    error=e,
                    context=self._get_telemetry_context(),
                )

                # Update call data
                call_data.update(
                    {
                        "success": False,
                        "execution_time": execution_time,
                        "error": str(e),
                    }
                )

                # Analyze failure for optimization opportunities
                self._analyze_failure(call_data, e)

                raise
            finally:
                # Remove from call stack
                if self.call_stack and self.call_stack[-1] == call_data:
                    self.call_stack.pop()

        return wrapper

    def _get_telemetry_context(self) -> Dict[str, Any]:
        """Get context information for telemetry."""
        context = {}

        if self.current_context:
            context.update(
                {
                    "user_intent": self.current_context.user_intent,
                    "task_type": self.current_context.task_type,
                    "expected_outcome": self.current_context.expected_outcome,
                    "performance_target": self.current_context.performance_target,
                    "sequence_position": len(self.call_stack),
                    "parallel_execution": self.current_context.parallel_execution,
                }
            )

        # Add call stack information
        if self.call_stack:
            context["call_stack_depth"] = len(self.call_stack)
            context["previous_tools"] = [call["tool_name"] for call in self.call_stack[-3:]]

        return context

    def _check_pre_execution_optimization(self, tool_name: str, kwargs: Dict[str, Any]) -> Optional[str]:
        """Check for optimization opportunities before tool execution."""
        optimizations = []

        # Check for redundant calls
        if self._is_redundant_call(tool_name, kwargs):
            optimizations.append("redundant_call_detected")

        # Check for better tool alternatives
        alternative = self._suggest_tool_alternative(tool_name, kwargs)
        if alternative:
            optimizations.append(f"consider_alternative:{alternative}")

        # Check for parameter optimizations
        param_opts = self._suggest_parameter_optimizations(tool_name, kwargs)
        if param_opts:
            optimizations.extend(param_opts)

        return "; ".join(optimizations) if optimizations else None

    def _check_post_execution_optimization(self, call_data: Dict[str, Any], result: Any) -> None:
        """Check for optimization opportunities after tool execution."""
        tool_name = call_data["tool_name"]
        execution_time = call_data["execution_time"]

        # Cache successful results for potential reuse
        if call_data["success"] and self.current_context and self.current_context.cache_enabled:
            cache_key = self._generate_cache_key(tool_name, call_data["args"])
            self.performance_cache[cache_key] = {
                "result": result,
                "execution_time": execution_time,
                "timestamp": time.time(),
            }

        # Analyze performance
        if execution_time > 5.0:  # Slow execution threshold
            logger.warning(f"Slow tool execution detected: {tool_name} took {execution_time:.2f}s")
            self._suggest_performance_improvements(call_data)

        # Check for sequence optimization opportunities
        self._analyze_call_sequence()

    def _analyze_failure(self, call_data: Dict[str, Any], error: Exception) -> None:
        """Analyze failed calls for optimization opportunities."""
        tool_name = call_data["tool_name"]
        error_type = type(error).__name__

        logger.debug(f"Analyzing failure: {tool_name} failed with {error_type}")

        # Common failure patterns and suggestions
        failure_patterns = {
            "PermissionError": "check_permissions_first",
            "FileNotFoundError": "verify_resource_exists",
            "ConnectionError": "check_network_connectivity",
            "TimeoutError": "increase_timeout_or_retry",
            "ValidationError": "validate_parameters_first",
        }

        if error_type in failure_patterns:
            suggestion = failure_patterns[error_type]
            logger.info(f"Optimization suggestion for {tool_name}: {suggestion}")

    def _is_redundant_call(self, tool_name: str, kwargs: Dict[str, Any]) -> bool:
        """Check if this call is redundant based on recent history."""
        if not self.call_stack:
            return False

        # Check last few calls for identical operations
        recent_calls = self.call_stack[-3:]
        for call in recent_calls:
            if (
                call["tool_name"] == tool_name
                and call.get("success", False)
                and self._args_similar(call["args"], kwargs)
            ):
                return True

        return False

    def _suggest_tool_alternative(self, tool_name: str, kwargs: Dict[str, Any]) -> Optional[str]:
        """Suggest alternative tools that might be more efficient."""

        # Tool alternatives mapping
        alternatives = {
            "package_create": {
                "condition": lambda args: len(args.get("s3_uris", [])) > 10,
                "alternative": "package_create_from_s3",
            },
            "bucket_objects_list": {
                "condition": lambda args: args.get("max_keys", 100) < 10,
                "alternative": "bucket_object_info",
            },
            "packages_list": {
                "condition": lambda args: args.get("prefix", ""),
                "alternative": "packages_search",
            },
        }

        if tool_name in alternatives:
            alt_config = alternatives[tool_name]
            if alt_config["condition"](kwargs):
                return alt_config["alternative"]

        return None

    def _suggest_parameter_optimizations(self, tool_name: str, kwargs: Dict[str, Any]) -> List[str]:
        """Suggest parameter optimizations for better performance."""
        suggestions = []

        # Common parameter optimizations
        if tool_name == "bucket_objects_list":
            if kwargs.get("max_keys", 100) > 1000:
                suggestions.append("consider_reducing_max_keys")
            if not kwargs.get("prefix"):
                suggestions.append("consider_adding_prefix_filter")

        elif tool_name == "package_browse":
            if kwargs.get("recursive", True) and kwargs.get("max_depth", 0) == 0:
                suggestions.append("consider_limiting_max_depth")

        elif tool_name == "athena_query_execute":
            if "LIMIT" not in kwargs.get("query", "").upper():
                suggestions.append("consider_adding_limit_clause")

        return suggestions

    def _suggest_performance_improvements(self, call_data: Dict[str, Any]) -> None:
        """Suggest performance improvements for slow calls."""
        tool_name = call_data["tool_name"]
        execution_time = call_data["execution_time"]

        improvements = {
            "package_browse": [
                "Use recursive=False for faster top-level browsing",
                "Set max_depth to limit recursion",
                "Use include_file_info=False if metadata not needed",
            ],
            "bucket_objects_list": [
                "Reduce max_keys parameter",
                "Use more specific prefix filtering",
                "Consider pagination for large results",
            ],
            "athena_query_execute": [
                "Add LIMIT clause to queries",
                "Use column selection instead of SELECT *",
                "Consider query optimization",
            ],
        }

        if tool_name in improvements:
            for improvement in improvements[tool_name]:
                logger.info(f"Performance improvement for {tool_name}: {improvement}")

    def _analyze_call_sequence(self) -> None:
        """Analyze the current call sequence for optimization opportunities."""
        if len(self.call_stack) < 2:
            return

        # Look for common inefficient patterns
        recent_tools = [call["tool_name"] for call in self.call_stack[-5:]]

        # Pattern: auth_status followed by every operation
        if recent_tools.count("auth_status") > 1:
            logger.info("Optimization: Consider caching auth_status results")

        # Pattern: Multiple list operations that could be combined
        list_tools = ["packages_list", "bucket_objects_list", "tables_list"]
        list_count = sum(1 for tool in recent_tools if tool in list_tools)
        if list_count > 2:
            logger.info("Optimization: Consider combining list operations")

        # Pattern: Browse followed by search (could be optimized)
        if len(recent_tools) >= 2 and recent_tools[-2:] == [
            "package_browse",
            "package_contents_search",
        ]:
            logger.info("Optimization: Consider using search with filters instead of browse+search")

    def _args_similar(self, args1: Dict[str, Any], args2: Dict[str, Any]) -> bool:
        """Check if two argument sets are similar enough to be considered redundant."""
        # Simple similarity check - could be made more sophisticated
        return args1 == args2

    def _generate_cache_key(self, tool_name: str, args: Dict[str, Any]) -> str:
        """Generate a cache key for tool results."""
        import hashlib
        import json

        cache_data = {"tool": tool_name, "args": args}

        cache_str = json.dumps(cache_data, sort_keys=True, default=str)
        return hashlib.md5(cache_str.encode()).hexdigest()

    def get_optimization_report(self) -> Dict[str, Any]:
        """Generate an optimization report based on collected data."""
        return {
            "total_calls": len(self.call_stack),
            "current_context": (self.current_context.__dict__ if self.current_context else None),
            "cache_size": len(self.performance_cache),
            "recent_tools": [call["tool_name"] for call in self.call_stack[-10:]],
            "performance_summary": self.telemetry.get_performance_metrics(),
        }


# Global interceptor instance
_global_interceptor: Optional[ToolCallInterceptor] = None


def get_tool_interceptor() -> ToolCallInterceptor:
    """Get or create the global tool call interceptor."""
    global _global_interceptor
    if _global_interceptor is None:
        _global_interceptor = ToolCallInterceptor()
    return _global_interceptor


def intercept_tool(func: Callable) -> Callable:
    """Decorator to intercept a tool function."""
    interceptor = get_tool_interceptor()
    return interceptor.intercept_tool_call(func)


def optimization_context(context: OptimizationContext):
    """Context manager for optimization analysis."""
    interceptor = get_tool_interceptor()
    return interceptor.optimization_context(context)

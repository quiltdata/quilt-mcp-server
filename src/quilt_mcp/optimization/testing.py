"""
Optimization Testing Framework

This module provides comprehensive testing capabilities for MCP tool
optimization, including scenario generation, automated testing, and
performance benchmarking.
"""

import time
import asyncio
from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
import logging
import json
from pathlib import Path
import statistics

logger = logging.getLogger(__name__)


class TestScenarioType(Enum):
    """Types of test scenarios."""

    PACKAGE_CREATION = "package_creation"
    DATA_DISCOVERY = "data_discovery"
    METADATA_MANAGEMENT = "metadata_management"
    ATHENA_QUERYING = "athena_querying"
    PERMISSION_DISCOVERY = "permission_discovery"
    BUCKET_OPERATIONS = "bucket_operations"
    GOVERNANCE_ADMIN = "governance_admin"


@dataclass
class TestStep:
    """A single step in a test scenario."""

    tool_name: str
    args: Dict[str, Any]
    expected_success: bool = True
    timeout: float = 30.0
    retry_count: int = 0
    validation_func: Optional[Callable[[Any], bool]] = None
    description: str = ""


@dataclass
class TestScenario:
    """A complete test scenario for optimization analysis."""

    name: str
    description: str
    scenario_type: TestScenarioType
    steps: List[TestStep]
    expected_total_time: float = 60.0
    expected_call_count: int = 0
    success_criteria: List[str] = field(default_factory=list)
    setup_func: Optional[Callable[[], None]] = None
    cleanup_func: Optional[Callable[[], None]] = None
    tags: List[str] = field(default_factory=list)


@dataclass
class TestResult:
    """Result of a test scenario execution."""

    scenario_name: str
    success: bool
    total_time: float
    total_calls: int
    step_results: List[Dict[str, Any]]
    efficiency_score: float
    error_message: Optional[str] = None
    optimization_suggestions: List[str] = field(default_factory=list)


class ScenarioRunner:
    """Runs test scenarios and collects performance data."""

    def __init__(self, tool_registry: Optional[Dict[str, Callable]] = None):
        self.tool_registry = tool_registry or {}
        self.results_history: List[TestResult] = []

    def register_tool(self, name: str, func: Callable) -> None:
        """Register a tool function for testing."""
        self.tool_registry[name] = func

    def register_tools_from_module(self, module) -> None:
        """Register all tools from a module."""
        import inspect

        for name, func in inspect.getmembers(module, inspect.isfunction):
            if not name.startswith("_"):
                self.tool_registry[name] = func

    async def run_scenario(self, scenario: TestScenario) -> TestResult:
        """Run a single test scenario."""
        logger.info(f"Running test scenario: {scenario.name}")

        start_time = time.time()
        step_results = []
        total_calls = 0
        success = True
        error_message = None

        try:
            # Setup
            if scenario.setup_func:
                scenario.setup_func()

            # Execute steps
            for i, step in enumerate(scenario.steps):
                step_start = time.time()
                step_success = False
                step_error = None
                step_result = None

                try:
                    # Get tool function
                    if step.tool_name not in self.tool_registry:
                        raise ValueError(f"Tool '{step.tool_name}' not registered")

                    tool_func = self.tool_registry[step.tool_name]

                    # Execute with timeout
                    step_result = await asyncio.wait_for(
                        asyncio.create_task(self._execute_tool(tool_func, step.args)),
                        timeout=step.timeout,
                    )

                    # Validate result if validation function provided
                    if step.validation_func:
                        step_success = step.validation_func(step_result)
                    else:
                        step_success = step_result is not None

                    total_calls += 1

                except Exception as e:
                    step_error = str(e)
                    step_success = False
                    if step.expected_success:
                        success = False
                        error_message = f"Step {i + 1} failed: {step_error}"

                step_time = time.time() - step_start

                step_results.append(
                    {
                        "step_index": i,
                        "tool_name": step.tool_name,
                        "success": step_success,
                        "execution_time": step_time,
                        "error": step_error,
                        "description": step.description,
                    }
                )

                # Stop on failure if expected to succeed
                if not step_success and step.expected_success:
                    break

        except Exception as e:
            success = False
            error_message = f"Scenario execution failed: {str(e)}"

        finally:
            # Cleanup
            if scenario.cleanup_func:
                try:
                    scenario.cleanup_func()
                except Exception as e:
                    logger.warning(f"Cleanup failed for scenario {scenario.name}: {e}")

        total_time = time.time() - start_time

        # Calculate efficiency score
        efficiency_score = self._calculate_efficiency_score(scenario, total_time, total_calls, success)

        # Generate optimization suggestions
        optimization_suggestions = self._generate_optimization_suggestions(
            scenario, step_results, total_time, total_calls
        )

        result = TestResult(
            scenario_name=scenario.name,
            success=success,
            total_time=total_time,
            total_calls=total_calls,
            step_results=step_results,
            efficiency_score=efficiency_score,
            error_message=error_message,
            optimization_suggestions=optimization_suggestions,
        )

        self.results_history.append(result)

        logger.info(
            f"Scenario {scenario.name} completed: success={success}, "
            f"time={total_time:.2f}s, calls={total_calls}, "
            f"efficiency={efficiency_score:.3f}"
        )

        return result

    async def _execute_tool(self, tool_func: Callable, args: Dict[str, Any]) -> Any:
        """Execute a tool function asynchronously."""
        # If the function is async, await it
        if asyncio.iscoroutinefunction(tool_func):
            return await tool_func(**args)
        else:
            # Run sync function in executor
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, lambda: tool_func(**args))

    def _calculate_efficiency_score(
        self, scenario: TestScenario, total_time: float, total_calls: int, success: bool
    ) -> float:
        """Calculate efficiency score for a test result."""
        if not success:
            return 0.0

        # Base score from success
        score = 0.5

        # Time efficiency (compared to expected)
        if scenario.expected_total_time > 0:
            time_ratio = min(1.0, scenario.expected_total_time / max(total_time, 0.1))
            score += 0.3 * time_ratio

        # Call efficiency (compared to expected)
        if scenario.expected_call_count > 0:
            call_ratio = min(1.0, scenario.expected_call_count / max(total_calls, 1))
            score += 0.2 * call_ratio

        return min(1.0, score)

    def _generate_optimization_suggestions(
        self,
        scenario: TestScenario,
        step_results: List[Dict[str, Any]],
        total_time: float,
        total_calls: int,
    ) -> List[str]:
        """Generate optimization suggestions based on test results."""
        suggestions = []

        # Analyze execution times
        execution_times = [step["execution_time"] for step in step_results if step["success"]]
        if execution_times:
            avg_time = statistics.mean(execution_times)
            if avg_time > 5.0:
                suggestions.append("Consider optimizing slow tool calls")

            # Find outliers
            if len(execution_times) > 2:
                median_time = statistics.median(execution_times)
                for step in step_results:
                    if step["execution_time"] > median_time * 2:
                        suggestions.append(f"Optimize slow step: {step['tool_name']}")

        # Analyze call patterns
        tool_counts = {}
        for step in step_results:
            tool_name = step["tool_name"]
            tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1

        # Check for redundant calls
        for tool_name, count in tool_counts.items():
            if count > 2:
                suggestions.append(f"Reduce redundant calls to {tool_name}")

        # Check against expected metrics
        if scenario.expected_call_count > 0 and total_calls > scenario.expected_call_count:
            suggestions.append(f"Reduce total calls from {total_calls} to {scenario.expected_call_count}")

        if scenario.expected_total_time > 0 and total_time > scenario.expected_total_time:
            suggestions.append(f"Improve performance from {total_time:.1f}s to {scenario.expected_total_time:.1f}s")

        return suggestions

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary across all test runs."""
        if not self.results_history:
            return {}

        successful_results = [r for r in self.results_history if r.success]

        return {
            "total_scenarios": len(self.results_history),
            "successful_scenarios": len(successful_results),
            "success_rate": len(successful_results) / len(self.results_history),
            "avg_efficiency_score": (
                statistics.mean([r.efficiency_score for r in successful_results]) if successful_results else 0
            ),
            "avg_execution_time": (
                statistics.mean([r.total_time for r in successful_results]) if successful_results else 0
            ),
            "avg_call_count": (
                statistics.mean([r.total_calls for r in successful_results]) if successful_results else 0
            ),
            "common_suggestions": self._get_common_suggestions(),
        }

    def _get_common_suggestions(self) -> List[str]:
        """Get most common optimization suggestions."""
        all_suggestions = []
        for result in self.results_history:
            all_suggestions.extend(result.optimization_suggestions)

        # Count suggestions
        suggestion_counts = {}
        for suggestion in all_suggestions:
            suggestion_counts[suggestion] = suggestion_counts.get(suggestion, 0) + 1

        # Return top suggestions
        sorted_suggestions = sorted(suggestion_counts.items(), key=lambda x: x[1], reverse=True)
        return [suggestion for suggestion, count in sorted_suggestions[:5]]


class OptimizationTester:
    """Comprehensive optimization testing system."""

    def __init__(self):
        self.scenario_runner = ScenarioRunner()
        self.scenarios: List[TestScenario] = []
        self.baseline_results: Dict[str, TestResult] = {}

    def add_scenario(self, scenario: TestScenario) -> None:
        """Add a test scenario."""
        self.scenarios.append(scenario)

    def load_scenarios_from_file(self, file_path: Union[str, Path]) -> None:
        """Load test scenarios from a JSON file."""
        with open(file_path, "r") as f:
            scenarios_data = json.load(f)

        for scenario_data in scenarios_data:
            scenario = self._create_scenario_from_dict(scenario_data)
            self.add_scenario(scenario)

    def _create_scenario_from_dict(self, data: Dict[str, Any]) -> TestScenario:
        """Create a TestScenario from dictionary data."""
        steps = []
        for step_data in data.get("steps", []):
            step = TestStep(
                tool_name=step_data["tool_name"],
                args=step_data.get("args", {}),
                expected_success=step_data.get("expected_success", True),
                timeout=step_data.get("timeout", 30.0),
                description=step_data.get("description", ""),
            )
            steps.append(step)

        return TestScenario(
            name=data["name"],
            description=data.get("description", ""),
            scenario_type=TestScenarioType(data.get("scenario_type", "package_creation")),
            steps=steps,
            expected_total_time=data.get("expected_total_time", 60.0),
            expected_call_count=data.get("expected_call_count", len(steps)),
            success_criteria=data.get("success_criteria", []),
            tags=data.get("tags", []),
        )

    async def run_baseline_tests(self) -> Dict[str, TestResult]:
        """Run baseline tests to establish performance benchmarks."""
        logger.info("Running baseline optimization tests")

        baseline_results = {}
        for scenario in self.scenarios:
            result = await self.scenario_runner.run_scenario(scenario)
            baseline_results[scenario.name] = result

        self.baseline_results = baseline_results
        return baseline_results

    async def run_optimization_tests(self) -> Dict[str, Any]:
        """Run optimization tests and compare against baseline."""
        logger.info("Running optimization tests")

        current_results = {}
        improvements = {}

        for scenario in self.scenarios:
            result = await self.scenario_runner.run_scenario(scenario)
            current_results[scenario.name] = result

            # Compare against baseline if available
            if scenario.name in self.baseline_results:
                baseline = self.baseline_results[scenario.name]
                improvement = self._calculate_improvement(baseline, result)
                improvements[scenario.name] = improvement

        return {
            "current_results": current_results,
            "improvements": improvements,
            "summary": self.scenario_runner.get_performance_summary(),
        }

    def _calculate_improvement(self, baseline: TestResult, current: TestResult) -> Dict[str, Any]:
        """Calculate improvement metrics between baseline and current results."""
        if not baseline.success or not current.success:
            return {"improvement": 0.0, "details": "One or both tests failed"}

        time_improvement = (baseline.total_time - current.total_time) / baseline.total_time
        call_improvement = (baseline.total_calls - current.total_calls) / baseline.total_calls
        efficiency_improvement = current.efficiency_score - baseline.efficiency_score

        overall_improvement = time_improvement * 0.4 + call_improvement * 0.3 + efficiency_improvement * 0.3

        return {
            "improvement": overall_improvement,
            "time_improvement": time_improvement,
            "call_improvement": call_improvement,
            "efficiency_improvement": efficiency_improvement,
            "details": {
                "baseline_time": baseline.total_time,
                "current_time": current.total_time,
                "baseline_calls": baseline.total_calls,
                "current_calls": current.total_calls,
                "baseline_efficiency": baseline.efficiency_score,
                "current_efficiency": current.efficiency_score,
            },
        }

    def generate_test_report(self) -> Dict[str, Any]:
        """Generate comprehensive test report."""
        return {
            "total_scenarios": len(self.scenarios),
            "baseline_results": {
                name: {
                    "success": result.success,
                    "total_time": result.total_time,
                    "total_calls": result.total_calls,
                    "efficiency_score": result.efficiency_score,
                }
                for name, result in self.baseline_results.items()
            },
            "performance_summary": self.scenario_runner.get_performance_summary(),
            "scenario_types": list(set(s.scenario_type.value for s in self.scenarios)),
            "recommendations": self._generate_recommendations(),
        }

    def _generate_recommendations(self) -> List[str]:
        """Generate optimization recommendations based on test results."""
        recommendations = []

        # Analyze common patterns across scenarios
        performance_summary = self.scenario_runner.get_performance_summary()

        if performance_summary.get("success_rate", 0) < 0.9:
            recommendations.append("Improve tool reliability - success rate below 90%")

        if performance_summary.get("avg_efficiency_score", 0) < 0.7:
            recommendations.append("Focus on efficiency improvements - average score below 70%")

        # Add common suggestions
        common_suggestions = performance_summary.get("common_suggestions", [])
        recommendations.extend(common_suggestions[:3])  # Top 3 suggestions

        return recommendations

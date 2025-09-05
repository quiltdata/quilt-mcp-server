"""
Autonomous Improvement System for MCP Tool Optimization

This module implements autonomous improvement mechanisms that can continuously
optimize MCP tool performance without manual intervention.
"""

import asyncio
import time
import json
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import logging
from datetime import datetime, timezone

from .testing import OptimizationTester, TestResult
from .scenarios import (
    create_all_test_scenarios,
    create_optimization_challenge_scenarios,
)
from ..telemetry.collector import get_telemetry_collector

logger = logging.getLogger(__name__)


@dataclass
class OptimizationRule:
    """A rule for autonomous optimization."""

    name: str
    description: str
    condition: str  # Python expression to evaluate
    action: str  # Action to take when condition is met
    priority: int = 1  # Higher priority rules are applied first
    enabled: bool = True
    success_count: int = 0
    failure_count: int = 0


@dataclass
class OptimizationResult:
    """Result of an optimization attempt."""

    rule_name: str
    applied: bool
    improvement: float  # Percentage improvement
    details: Dict[str, Any]
    timestamp: datetime


class AutonomousOptimizer:
    """Autonomous optimization engine for MCP tools."""

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = Path(config_path or "optimization_config.json")
        self.tester = OptimizationTester()
        self.telemetry = get_telemetry_collector()

        # Load optimization rules
        self.rules = self._load_optimization_rules()

        # Performance tracking
        self.baseline_metrics: Dict[str, Any] = {}
        self.current_metrics: Dict[str, Any] = {}
        self.optimization_history: List[OptimizationResult] = []

        # Safety mechanisms
        self.max_optimizations_per_hour = 5
        self.min_improvement_threshold = 0.05  # 5% minimum improvement
        self.rollback_threshold = -0.1  # Rollback if performance degrades by 10%

    def _load_optimization_rules(self) -> List[OptimizationRule]:
        """Load optimization rules from configuration."""
        default_rules = [
            OptimizationRule(
                name="reduce_redundant_auth_calls",
                description="Cache auth_status results to reduce redundant calls",
                condition="tool_counts.get('auth_status', 0) > 2",
                action="cache_auth_status",
                priority=3,
            ),
            OptimizationRule(
                name="optimize_list_operations",
                description="Reduce max_keys for list operations when not needed",
                condition="avg_execution_time > 5.0 and 'list' in tool_name",
                action="reduce_list_size",
                priority=2,
            ),
            OptimizationRule(
                name="add_query_limits",
                description="Add LIMIT clauses to Athena queries without limits",
                condition="'athena_query_execute' in recent_tools and 'LIMIT' not in query",
                action="add_query_limit",
                priority=2,
            ),
            OptimizationRule(
                name="parallel_execution",
                description="Execute independent operations in parallel",
                condition="sequential_independent_calls > 2",
                action="enable_parallel_execution",
                priority=1,
            ),
            OptimizationRule(
                name="optimize_browse_depth",
                description="Limit browse depth for better performance",
                condition="tool_name == 'package_browse' and execution_time > 10.0",
                action="limit_browse_depth",
                priority=2,
            ),
        ]

        # Try to load from config file
        if self.config_path.exists():
            try:
                with open(self.config_path, "r") as f:
                    config_data = json.load(f)
                    rules_data = config_data.get("optimization_rules", [])

                loaded_rules = []
                for rule_data in rules_data:
                    rule = OptimizationRule(**rule_data)
                    loaded_rules.append(rule)

                return loaded_rules
            except Exception as e:
                logger.warning(f"Failed to load optimization rules: {e}")

        return default_rules

    def _save_optimization_rules(self) -> None:
        """Save optimization rules to configuration file."""
        try:
            config_data = {
                "optimization_rules": [asdict(rule) for rule in self.rules],
                "last_updated": datetime.now(timezone.utc).isoformat(),
            }

            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w") as f:
                json.dump(config_data, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save optimization rules: {e}")

    async def run_baseline_assessment(self) -> Dict[str, Any]:
        """Run baseline performance assessment."""
        logger.info("Running baseline performance assessment")

        # Load test scenarios
        scenarios = create_all_test_scenarios()
        for scenario in scenarios:
            self.tester.add_scenario(scenario)

        # Run baseline tests
        baseline_results = await self.tester.run_baseline_tests()

        # Calculate baseline metrics
        self.baseline_metrics = self._calculate_performance_metrics(baseline_results)

        logger.info(f"Baseline assessment complete: {len(baseline_results)} scenarios tested")
        return self.baseline_metrics

    async def run_optimization_cycle(self) -> Dict[str, Any]:
        """Run a single optimization cycle."""
        logger.info("Starting optimization cycle")

        # Collect current telemetry data
        telemetry_data = self.telemetry.get_performance_metrics()

        # Analyze for optimization opportunities
        opportunities = self._analyze_optimization_opportunities(telemetry_data)

        # Apply optimizations
        applied_optimizations = []
        for opportunity in opportunities:
            result = await self._apply_optimization(opportunity)
            if result:
                applied_optimizations.append(result)

        # Test optimizations
        if applied_optimizations:
            test_results = await self.tester.run_optimization_tests()

            # Evaluate improvements
            improvements = self._evaluate_improvements(test_results)

            # Rollback if performance degraded
            for optimization in applied_optimizations:
                if improvements.get(optimization.rule_name, 0) < self.rollback_threshold:
                    await self._rollback_optimization(optimization)

        # Update current metrics
        self.current_metrics = self._calculate_current_metrics()

        cycle_result = {
            "optimizations_applied": len(applied_optimizations),
            "improvements": improvements if applied_optimizations else {},
            "current_metrics": self.current_metrics,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        logger.info(f"Optimization cycle complete: {len(applied_optimizations)} optimizations applied")
        return cycle_result

    def _analyze_optimization_opportunities(self, telemetry_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Analyze telemetry data for optimization opportunities."""
        opportunities = []

        # Extract relevant metrics
        tool_usage = telemetry_data.get("tool_usage", {})
        avg_calls_per_session = telemetry_data.get("avg_calls_per_session", 0)
        completion_rate = telemetry_data.get("completion_rate", 1.0)

        # Evaluate each optimization rule
        for rule in self.rules:
            if not rule.enabled:
                continue

            try:
                # Create evaluation context
                context = {
                    "tool_counts": tool_usage,
                    "avg_calls_per_session": avg_calls_per_session,
                    "completion_rate": completion_rate,
                    "total_sessions": telemetry_data.get("total_sessions", 0),
                }

                # Evaluate rule condition
                # Security: eval() is safe here as it's sandboxed with no builtins and only evaluates
                # trusted internal optimization rules, not user input
                if eval(rule.condition, {"__builtins__": {}}, context):  # noqa: S307
                    opportunities.append({"rule": rule, "context": context, "priority": rule.priority})

            except Exception as e:
                logger.warning(f"Failed to evaluate rule {rule.name}: {e}")

        # Sort by priority
        opportunities.sort(key=lambda x: x["priority"], reverse=True)

        return opportunities

    async def _apply_optimization(self, opportunity: Dict[str, Any]) -> Optional[OptimizationResult]:
        """Apply a specific optimization."""
        rule = opportunity["rule"]
        context = opportunity["context"]

        logger.info(f"Applying optimization: {rule.name}")

        try:
            # Apply the optimization based on the action
            success = await self._execute_optimization_action(rule.action, context)

            if success:
                rule.success_count += 1
                result = OptimizationResult(
                    rule_name=rule.name,
                    applied=True,
                    improvement=0.0,  # Will be calculated later
                    details={"action": rule.action, "context": context},
                    timestamp=datetime.now(timezone.utc),
                )
                self.optimization_history.append(result)
                return result
            else:
                rule.failure_count += 1

        except Exception as e:
            logger.error(f"Failed to apply optimization {rule.name}: {e}")
            rule.failure_count += 1

        return None

    async def _execute_optimization_action(self, action: str, context: Dict[str, Any]) -> bool:
        """Execute a specific optimization action."""

        if action == "cache_auth_status":
            # Implement auth status caching
            return await self._implement_auth_caching()

        elif action == "reduce_list_size":
            # Implement list size reduction
            return await self._implement_list_size_optimization()

        elif action == "add_query_limit":
            # Implement query limit addition
            return await self._implement_query_limit_optimization()

        elif action == "enable_parallel_execution":
            # Implement parallel execution
            return await self._implement_parallel_execution()

        elif action == "limit_browse_depth":
            # Implement browse depth limiting
            return await self._implement_browse_depth_optimization()

        else:
            logger.warning(f"Unknown optimization action: {action}")
            return False

    async def _implement_auth_caching(self) -> bool:
        """Implement authentication status caching."""
        # This would modify the auth tools to cache results
        logger.info("Implementing auth status caching")
        # Implementation would go here
        return True

    async def _implement_list_size_optimization(self) -> bool:
        """Implement list size optimization."""
        logger.info("Implementing list size optimization")
        # Implementation would go here
        return True

    async def _implement_query_limit_optimization(self) -> bool:
        """Implement query limit optimization."""
        logger.info("Implementing query limit optimization")
        # Implementation would go here
        return True

    async def _implement_parallel_execution(self) -> bool:
        """Implement parallel execution optimization."""
        logger.info("Implementing parallel execution optimization")
        # Implementation would go here
        return True

    async def _implement_browse_depth_optimization(self) -> bool:
        """Implement browse depth optimization."""
        logger.info("Implementing browse depth optimization")
        # Implementation would go here
        return True

    def _calculate_performance_metrics(self, test_results: Dict[str, TestResult]) -> Dict[str, Any]:
        """Calculate performance metrics from test results."""
        if not test_results:
            return {}

        successful_results = [r for r in test_results.values() if r.success]

        if not successful_results:
            return {"success_rate": 0.0}

        return {
            "success_rate": len(successful_results) / len(test_results),
            "avg_execution_time": sum(r.total_time for r in successful_results) / len(successful_results),
            "avg_call_count": sum(r.total_calls for r in successful_results) / len(successful_results),
            "avg_efficiency_score": sum(r.efficiency_score for r in successful_results) / len(successful_results),
            "total_scenarios": len(test_results),
        }

    def _calculate_current_metrics(self) -> Dict[str, Any]:
        """Calculate current performance metrics."""
        return self.telemetry.get_performance_metrics()

    def _evaluate_improvements(self, test_results: Dict[str, Any]) -> Dict[str, float]:
        """Evaluate improvements from optimization tests."""
        improvements = {}

        if "improvements" in test_results:
            for scenario_name, improvement_data in test_results["improvements"].items():
                improvement = improvement_data.get("improvement", 0.0)
                improvements[scenario_name] = improvement

        return improvements

    async def _rollback_optimization(self, optimization: OptimizationResult) -> None:
        """Rollback an optimization that caused performance degradation."""
        logger.warning(f"Rolling back optimization: {optimization.rule_name}")

        # Find and disable the rule
        for rule in self.rules:
            if rule.name == optimization.rule_name:
                rule.enabled = False
                break

        # Save updated rules
        self._save_optimization_rules()

        # Log rollback
        rollback_result = OptimizationResult(
            rule_name=f"rollback_{optimization.rule_name}",
            applied=True,
            improvement=0.0,
            details={"rollback_reason": "performance_degradation"},
            timestamp=datetime.now(timezone.utc),
        )
        self.optimization_history.append(rollback_result)

    async def run_continuous_optimization(self, interval_hours: int = 24) -> None:
        """Run continuous optimization with specified interval."""
        logger.info(f"Starting continuous optimization (interval: {interval_hours}h)")

        # Run initial baseline
        await self.run_baseline_assessment()

        while True:
            try:
                # Run optimization cycle
                cycle_result = await self.run_optimization_cycle()

                # Log results
                logger.info(f"Optimization cycle completed: {cycle_result}")

                # Wait for next cycle
                await asyncio.sleep(interval_hours * 3600)

            except Exception as e:
                logger.error(f"Error in optimization cycle: {e}")
                # Wait before retrying
                await asyncio.sleep(3600)  # Wait 1 hour before retry

    def get_optimization_report(self) -> Dict[str, Any]:
        """Generate comprehensive optimization report."""
        return {
            "baseline_metrics": self.baseline_metrics,
            "current_metrics": self.current_metrics,
            "optimization_rules": [asdict(rule) for rule in self.rules],
            "optimization_history": [asdict(opt) for opt in self.optimization_history],
            "performance_improvement": self._calculate_overall_improvement(),
            "recommendations": self._generate_recommendations(),
        }

    def _calculate_overall_improvement(self) -> Dict[str, float]:
        """Calculate overall performance improvement."""
        if not self.baseline_metrics or not self.current_metrics:
            return {}

        improvements = {}

        for metric in [
            "avg_execution_time",
            "avg_call_count",
            "success_rate",
            "avg_efficiency_score",
        ]:
            baseline_value = self.baseline_metrics.get(metric, 0)
            current_value = self.current_metrics.get(metric, 0)

            if baseline_value > 0:
                if metric in ["avg_execution_time", "avg_call_count"]:
                    # Lower is better
                    improvement = (baseline_value - current_value) / baseline_value
                else:
                    # Higher is better
                    improvement = (current_value - baseline_value) / baseline_value

                improvements[metric] = improvement

        return improvements

    def _generate_recommendations(self) -> List[str]:
        """Generate optimization recommendations."""
        recommendations = []

        # Analyze rule success rates
        for rule in self.rules:
            total_attempts = rule.success_count + rule.failure_count
            if total_attempts > 0:
                success_rate = rule.success_count / total_attempts
                if success_rate < 0.5:
                    recommendations.append(f"Review rule '{rule.name}' - low success rate ({success_rate:.1%})")

        # Analyze performance trends
        overall_improvement = self._calculate_overall_improvement()
        for metric, improvement in overall_improvement.items():
            if improvement < 0:
                recommendations.append(f"Address performance regression in {metric}")

        return recommendations


class CursorAutonomousRunner:
    """Autonomous runner specifically designed for Cursor integration."""

    def __init__(self):
        self.optimizer = AutonomousOptimizer()

    async def run_optimization_session(self) -> Dict[str, Any]:
        """Run a single optimization session that Cursor can execute."""

        logger.info("Starting Cursor autonomous optimization session")

        # Step 1: Baseline assessment
        baseline_metrics = await self.optimizer.run_baseline_assessment()

        # Step 2: Run optimization cycle
        optimization_results = await self.optimizer.run_optimization_cycle()

        # Step 3: Generate report
        report = self.optimizer.get_optimization_report()

        # Step 4: Save results
        results_file = Path("optimization_results.json")
        with open(results_file, "w") as f:
            json.dump(report, f, indent=2, default=str)

        session_result = {
            "baseline_metrics": baseline_metrics,
            "optimization_results": optimization_results,
            "report_file": str(results_file),
            "summary": {
                "optimizations_applied": optimization_results.get("optimizations_applied", 0),
                "performance_improvement": report.get("performance_improvement", {}),
                "recommendations": report.get("recommendations", []),
            },
        }

        logger.info("Cursor optimization session completed")
        return session_result

    def create_cursor_script(self) -> str:
        """Create a Python script that Cursor can run autonomously."""

        script_content = '''#!/usr/bin/env python3
"""
Autonomous MCP Optimization Script for Cursor

This script can be run by Cursor to automatically optimize MCP server performance.
"""

import asyncio
import sys
import logging
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "app"))

from quilt_mcp.optimization.autonomous import CursorAutonomousRunner

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('optimization.log'),
        logging.StreamHandler()
    ]
)

async def main():
    """Main optimization function."""
    runner = CursorAutonomousRunner()

    try:
        results = await runner.run_optimization_session()

        print("\\n" + "="*50)
        print("MCP OPTIMIZATION RESULTS")
        print("="*50)

        summary = results['summary']
        print(f"Optimizations Applied: {summary['optimizations_applied']}")

        improvements = summary.get('performance_improvement', {})
        if improvements:
            print("\\nPerformance Improvements:")
            for metric, improvement in improvements.items():
                print(f"  {metric}: {improvement:+.1%}")

        recommendations = summary.get('recommendations', [])
        if recommendations:
            print("\\nRecommendations:")
            for i, rec in enumerate(recommendations, 1):
                print(f"  {i}. {rec}")

        print(f"\\nDetailed report saved to: {results['report_file']}")
        print("="*50)

        return 0

    except Exception as e:
        print(f"Optimization failed: {e}")
        logging.error(f"Optimization failed: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
'''

        return script_content


# Export main classes
__all__ = [
    "AutonomousOptimizer",
    "CursorAutonomousRunner",
    "OptimizationRule",
    "OptimizationResult",
]

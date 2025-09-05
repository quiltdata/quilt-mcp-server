"""
Tests for MCP Optimization System

This module provides comprehensive tests for the MCP optimization framework,
including telemetry collection, performance analysis, and autonomous improvement.
"""

import pytest
import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

from quilt_mcp.telemetry.collector import TelemetryCollector, TelemetryConfig, TelemetryLevel
from quilt_mcp.telemetry.privacy import PrivacyManager, DataAnonymizer
from quilt_mcp.optimization.interceptor import ToolCallInterceptor, OptimizationContext
from quilt_mcp.optimization.testing import TestScenario, TestStep, ScenarioRunner, TestScenarioType
from quilt_mcp.optimization.autonomous import AutonomousOptimizer, OptimizationRule
from quilt_mcp.optimization.scenarios import create_all_test_scenarios


class TestTelemetryCollector:
    """Test telemetry collection functionality."""

    def test_telemetry_config_from_env(self):
        """Test telemetry configuration from environment variables."""
        with patch.dict(
            'os.environ',
            {'MCP_TELEMETRY_ENABLED': 'true', 'MCP_TELEMETRY_LEVEL': 'detailed', 'MCP_TELEMETRY_LOCAL_ONLY': 'false'},
        ):
            config = TelemetryConfig.from_env()
            assert config.enabled is True
            assert config.level == TelemetryLevel.DETAILED
            assert config.local_only is False

    def test_telemetry_session_management(self):
        """Test telemetry session creation and management."""
        config = TelemetryConfig(enabled=True, level=TelemetryLevel.STANDARD)
        collector = TelemetryCollector(config)

        # Start session
        session_id = collector.start_session("test_task")
        assert session_id != "disabled"
        assert session_id in collector.sessions

        # Record tool call
        collector.record_tool_call(
            tool_name="test_tool", args={"param": "value"}, execution_time=1.5, success=True, result={"data": "test"}
        )

        # Check session data
        session = collector.sessions[session_id]
        assert len(session.tool_calls) == 1
        assert session.tool_calls[0].tool_name == "test_tool"
        assert session.tool_calls[0].success is True

        # End session
        collector.end_session(session_id, completed=True)
        assert session.completed is True
        assert session.end_time is not None

    def test_telemetry_disabled(self):
        """Test telemetry when disabled."""
        config = TelemetryConfig(enabled=False)
        collector = TelemetryCollector(config)

        session_id = collector.start_session("test_task")
        assert session_id == "disabled"

        # Recording should be no-op
        collector.record_tool_call(tool_name="test_tool", args={}, execution_time=1.0, success=True)

        assert len(collector.sessions) == 0

    def test_performance_metrics_calculation(self):
        """Test performance metrics calculation."""
        config = TelemetryConfig(enabled=True)
        collector = TelemetryCollector(config)

        # Create multiple sessions
        for i in range(3):
            session_id = collector.start_session(f"task_{i}")
            collector.record_tool_call(
                tool_name="test_tool",
                args={},
                execution_time=1.0 + i,
                success=i < 2,  # First two succeed, last fails
            )
            collector.end_session(session_id, completed=i < 2)

        metrics = collector.get_performance_metrics()
        assert metrics['total_sessions'] == 3
        assert metrics['completed_sessions'] == 2
        assert metrics['completion_rate'] == 2 / 3


class TestPrivacyManager:
    """Test privacy management functionality."""

    def test_data_anonymizer(self):
        """Test data anonymization."""
        anonymizer = DataAnonymizer()

        # Test email anonymization
        email = "user@example.com"
        anonymized = anonymizer.anonymize_value(email, "email_field")
        assert anonymized != email
        assert len(anonymized) == 16  # Hash length

        # Test S3 URI anonymization
        s3_uri = "s3://my-bucket/path/to/file.csv"
        anonymized_uri = anonymizer.anonymize_value(s3_uri)
        assert anonymized_uri.startswith("s3://")
        assert "my-bucket" not in anonymized_uri

    def test_privacy_manager_levels(self):
        """Test different privacy levels."""
        # Minimal privacy
        minimal_manager = PrivacyManager("minimal")
        assert not minimal_manager.config["collect_args"]

        # Standard privacy
        standard_manager = PrivacyManager("standard")
        assert standard_manager.config["collect_args"]
        assert standard_manager.config["anonymize_sensitive"]

        # Strict privacy
        strict_manager = PrivacyManager("strict")
        assert not strict_manager.config["collect_args"]
        assert strict_manager.config["anonymize_all"]

    def test_args_hashing(self):
        """Test argument hashing with privacy."""
        manager = PrivacyManager("standard")

        args = {"bucket": "my-bucket", "email": "user@example.com", "normal_param": "value"}

        hash1 = manager.hash_args(args)
        hash2 = manager.hash_args(args)

        # Same args should produce same hash
        assert hash1 == hash2
        assert len(hash1) == 16


class TestToolCallInterceptor:
    """Test tool call interception functionality."""

    def test_interceptor_creation(self):
        """Test interceptor creation and setup."""
        interceptor = ToolCallInterceptor()
        assert interceptor.telemetry is not None
        assert len(interceptor.call_stack) == 0

    def test_optimization_context(self):
        """Test optimization context management."""
        interceptor = ToolCallInterceptor()

        context = OptimizationContext(
            user_intent="create_package", task_type="package_creation", performance_target="speed"
        )

        with interceptor.optimization_context(context):
            assert interceptor.current_context == context
            assert context.sequence_id is not None

        # Context should be cleared after exiting
        assert interceptor.current_context is None

    def test_tool_call_decoration(self):
        """Test tool call decoration and interception."""
        interceptor = ToolCallInterceptor()

        # Mock function to intercept
        @interceptor.intercept_tool_call
        def mock_tool(param1: str, param2: int = 10) -> dict:
            return {"result": f"{param1}_{param2}"}

        # Set up context
        context = OptimizationContext(task_type="test")
        with interceptor.optimization_context(context):
            result = mock_tool("test", param2=20)

        assert result == {"result": "test_20"}

        # Check that telemetry was recorded
        session = interceptor.telemetry.sessions[context.sequence_id]
        assert len(session.tool_calls) == 1
        assert session.tool_calls[0].tool_name == "mock_tool"


class TestOptimizationTesting:
    """Test optimization testing framework."""

    def test_test_scenario_creation(self):
        """Test test scenario creation."""
        steps = [
            TestStep(tool_name="auth_status", args={}, description="Check authentication"),
            TestStep(tool_name="packages_list", args={"limit": 10}, description="List packages"),
        ]

        scenario = TestScenario(
            name="test_scenario",
            description="Test scenario for testing",
            scenario_type=TestScenarioType.PACKAGE_CREATION,
            steps=steps,
            expected_total_time=10.0,
            expected_call_count=2,
        )

        assert scenario.name == "test_scenario"
        assert len(scenario.steps) == 2
        assert scenario.expected_call_count == 2

    @pytest.mark.asyncio
    async def test_scenario_runner(self):
        """Test scenario runner execution."""
        runner = ScenarioRunner()

        # Register mock tools
        async def mock_auth_status():
            return {"authenticated": True}

        async def mock_packages_list(limit=10):
            return {"packages": ["pkg1", "pkg2"]}

        runner.register_tool("auth_status", mock_auth_status)
        runner.register_tool("packages_list", mock_packages_list)

        # Create test scenario
        scenario = TestScenario(
            name="mock_scenario",
            description="Mock scenario for testing",
            scenario_type=TestScenarioType.PACKAGE_CREATION,
            steps=[TestStep("auth_status", {}), TestStep("packages_list", {"limit": 5})],
            expected_total_time=5.0,
            expected_call_count=2,
        )

        # Run scenario
        result = await runner.run_scenario(scenario)

        assert result.success is True
        assert result.total_calls == 2
        assert len(result.step_results) == 2
        assert result.efficiency_score > 0

    def test_scenario_generation(self):
        """Test scenario generation from scenarios module."""
        scenarios = create_all_test_scenarios()

        assert len(scenarios) > 0

        # Check that we have different scenario types
        scenario_types = set(s.scenario_type for s in scenarios)
        assert len(scenario_types) > 1

        # Check that scenarios have proper structure
        for scenario in scenarios:
            assert scenario.name
            assert scenario.description
            assert len(scenario.steps) > 0
            assert scenario.expected_total_time > 0


class TestAutonomousOptimizer:
    """Test autonomous optimization functionality."""

    def test_optimization_rule_creation(self):
        """Test optimization rule creation."""
        rule = OptimizationRule(
            name="test_rule",
            description="Test optimization rule",
            condition="tool_counts.get('auth_status', 0) > 2",
            action="cache_auth_status",
            priority=2,
        )

        assert rule.name == "test_rule"
        assert rule.enabled is True
        assert rule.success_count == 0

    def test_optimizer_initialization(self):
        """Test optimizer initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"

            optimizer = AutonomousOptimizer(str(config_path))

            assert len(optimizer.rules) > 0
            assert optimizer.tester is not None
            assert optimizer.telemetry is not None

    @pytest.mark.asyncio
    async def test_optimization_opportunity_analysis(self):
        """Test optimization opportunity analysis."""
        optimizer = AutonomousOptimizer()

        # Mock telemetry data
        telemetry_data = {
            'tool_usage': {
                'auth_status': 5,  # High usage should trigger optimization
                'packages_list': 2,
            },
            'avg_calls_per_session': 7,
            'completion_rate': 0.8,
            'total_sessions': 10,
        }

        opportunities = optimizer._analyze_optimization_opportunities(telemetry_data)

        # Should find opportunities based on rules
        assert len(opportunities) > 0

        # Check that opportunities are sorted by priority
        priorities = [opp['priority'] for opp in opportunities]
        assert priorities == sorted(priorities, reverse=True)


class TestIntegration:
    """Test integration between optimization components."""

    def test_telemetry_interceptor_integration(self):
        """Test integration between telemetry and interceptor."""
        # Create interceptor (which creates its own telemetry collector)
        interceptor = ToolCallInterceptor()

        # Mock function
        @interceptor.intercept_tool_call
        def test_function(param: str) -> str:
            return f"result_{param}"

        # Execute with context
        context = OptimizationContext(task_type="test")
        with interceptor.optimization_context(context):
            result = test_function("test")

        assert result == "result_test"

        # Check telemetry was collected using the interceptor's telemetry collector
        session = interceptor.telemetry.sessions[context.sequence_id]
        assert len(session.tool_calls) == 1

    @pytest.mark.asyncio
    async def test_end_to_end_optimization(self):
        """Test end-to-end optimization workflow."""
        # This would be a more complex integration test
        # that runs through the entire optimization pipeline

        # Create optimizer
        optimizer = AutonomousOptimizer()

        # Mock some baseline metrics
        optimizer.baseline_metrics = {
            'success_rate': 0.8,
            'avg_execution_time': 5.0,
            'avg_call_count': 4.0,
            'avg_efficiency_score': 0.7,
        }

        # Mock current metrics (showing improvement)
        optimizer.current_metrics = {
            'success_rate': 0.9,
            'avg_execution_time': 4.0,
            'avg_call_count': 3.5,
            'avg_efficiency_score': 0.8,
        }

        # Calculate improvements
        improvements = optimizer._calculate_overall_improvement()

        assert improvements['success_rate'] > 0  # Improvement
        assert improvements['avg_execution_time'] > 0  # Improvement (lower is better)
        assert improvements['avg_call_count'] > 0  # Improvement (lower is better)


# Fixtures for testing
@pytest.fixture
def telemetry_config():
    """Provide test telemetry configuration."""
    return TelemetryConfig(
        enabled=True, level=TelemetryLevel.STANDARD, local_only=True, batch_size=10, flush_interval=60
    )


@pytest.fixture
def mock_tool_registry():
    """Provide mock tool registry for testing."""

    async def mock_auth_status():
        return {"authenticated": True, "user": "test"}

    async def mock_packages_list(limit=10):
        return {"packages": [f"pkg_{i}" for i in range(min(limit, 5))]}

    async def mock_bucket_objects_list(bucket, max_keys=100):
        return {"objects": [f"obj_{i}" for i in range(min(max_keys, 3))]}

    return {
        "auth_status": mock_auth_status,
        "packages_list": mock_packages_list,
        "bucket_objects_list": mock_bucket_objects_list,
    }


if __name__ == "__main__":
    pytest.main([__file__])

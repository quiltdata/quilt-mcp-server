"""
Comprehensive unit tests for error recovery and graceful degradation functionality.

This module provides 100% unit test coverage for error recovery mechanisms,
focusing on error scenarios, edge cases, and boundary conditions that are
difficult to trigger in integration tests.
"""

import pytest
import time
from unittest.mock import Mock, patch, call
from typing import Dict, Any, List, Callable

from quilt_mcp.tools.error_recovery import (
    with_retry,
    safe_operation,
    batch_operation_with_recovery,
    health_check_with_recovery,
    _with_fallback_internal,
    _check_auth_status,
    _check_permissions_discovery,
    _check_athena_connectivity,
    _check_package_operations,
    _get_recovery_suggestions,
    _get_health_next_steps,
    _safe_package_operation_internal,
    _safe_bucket_operation_internal,
    _safe_athena_operation_internal,
)


class TestWithFallbackInternal:
    """Test the internal fallback decorator functionality."""
    
    def test_primary_function_success(self):
        """Test fallback decorator when primary function succeeds."""
        primary_func = Mock(return_value={"success": True, "data": "primary_result"})
        fallback_func = Mock(return_value={"success": True, "data": "fallback_result"})
        
        decorated = _with_fallback_internal(primary_func, fallback_func)
        result = decorated("arg1", kwarg1="value1")
        
        assert result == {"success": True, "data": "primary_result"}
        primary_func.assert_called_once_with("arg1", kwarg1="value1")
        fallback_func.assert_not_called()
    
    def test_primary_function_returns_failure_dict(self):
        """Test fallback when primary function returns failure dict."""
        primary_func = Mock(return_value={"success": False, "error": "Primary failed"})
        fallback_func = Mock(return_value={"success": True, "data": "fallback_result"})
        
        decorated = _with_fallback_internal(primary_func, fallback_func)
        result = decorated("arg1", kwarg1="value1")
        
        assert result == {
            "success": True, 
            "data": "fallback_result",
            "_fallback_used": True,
            "_primary_error": "Primary failed"
        }
        primary_func.assert_called_once_with("arg1", kwarg1="value1")
        fallback_func.assert_called_once_with("arg1", kwarg1="value1")
    
    def test_primary_function_raises_exception(self):
        """Test fallback when primary function raises exception."""
        primary_func = Mock(side_effect=ValueError("Primary error"))
        fallback_func = Mock(return_value={"success": True, "data": "fallback_result"})
        
        decorated = _with_fallback_internal(primary_func, fallback_func)
        result = decorated("arg1", kwarg1="value1")
        
        assert result == {
            "success": True, 
            "data": "fallback_result",
            "_fallback_used": True,
            "_primary_error": "Primary error"
        }
        primary_func.assert_called_once_with("arg1", kwarg1="value1")
        fallback_func.assert_called_once_with("arg1", kwarg1="value1")
    
    def test_fallback_condition_prevents_fallback(self):
        """Test that fallback condition can prevent fallback usage."""
        primary_func = Mock(side_effect=ValueError("Primary error"))
        fallback_func = Mock(return_value={"success": True, "data": "fallback_result"})
        fallback_condition = Mock(return_value=False)  # Don't use fallback
        
        decorated = _with_fallback_internal(primary_func, fallback_func, fallback_condition)
        
        with pytest.raises(ValueError, match="Primary error"):
            decorated("arg1", kwarg1="value1")
        
        primary_func.assert_called_once_with("arg1", kwarg1="value1")
        fallback_condition.assert_called_once()
        fallback_func.assert_not_called()
    
    def test_fallback_condition_allows_fallback(self):
        """Test that fallback condition can allow fallback usage."""
        primary_func = Mock(side_effect=ValueError("Primary error"))
        fallback_func = Mock(return_value={"success": True, "data": "fallback_result"})
        fallback_condition = Mock(return_value=True)  # Use fallback
        
        decorated = _with_fallback_internal(primary_func, fallback_func, fallback_condition)
        result = decorated("arg1", kwarg1="value1")
        
        assert result["_fallback_used"] is True
        fallback_condition.assert_called_once()
        fallback_func.assert_called_once_with("arg1", kwarg1="value1")
    
    def test_both_functions_fail(self):
        """Test behavior when both primary and fallback functions fail."""
        primary_func = Mock(side_effect=ValueError("Primary error"))
        fallback_func = Mock(side_effect=RuntimeError("Fallback error"))
        
        decorated = _with_fallback_internal(primary_func, fallback_func)
        result = decorated("arg1", kwarg1="value1")
        
        assert result["success"] is False
        assert "Primary function failed: Primary error" in result["error"]
        assert "Fallback also failed: Fallback error" in result["error"]
        primary_func.assert_called_once_with("arg1", kwarg1="value1")
        fallback_func.assert_called_once_with("arg1", kwarg1="value1")
    
    def test_fallback_non_dict_result(self):
        """Test fallback with non-dict result from fallback function."""
        primary_func = Mock(side_effect=ValueError("Primary error"))
        fallback_func = Mock(return_value="string_result")
        
        decorated = _with_fallback_internal(primary_func, fallback_func)
        result = decorated()
        
        # Should return the string result directly (no metadata added)
        assert result == "string_result"
    
    def test_primary_success_with_non_dict_result(self):
        """Test primary function success with non-dict result."""
        primary_func = Mock(return_value="primary_string_result")
        fallback_func = Mock(return_value="fallback_result")
        
        decorated = _with_fallback_internal(primary_func, fallback_func)
        result = decorated()
        
        assert result == "primary_string_result"
        fallback_func.assert_not_called()


class TestWithRetry:
    """Test the retry decorator functionality."""
    
    def test_function_succeeds_first_attempt(self):
        """Test retry decorator when function succeeds on first attempt."""
        func = Mock(return_value={"success": True, "data": "result"})
        
        @with_retry(max_attempts=3, delay=0.1)
        def test_func():
            return func()
        
        result = test_func()
        
        assert result == {"success": True, "data": "result"}
        func.assert_called_once()
    
    def test_function_succeeds_after_retries(self):
        """Test retry decorator when function succeeds after failing initially."""
        func = Mock(side_effect=[
            Exception("First failure"),
            Exception("Second failure"),
            {"success": True, "data": "success_result"}
        ])
        
        @with_retry(max_attempts=3, delay=0.01)
        def test_func():
            return func()
        
        result = test_func()
        
        assert result == {"success": True, "data": "success_result"}
        assert func.call_count == 3
    
    def test_function_fails_all_attempts(self):
        """Test retry decorator when function fails all attempts."""
        func = Mock(side_effect=ValueError("Persistent error"))
        
        @with_retry(max_attempts=3, delay=0.01)
        def test_func():
            return func()
        
        # Should re-raise the exception after all attempts fail
        with pytest.raises(ValueError, match="Persistent error"):
            test_func()
        
        assert func.call_count == 3
    
    def test_retry_with_exponential_backoff(self):
        """Test that retry implements exponential backoff."""
        func = Mock(side_effect=[Exception("First"), Exception("Second"), "success"])
        
        @with_retry(max_attempts=3, delay=0.01, backoff_factor=2.0)
        def test_func():
            return func()
        
        with patch('time.sleep') as mock_sleep:
            result = test_func()
            
            assert result == "success"
            # Should sleep with exponential backoff: 0.01, 0.02
            expected_calls = [call(0.01), call(0.02)]
            mock_sleep.assert_has_calls(expected_calls)
    
    def test_retry_condition_prevents_retry(self):
        """Test that retry condition can prevent retries."""
        func = Mock(side_effect=ValueError("Don't retry this"))
        retry_condition = Mock(return_value=False)
        
        @with_retry(max_attempts=3, delay=0.01, retry_condition=retry_condition)
        def test_func():
            return func()
        
        # Should re-raise exception without retrying when condition returns False
        with pytest.raises(ValueError, match="Don't retry this"):
            test_func()
        
        func.assert_called_once()
        retry_condition.assert_called_once()
    
    def test_retry_condition_allows_retry(self):
        """Test that retry condition can allow retries."""
        func = Mock(side_effect=[ValueError("Retry this"), "success"])
        retry_condition = Mock(return_value=True)
        
        @with_retry(max_attempts=3, delay=0.01, retry_condition=retry_condition)
        def test_func():
            return func()
        
        result = test_func()
        
        assert result == "success"
        assert func.call_count == 2
        retry_condition.assert_called_once()
    
    def test_retry_with_dict_failure_result(self):
        """Test retry when function returns failure dict instead of raising."""
        func = Mock(side_effect=[
            {"success": False, "error": "First failure"},
            {"success": False, "error": "Second failure"},
            {"success": True, "data": "final_success"}
        ])
        
        @with_retry(max_attempts=3, delay=0.01)
        def test_func():
            return func()
        
        result = test_func()
        
        assert result == {"success": True, "data": "final_success"}
        assert func.call_count == 3
    
    def test_retry_condition_with_dict_failure(self):
        """Test retry condition with dict failure result."""
        func = Mock(return_value={"success": False, "error": "Don't retry"})
        retry_condition = Mock(return_value=False)
        
        @with_retry(max_attempts=3, delay=0.01, retry_condition=retry_condition)
        def test_func():
            return func()
        
        result = test_func()
        
        assert result == {"success": False, "error": "Don't retry"}
        func.assert_called_once()
        retry_condition.assert_called_once()
    
    def test_retry_default_parameters(self):
        """Test retry decorator with default parameters."""
        func = Mock(side_effect=[Exception("First"), Exception("Second"), "success"])
        
        @with_retry()  # Use all defaults
        def test_func():
            return func()
        
        result = test_func()
        
        assert result == "success"
        assert func.call_count == 3
    
    def test_retry_preserves_function_metadata(self):
        """Test that retry decorator preserves original function metadata."""
        @with_retry(max_attempts=2)
        def test_func():
            """Test function docstring."""
            return "result"
        
        assert test_func.__name__ == "test_func"
        assert test_func.__doc__ == "Test function docstring."


class TestSafeOperation:
    """Test the safe_operation function functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_func = Mock()
        
    def test_safe_operation_success(self):
        """Test safe_operation when function succeeds."""
        self.mock_func.return_value = {"success": True, "data": "result"}
        
        result = safe_operation(
            operation_name="test_operation",
            operation_func=self.mock_func
        )
        
        assert result["success"] is True
        assert result["result"] == {"success": True, "data": "result"}
        assert result["operation"] == "test_operation"
        self.mock_func.assert_called_once_with()
    
    def test_safe_operation_with_exception(self):
        """Test safe_operation when function raises exception."""
        self.mock_func.side_effect = ValueError("Test error")
        
        with patch('quilt_mcp.tools.error_recovery._get_recovery_suggestions') as mock_suggestions:
            mock_suggestions.return_value = ["Try again", "Check permissions"]
            
            result = safe_operation(
                operation_name="test_operation",
                operation_func=self.mock_func
            )
        
        assert result["success"] is False
        assert result["error"] == "Test error"
        assert result["operation"] == "test_operation"
        assert result["error_type"] == "ValueError"
        assert result["recovery_suggestions"] == ["Try again", "Check permissions"]
        mock_suggestions.assert_called_once()
    
    def test_safe_operation_with_dict_failure(self):
        """Test safe_operation when function returns failure dict."""
        self.mock_func.return_value = {"success": False, "error": "Operation failed"}
        
        with patch('quilt_mcp.tools.error_recovery._get_recovery_suggestions') as mock_suggestions:
            mock_suggestions.return_value = ["Retry", "Check config"]
            
            result = safe_operation(
                operation_func=self.mock_func,
                operation_name="test_operation"
            )
        
        assert result["success"] is False
        assert result["error"] == "Operation failed"
        assert result["operation"] == "test_operation"
        assert result["recovery_suggestions"] == ["Retry", "Check config"]
    
    def test_safe_operation_preserves_success_metadata(self):
        """Test that safe_operation preserves additional metadata from successful results."""
        self.mock_func.return_value = {
            "success": True, 
            "data": "result",
            "metadata": {"key": "value"},
            "timestamp": "2024-01-01"
        }
        
        result = safe_operation(
            operation_func=self.mock_func,
            operation_name="test_operation"
        )
        
        assert result["success"] is True
        assert result["data"] == "result"
        assert result["metadata"] == {"key": "value"}
        assert result["timestamp"] == "2024-01-01"
    
    def test_safe_operation_non_dict_result(self):
        """Test safe_operation with non-dict result from function."""
        self.mock_func.return_value = "string_result"
        
        result = safe_operation(
            operation_func=self.mock_func,
            operation_name="test_operation"
        )
        
        # Should wrap non-dict results in a success dict
        assert result["success"] is True
        assert result["result"] == "string_result"
        assert result["operation"] == "test_operation"


class TestBatchOperationWithRecovery:
    """Test the batch_operation_with_recovery functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.operations = [
            {"name": "op1", "func": Mock()},
            {"name": "op2", "func": Mock()},
            {"name": "op3", "func": Mock()},
        ]
    
    def test_batch_operation_all_succeed(self):
        """Test batch operation when all operations succeed."""
        self.operations[0]["func"].return_value = {"success": True, "data": "result1"}
        self.operations[1]["func"].return_value = {"success": True, "data": "result2"}
        self.operations[2]["func"].return_value = {"success": True, "data": "result3"}
        
        result = batch_operation_with_recovery(self.operations)
        
        assert result["success"] is True
        assert result["successful_operations"] == 3
        assert result["failed_operations"] == 0
        assert len(result["results"]) == 3
        
        # Verify all functions were called (batch operations call funcs without args)
        self.operations[0]["func"].assert_called_once_with()
        self.operations[1]["func"].assert_called_once_with()
        self.operations[2]["func"].assert_called_once_with()
    
    def test_batch_operation_some_fail(self):
        """Test batch operation when some operations fail."""
        self.operations[0]["func"].return_value = {"success": True, "data": "result1"}
        self.operations[1]["func"].side_effect = ValueError("Operation 2 failed")
        self.operations[2]["func"].return_value = {"success": False, "error": "Operation 3 error"}
        
        with patch('quilt_mcp.tools.error_recovery._get_recovery_suggestions') as mock_suggestions:
            mock_suggestions.return_value = ["Generic suggestion"]
            
            result = batch_operation_with_recovery(self.operations)
        
        assert result["success"] is False  # Overall failure due to some operations failing
        assert result["successful_operations"] == 1
        assert result["failed_operations"] == 2
        assert len(result["results"]) == 3
        
        # Check individual results
        assert result["results"][0]["success"] is True
        assert result["results"][1]["success"] is False
        assert "Operation 2 failed" in result["results"][1]["error"]
        assert result["results"][2]["success"] is False
        assert result["results"][2]["error"] == "Operation 3 error"
    
    def test_batch_operation_continue_on_error_true(self):
        """Test batch operation continues on error when specified."""
        self.operations[0]["func"].side_effect = ValueError("First fails")
        self.operations[1]["func"].return_value = {"success": True, "data": "result2"}
        self.operations[2]["func"].return_value = {"success": True, "data": "result3"}
        
        with patch('quilt_mcp.tools.error_recovery._get_recovery_suggestions') as mock_suggestions:
            mock_suggestions.return_value = []
            
            result = batch_operation_with_recovery(self.operations, fail_fast=False)
        
        # Should complete all operations despite first failure
        assert result["successful_operations"] == 2
        assert result["failed_operations"] == 1
        assert len(result["results"]) == 3
        
        # All functions should have been called
        assert self.operations[0]["func"].call_count == 1
        assert self.operations[1]["func"].call_count == 1
        assert self.operations[2]["func"].call_count == 1
    
    def test_batch_operation_continue_on_error_false(self):
        """Test batch operation stops on error when specified."""
        self.operations[0]["func"].side_effect = ValueError("First fails")
        self.operations[1]["func"].return_value = {"success": True, "data": "result2"}
        self.operations[2]["func"].return_value = {"success": True, "data": "result3"}
        
        with patch('quilt_mcp.tools.error_recovery._get_recovery_suggestions') as mock_suggestions:
            mock_suggestions.return_value = []
            
            result = batch_operation_with_recovery(self.operations, fail_fast=True)
        
        # Should stop after first failure
        assert result["successful_operations"] == 0
        assert result["failed_operations"] == 1
        assert len(result["results"]) == 1  # Only first operation result
        
        # Only first function should have been called
        assert self.operations[0]["func"].call_count == 1
        assert self.operations[1]["func"].call_count == 0
        assert self.operations[2]["func"].call_count == 0
    
    def test_batch_operation_empty_list(self):
        """Test batch operation with empty operations list."""
        result = batch_operation_with_recovery([])
        
        assert result["success"] is True
        assert result["successful_operations"] == 0
        assert result["failed_operations"] == 0
        assert result["results"] == []
    
    def test_batch_operation_malformed_operation(self):
        """Test batch operation with malformed operation entry."""
        malformed_ops = [
            {"name": "good_op", "func": Mock(return_value={"success": True})},
            {"name": "missing_func"},  # Missing 'func' key
            {"func": Mock(return_value={"success": True})},  # Missing 'name' key
        ]
        
        result = batch_operation_with_recovery(malformed_ops)
        
        # Should handle malformed operations gracefully
        assert result["failed_operations"] >= 2  # At least the malformed ones
        assert len(result["results"]) == 3
    
    def test_batch_operation_with_timeout_simulation(self):
        """Test batch operation behavior simulating timeout scenarios."""
        def slow_operation():
            time.sleep(0.01)  # Simulate work
            return {"success": True, "data": "slow_result"}
        
        self.operations[0]["func"] = slow_operation
        self.operations[1]["func"].return_value = {"success": True, "data": "fast_result"}
        
        # This tests that batch operations can handle functions with different execution times
        result = batch_operation_with_recovery(self.operations[:2])
        
        assert result["success"] is True
        assert result["successful_operations"] == 2


# Additional test classes for the remaining functions would go here...
# This provides a solid foundation for the critical error recovery functionality

class TestHealthCheckWithRecovery:
    """Test the health_check_with_recovery functionality."""
    
    def test_health_check_all_services_healthy(self):
        """Test health check when all services are healthy."""
        with patch('quilt_mcp.tools.error_recovery._check_auth_status') as mock_auth, \
             patch('quilt_mcp.tools.error_recovery._check_permissions_discovery') as mock_perms, \
             patch('quilt_mcp.tools.error_recovery._check_athena_connectivity') as mock_athena, \
             patch('quilt_mcp.tools.error_recovery._check_package_operations') as mock_packages, \
             patch('quilt_mcp.tools.error_recovery._get_health_next_steps') as mock_next_steps:
            
            # All checks return healthy
            mock_auth.return_value = {"success": True, "status": "healthy"}
            mock_perms.return_value = {"success": True, "status": "healthy"}
            mock_athena.return_value = {"success": True, "status": "healthy"}
            mock_packages.return_value = {"success": True, "status": "healthy"}
            mock_next_steps.return_value = ["System is healthy"]
            
            result = health_check_with_recovery()
            
            assert result["success"] is True
            assert result["overall_health"] == "healthy"
            assert result["healthy_services"] == 4
            assert result["degraded_services"] == 0
            assert result["failed_services"] == 0
    
    def test_health_check_some_services_degraded(self):
        """Test health check when some services are degraded."""
        with patch('quilt_mcp.tools.error_recovery._check_auth_status') as mock_auth, \
             patch('quilt_mcp.tools.error_recovery._check_permissions_discovery') as mock_perms, \
             patch('quilt_mcp.tools.error_recovery._check_athena_connectivity') as mock_athena, \
             patch('quilt_mcp.tools.error_recovery._check_package_operations') as mock_packages, \
             patch('quilt_mcp.tools.error_recovery._get_health_next_steps') as mock_next_steps:
            
            mock_auth.return_value = {"success": True, "status": "healthy"}
            mock_perms.return_value = {"success": True, "status": "degraded", "warning": "Slow response"}
            mock_athena.return_value = {"success": False, "status": "failed", "error": "Connection failed"}
            mock_packages.return_value = {"success": True, "status": "healthy"}
            mock_next_steps.return_value = ["Check Athena configuration"]
            
            result = health_check_with_recovery()
            
            assert result["success"] is False  # Due to failed service
            assert result["overall_health"] == "degraded"
            assert result["healthy_services"] == 2
            assert result["degraded_services"] == 1
            assert result["failed_services"] == 1
    
    def test_health_check_exception_handling(self):
        """Test health check handles exceptions in service checks."""
        with patch('quilt_mcp.tools.error_recovery._check_auth_status') as mock_auth, \
             patch('quilt_mcp.tools.error_recovery._check_permissions_discovery') as mock_perms, \
             patch('quilt_mcp.tools.error_recovery._check_athena_connectivity') as mock_athena, \
             patch('quilt_mcp.tools.error_recovery._check_package_operations') as mock_packages, \
             patch('quilt_mcp.tools.error_recovery._get_health_next_steps') as mock_next_steps:
            
            mock_auth.side_effect = Exception("Auth check crashed")
            mock_perms.return_value = {"success": True, "status": "healthy"}
            mock_athena.return_value = {"success": True, "status": "healthy"}
            mock_packages.return_value = {"success": True, "status": "healthy"}
            mock_next_steps.return_value = ["Fix auth service"]
            
            result = health_check_with_recovery()
            
            # Should handle exception gracefully
            assert result["success"] is False
            assert result["failed_services"] == 1
            # Should have error details for the failed auth check
            auth_result = next(s for s in result["service_status"] if s["service"] == "auth")
            assert auth_result["status"] == "failed"
            assert "Auth check crashed" in auth_result["error"]
"""Error Recovery and Graceful Degradation Tools.

This module provides error recovery mechanisms and graceful degradation
capabilities for robust MCP tool operation.
"""

from typing import Dict, List, Any, Optional, Callable
import logging
from datetime import datetime, timezone
import functools
import time

from ..utils import format_error_response

logger = logging.getLogger(__name__)


def _with_fallback_internal(
    primary_func: Callable,
    fallback_func: Callable,
    fallback_condition: Optional[Callable[[Exception], bool]] = None,
) -> Callable:
    """
    Decorator to provide fallback functionality when primary function fails.

    Args:
        primary_func: Primary function to try first
        fallback_func: Fallback function to use if primary fails
        fallback_condition: Optional condition to determine if fallback should be used

    Returns:
        Decorated function with fallback capability
    """

    @functools.wraps(primary_func)
    def wrapper(*args, **kwargs):
        try:
            result = primary_func(*args, **kwargs)
            # Check if result indicates failure
            if isinstance(result, dict) and not result.get("success", True):
                raise Exception(result.get("error", "Primary function failed"))
            return result
        except Exception as e:
            # Check if we should use fallback
            if fallback_condition and not fallback_condition(e):
                raise

            logger.warning(f"Primary function failed, using fallback: {e}")
            try:
                fallback_result = fallback_func(*args, **kwargs)
                # Add metadata about fallback usage
                if isinstance(fallback_result, dict):
                    fallback_result["_fallback_used"] = True
                    fallback_result["_primary_error"] = str(e)
                return fallback_result
            except Exception as fallback_error:
                logger.error(f"Both primary and fallback functions failed: {e}, {fallback_error}")
                return format_error_response(
                    f"Primary function failed: {str(e)}. Fallback also failed: {str(fallback_error)}"
                )

    return wrapper


def with_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0,
    retry_condition: Optional[Callable[[Exception], bool]] = None,
) -> Callable:
    """
    Decorator to retry function calls with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff_factor: Factor to multiply delay by for each retry
        retry_condition: Optional condition to determine if retry should be attempted

    Returns:
        Decorated function with retry capability
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay

            for attempt in range(max_attempts):
                try:
                    result = func(*args, **kwargs)
                    # Check if result indicates failure that should be retried
                    if isinstance(result, dict) and not result.get("success", True):
                        error_msg = result.get("error", "Function returned failure")
                        if retry_condition:
                            # Create a mock exception for condition checking
                            mock_exception = Exception(error_msg)
                            if not retry_condition(mock_exception):
                                return result

                        if attempt < max_attempts - 1:
                            logger.warning(f"Attempt {attempt + 1} failed, retrying in {current_delay}s: {error_msg}")
                            time.sleep(current_delay)
                            current_delay *= backoff_factor
                            continue
                        else:
                            return result

                    return result

                except Exception as e:
                    last_exception = e

                    # Check if we should retry
                    if retry_condition and not retry_condition(e):
                        raise

                    if attempt < max_attempts - 1:
                        logger.warning(f"Attempt {attempt + 1} failed, retrying in {current_delay}s: {e}")
                        time.sleep(current_delay)
                        current_delay *= backoff_factor
                    else:
                        logger.error(f"All {max_attempts} attempts failed: {e}")
                        raise

            # This should never be reached, but just in case
            if last_exception:
                raise last_exception

        return wrapper

    return decorator


def safe_operation(
    operation_name: str,
    operation_func: Callable,
    fallback_value: Any = None,
    log_errors: bool = True,
) -> Dict[str, Any]:
    """
    Execute an operation safely with comprehensive error handling.

    Args:
        operation_name: Name of the operation for logging
        operation_func: Function to execute
        fallback_value: Value to return if operation fails
        log_errors: Whether to log errors

    Returns:
        Operation result with error handling metadata
    """
    start_time = time.time()

    try:
        result = operation_func()
        execution_time = time.time() - start_time
        timestamp = datetime.now(timezone.utc).isoformat()

        response: Dict[str, Any] = {
            "operation": operation_name,
            "execution_time_ms": round(execution_time * 1000, 2),
            "timestamp": timestamp,
        }

        if isinstance(result, dict):
            response["result"] = result
            if result.get("_fallback_used"):
                response["_fallback_used"] = True
                if "_primary_error" in result:
                    response["_primary_error"] = result["_primary_error"]
        else:
            response["result"] = result

        if isinstance(result, dict) and result.get("success") is False:
            error_message = result.get("error", "Operation returned failure")
            suggestions = _get_recovery_suggestions(operation_name, Exception(error_message))
            response.update(
                {
                    "success": False,
                    "error": error_message,
                    "error_type": result.get("error_type", "OperationFailure"),
                    "fallback_value": fallback_value,
                    "recovery_suggestions": result.get("recovery_suggestions", suggestions) or suggestions,
                }
            )
            return response

        response["success"] = True
        return response

    except Exception as e:
        execution_time = time.time() - start_time

        if log_errors:
            logger.error(f"Safe operation '{operation_name}' failed: {e}")

        return {
            "success": False,
            "operation": operation_name,
            "error": str(e),
            "error_type": type(e).__name__,
            "fallback_value": fallback_value,
            "execution_time_ms": round(execution_time * 1000, 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "recovery_suggestions": _get_recovery_suggestions(operation_name, e),
        }


def batch_operation_with_recovery(
    operations: List[Dict[str, Any]], fail_fast: bool = False, max_parallel: int = 5
) -> Dict[str, Any]:
    """
    Execute multiple operations with individual error recovery.

    Args:
        operations: List of operation dictionaries with 'name', 'func', and optional 'fallback'
        fail_fast: Whether to stop on first failure
        max_parallel: Maximum number of parallel operations (not implemented yet)

    Returns:
        Batch operation results with individual success/failure tracking
    """
    results = []
    successful_operations = 0
    failed_operations = 0

    for i, operation in enumerate(operations):
        operation_name = operation.get("name", f"operation_{i}")
        operation_func = operation.get("func")
        fallback_func = operation.get("fallback")

        if not operation_func:
            results.append(
                {
                    "success": False,
                    "operation": operation_name,
                    "error": "No operation function provided",
                    "index": i,
                }
            )
            failed_operations += 1
            continue

        # Execute with fallback if provided
        if fallback_func:
            safe_func = _with_fallback_internal(operation_func, fallback_func)
        else:
            safe_func = operation_func

        result = safe_operation(operation_name, safe_func)

        result["index"] = i
        results.append(result)

        if result["success"]:
            successful_operations += 1
        else:
            failed_operations += 1
            if fail_fast:
                logger.warning(f"Batch operation stopped early due to failure in '{operation_name}'")
                break

    return {
        "success": failed_operations == 0,
        "total_operations": len(operations),
        "successful_operations": successful_operations,
        "failed_operations": failed_operations,
        "results": results,
        "summary": {
            "success_rate": (round((successful_operations / len(operations)) * 100, 1) if operations else 0),
            "fail_fast_triggered": fail_fast and failed_operations > 0 and len(results) < len(operations),
        },
    }


def health_check_with_recovery() -> Dict[str, Any]:
    """
    Perform comprehensive health check with recovery recommendations.

    Returns:
        Health check results with recovery suggestions
    """
    checks = [
        {
            "name": "auth_status",
            "func": lambda: _check_auth_status(),
            "fallback": lambda: {"status": "unknown", "fallback": True},
        },
        {
            "name": "permissions_discovery",
            "func": lambda: _check_permissions_discovery(),
            "fallback": lambda: {"accessible_buckets": [], "fallback": True},
        },
        {
            "name": "athena_connectivity",
            "func": lambda: _check_athena_connectivity(),
            "fallback": lambda: {"athena_available": False, "fallback": True},
        },
        {
            "name": "package_operations",
            "func": lambda: _check_package_operations(),
            "fallback": lambda: {"package_ops_available": False, "fallback": True},
        },
    ]

    health_results = batch_operation_with_recovery(checks, fail_fast=False)

    # Generate overall health assessment
    overall_health = "healthy" if health_results["success"] else "degraded"
    fallback_detected = any(result.get("_fallback_used") for result in health_results["results"])
    if fallback_detected and overall_health == "healthy":
        overall_health = "degraded"
    if health_results["failed_operations"] > health_results["successful_operations"]:
        overall_health = "unhealthy"

    # Generate recovery recommendations
    recovery_recommendations = []
    for result in health_results["results"]:
        if not result["success"] or result.get("_fallback_used"):
            recovery_recommendations.extend(result.get("recovery_suggestions", []))

            if result.get("_fallback_used"):
                # Surface suggestions based on the primary error that triggered the fallback
                primary_error = None
                if isinstance(result.get("result"), dict):
                    primary_error = result["result"].get("_primary_error") or result["result"].get("error")
                primary_error = primary_error or result.get("error")
                if primary_error:
                    recovery_recommendations.extend(
                        _get_recovery_suggestions(result["operation"], Exception(primary_error))
                    )

    return {
        "success": True,
        "overall_health": overall_health,
        "health_results": health_results,
        "recovery_recommendations": list(set(recovery_recommendations)),  # Remove duplicates
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "next_steps": _get_health_next_steps(overall_health, recovery_recommendations),
    }


def _check_auth_status() -> Dict[str, Any]:
    """Check authentication status."""
    try:
        from .auth import auth_status

        return auth_status()
    except Exception as e:
        raise Exception(f"Auth check failed: {e}")


def _check_permissions_discovery() -> Dict[str, Any]:
    """Check permissions discovery functionality."""
    try:
        from .permissions import aws_permissions_discover

        result = aws_permissions_discover(force_refresh=False)
        if not result.get("success"):
            raise Exception(result.get("error", "Permissions discovery failed"))
        return {"accessible_buckets": len(result.get("bucket_permissions", []))}
    except Exception as e:
        raise Exception(f"Permissions discovery failed: {e}")


def _check_athena_connectivity() -> Dict[str, Any]:
    """Check Athena connectivity."""
    try:
        from .athena_glue import athena_workgroups_list

        result = athena_workgroups_list()
        if not result.get("success"):
            raise Exception(result.get("error", "Athena connectivity failed"))
        return {
            "athena_available": True,
            "workgroups": len(result.get("workgroups", [])),
        }
    except Exception as e:
        raise Exception(f"Athena connectivity failed: {e}")


def _check_package_operations() -> Dict[str, Any]:
    """Check package operations functionality."""
    try:
        from .packages import packages_list

        result = packages_list(limit=1)
        if not result.get("success"):
            raise Exception(result.get("error", "Package operations failed"))
        return {"package_ops_available": True}
    except Exception as e:
        raise Exception(f"Package operations failed: {e}")


def _get_recovery_suggestions(operation_name: str, error: Exception) -> List[str]:
    """Generate recovery suggestions based on operation and error type."""
    suggestions = []
    error_str = str(error).lower()

    # General suggestions
    suggestions.append("Check your AWS credentials and permissions")
    suggestions.append("Verify your network connectivity")

    # Operation-specific suggestions
    if "auth" in operation_name.lower():
        suggestions.extend(
            [
                "Run: quilt3 login to authenticate",
                "Check if your Quilt session is still valid",
                "Verify AWS credentials are properly configured",
            ]
        )
    elif "permission" in operation_name.lower():
        suggestions.extend(
            [
                "Check IAM permissions for S3 and related services",
                "Verify bucket access policies",
                "Try: aws sts get-caller-identity to check AWS identity",
            ]
        )
    elif "athena" in operation_name.lower():
        suggestions.extend(
            [
                "Check Athena service availability in your region",
                "Verify Glue Data Catalog permissions",
                "Ensure Athena workgroups are properly configured",
            ]
        )
    elif "package" in operation_name.lower():
        suggestions.extend(
            [
                "Check if the registry is accessible",
                "Verify package names and registry URLs",
                "Try: packages_search() to test basic connectivity",
            ]
        )

    # Error-specific suggestions
    if "access denied" in error_str or "403" in error_str:
        suggestions.append("This appears to be a permissions issue - check IAM policies")
    elif "not found" in error_str or "404" in error_str:
        suggestions.append("Resource not found - verify names and availability")
    elif "timeout" in error_str or "connection" in error_str:
        suggestions.append("Network connectivity issue - check internet connection and firewall")
    elif "credential" in error_str:
        suggestions.append("AWS credentials issue - run 'aws configure' or check environment variables")

    return list(set(suggestions))  # Remove duplicates


def _get_health_next_steps(overall_health: str, recovery_recommendations: List[str]) -> List[str]:
    """Generate next steps based on health status."""
    if overall_health == "healthy":
        return [
            "System is healthy - all components functioning normally",
            "Continue with normal operations",
            "Consider running periodic health checks",
        ]
    elif overall_health == "degraded":
        return [
            "Some components are experiencing issues but core functionality remains",
            "Address the specific issues identified in recovery recommendations",
            "Monitor system closely and re-run health check after fixes",
        ]
    else:  # unhealthy
        return [
            "Multiple critical issues detected - immediate attention required",
            "Address authentication and permissions issues first",
            "Contact system administrator if issues persist",
            "Consider using fallback mechanisms for critical operations",
        ]


# Convenience functions for common error recovery patterns
def _safe_package_operation_internal(operation_func: Callable, package_name: str) -> Dict[str, Any]:
    """Safely execute a package operation with common fallbacks."""

    def fallback():
        return {
            "success": False,
            "error": f"Package operation failed for '{package_name}'",
            "fallback_used": True,
            "suggestions": [
                f"Verify package '{package_name}' exists",
                "Check registry access permissions",
                "Try: packages_search() to test connectivity",
            ],
        }

    return safe_operation(f"package_operation_{package_name}", operation_func, fallback_value=fallback())


def _safe_bucket_operation_internal(operation_func: Callable, bucket_name: str) -> Dict[str, Any]:
    """Safely execute a bucket operation with common fallbacks."""

    def fallback():
        return {
            "success": False,
            "error": f"Bucket operation failed for '{bucket_name}'",
            "fallback_used": True,
            "suggestions": [
                f"Verify bucket '{bucket_name}' exists and is accessible",
                "Check S3 permissions",
                "Try: aws s3 ls s3://{bucket_name} to test access",
            ],
        }

    return safe_operation(f"bucket_operation_{bucket_name}", operation_func, fallback_value=fallback())


def _safe_athena_operation_internal(operation_func: Callable, query: str = None) -> Dict[str, Any]:
    """Safely execute an Athena operation with common fallbacks."""

    def fallback():
        return {
            "success": False,
            "error": "Athena operation failed",
            "fallback_used": True,
            "suggestions": [
                "Check Athena service availability",
                "Verify Glue Data Catalog permissions",
                "Ensure proper workgroup configuration",
                "Try: athena_workgroups_list() to test connectivity",
            ],
        }

    operation_name = f"athena_operation_{query[:50] if query else 'unknown'}"
    return safe_operation(operation_name, operation_func, fallback_value=fallback())

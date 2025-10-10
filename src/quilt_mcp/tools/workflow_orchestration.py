"""Workflow Orchestration MCP Tools.

This module provides workflow state management and orchestration capabilities
for complex data operations across multiple Quilt packages and buckets.
"""

from typing import Dict, List, Any, Optional
import logging
from datetime import datetime, timezone
import json
import uuid
from enum import Enum

from ..utils import format_error_response

logger = logging.getLogger(__name__)


class WorkflowStatus(Enum):
    """Workflow execution status."""

    CREATED = "created"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(Enum):
    """Individual step status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


# Global workflow storage (in production, this would be persistent)
_workflows: Dict[str, Dict[str, Any]] = {}


def workflow_create(
    workflow_id: str,
    name: str,
    description: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create a new workflow for tracking multi-step operations.

    Args:
        workflow_id: Unique identifier for the workflow
        name: Human-readable name for the workflow
        description: Optional description of the workflow
        metadata: Optional metadata dictionary

    Returns:
        Workflow creation result with tracking information
    """
    try:
        if not workflow_id or not workflow_id.strip():
            return format_error_response("Workflow ID cannot be empty")

        if workflow_id in _workflows:
            return format_error_response(f"Workflow '{workflow_id}' already exists")

        workflow = {
            "id": workflow_id,
            "name": name,
            "description": description,
            "status": WorkflowStatus.CREATED.value,
            "metadata": metadata or {},
            "steps": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "started_at": None,
            "completed_at": None,
            "total_steps": 0,
            "completed_steps": 0,
            "failed_steps": 0,
            "execution_log": [],
        }

        _workflows[workflow_id] = workflow

        return {
            "success": True,
            "workflow_id": workflow_id,
            "workflow": workflow,
            "message": f"Workflow '{name}' created successfully",
            "next_steps": [
                f"Add steps: workflow_add_step('{workflow_id}', 'step-name', 'description')",
                f"Start workflow: workflow_start('{workflow_id}')",
                f"Check status: workflow_get_status('{workflow_id}')",
            ],
        }

    except Exception as e:
        logger.error(f"Failed to create workflow {workflow_id}: {e}")
        return format_error_response(f"Failed to create workflow: {str(e)}")


def workflow_add_step(
    workflow_id: str,
    step_id: str,
    description: str,
    step_type: str = "manual",
    dependencies: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Add a step to an existing workflow.

    Args:
        workflow_id: ID of the workflow to add step to
        step_id: Unique identifier for the step
        description: Description of what this step does
        step_type: Type of step (manual, automated, validation, etc.)
        dependencies: List of step IDs that must complete before this step
        metadata: Optional step-specific metadata

    Returns:
        Step addition result
    """
    try:
        if workflow_id not in _workflows:
            return format_error_response(f"Workflow '{workflow_id}' not found")

        workflow = _workflows[workflow_id]

        # Check if step already exists
        existing_steps = {step["id"] for step in workflow["steps"]}
        if step_id in existing_steps:
            return format_error_response(f"Step '{step_id}' already exists in workflow")

        # Validate dependencies
        if dependencies:
            invalid_deps = set(dependencies) - existing_steps
            if invalid_deps:
                return format_error_response(f"Invalid dependencies: {list(invalid_deps)}")

        step = {
            "id": step_id,
            "description": description,
            "step_type": step_type,
            "status": StepStatus.PENDING.value,
            "dependencies": dependencies or [],
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "started_at": None,
            "completed_at": None,
            "error_message": None,
            "result": None,
        }

        workflow["steps"].append(step)
        workflow["total_steps"] = len(workflow["steps"])
        workflow["updated_at"] = datetime.now(timezone.utc).isoformat()

        return {
            "success": True,
            "workflow_id": workflow_id,
            "step_id": step_id,
            "step": step,
            "workflow_summary": {
                "total_steps": workflow["total_steps"],
                "status": workflow["status"],
            },
            "message": f"Step '{step_id}' added to workflow '{workflow_id}'",
        }

    except Exception as e:
        logger.error(f"Failed to add step to workflow {workflow_id}: {e}")
        return format_error_response(f"Failed to add step: {str(e)}")


def workflow_update_step(
    workflow_id: str,
    step_id: str,
    status: str,
    result: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Update the status of a workflow step.

    Args:
        workflow_id: ID of the workflow
        step_id: ID of the step to update
        status: New status (pending, in_progress, completed, failed, skipped)
        result: Optional result data from step execution
        error_message: Optional error message if step failed

    Returns:
        Step update result
    """
    try:
        if workflow_id not in _workflows:
            return format_error_response(f"Workflow '{workflow_id}' not found")

        workflow = _workflows[workflow_id]

        # Find the step
        step = None
        for s in workflow["steps"]:
            if s["id"] == step_id:
                step = s
                break

        if not step:
            return format_error_response(f"Step '{step_id}' not found in workflow")

        # Validate status
        try:
            new_status = StepStatus(status)
        except ValueError:
            return format_error_response(f"Invalid status: {status}")

        # Update step
        old_status = step["status"]
        step["status"] = new_status.value
        step["result"] = result
        step["error_message"] = error_message

        # Update timestamps
        now = datetime.now(timezone.utc).isoformat()
        if new_status == StepStatus.IN_PROGRESS and not step["started_at"]:
            step["started_at"] = now
        elif new_status in [
            StepStatus.COMPLETED,
            StepStatus.FAILED,
            StepStatus.SKIPPED,
        ]:
            step["completed_at"] = now

        # Update workflow counters
        workflow["completed_steps"] = sum(1 for s in workflow["steps"] if s["status"] == StepStatus.COMPLETED.value)
        workflow["failed_steps"] = sum(1 for s in workflow["steps"] if s["status"] == StepStatus.FAILED.value)
        workflow["updated_at"] = now

        # Update workflow status if needed
        if workflow["status"] == WorkflowStatus.CREATED.value and new_status == StepStatus.IN_PROGRESS:
            workflow["status"] = WorkflowStatus.IN_PROGRESS.value
            workflow["started_at"] = now
        elif workflow["completed_steps"] == workflow["total_steps"]:
            workflow["status"] = WorkflowStatus.COMPLETED.value
            workflow["completed_at"] = now
        elif workflow["failed_steps"] > 0 and workflow["status"] != WorkflowStatus.FAILED.value:
            workflow["status"] = WorkflowStatus.FAILED.value

        # Add to execution log
        workflow["execution_log"].append(
            {
                "timestamp": now,
                "step_id": step_id,
                "status_change": f"{old_status} -> {new_status.value}",
                "message": error_message or f"Step {new_status.value}",
            }
        )

        return {
            "success": True,
            "workflow_id": workflow_id,
            "step_id": step_id,
            "step": step,
            "workflow_status": workflow["status"],
            "progress": {
                "completed_steps": workflow["completed_steps"],
                "total_steps": workflow["total_steps"],
                "failed_steps": workflow["failed_steps"],
                "percentage": round((workflow["completed_steps"] / workflow["total_steps"]) * 100, 1),
            },
        }

    except Exception as e:
        logger.error(f"Failed to update step {step_id} in workflow {workflow_id}: {e}")
        return format_error_response(f"Failed to update step: {str(e)}")


def workflow_get_status(workflow_id: str) -> Dict[str, Any]:
    """
    Get the current status of a workflow.

    Args:
        workflow_id: ID of the workflow to check

    Returns:
        Comprehensive workflow status information
    """
    try:
        if workflow_id not in _workflows:
            return format_error_response(f"Workflow '{workflow_id}' not found")

        workflow = _workflows[workflow_id]

        # Calculate progress metrics
        total_steps = workflow["total_steps"]
        completed_steps = workflow["completed_steps"]
        failed_steps = workflow["failed_steps"]
        in_progress_steps = sum(1 for s in workflow["steps"] if s["status"] == StepStatus.IN_PROGRESS.value)
        pending_steps = sum(1 for s in workflow["steps"] if s["status"] == StepStatus.PENDING.value)

        # Get next available steps (dependencies satisfied)
        next_steps = []
        for step in workflow["steps"]:
            if step["status"] == StepStatus.PENDING.value:
                # Check if all dependencies are completed
                deps_completed = (
                    all(
                        any(s["id"] == dep_id and s["status"] == StepStatus.COMPLETED.value for s in workflow["steps"])
                        for dep_id in step["dependencies"]
                    )
                    if step["dependencies"]
                    else True
                )

                if deps_completed:
                    next_steps.append(step["id"])

        return {
            "success": True,
            "workflow": workflow,
            "progress": {
                "total_steps": total_steps,
                "completed_steps": completed_steps,
                "failed_steps": failed_steps,
                "in_progress_steps": in_progress_steps,
                "pending_steps": pending_steps,
                "percentage": (round((completed_steps / total_steps) * 100, 1) if total_steps > 0 else 0),
            },
            "next_available_steps": next_steps,
            "can_proceed": len(next_steps) > 0 and failed_steps == 0,
            "recent_activity": workflow["execution_log"][-5:],  # Last 5 log entries
            "recommendations": _get_workflow_recommendations(workflow),
        }

    except Exception as e:
        logger.error(f"Failed to get workflow status {workflow_id}: {e}")
        return format_error_response(f"Failed to get workflow status: {str(e)}")


def workflow_list_all() -> Dict[str, Any]:
    """
    List all workflows with their current status.

    Returns:
        List of all workflows with summary information
    """
    try:
        workflows_summary = []

        for workflow_id, workflow in _workflows.items():
            summary = {
                "id": workflow_id,
                "name": workflow["name"],
                "status": workflow["status"],
                "progress": {
                    "completed_steps": workflow["completed_steps"],
                    "total_steps": workflow["total_steps"],
                    "percentage": (
                        round(
                            (workflow["completed_steps"] / workflow["total_steps"]) * 100,
                            1,
                        )
                        if workflow["total_steps"] > 0
                        else 0
                    ),
                },
                "created_at": workflow["created_at"],
                "updated_at": workflow["updated_at"],
            }
            workflows_summary.append(summary)

        # Sort by updated_at (most recent first)
        workflows_summary.sort(key=lambda x: x["updated_at"], reverse=True)

        return {
            "success": True,
            "workflows": workflows_summary,
            "total_workflows": len(workflows_summary),
            "active_workflows": sum(1 for w in workflows_summary if w["status"] in ["created", "in_progress"]),
            "completed_workflows": sum(1 for w in workflows_summary if w["status"] == "completed"),
        }

    except Exception as e:
        logger.error(f"Failed to list workflows: {e}")
        return format_error_response(f"Failed to list workflows: {str(e)}")


def workflow_template_apply(template_name: str, workflow_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply a pre-defined workflow template.

    Args:
        template_name: Name of the template to apply
        workflow_id: ID for the new workflow
        params: Parameters to customize the template

    Returns:
        Workflow creation result with template-specific steps
    """
    try:
        # Use string-based template selection instead of function references
        # to avoid Pydantic serialization issues
        available_templates = [
            "cross-package-aggregation",
            "environment-promotion",
            "longitudinal-analysis",
            "data-validation",
        ]

        if template_name not in available_templates:
            return format_error_response(f"Unknown template '{template_name}'. Available: {available_templates}")

        # Create workflow from template using string-based dispatch
        if template_name == "cross-package-aggregation":
            workflow_config = _create_cross_package_template(params)
        elif template_name == "environment-promotion":
            workflow_config = _create_promotion_template(params)
        elif template_name == "longitudinal-analysis":
            workflow_config = _create_analysis_template(params)
        elif template_name == "data-validation":
            workflow_config = _create_validation_template(params)
        else:
            return format_error_response(f"Template implementation not found: {template_name}")

        # Create the workflow
        create_result = workflow_create(
            workflow_id=workflow_id,
            name=workflow_config["name"],
            description=workflow_config["description"],
            metadata=workflow_config.get("metadata", {}),
        )

        if not create_result.get("success"):
            return create_result

        # Add all template steps
        for step_config in workflow_config["steps"]:
            step_result = workflow_add_step(
                workflow_id=workflow_id,
                step_id=step_config["id"],
                description=step_config["description"],
                step_type=step_config.get("step_type", "manual"),
                dependencies=step_config.get("dependencies", []),
                metadata=step_config.get("metadata", {}),
            )

            if not step_result.get("success"):
                return step_result

        return {
            "success": True,
            "workflow_id": workflow_id,
            "template_applied": template_name,
            "workflow": _workflows[workflow_id],
            "message": f"Template '{template_name}' applied successfully",
            "next_steps": [
                f"Check status: workflow_get_status('{workflow_id}')",
                f"Start first step: workflow_update_step('{workflow_id}', 'step-1', 'in_progress')",
            ],
        }

    except Exception as e:
        logger.error(f"Failed to apply template {template_name}: {e}")
        return format_error_response(f"Failed to apply template: {str(e)}")


def _get_workflow_recommendations(workflow: Dict[str, Any]) -> List[str]:
    """Generate recommendations based on workflow state."""
    recommendations = []

    if workflow["status"] == WorkflowStatus.CREATED.value:
        recommendations.append("Start the workflow by updating the first step to 'in_progress'")
    elif workflow["status"] == WorkflowStatus.IN_PROGRESS.value:
        if workflow["failed_steps"] > 0:
            recommendations.append("Address failed steps before proceeding")
        else:
            recommendations.append("Continue with the next available steps")
    elif workflow["status"] == WorkflowStatus.COMPLETED.value:
        recommendations.append("Workflow completed successfully - review results")
    elif workflow["status"] == WorkflowStatus.FAILED.value:
        recommendations.append("Review failed steps and consider restarting or fixing issues")

    return recommendations


def _create_cross_package_template(params: Dict[str, Any]) -> Dict[str, Any]:
    """Create cross-package aggregation workflow template."""
    source_packages = params.get("source_packages", [])
    target_package = params.get("target_package", "aggregated-data")

    return {
        "name": f"Cross-Package Aggregation: {target_package}",
        "description": f"Aggregate data from {len(source_packages)} source packages",
        "metadata": {"template": "cross-package-aggregation", "params": params},
        "steps": [
            {
                "id": "discover-packages",
                "description": f"Discover and validate {len(source_packages)} source packages",
                "step_type": "discovery",
            },
            {
                "id": "analyze-structure",
                "description": "Analyze package structures and identify common data patterns",
                "step_type": "analysis",
                "dependencies": ["discover-packages"],
            },
            {
                "id": "extract-data",
                "description": "Extract relevant data from source packages",
                "step_type": "extraction",
                "dependencies": ["analyze-structure"],
            },
            {
                "id": "create-aggregated",
                "description": f"Create aggregated package: {target_package}",
                "step_type": "creation",
                "dependencies": ["extract-data"],
            },
            {
                "id": "validate-result",
                "description": "Validate the aggregated package",
                "step_type": "validation",
                "dependencies": ["create-aggregated"],
            },
        ],
    }


def _create_promotion_template(params: Dict[str, Any]) -> Dict[str, Any]:
    """Create environment promotion workflow template."""
    source_env = params.get("source_env", "staging")
    target_env = params.get("target_env", "production")
    package_name = params.get("package_name", "data-package")

    return {
        "name": f"Package Promotion: {source_env} → {target_env}",
        "description": f"Promote {package_name} from {source_env} to {target_env}",
        "metadata": {"template": "environment-promotion", "params": params},
        "steps": [
            {
                "id": "validate-source",
                "description": f"Validate source package in {source_env}",
                "step_type": "validation",
            },
            {
                "id": "run-tests",
                "description": "Run quality assurance tests",
                "step_type": "testing",
                "dependencies": ["validate-source"],
            },
            {
                "id": "create-promoted",
                "description": f"Create promoted package in {target_env}",
                "step_type": "promotion",
                "dependencies": ["run-tests"],
            },
            {
                "id": "verify-promotion",
                "description": f"Verify package in {target_env}",
                "step_type": "verification",
                "dependencies": ["create-promoted"],
            },
        ],
    }


def _create_analysis_template(params: Dict[str, Any]) -> Dict[str, Any]:
    """Create longitudinal analysis workflow template."""
    dataset = params.get("dataset", "time-series-data")
    time_range = params.get("time_range", "last-12-months")

    return {
        "name": f"Longitudinal Analysis: {dataset}",
        "description": f"Analyze {dataset} over {time_range}",
        "metadata": {"template": "longitudinal-analysis", "params": params},
        "steps": [
            {
                "id": "setup-athena",
                "description": "Set up Athena environment and validate permissions",
                "step_type": "setup",
            },
            {
                "id": "discover-tables",
                "description": "Discover available tables and data sources",
                "step_type": "discovery",
                "dependencies": ["setup-athena"],
            },
            {
                "id": "run-analysis",
                "description": f"Execute longitudinal analysis queries for {time_range}",
                "step_type": "analysis",
                "dependencies": ["discover-tables"],
            },
            {
                "id": "generate-report",
                "description": "Generate analysis report and visualizations",
                "step_type": "reporting",
                "dependencies": ["run-analysis"],
            },
        ],
    }


def _create_validation_template(params: Dict[str, Any]) -> Dict[str, Any]:
    """Create data validation workflow template."""
    packages = params.get("packages", [])
    validation_rules = params.get("validation_rules", [])

    return {
        "name": "Data Validation Workflow",
        "description": f"Validate {len(packages)} packages against {len(validation_rules)} rules",
        "metadata": {"template": "data-validation", "params": params},
        "steps": [
            {
                "id": "load-packages",
                "description": f"Load and inspect {len(packages)} packages",
                "step_type": "loading",
            },
            {
                "id": "run-validations",
                "description": f"Run {len(validation_rules)} validation rules",
                "step_type": "validation",
                "dependencies": ["load-packages"],
            },
            {
                "id": "generate-report",
                "description": "Generate validation report with findings",
                "step_type": "reporting",
                "dependencies": ["run-validations"],
            },
        ],
    }

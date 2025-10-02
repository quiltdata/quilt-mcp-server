#!/usr/bin/env python3
"""ECS deployment script for Quilt MCP Server.

Handles updating ECS task definitions and deploying to Fargate services.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any, Optional

import boto3
from botocore.exceptions import ClientError


class ECSDeployer:
    """Manages ECS task definition updates and service deployments."""

    def __init__(
        self,
        cluster: str,
        service: str,
        task_family: str,
        region: str = "us-east-1",
        dry_run: bool = False,
    ):
        self.cluster = cluster
        self.service = service
        self.task_family = task_family
        self.region = region
        self.dry_run = dry_run
        self.ecs = boto3.client("ecs", region_name=region)

    def get_current_task_definition(self) -> dict[str, Any]:
        """Retrieve the current task definition."""
        try:
            response = self.ecs.describe_task_definition(taskDefinition=self.task_family)
            return response["taskDefinition"]
        except ClientError as e:
            print(f"ERROR: Failed to get task definition: {e}", file=sys.stderr)
            raise

    def update_task_definition(self, image_uri: str) -> str:
        """Create a new task definition revision with updated image."""
        print(f"INFO: Fetching current task definition: {self.task_family}", file=sys.stderr)
        current_task = self.get_current_task_definition()

        # Extract only the fields needed for registration
        new_task_def = {
            "family": current_task["family"],
            "taskRoleArn": current_task.get("taskRoleArn"),
            "executionRoleArn": current_task.get("executionRoleArn"),
            "networkMode": current_task.get("networkMode"),
            "containerDefinitions": current_task["containerDefinitions"],
            "volumes": current_task.get("volumes", []),
            "requiresCompatibilities": current_task.get("requiresCompatibilities", []),
            "cpu": current_task.get("cpu"),
            "memory": current_task.get("memory"),
            "runtimePlatform": current_task.get("runtimePlatform"),
        }

        # Remove None values
        new_task_def = {k: v for k, v in new_task_def.items() if v is not None}

        # Update image in container definitions
        for container in new_task_def["containerDefinitions"]:
            old_image = container["image"]
            container["image"] = image_uri
            print(f"INFO: Updating container '{container['name']}':", file=sys.stderr)
            print(f"INFO:   Old image: {old_image}", file=sys.stderr)
            print(f"INFO:   New image: {image_uri}", file=sys.stderr)

        if self.dry_run:
            print("DRY RUN: Would register new task definition", file=sys.stderr)
            print(json.dumps(new_task_def, indent=2))
            return f"{self.task_family}:999"  # Fake revision number

        # Register new task definition
        print("INFO: Registering new task definition revision...", file=sys.stderr)
        try:
            response = self.ecs.register_task_definition(**new_task_def)
            task_def_arn = response["taskDefinition"]["taskDefinitionArn"]
            revision = response["taskDefinition"]["revision"]
            print(f"INFO: Registered new task definition: {self.task_family}:{revision}", file=sys.stderr)
            return task_def_arn
        except ClientError as e:
            print(f"ERROR: Failed to register task definition: {e}", file=sys.stderr)
            raise

    def update_service(self, task_definition_arn: str) -> bool:
        """Update the ECS service to use the new task definition."""
        print(f"INFO: Updating service '{self.service}' in cluster '{self.cluster}'", file=sys.stderr)

        if self.dry_run:
            print(f"DRY RUN: Would update service to use: {task_definition_arn}", file=sys.stderr)
            return True

        try:
            response = self.ecs.update_service(
                cluster=self.cluster,
                service=self.service,
                taskDefinition=task_definition_arn,
                forceNewDeployment=True,
            )
            deployment_id = response["service"]["deployments"][0]["id"]
            print(f"INFO: Service update initiated. Deployment ID: {deployment_id}", file=sys.stderr)
            return True
        except ClientError as e:
            print(f"ERROR: Failed to update service: {e}", file=sys.stderr)
            return False

    def wait_for_deployment(self, timeout_seconds: int = 600) -> bool:
        """Wait for the service deployment to complete."""
        if self.dry_run:
            print("DRY RUN: Would wait for deployment to stabilize", file=sys.stderr)
            return True

        print(f"INFO: Waiting for service to stabilize (timeout: {timeout_seconds}s)...", file=sys.stderr)
        waiter = self.ecs.get_waiter("services_stable")

        try:
            waiter.wait(
                cluster=self.cluster,
                services=[self.service],
                WaiterConfig={"Delay": 15, "MaxAttempts": timeout_seconds // 15},
            )
            print("INFO: ✅ Service deployment completed successfully!", file=sys.stderr)
            return True
        except Exception as e:
            print(f"ERROR: Service deployment failed or timed out: {e}", file=sys.stderr)
            return False

    def get_service_status(self) -> dict[str, Any]:
        """Get current service status."""
        try:
            response = self.ecs.describe_services(cluster=self.cluster, services=[self.service])
            if not response["services"]:
                raise ValueError(f"Service {self.service} not found")
            return response["services"][0]
        except ClientError as e:
            print(f"ERROR: Failed to get service status: {e}", file=sys.stderr)
            raise

    def deploy(self, image_uri: str, wait: bool = True, timeout: int = 600) -> bool:
        """Execute full deployment: update task definition and service."""
        print(f"INFO: Starting ECS deployment", file=sys.stderr)
        print(f"INFO:   Cluster: {self.cluster}", file=sys.stderr)
        print(f"INFO:   Service: {self.service}", file=sys.stderr)
        print(f"INFO:   Task Family: {self.task_family}", file=sys.stderr)
        print(f"INFO:   Image: {image_uri}", file=sys.stderr)
        print(f"INFO:   Region: {self.region}", file=sys.stderr)

        # Step 1: Update task definition
        try:
            task_def_arn = self.update_task_definition(image_uri)
        except Exception as e:
            print(f"ERROR: Failed to update task definition: {e}", file=sys.stderr)
            return False

        # Step 2: Update service
        if not self.update_service(task_def_arn):
            return False

        # Step 3: Wait for deployment (optional)
        if wait and not self.dry_run:
            if not self.wait_for_deployment(timeout):
                return False

        print("INFO: ✅ ECS deployment completed successfully!", file=sys.stderr)
        return True


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Deploy Quilt MCP Server to ECS Fargate",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
EXAMPLES:
    # Deploy new image to ECS
    %(prog)s --image 712023778557.dkr.ecr.us-east-1.amazonaws.com/quilt-mcp-server:1.2.3

    # Deploy without waiting for service to stabilize
    %(prog)s --image IMAGE_URI --no-wait

    # Dry run to see what would happen
    %(prog)s --image IMAGE_URI --dry-run

ENVIRONMENT VARIABLES:
    ECS_CLUSTER          ECS cluster name (default: quilt-mcp-cluster)
    ECS_SERVICE          ECS service name (default: quilt-mcp-service)
    ECS_TASK_FAMILY      Task definition family (default: quilt-mcp-task)
    AWS_DEFAULT_REGION   AWS region (default: us-east-1)
        """,
    )

    parser.add_argument(
        "--image",
        required=True,
        help="Full Docker image URI to deploy",
    )
    parser.add_argument(
        "--cluster",
        default="quilt-mcp-cluster",
        help="ECS cluster name",
    )
    parser.add_argument(
        "--service",
        default="quilt-mcp-service",
        help="ECS service name",
    )
    parser.add_argument(
        "--task-family",
        default="quilt-mcp-task",
        help="Task definition family name",
    )
    parser.add_argument(
        "--region",
        default="us-east-1",
        help="AWS region",
    )
    parser.add_argument(
        "--no-wait",
        action="store_true",
        help="Don't wait for deployment to complete",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Deployment wait timeout in seconds (default: 600)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )

    return parser.parse_args()


def main() -> int:
    """Main entry point."""
    args = parse_args()

    deployer = ECSDeployer(
        cluster=args.cluster,
        service=args.service,
        task_family=args.task_family,
        region=args.region,
        dry_run=args.dry_run,
    )

    success = deployer.deploy(
        image_uri=args.image,
        wait=not args.no_wait,
        timeout=args.timeout,
    )

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())


#!/usr/bin/env python3
"""ECS Deployment and Validation Script for Quilt MCP Server.

This script automates the complete ECS deployment process including:
- Docker image building with platform compatibility
- ECR authentication and push
- Task definition updates
- ECS service deployment
- Health validation and monitoring
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Configuration
DEFAULT_CLUSTER = "sales-prod"
DEFAULT_SERVICE = "sales-prod-mcp-server-production"
DEFAULT_REGION = "us-east-1"
DEFAULT_IMAGE_NAME = "quilt-mcp-server"
HEALTH_CHECK_TIMEOUT = 300  # 5 minutes
HEALTH_CHECK_INTERVAL = 30  # 30 seconds


@dataclass
class DeploymentConfig:
    """Configuration for ECS deployment."""
    
    cluster: str
    service: str
    region: str
    image_name: str
    version: str
    task_definition_file: str
    registry: str
    dry_run: bool = False


class ECSDeploymentManager:
    """Manages ECS deployment operations for Quilt MCP Server."""
    
    def __init__(self, config: DeploymentConfig):
        self.config = config
        self.project_root = Path(__file__).parent.parent
        
    def _run_command(self, cmd: list[str], check: bool = True, cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
        """Execute a command with optional dry-run mode."""
        if self.config.dry_run:
            print(f"DRY RUN: Would execute: {' '.join(cmd)}", file=sys.stderr)
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        
        print(f"INFO: Executing: {' '.join(cmd)}", file=sys.stderr)
        return subprocess.run(
            cmd, 
            check=check, 
            capture_output=True, 
            text=True,
            cwd=cwd or self.project_root
        )
    
    def _get_registry(self) -> str:
        """Determine ECR registry URL."""
        if ecr_registry := os.getenv("ECR_REGISTRY"):
            return ecr_registry
        
        if aws_account_id := os.getenv("AWS_ACCOUNT_ID"):
            return f"{aws_account_id}.dkr.ecr.{self.config.region}.amazonaws.com"
        
        raise ValueError("ECR_REGISTRY or AWS_ACCOUNT_ID environment variable required")
    
    def _authenticate_ecr(self) -> bool:
        """Authenticate with ECR registry."""
        print("🔐 Authenticating with ECR...", file=sys.stderr)
        
        try:
            # Get login token and authenticate
            cmd = [
                "aws", "ecr", "get-login-password",
                "--region", self.config.region
            ]
            result = self._run_command(cmd)
            
            if result.returncode != 0:
                print(f"ERROR: Failed to get ECR login token: {result.stderr}", file=sys.stderr)
                return False
            
            # Login to Docker registry
            login_cmd = [
                "docker", "login",
                "--username", "AWS",
                "--password-stdin",
                self.config.registry
            ]
            
            # Use the login token as stdin
            login_process = subprocess.Popen(
                login_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, stderr = login_process.communicate(input=result.stdout.strip())
            
            if login_process.returncode != 0:
                print(f"ERROR: Failed to login to ECR: {stderr}", file=sys.stderr)
                return False
            
            print("✅ ECR authentication successful", file=sys.stderr)
            return True
            
        except Exception as e:
            print(f"ERROR: ECR authentication failed: {e}", file=sys.stderr)
            return False
    
    def _build_docker_image(self) -> bool:
        """Build Docker image with platform compatibility for ECS."""
        print("🐳 Building Docker image with platform compatibility...", file=sys.stderr)
        
        # Validate version
        if not self.config.version or self.config.version == "dev":
            print("ERROR: Invalid version for deployment. Version must be specified.", file=sys.stderr)
            return False
        
        # Build with explicit platform for ECS compatibility
        image_tag = f"{self.config.registry}/{self.config.image_name}:{self.config.version}"
        
        cmd = [
            "docker", "build",
            "--platform", "linux/amd64",  # ECS Fargate compatibility
            "--tag", image_tag,
            "--file", "Dockerfile",
            "."
        ]
        
        result = self._run_command(cmd)
        
        if result.returncode == 0:
            print(f"✅ Docker image built successfully: {image_tag}", file=sys.stderr)
            return True
        else:
            print(f"ERROR: Docker build failed: {result.stderr}", file=sys.stderr)
            return False
    
    def _push_docker_image(self) -> bool:
        """Push Docker image to ECR registry."""
        print("📤 Pushing Docker image to ECR...", file=sys.stderr)
        
        image_tag = f"{self.config.registry}/{self.config.image_name}:{self.config.version}"
        
        cmd = ["docker", "push", image_tag]
        result = self._run_command(cmd)
        
        if result.returncode == 0:
            print(f"✅ Docker image pushed successfully: {image_tag}", file=sys.stderr)
            return True
        else:
            print(f"ERROR: Docker push failed: {result.stderr}", file=sys.stderr)
            return False
    
    def _update_task_definition(self) -> bool:
        """Update task definition with new image."""
        print("📝 Updating ECS task definition...", file=sys.stderr)
        
        task_def_path = self.project_root / self.config.task_definition_file
        
        if not task_def_path.exists():
            print(f"ERROR: Task definition file not found: {task_def_path}", file=sys.stderr)
            return False
        
        try:
            # Read current task definition
            with open(task_def_path, 'r') as f:
                task_def = json.load(f)
            
            # Update image URI
            image_uri = f"{self.config.registry}/{self.config.image_name}:{self.config.version}"
            print(f"📝 Updating task definition with image: {image_uri}", file=sys.stderr)
            
            # Find and update the mcp-server container
            updated = False
            for container in task_def.get("containerDefinitions", []):
                if container.get("name") == "mcp-server":
                    old_image = container.get("image", "unknown")
                    container["image"] = image_uri
                    print(f"📝 Updated container image: {old_image} → {image_uri}", file=sys.stderr)
                    updated = True
                    
                    # Update version in environment variables
                    for env_var in container.get("environment", []):
                        if env_var.get("name") == "MCP_SERVER_VERSION":
                            old_version = env_var.get("value", "unknown")
                            env_var["value"] = self.config.version
                            print(f"📝 Updated MCP_SERVER_VERSION: {old_version} → {self.config.version}", file=sys.stderr)
                            break
                    
                    # Ensure JWT secret uses SSM Parameter Store reference
                    # Remove inline JWT secret if present
                    container["environment"] = [
                        env for env in container.get("environment", [])
                        if env.get("name") != "MCP_ENHANCED_JWT_SECRET"
                    ]
                    
                    # Add or update secrets section to use SSM
                    if "secrets" not in container:
                        container["secrets"] = []
                    
                    # Remove existing JWT secret reference if present
                    container["secrets"] = [
                        secret for secret in container.get("secrets", [])
                        if secret.get("name") != "MCP_ENHANCED_JWT_SECRET"
                    ]
                    
                    # Add SSM reference for JWT secret
                    ssm_arn = f"arn:aws:ssm:{self.config.region}:850787717197:parameter/quilt/mcp-server/jwt-secret"
                    container["secrets"].append({
                        "name": "MCP_ENHANCED_JWT_SECRET",
                        "valueFrom": ssm_arn
                    })
                    
                    print("📝 Updated MCP_ENHANCED_JWT_SECRET to use SSM Parameter Store", file=sys.stderr)
                    print(f"📝 SSM Parameter: {ssm_arn}", file=sys.stderr)
                    
                    break
            
            if not updated:
                print("ERROR: Could not find 'mcp-server' container in task definition", file=sys.stderr)
                return False
            
            if self.config.dry_run:
                print(f"DRY RUN: Would update task definition with image: {image_uri}", file=sys.stderr)
                return True
            
            # Write updated task definition to a temporary file
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
                json.dump(task_def, temp_file, indent=2)
                temp_task_def_path = temp_file.name
            
            try:
                # Register new task definition using the updated file
                cmd = [
                    "aws", "ecs", "register-task-definition",
                    "--cli-input-json", f"file://{temp_task_def_path}",
                    "--region", self.config.region
                ]
                
                result = self._run_command(cmd)
                
                if result.returncode == 0:
                    # Extract task definition ARN from output
                    response = json.loads(result.stdout)
                    task_def_arn = response["taskDefinition"]["taskDefinitionArn"]
                    print(f"✅ Task definition registered: {task_def_arn}", file=sys.stderr)
                    return True
                else:
                    print(f"ERROR: Failed to register task definition: {result.stderr}", file=sys.stderr)
                    return False
            finally:
                # Clean up temporary file
                import os
                try:
                    os.unlink(temp_task_def_path)
                except:
                    pass
                
        except Exception as e:
            print(f"ERROR: Failed to update task definition: {e}", file=sys.stderr)
            return False
    
    def _deploy_service(self) -> bool:
        """Deploy ECS service with new task definition."""
        print("🚀 Deploying ECS service...", file=sys.stderr)
        
        # Get the latest task definition revision
        cmd = [
            "aws", "ecs", "describe-task-definition",
            "--task-definition", "quilt-mcp-server",
            "--region", self.config.region,
            "--query", "taskDefinition.revision"
        ]
        
        result = self._run_command(cmd)
        
        if result.returncode != 0:
            print(f"ERROR: Failed to get task definition revision: {result.stderr}", file=sys.stderr)
            return False
        
        task_def_revision = result.stdout.strip()
        
        # Update service with new task definition
        cmd = [
            "aws", "ecs", "update-service",
            "--cluster", self.config.cluster,
            "--service", self.config.service,
            "--task-definition", f"quilt-mcp-server:{task_def_revision}",
            "--region", self.config.region
        ]
        
        result = self._run_command(cmd)
        
        if result.returncode == 0:
            print(f"✅ ECS service updated with task definition revision: {task_def_revision}", file=sys.stderr)
            return True
        else:
            print(f"ERROR: Failed to update ECS service: {result.stderr}", file=sys.stderr)
            return False
    
    def _wait_for_deployment(self) -> bool:
        """Wait for deployment to complete and become healthy."""
        print("⏳ Waiting for deployment to complete...", file=sys.stderr)
        
        start_time = time.time()
        
        while time.time() - start_time < HEALTH_CHECK_TIMEOUT:
            # Check service status
            cmd = [
                "aws", "ecs", "describe-services",
                "--cluster", self.config.cluster,
                "--services", self.config.service,
                "--region", self.config.region,
                "--query", "services[0].deployments[0].{status:status,desiredCount:desiredCount,runningCount:runningCount,pendingCount:pendingCount,rolloutState:rolloutState}"
            ]
            
            result = self._run_command(cmd)
            
            if result.returncode != 0:
                print(f"ERROR: Failed to check service status: {result.stderr}", file=sys.stderr)
                return False
            
            try:
                status = json.loads(result.stdout)
                print(f"📊 Deployment status: {status}", file=sys.stderr)
                
                # Check if deployment is complete
                if (status.get("status") == "PRIMARY" and 
                    status.get("rolloutState") == "COMPLETED" and
                    status.get("runningCount", 0) > 0 and
                    status.get("pendingCount", 0) == 0):
                    
                    print("✅ Deployment completed successfully!", file=sys.stderr)
                    return True
                
                # Check for failed tasks
                if status.get("status") == "PRIMARY" and status.get("rolloutState") == "FAILED":
                    print("❌ Deployment failed!", file=sys.stderr)
                    return False
                
            except json.JSONDecodeError:
                print(f"WARNING: Could not parse service status: {result.stdout}", file=sys.stderr)
            
            print(f"⏳ Waiting {HEALTH_CHECK_INTERVAL}s for deployment to complete...", file=sys.stderr)
            time.sleep(HEALTH_CHECK_INTERVAL)
        
        print(f"❌ Deployment timed out after {HEALTH_CHECK_TIMEOUT}s", file=sys.stderr)
        return False
    
    def _validate_health(self) -> bool:
        """Validate that the deployed service is healthy."""
        print("🏥 Validating service health...", file=sys.stderr)
        
        # Get running tasks
        cmd = [
            "aws", "ecs", "list-tasks",
            "--cluster", self.config.cluster,
            "--service-name", self.config.service,
            "--region", self.config.region
        ]
        
        result = self._run_command(cmd)
        
        if result.returncode != 0:
            print(f"ERROR: Failed to list tasks: {result.stderr}", file=sys.stderr)
            return False
        
        try:
            tasks_response = json.loads(result.stdout)
            task_arns = tasks_response.get("taskArns", [])
            
            if not task_arns:
                print("❌ No running tasks found", file=sys.stderr)
                return False
            
            # Check the first task's health
            task_arn = task_arns[0]
            task_id = task_arn.split("/")[-1]
            
            cmd = [
                "aws", "ecs", "describe-tasks",
                "--cluster", self.config.cluster,
                "--tasks", task_arn,
                "--region", self.config.region,
                "--query", "tasks[0].{lastStatus:lastStatus,healthStatus:healthStatus,desiredStatus:desiredStatus}"
            ]
            
            result = self._run_command(cmd)
            
            if result.returncode != 0:
                print(f"ERROR: Failed to describe task: {result.stderr}", file=sys.stderr)
                return False
            
            task_status = json.loads(result.stdout)
            print(f"📊 Task {task_id} status: {task_status}", file=sys.stderr)
            
            # Check if task is healthy
            if (task_status.get("lastStatus") == "RUNNING" and 
                task_status.get("healthStatus") in ["HEALTHY", None] and  # HEALTHY or no health check
                task_status.get("desiredStatus") == "RUNNING"):
                
                print("✅ Service is healthy and running!", file=sys.stderr)
                return True
            else:
                print(f"❌ Service is not healthy: {task_status}", file=sys.stderr)
                return False
                
        except json.JSONDecodeError:
            print(f"ERROR: Could not parse task response: {result.stdout}", file=sys.stderr)
            return False
    
    def _get_recent_logs(self) -> bool:
        """Get recent logs from the running container."""
        print("📋 Getting recent logs from deployed container...", file=sys.stderr)
        
        # Get running tasks
        cmd = [
            "aws", "ecs", "list-tasks",
            "--cluster", self.config.cluster,
            "--service-name", self.config.service,
            "--region", self.config.region
        ]
        
        result = self._run_command(cmd)
        
        if result.returncode != 0:
            print(f"ERROR: Failed to list tasks: {result.stderr}", file=sys.stderr)
            return False
        
        try:
            tasks_response = json.loads(result.stdout)
            task_arns = tasks_response.get("taskArns", [])
            
            if not task_arns:
                print("❌ No running tasks found", file=sys.stderr)
                return False
            
            task_arn = task_arns[0]
            task_id = task_arn.split("/")[-1]
            
            # Get logs from the last 5 minutes
            log_stream = f"ecs/mcp-server/{task_id}"
            start_time = int((time.time() - 300) * 1000)  # 5 minutes ago in milliseconds
            
            cmd = [
                "aws", "logs", "get-log-events",
                "--log-group-name", "/ecs/mcp-server-production",
                "--log-stream-name", log_stream,
                "--region", self.config.region,
                "--start-time", str(start_time)
            ]
            
            result = self._run_command(cmd)
            
            if result.returncode != 0:
                print(f"WARNING: Could not get logs: {result.stderr}", file=sys.stderr)
                return False
            
            try:
                logs_response = json.loads(result.stdout)
                events = logs_response.get("events", [])
                
                print(f"📋 Recent logs from {log_stream}:", file=sys.stderr)
                for event in events[-10:]:  # Show last 10 log entries
                    message = event.get("message", "").strip()
                    if message:
                        print(f"  {message}", file=sys.stderr)
                
                return True
                
            except json.JSONDecodeError:
                print(f"WARNING: Could not parse logs: {result.stdout}", file=sys.stderr)
                return False
                
        except json.JSONDecodeError:
            print(f"ERROR: Could not parse task response: {result.stdout}", file=sys.stderr)
            return False
    
    def deploy(self) -> bool:
        """Execute complete deployment process."""
        print(f"🚀 Starting ECS deployment for version: '{self.config.version}'", file=sys.stderr)
        print(f"📍 Target: {self.config.cluster}/{self.config.service}", file=sys.stderr)
        print(f"🏷️  Registry: {self.config.registry}", file=sys.stderr)
        
        # Validate version
        if not self.config.version or self.config.version == "dev":
            print("ERROR: Invalid version for deployment. Version must be specified.", file=sys.stderr)
            return False
        
        # Step 1: Authenticate with ECR
        if not self._authenticate_ecr():
            return False
        
        # Step 2: Build Docker image with platform compatibility
        if not self._build_docker_image():
            return False
        
        # Step 3: Push Docker image
        if not self._push_docker_image():
            return False
        
        # Step 4: Update task definition
        if not self._update_task_definition():
            return False
        
        # Step 5: Deploy service
        if not self._deploy_service():
            return False
        
        # Step 6: Wait for deployment completion
        if not self._wait_for_deployment():
            return False
        
        # Step 7: Validate health
        if not self._validate_health():
            return False
        
        # Step 8: Show recent logs
        self._get_recent_logs()
        
        print("🎉 Deployment completed successfully!", file=sys.stderr)
        return True
    
    def validate_only(self) -> bool:
        """Validate existing deployment without making changes."""
        print("🏥 Validating existing ECS deployment...", file=sys.stderr)
        
        # Check service status
        if not self._validate_health():
            return False
        
        # Show recent logs
        self._get_recent_logs()
        
        print("✅ Deployment validation completed!", file=sys.stderr)
        return True


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="ECS Deployment and Validation for Quilt MCP Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
EXAMPLES:
    # Deploy with automatic version detection
    %(prog)s deploy
    
    # Deploy with specific version
    %(prog)s deploy --version jwt-auth-v1.0.0
    
    # Validate existing deployment
    %(prog)s validate
    
    # Dry run to see what would happen
    %(prog)s deploy --dry-run

ENVIRONMENT VARIABLES:
    ECR_REGISTRY           ECR registry URL
    AWS_ACCOUNT_ID         AWS account ID (used to construct registry)
    AWS_DEFAULT_REGION     AWS region (default: us-east-1)
    VERSION                Version tag (can override --version)
        """,
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Deploy command
    deploy_parser = subparsers.add_parser("deploy", help="Deploy to ECS")
    deploy_parser.add_argument("--version", help="Version tag for the deployment")
    deploy_parser.add_argument("--cluster", default=DEFAULT_CLUSTER, help="ECS cluster name")
    deploy_parser.add_argument("--service", default=DEFAULT_SERVICE, help="ECS service name")
    deploy_parser.add_argument("--region", default=DEFAULT_REGION, help="AWS region")
    deploy_parser.add_argument("--registry", help="ECR registry URL")
    deploy_parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    
    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate existing deployment")
    validate_parser.add_argument("--cluster", default=DEFAULT_CLUSTER, help="ECS cluster name")
    validate_parser.add_argument("--service", default=DEFAULT_SERVICE, help="ECS service name")
    validate_parser.add_argument("--region", default=DEFAULT_REGION, help="AWS region")
    
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Main entry point."""
    args = parse_args(argv or sys.argv[1:])
    
    if not args.command:
        print("ERROR: Command is required. Use --help for usage information.", file=sys.stderr)
        return 1
    
    # Get version from environment or use default
    version = os.getenv("VERSION", getattr(args, "version", None) or "dev")
    
    # Create deployment config
    config = DeploymentConfig(
        cluster=args.cluster,
        service=args.service,
        region=args.region,
        image_name=DEFAULT_IMAGE_NAME,
        version=version,
        task_definition_file="deploy/ecs-task-definition.json",
        registry=getattr(args, "registry", None) or "",  # Will be determined in _get_registry()
        dry_run=getattr(args, "dry_run", False)
    )
    
    # Set registry if not provided
    if not config.registry:
        try:
            # Create a temporary manager to get registry
            temp_manager = ECSDeploymentManager(config)
            config.registry = temp_manager._get_registry()
        except ValueError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1
    
    # Create deployment manager
    manager = ECSDeploymentManager(config)
    
    # Execute command
    if args.command == "deploy":
        success = manager.deploy()
    elif args.command == "validate":
        success = manager.validate_only()
    else:
        print(f"ERROR: Unknown command: {args.command}", file=sys.stderr)
        return 1
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

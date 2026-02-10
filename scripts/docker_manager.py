#!/usr/bin/env python3
"""Unified Docker build and deployment script for Quilt MCP Server.

Combines Docker image tag generation with build and push operations.
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
from typing import Any, Iterable, Optional
from urllib.parse import urlparse

# Optional quiltx integration for auto-discovery
try:
    from quiltx import get_catalog_url, get_catalog_region  # type: ignore

    QUILTX_AVAILABLE = True
except ImportError:
    QUILTX_AVAILABLE = False


# Configuration
# DOCKER_IMAGE_NAME can be set via environment variable (typically exported from Makefile)
# If not set, it will be checked when actually needed (allows --help to work)
DOCKER_IMAGE_NAME: Optional[str] = os.getenv("DOCKER_IMAGE_NAME")

DEFAULT_REGION = "us-east-1"
LATEST_TAG = "latest"


def get_docker_image_name() -> str:
    """Get DOCKER_IMAGE_NAME or raise an error if not set."""
    if not DOCKER_IMAGE_NAME:
        print("ERROR: DOCKER_IMAGE_NAME environment variable must be set", file=sys.stderr)
        print("  Set it like: export DOCKER_IMAGE_NAME=quiltdata/mcp", file=sys.stderr)
        sys.exit(1)
    return DOCKER_IMAGE_NAME


@dataclass(frozen=True)
class ImageReference:
    """Represents a fully-qualified Docker image reference."""

    registry: str
    image: str
    tag: str

    @property
    def uri(self) -> str:
        return f"{self.registry}/{self.image}:{self.tag}"


@dataclass(frozen=True)
class ContainerConfig:
    """Configuration for a Docker container."""

    name: str
    image: str
    port: int  # Container internal port
    host_port: int  # Host port
    env_vars: dict[str, str]
    security_opts: list[str]
    tmpfs_mounts: dict[str, str]
    memory_limit: str
    memory_swap: str
    cpu_quota: int
    cpu_period: int
    read_only: bool

    def to_docker_run_args(self) -> list[str]:
        """Convert config to docker run command arguments."""
        args = ["docker", "run", "-d", "--name", self.name]

        # Security options
        if self.read_only:
            args.append("--read-only")
        for opt in self.security_opts:
            args.extend(["--security-opt", opt])

        # Resource limits
        args.extend(["--memory", self.memory_limit])
        args.extend(["--memory-swap", self.memory_swap])
        args.extend(["--cpu-quota", str(self.cpu_quota)])
        args.extend(["--cpu-period", str(self.cpu_period)])

        # Tmpfs mounts
        for path, opts in self.tmpfs_mounts.items():
            args.extend(["--tmpfs", f"{path}:{opts}"])

        # Environment variables
        for key, value in self.env_vars.items():
            args.extend(["-e", f"{key}={value}"])

        # Port mapping
        args.extend(["-p", f"{self.host_port}:{self.port}"])

        # Image name
        args.append(self.image)

        return args


class DockerManager:
    """Manages Docker operations for Quilt MCP Server."""

    def __init__(
        self,
        registry: Optional[str] = None,
        region: str = DEFAULT_REGION,
        dry_run: bool = False,
    ):
        self.image_name = get_docker_image_name()
        self.region = region
        self.dry_run = dry_run
        self.registry = self._get_registry(registry)
        self.project_root = Path(__file__).parent.parent

    def _get_registry(self, registry: Optional[str]) -> str:
        """Determine ECR registry URL from various sources."""
        # Priority: explicit parameter > ECR_REGISTRY env > detect via STS > construct from AWS_ACCOUNT_ID
        if registry:
            return registry

        if ecr_registry := os.getenv("ECR_REGISTRY"):
            return ecr_registry

        # Try to get account ID from AWS STS if credentials are available
        try:
            result = subprocess.run(
                ["aws", "sts", "get-caller-identity", "--query", "Account", "--output", "text"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )
            aws_account_id = result.stdout.strip()
            if aws_account_id:
                # Get region from environment or detect from AWS config
                region = os.getenv("AWS_DEFAULT_REGION")
                if not region:
                    # Try to get region from AWS CLI configuration
                    try:
                        region_result = subprocess.run(
                            ["aws", "configure", "get", "region"],
                            capture_output=True,
                            text=True,
                            check=False,
                            timeout=2,
                        )
                        if region_result.returncode == 0 and region_result.stdout.strip():
                            region = region_result.stdout.strip()
                    except (subprocess.TimeoutExpired, FileNotFoundError):
                        pass

                # Final fallback
                if not region:
                    region = self.region

                print(f"INFO: Detected AWS account {aws_account_id} (region: {region}) via STS", file=sys.stderr)
                return f"{aws_account_id}.dkr.ecr.{region}.amazonaws.com"
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            # STS call failed, try environment variable fallback
            pass

        if aws_account_id := os.getenv("AWS_ACCOUNT_ID"):
            region = os.getenv("AWS_DEFAULT_REGION", self.region)
            return f"{aws_account_id}.dkr.ecr.{region}.amazonaws.com"

        # For local builds, use a default local registry
        print("WARNING: No AWS credentials found, using localhost:5000 for local testing", file=sys.stderr)
        return "localhost:5000"

    def _run_command(self, cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
        """Execute a command with optional dry-run mode."""
        if self.dry_run:
            print(f"DRY RUN: Would execute: {' '.join(cmd)}", file=sys.stderr)
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        print(f"INFO: Executing: {' '.join(cmd)}", file=sys.stderr)
        return subprocess.run(cmd, check=check, capture_output=True, text=True)

    def get_quilt_config(self) -> tuple[Optional[str], Optional[str]]:
        """Get Quilt catalog and registry URLs.

        Priority order:
        1. Environment variables (QUILT_CATALOG_URL, QUILT_REGISTRY_URL)
        2. Auto-discovery via quiltx (if available)
        3. None (requires manual configuration)

        Returns:
            Tuple of (catalog_url, registry_url) or (None, None) if not found
        """
        # Try environment variables first
        catalog_url = os.getenv("QUILT_CATALOG_URL")
        registry_url = os.getenv("QUILT_REGISTRY_URL")

        if catalog_url and registry_url:
            print(f"INFO: Using Quilt config from environment variables", file=sys.stderr)
            print(f"   Catalog: {catalog_url}", file=sys.stderr)
            print(f"   Registry: {registry_url}", file=sys.stderr)
            return (catalog_url, registry_url)

        # Try quiltx auto-discovery
        if QUILTX_AVAILABLE:
            try:
                catalog_url = get_catalog_url()
                # Construct registry URL by adding 'registry.' subdomain
                # e.g., https://my-catalog.quiltdata.com -> https://registry.my-catalog.quiltdata.com
                if catalog_url:
                    parsed = urlparse(catalog_url)
                    registry_host = f"registry.{parsed.netloc}"
                    registry_url = f"{parsed.scheme}://{registry_host}"

                    print(f"INFO: Auto-discovered Quilt config via quiltx", file=sys.stderr)
                    print(f"   Catalog: {catalog_url}", file=sys.stderr)
                    print(f"   Registry: {registry_url}", file=sys.stderr)
                    return (catalog_url, registry_url)
            except Exception as e:
                print(f"WARNING: Could not auto-discover Quilt config: {e}", file=sys.stderr)
        else:
            print("INFO: quiltx not available for auto-discovery", file=sys.stderr)

        return (None, None)

    def validate_quilt_config(self) -> bool:
        """Validate that Quilt configuration is available.

        Returns:
            True if configuration is valid, False otherwise
        """
        catalog_url, registry_url = self.get_quilt_config()

        if not catalog_url or not registry_url:
            print("", file=sys.stderr)
            print("ERROR: Quilt catalog configuration not found", file=sys.stderr)
            print("", file=sys.stderr)
            print("Please configure using one of these methods:", file=sys.stderr)
            print("", file=sys.stderr)
            print("1. Set environment variables:", file=sys.stderr)
            print("   export QUILT_CATALOG_URL=https://your-catalog.quiltdata.com", file=sys.stderr)
            print("   export QUILT_REGISTRY_URL=https://registry.your-catalog.quiltdata.com", file=sys.stderr)
            print("", file=sys.stderr)
            print("2. Run 'quilt3 login' to configure quiltx auto-discovery", file=sys.stderr)
            print("   (requires: pip install quiltx)", file=sys.stderr)
            print("", file=sys.stderr)
            return False

        return True

    def create_stateless_config(
        self,
        container_name: str = "mcp-stateless-test",
        image: str = "quilt-mcp:test",
        port: int = 8002,
        jwt_secret: Optional[str] = None,
    ) -> Optional[ContainerConfig]:
        """Create configuration for stateless MCP container.

        Args:
            container_name: Name for the Docker container
            image: Docker image to use
            port: Host port to expose
            jwt_secret: JWT secret key (defaults to test key)

        Returns:
            ContainerConfig instance or None if validation fails
        """
        # Validate Quilt configuration
        if not self.validate_quilt_config():
            return None

        catalog_url, registry_url = self.get_quilt_config()
        # After validation, these are guaranteed to be non-None
        assert catalog_url is not None and registry_url is not None

        # Default JWT secret for testing
        if not jwt_secret:
            jwt_secret = "test-secret"

        env_vars = {
            "QUILT_MULTIUSER_MODE": "true",
            "QUILT_CATALOG_URL": catalog_url,
            "QUILT_REGISTRY_URL": registry_url,
            "QUILT_DISABLE_CACHE": "true",
            "HOME": "/tmp",
            "LOG_LEVEL": "DEBUG",
            "FASTMCP_TRANSPORT": "http",
            "FASTMCP_HOST": "0.0.0.0",
            "FASTMCP_PORT": "8000",
            "AWS_REGION": "us-east-1",
        }

        return ContainerConfig(
            name=container_name,
            image=image,
            port=8000,  # Container internal port
            host_port=port,  # Host port
            env_vars=env_vars,
            security_opts=["no-new-privileges:true"],
            tmpfs_mounts={
                "/tmp": "size=100M,mode=1777",
                "/run": "size=10M,mode=755",
            },
            memory_limit="512m",
            memory_swap="512m",
            cpu_quota=100000,
            cpu_period=100000,
            read_only=True,
        )

    def create_multiuser_fake_config(
        self,
        container_name: str = "mcp-multiuser-fake-test",
        image: str = "quilt-mcp:test",
        port: int = 8003,
        jwt_secret: Optional[str] = None,
    ) -> Optional[ContainerConfig]:
        """Create configuration for multiuser fake role testing.

        Args:
            container_name: Name for the Docker container
            image: Docker image to use
            port: Host port to expose
            jwt_secret: JWT secret key (defaults to test-secret)

        Returns:
            ContainerConfig instance or None if validation fails
        """
        # Validate Quilt configuration
        if not self.validate_quilt_config():
            return None

        catalog_url, registry_url = self.get_quilt_config()
        # After validation, these are guaranteed to be non-None
        assert catalog_url is not None and registry_url is not None

        # Default JWT secret for multiuser testing
        if not jwt_secret:
            jwt_secret = "test-secret"

        env_vars = {
            "QUILT_MULTIUSER_MODE": "true",
            "QUILT_CATALOG_URL": catalog_url,
            "QUILT_REGISTRY_URL": registry_url,
            "QUILT_DISABLE_CACHE": "true",
            "HOME": "/tmp",
            "LOG_LEVEL": "DEBUG",
            "FASTMCP_TRANSPORT": "http",
            "FASTMCP_HOST": "0.0.0.0",
            "FASTMCP_PORT": "8000",
            "AWS_REGION": "us-east-1",
        }

        return ContainerConfig(
            name=container_name,
            image=image,
            port=8000,  # Container internal port
            host_port=port,  # Host port
            env_vars=env_vars,
            security_opts=["no-new-privileges:true"],
            tmpfs_mounts={
                "/tmp": "size=100M,mode=1777",
                "/run": "size=10M,mode=755",
            },
            memory_limit="512m",
            memory_swap="512m",
            cpu_quota=100000,
            cpu_period=100000,
            read_only=True,
        )

    def container_exists(self, name: str) -> bool:
        """Check if a container exists (running or stopped).

        Args:
            name: Container name

        Returns:
            True if container exists, False otherwise
        """
        result = self._run_command(["docker", "ps", "-a", "--format", "{{.Names}}"], check=False)

        if result.returncode != 0:
            return False

        containers = result.stdout.strip().split("\n")
        return name in containers

    def container_is_running(self, name: str) -> bool:
        """Check if a container is currently running.

        Args:
            name: Container name

        Returns:
            True if container is running, False otherwise
        """
        result = self._run_command(["docker", "ps", "--format", "{{.Names}}"], check=False)

        if result.returncode != 0:
            return False

        containers = result.stdout.strip().split("\n")
        return name in containers

    def start_container(self, config: ContainerConfig) -> bool:
        """Start a Docker container with the specified configuration.

        Args:
            config: Container configuration

        Returns:
            True if container started successfully, False otherwise
        """
        if not self._check_docker():
            return False

        # Stop and remove existing container if it exists
        if self.container_exists(config.name):
            print(f"INFO: Removing existing container: {config.name}", file=sys.stderr)
            self.stop_container(config.name)

        print(f"INFO: Starting container: {config.name}", file=sys.stderr)
        print(f"   Image: {config.image}", file=sys.stderr)
        print(f"   Port: {config.host_port} -> {config.port}", file=sys.stderr)

        # Add --cap-drop=ALL to security options
        docker_args = config.to_docker_run_args()
        # Insert --cap-drop=ALL after the "run" command
        run_idx = docker_args.index("run")
        docker_args.insert(run_idx + 1, "--cap-drop=ALL")

        # Start container
        result = self._run_command(docker_args, check=False)

        if result.returncode != 0:
            print(f"ERROR: Failed to start container: {result.stderr}", file=sys.stderr)
            return False

        # Wait for container to start
        print("INFO: Waiting for container to start...", file=sys.stderr)
        time.sleep(3)

        # Verify container is running
        if not self.container_is_running(config.name):
            print(f"ERROR: Container failed to start", file=sys.stderr)
            # Show logs for debugging
            log_result = self._run_command(["docker", "logs", config.name], check=False)
            if log_result.stdout:
                print(log_result.stdout, file=sys.stderr)
            return False

        print(f"INFO: Container started successfully", file=sys.stderr)
        print(f"   Access at: http://localhost:{config.host_port}/mcp", file=sys.stderr)
        print(f"   View logs: docker logs {config.name}", file=sys.stderr)
        return True

    def stop_container(self, name: str) -> bool:
        """Stop and remove a Docker container.

        Args:
            name: Container name

        Returns:
            True if container stopped successfully, False otherwise
        """
        if not self.container_exists(name):
            print(f"INFO: Container does not exist: {name}", file=sys.stderr)
            return True

        print(f"INFO: Stopping container: {name}", file=sys.stderr)

        # Stop container
        stop_result = self._run_command(["docker", "stop", name], check=False)

        if stop_result.returncode != 0:
            print(f"WARNING: Failed to stop container: {stop_result.stderr}", file=sys.stderr)

        # Remove container
        remove_result = self._run_command(["docker", "rm", name], check=False)

        if remove_result.returncode != 0:
            print(f"ERROR: Failed to remove container: {remove_result.stderr}", file=sys.stderr)
            return False

        print(f"INFO: Container stopped and removed", file=sys.stderr)
        return True

    def show_logs(self, name: str, tail: int = 50, follow: bool = False) -> bool:
        """Show container logs.

        Args:
            name: Container name
            tail: Number of lines to show from end of logs
            follow: Whether to follow log output (stream)

        Returns:
            True if successful, False otherwise
        """
        if not self.container_exists(name):
            print(f"ERROR: Container does not exist: {name}", file=sys.stderr)
            return False

        cmd = ["docker", "logs"]

        if tail > 0:
            cmd.extend(["--tail", str(tail)])

        if follow:
            cmd.append("-f")

        cmd.append(name)

        # Don't use _run_command here - we want logs to stream to stdout
        if self.dry_run:
            print(f"DRY RUN: Would execute: {' '.join(cmd)}", file=sys.stderr)
            return True

        print(f"INFO: Showing logs for container: {name}", file=sys.stderr)

        # Run without capturing output so logs stream directly
        result = subprocess.run(cmd, check=False)

        return result.returncode == 0

    def _check_docker(self) -> bool:
        """Validate Docker is available and running."""
        try:
            result = self._run_command(["docker", "info"], check=False)
            if result.returncode != 0:
                print("ERROR: Docker daemon is not running or not accessible", file=sys.stderr)
                return False
            return True
        except FileNotFoundError:
            print("ERROR: Docker is not installed or not in PATH", file=sys.stderr)
            return False

    def generate_tags(self, version: str, include_latest: bool = True) -> list[ImageReference]:
        """Generate Docker image tags for a given version."""
        if not self.registry:
            raise ValueError("registry is required")
        if not version:
            raise ValueError("version is required")

        tags = [ImageReference(registry=self.registry, image=self.image_name, tag=version)]

        if include_latest:
            tags.append(ImageReference(registry=self.registry, image=self.image_name, tag=LATEST_TAG))

        return tags

    def build(self, tag: str, platform: str = "linux/amd64") -> bool:
        """Build Docker image with the specified tag.

        Args:
            tag: Image tag to build
            platform: Target platform (default: linux/amd64 for production)
        """
        # Check architecture - warn on arm64 but allow local builds for testing
        import platform as platform_module

        machine = platform_module.machine().lower()
        if machine in ("arm64", "aarch64") and platform == "linux/amd64":
            print("", file=sys.stderr)
            print("⚠️  WARNING: Building linux/amd64 on arm64 architecture", file=sys.stderr)
            print("⚠️  This will use emulation and be very slow", file=sys.stderr)
            print("⚠️  For testing only - production images should be built in CI", file=sys.stderr)
            print("", file=sys.stderr)

        print(f"INFO: Building Docker image: {tag}", file=sys.stderr)
        print(f"INFO: Target platform: {platform}", file=sys.stderr)

        os.chdir(self.project_root)
        result = self._run_command(
            ["docker", "build", "--platform", platform, "--file", "Dockerfile", "--tag", tag, "."]
        )

        if result.returncode == 0:
            print(f"INFO: Successfully built: {tag}", file=sys.stderr)
            return True
        else:
            print(f"ERROR: Failed to build image: {result.stderr}", file=sys.stderr)
            return False

    def tag(self, source: str, target: str) -> bool:
        """Tag a Docker image."""
        print(f"INFO: Tagging image: {source} -> {target}", file=sys.stderr)

        result = self._run_command(["docker", "tag", source, target])

        if result.returncode == 0:
            return True
        else:
            print(f"ERROR: Failed to tag image: {result.stderr}", file=sys.stderr)
            return False

    def push(self, tag: str) -> bool:
        """Push Docker image to registry."""
        print(f"INFO: Pushing image: {tag}", file=sys.stderr)

        result = self._run_command(["docker", "push", tag])

        if result.returncode == 0:
            print(f"INFO: Successfully pushed: {tag}", file=sys.stderr)
            return True
        else:
            print(f"ERROR: Failed to push image: {result.stderr}", file=sys.stderr)
            return False

    def build_and_push(self, version: str, include_latest: bool = True) -> bool:
        """Build and push Docker image with all generated tags.

        NOTE: Only supports amd64. On arm64, runs in dry-run mode to show what would happen.
        Production images should be built in CI on amd64 runners.
        """
        if not self._check_docker():
            return False

        # Check architecture - enable dry-run mode on arm64
        import platform

        machine = platform.machine().lower()
        if machine in ("arm64", "aarch64"):
            print("", file=sys.stderr)
            print("⚠️  WARNING: Running on arm64 architecture", file=sys.stderr)
            print("⚠️  Build will use emulation (very slow)", file=sys.stderr)
            print("⚠️  Push will run in DRY-RUN mode (no actual push)", file=sys.stderr)
            print("⚠️  Production images MUST be built in CI on amd64", file=sys.stderr)
            print("", file=sys.stderr)
            self.dry_run = True

        # Generate tags
        tags = self.generate_tags(version, include_latest)

        print(f"INFO: Using registry: {self.registry}", file=sys.stderr)
        print(f"INFO: Generated {len(tags)} image tags:", file=sys.stderr)
        for ref in tags:
            print(f"INFO:   - {ref.uri}", file=sys.stderr)

        # Build with first tag
        primary_tag = tags[0].uri
        if not self.build(primary_tag):
            return False

        # Tag with additional tags
        for ref in tags[1:]:
            if not self.tag(primary_tag, ref.uri):
                return False

        # Push all tags
        for ref in tags:
            if not self.push(ref.uri):
                return False

        print(f"INFO: Docker push completed successfully", file=sys.stderr)
        print(f"INFO: Pushed {len(tags)} tags to registry: {self.registry}", file=sys.stderr)

        # Output the primary image URI for capture by CI
        primary_uri = tags[0].uri
        print(f"DOCKER_IMAGE_URI={primary_uri}", file=sys.stdout)

        return True

    def build_local(self, version: str = "dev") -> bool:
        """Build Docker image locally without pushing.

        Uses native platform for fast local builds (no emulation).
        """
        if not self._check_docker():
            return False

        # For local builds, use simple tagging without registry prefix
        # Extract just the image name without any path separators
        # e.g., "quiltdata/mcp" -> "quilt-mcp" for local testing
        simple_name = self.image_name.split("/")[-1]
        if simple_name == "mcp":
            simple_name = "quilt-mcp"  # Use full name for clarity
        local_tag = f"{simple_name}:{version}"

        # Detect native platform for fast local builds
        import platform as platform_module

        machine = platform_module.machine().lower()
        if machine in ("arm64", "aarch64"):
            native_platform = "linux/arm64"
        elif machine in ("x86_64", "amd64"):
            native_platform = "linux/amd64"
        else:
            # Fallback to docker's default behavior
            native_platform = "linux/amd64"
            print(f"WARNING: Unknown machine type {machine}, using {native_platform}", file=sys.stderr)

        print(f"INFO: Building Docker image locally for native platform ({native_platform})", file=sys.stderr)
        if not self.build(local_tag, platform=native_platform):
            return False

        print(f"INFO: Local build completed: {local_tag}", file=sys.stderr)
        return True

    def _get_project_version(self) -> str:
        """Get current version from pyproject.toml via version.py."""
        version_script = self.project_root / "scripts" / "version.py"
        result = subprocess.run(
            ["python3", str(version_script), "get-version"],
            capture_output=True,
            text=True,
            check=True,
            cwd=self.project_root,
        )
        return result.stdout.strip()

    def _get_latest_git_tag(self) -> Optional[str]:
        """Get the most recent git tag from the repository.

        Looks for the latest tag pointing to HEAD or recent commits.
        Returns the version without the 'v' prefix.
        Returns None if not found or on error.
        """
        try:
            # Get the latest tag from git log (tags pointing to HEAD or recent commits)
            result = subprocess.run(
                ["git", "describe", "--tags", "--abbrev=0", "HEAD"],
                capture_output=True,
                text=True,
                check=False,
                cwd=self.project_root,
            )

            if result.returncode != 0:
                print(f"INFO: No git tag found on current commit", file=sys.stderr)
                return None

            tag_name = result.stdout.strip()

            # Remove 'v' prefix if present (e.g., v0.6.17-dev-20251011232530 -> 0.6.17-dev-20251011232530)
            if tag_name.startswith("v"):
                version = tag_name[1:]
            else:
                version = tag_name

            print(f"INFO: Found git tag: {tag_name} (version: {version})", file=sys.stderr)
            return version

        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            print(f"INFO: Error getting git tag: {exc}", file=sys.stderr)
            return None

    def _ecr_login(self) -> bool:
        """Login to ECR registry if needed."""
        # Check if registry is ECR
        if ".ecr." not in self.registry or ".amazonaws.com" not in self.registry:
            return True  # Not ECR, no login needed

        print(f"INFO: Logging in to ECR registry...", file=sys.stderr)

        # Use AWS CLI to get ECR login password
        result = subprocess.run(
            ["aws", "ecr", "get-login-password", "--region", self.region],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            print(f"ERROR: Failed to get ECR login password: {result.stderr}", file=sys.stderr)
            return False

        password = result.stdout.strip()

        # Login to Docker registry
        login_result = subprocess.run(
            ["docker", "login", "--username", "AWS", "--password-stdin", self.registry],
            input=password,
            capture_output=True,
            text=True,
            check=False,
        )

        if login_result.returncode != 0:
            print(f"ERROR: Failed to login to ECR: {login_result.stderr}", file=sys.stderr)
            return False

        print(f"INFO: Successfully logged in to ECR", file=sys.stderr)
        return True

    def _get_image_info(self, tag: str) -> dict[str, Any]:
        """Get image metadata from registry using docker manifest inspect."""
        full_uri = f"{self.registry}/{self.image_name}:{tag}"

        # Use docker manifest inspect to get image details
        result = subprocess.run(
            ["docker", "manifest", "inspect", full_uri],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Failed to inspect image {full_uri}: {result.stderr}")

        return json.loads(result.stdout)

    def validate(self, version: Optional[str] = None, check_latest: bool = True, skip_auth: bool = False) -> bool:
        """Validate pushed Docker images in registry.

        Args:
            version: Specific version to validate (defaults to latest git tag, then pyproject.toml)
            check_latest: Whether to verify latest tag matches expected version
            skip_auth: Skip ECR authentication (for public registries)

        Returns:
            True if validation passes, False otherwise
        """
        try:
            # Login to ECR if needed (skip for public registries)
            if not skip_auth:
                if not self._ecr_login():
                    print(f"ERROR: ECR login failed", file=sys.stderr)
                    return False
            else:
                print(f"INFO: Skipping ECR authentication (public registry mode)", file=sys.stderr)

            # Get expected version:
            # 1. Use explicit version if provided
            # 2. Try to get from latest git tag
            # 3. Fall back to pyproject.toml version
            if version:
                expected_version = version
            else:
                expected_version = self._get_latest_git_tag()
                if not expected_version:
                    print(f"INFO: No git tag found, using version from pyproject.toml", file=sys.stderr)
                    expected_version = self._get_project_version()

            print(f"INFO: Validating Docker images for version {expected_version}", file=sys.stderr)
            print(f"INFO: Registry: {self.registry}", file=sys.stderr)
            print(f"INFO: Image: {self.image_name}", file=sys.stderr)
            print("", file=sys.stderr)

            # Validate versioned image
            full_image_uri = f"{self.registry}/{self.image_name}:{expected_version}"
            print(f"INFO: Checking image: {full_image_uri}", file=sys.stderr)
            version_info = self._get_image_info(expected_version)

            # Extract digest and architecture info
            has_amd64 = False
            if "manifests" in version_info:
                # Multi-arch or manifest list
                print(f"INFO: Manifest list found", file=sys.stderr)
                print(f"   Architectures:", file=sys.stderr)
                for manifest in version_info["manifests"]:
                    platform = manifest.get("platform", {})
                    arch = platform.get("architecture", "unknown")
                    os_name = platform.get("os", "unknown")
                    digest = manifest.get("digest", "unknown")
                    size_bytes = manifest.get("size", 0)

                    # Check for amd64
                    if arch == "amd64" and os_name == "linux":
                        has_amd64 = True

                    # Format size appropriately
                    if size_bytes < 1024:
                        size_str = f"{size_bytes} B"
                    elif size_bytes < 1024 * 1024:
                        size_str = f"{size_bytes / 1024:.1f} KB"
                    else:
                        size_str = f"{size_bytes / (1024 * 1024):.1f} MB"

                    # Skip attestation manifests (very small, unknown platform)
                    if arch == "unknown" and size_bytes < 10000:
                        print(f"     - {os_name}/{arch}: {digest[:19]}... ({size_str}) [attestation]", file=sys.stderr)
                    else:
                        print(f"     - {os_name}/{arch}: {digest[:19]}... ({size_str})", file=sys.stderr)
            else:
                # Single-arch image - need to pull and inspect to get architecture
                config = version_info.get("config", {})
                digest = config.get("digest", "unknown")

                # Calculate total size from layers
                layers = version_info.get("layers", [])
                size_bytes = sum(layer.get("size", 0) for layer in layers)
                size_mb = size_bytes / (1024 * 1024)

                print(f"INFO: Single-architecture image found", file=sys.stderr)
                print(f"   Digest: {digest}", file=sys.stderr)
                print(f"   Size: {size_mb:.1f} MB", file=sys.stderr)

                # Get architecture from config blob using docker buildx imagetools
                full_uri = f"{self.registry}/{self.image_name}:{expected_version}"
                print(f"INFO: Getting architecture from image config...", file=sys.stderr)

                # Get the config digest from manifest
                config_digest_result = subprocess.run(
                    ["docker", "buildx", "imagetools", "inspect", "--raw", full_uri],
                    capture_output=True,
                    text=True,
                    check=False,
                )

                if config_digest_result.returncode != 0:
                    print(f"⚠️  Failed to get image manifest", file=sys.stderr)
                    print(f"⚠️  Single-arch images should be linux/amd64 for production", file=sys.stderr)
                else:
                    try:
                        manifest_data = json.loads(config_digest_result.stdout)
                        config_digest = manifest_data.get("config", {}).get("digest", "")

                        if config_digest:
                            # Get config blob to extract architecture
                            config_uri = f"{self.registry}/{self.image_name}@{config_digest}"
                            config_result = subprocess.run(
                                ["docker", "buildx", "imagetools", "inspect", "--raw", config_uri],
                                capture_output=True,
                                text=True,
                                check=False,
                            )

                            if config_result.returncode == 0:
                                config_data = json.loads(config_result.stdout)
                                arch = config_data.get("architecture", "")
                                os_name = config_data.get("os", "")

                                if arch and os_name:
                                    arch_info = f"{arch}/{os_name}"
                                    print(f"   Architecture: {arch_info}", file=sys.stderr)

                                    if arch == "amd64" and os_name == "linux":
                                        has_amd64 = True
                                    else:
                                        print(f"❌ Invalid architecture: {arch_info}", file=sys.stderr)
                                        print(f"   Production images MUST be linux/amd64", file=sys.stderr)
                                        return False
                                else:
                                    print(f"⚠️  Architecture metadata not found in config", file=sys.stderr)
                            else:
                                print(f"⚠️  Failed to fetch image config blob", file=sys.stderr)
                        else:
                            print(f"⚠️  Config digest not found in manifest", file=sys.stderr)
                    except (json.JSONDecodeError, KeyError) as e:
                        print(f"⚠️  Failed to parse manifest/config: {e}", file=sys.stderr)

            # Validate amd64 is present
            if not has_amd64 and "manifests" in version_info:
                print("", file=sys.stderr)
                print(f"❌ Missing required architecture: linux/amd64", file=sys.stderr)
                print(f"   Production images must include amd64 for server deployment", file=sys.stderr)
                return False

            if has_amd64:
                print(f"✅ Required architecture present: linux/amd64", file=sys.stderr)

            print("", file=sys.stderr)

            # Validate latest tag if requested
            if check_latest:
                print(f"INFO: Checking latest tag", file=sys.stderr)
                latest_info = self._get_image_info(LATEST_TAG)

                # Compare digests to verify latest points to expected version
                version_digest = self._extract_digest(version_info)
                latest_digest = self._extract_digest(latest_info)

                if version_digest == latest_digest:
                    print(f"✅ Latest tag points to version {expected_version}", file=sys.stderr)
                    print(f"   Digest: {version_digest[:19]}...", file=sys.stderr)
                else:
                    print(f"❌ Latest tag mismatch!", file=sys.stderr)
                    print(f"   Expected (v{expected_version}): {version_digest[:19]}...", file=sys.stderr)
                    print(f"   Actual (latest): {latest_digest[:19]}...", file=sys.stderr)
                    return False

            print("", file=sys.stderr)
            print(f"✅ Docker image validation passed", file=sys.stderr)
            return True

        except subprocess.CalledProcessError as exc:
            print(f"❌ Failed to get project version: {exc}", file=sys.stderr)
            return False
        except RuntimeError as exc:
            print(f"❌ {exc}", file=sys.stderr)
            return False
        except Exception as exc:
            print(f"❌ Validation failed: {exc}", file=sys.stderr)
            return False

    def _extract_digest(self, manifest_info: dict[str, Any]) -> str:
        """Extract a comparable digest from manifest info."""
        # For multi-arch manifests, use the manifest list digest
        if "manifests" in manifest_info:
            # Use first manifest's digest as representative
            return manifest_info["manifests"][0].get("digest", "")

        # For single-arch images, use config digest
        return manifest_info.get("config", {}).get("digest", "")


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Docker build and deployment for Quilt MCP Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
EXAMPLES:
    # Generate tags for a version
    %(prog)s tags --version 1.2.3

    # Build locally for testing
    %(prog)s build

    # Build and push to ECR
    %(prog)s push --version 1.2.3

    # Dry run to see what would happen
    %(prog)s push --version 1.2.3 --dry-run

    # Start a stateless test container
    %(prog)s start --mode stateless

    # Start a multiuser fake test container
    %(prog)s start --mode multiuser-fake

    # Stop a container
    %(prog)s stop --name mcp-stateless-test

    # View container logs
    %(prog)s logs --name mcp-stateless-test --tail 100

    # Follow container logs
    %(prog)s logs --name mcp-stateless-test --follow

ENVIRONMENT VARIABLES:
    ECR_REGISTRY           ECR registry URL
    AWS_ACCOUNT_ID         AWS account ID (used to construct registry)
    AWS_DEFAULT_REGION     AWS region (default: us-east-1)
    VERSION                Version tag (can override --version)
    QUILT_CATALOG_URL      Quilt catalog URL (for container start)
    QUILT_REGISTRY_URL     Quilt registry URL (for container start)
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Tags command (replaces docker_image.py functionality)
    tags_parser = subparsers.add_parser("tags", help="Generate Docker image tags")
    tags_parser.add_argument("--version", required=True, help="Version tag for the image")
    tags_parser.add_argument("--registry", help="ECR registry URL")
    tags_parser.add_argument("--output", choices=["text", "json"], default="text", help="Output format")
    tags_parser.add_argument("--no-latest", action="store_true", help="Don't include latest tag")

    # Build command
    build_parser = subparsers.add_parser("build", help="Build Docker image locally")
    build_parser.add_argument("--version", default="dev", help="Version tag (default: dev)")
    build_parser.add_argument("--registry", help="Registry URL")

    # Push command
    push_parser = subparsers.add_parser("push", help="Build and push Docker image to registry")
    push_parser.add_argument("--version", required=True, help="Version tag for the image")
    push_parser.add_argument("--registry", help="ECR registry URL")
    push_parser.add_argument("--region", default=DEFAULT_REGION, help="AWS region")
    push_parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    push_parser.add_argument("--no-latest", action="store_true", help="Don't tag as latest")

    # Info command
    info_parser = subparsers.add_parser("info", help="Get Docker image URI for a version")
    info_parser.add_argument("--version", required=True, help="Version tag for the image")
    info_parser.add_argument("--registry", help="ECR registry URL")
    info_parser.add_argument("--output", choices=["text", "github"], default="text", help="Output format")

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate pushed Docker images in registry")
    validate_parser.add_argument("--version", help="Version to validate (defaults to current pyproject.toml version)")
    validate_parser.add_argument("--registry", help="ECR registry URL")
    validate_parser.add_argument("--region", default=DEFAULT_REGION, help="AWS region")
    validate_parser.add_argument("--no-latest", action="store_true", help="Skip latest tag validation")
    validate_parser.add_argument(
        "--skip-auth", action="store_true", help="Skip ECR authentication (for public registries)"
    )

    # Start command
    start_parser = subparsers.add_parser("start", help="Start a Docker container for testing")
    start_parser.add_argument(
        "--mode", choices=["stateless", "multiuser-fake"], required=True, help="Container mode/preset"
    )
    start_parser.add_argument(
        "--image", default="quilt-mcp:test", help="Docker image to use (default: quilt-mcp:test)"
    )
    start_parser.add_argument("--name", help="Container name (defaults based on mode)")
    start_parser.add_argument(
        "--port", type=int, help="Host port to expose (defaults: 8002 for stateless, 8003 for multiuser-fake)"
    )
    start_parser.add_argument("--jwt-secret", help="JWT secret key (defaults based on mode)")

    # Stop command
    stop_parser = subparsers.add_parser("stop", help="Stop and remove a Docker container")
    stop_parser.add_argument("--name", required=True, help="Container name to stop")

    # Logs command
    logs_parser = subparsers.add_parser("logs", help="Show container logs")
    logs_parser.add_argument("--name", required=True, help="Container name")
    logs_parser.add_argument("--tail", type=int, default=50, help="Number of lines to show from end (default: 50)")
    logs_parser.add_argument("--follow", action="store_true", help="Follow log output (stream)")

    return parser.parse_args(list(argv))


def cmd_tags(args: argparse.Namespace) -> int:
    """Generate and display Docker image tags."""
    try:
        manager = DockerManager(registry=args.registry)
        references = manager.generate_tags(args.version, include_latest=not args.no_latest)

        if args.output == "json":
            payload = {
                "registry": manager.registry,
                "image": get_docker_image_name(),
                "tags": [ref.tag for ref in references],
                "uris": [ref.uri for ref in references],
            }
            print(json.dumps(payload))
        else:
            for ref in references:
                print(ref.uri)

        return 0
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def cmd_build(args: argparse.Namespace) -> int:
    """Build Docker image locally."""
    # Allow VERSION env var to override
    version = os.getenv("VERSION", args.version)

    manager = DockerManager(registry=args.registry)
    success = manager.build_local(version)
    return 0 if success else 1


def cmd_push(args: argparse.Namespace) -> int:
    """Build and push Docker image to registry."""
    # Allow VERSION env var to override
    version = os.getenv("VERSION", args.version)

    manager = DockerManager(
        registry=args.registry,
        region=args.region,
        dry_run=args.dry_run,
    )
    success = manager.build_and_push(version, include_latest=not args.no_latest)
    return 0 if success else 1


def cmd_info(args: argparse.Namespace) -> int:
    """Get Docker image info for GitHub Actions."""
    # Allow VERSION env var to override
    version = os.getenv("VERSION", args.version)

    try:
        manager = DockerManager(registry=args.registry)
        ref = ImageReference(manager.registry, get_docker_image_name(), version)

        if args.output == "github":
            # Output for GitHub Actions
            print(f"image-uri={ref.uri}")
        else:
            # Plain text output
            print(ref.uri)

        return 0
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate Docker images in registry."""
    # Allow VERSION env var to override
    version = os.getenv("VERSION", args.version) if args.version else None

    manager = DockerManager(
        registry=args.registry,
        region=args.region,
    )
    success = manager.validate(version=version, check_latest=not args.no_latest, skip_auth=args.skip_auth)
    return 0 if success else 1


def cmd_start(args: argparse.Namespace) -> int:
    """Start a Docker container."""
    manager = DockerManager(dry_run=getattr(args, 'dry_run', False))

    # Determine container configuration based on mode
    if args.mode == "stateless":
        container_name = args.name or "mcp-stateless-test"
        port = args.port or 8002
        config = manager.create_stateless_config(
            container_name=container_name,
            image=args.image,
            port=port,
            jwt_secret=args.jwt_secret,
        )
    elif args.mode == "multiuser-fake":
        container_name = args.name or "mcp-multiuser-fake-test"
        port = args.port or 8003
        config = manager.create_multiuser_fake_config(
            container_name=container_name,
            image=args.image,
            port=port,
            jwt_secret=args.jwt_secret,
        )
    else:
        print(f"ERROR: Unknown mode: {args.mode}", file=sys.stderr)
        return 1

    # Validation failed
    if config is None:
        return 1

    # Start container
    success = manager.start_container(config)
    return 0 if success else 1


def cmd_stop(args: argparse.Namespace) -> int:
    """Stop a Docker container."""
    manager = DockerManager()
    success = manager.stop_container(args.name)
    return 0 if success else 1


def cmd_logs(args: argparse.Namespace) -> int:
    """Show container logs."""
    manager = DockerManager()
    success = manager.show_logs(args.name, args.tail, args.follow)
    return 0 if success else 1


def main(argv: Iterable[str] | None = None) -> int:
    """Main entry point."""
    args = parse_args(argv or sys.argv[1:])

    if not args.command:
        print("ERROR: Command is required. Use --help for usage information.", file=sys.stderr)
        return 1

    if args.command == "tags":
        return cmd_tags(args)
    elif args.command == "build":
        return cmd_build(args)
    elif args.command == "push":
        return cmd_push(args)
    elif args.command == "info":
        return cmd_info(args)
    elif args.command == "validate":
        return cmd_validate(args)
    elif args.command == "start":
        return cmd_start(args)
    elif args.command == "stop":
        return cmd_stop(args)
    elif args.command == "logs":
        return cmd_logs(args)
    else:
        print(f"ERROR: Unknown command: {args.command}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

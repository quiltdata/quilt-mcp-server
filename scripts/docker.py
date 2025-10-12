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
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional


# Configuration
DEFAULT_IMAGE_NAME = "quiltdata/mcp"  # Used as fallback for build/info commands
DEFAULT_REGION = "us-east-1"
LATEST_TAG = "latest"


@dataclass(frozen=True)
class ImageReference:
    """Represents a fully-qualified Docker image reference."""

    registry: str
    image: str
    tag: str

    @property
    def uri(self) -> str:
        return f"{self.registry}/{self.image}:{self.tag}"


class DockerManager:
    """Manages Docker operations for Quilt MCP Server."""

    def __init__(
        self,
        registry: Optional[str] = None,
        image_name: str = DEFAULT_IMAGE_NAME,
        region: str = DEFAULT_REGION,
        dry_run: bool = False,
    ):
        self.image_name = image_name
        self.region = region
        self.dry_run = dry_run
        self.registry = self._get_registry(registry)
        self.project_root = Path(__file__).parent.parent

    def _get_registry(self, registry: Optional[str]) -> str:
        """Determine ECR registry URL from various sources."""
        # Priority: explicit parameter > ECR_REGISTRY env > construct from AWS_ACCOUNT_ID
        if registry:
            return registry

        if ecr_registry := os.getenv("ECR_REGISTRY"):
            return ecr_registry

        if aws_account_id := os.getenv("AWS_ACCOUNT_ID"):
            region = os.getenv("AWS_DEFAULT_REGION", self.region)
            return f"{aws_account_id}.dkr.ecr.{region}.amazonaws.com"

        # For local builds, use a default local registry
        return "localhost:5000"

    def _run_command(self, cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
        """Execute a command with optional dry-run mode."""
        if self.dry_run:
            print(f"DRY RUN: Would execute: {' '.join(cmd)}", file=sys.stderr)
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        print(f"INFO: Executing: {' '.join(cmd)}", file=sys.stderr)
        return subprocess.run(cmd, check=check, capture_output=True, text=True)

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

    def build(self, tag: str) -> bool:
        """Build Docker image with the specified tag."""
        print(f"INFO: Building Docker image: {tag}", file=sys.stderr)

        os.chdir(self.project_root)
        result = self._run_command(["docker", "build", "--file", "Dockerfile", "--tag", tag, "."])

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

        NOTE: Only supports amd64. Will fail on arm64 to prevent pushing unusable images.
        Production images should be built in CI on amd64 runners.
        """
        if not self._check_docker():
            return False

        # Check architecture - only allow amd64 for push
        import platform
        machine = platform.machine().lower()
        if machine in ("arm64", "aarch64"):
            print("ERROR: docker push is not supported on arm64 architecture", file=sys.stderr)
            print("ERROR: Docker images must be built on amd64 for server deployment", file=sys.stderr)
            print("ERROR: Use CI/CD to build and push production images", file=sys.stderr)
            return False

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
        return True

    def build_local(self, version: str = "dev") -> bool:
        """Build Docker image locally without pushing."""
        if not self._check_docker():
            return False

        # For local builds, use simple tagging
        local_tag = f"{self.registry}/{self.image_name}:{version}"

        print(f"INFO: Building Docker image locally", file=sys.stderr)
        if not self.build(local_tag):
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

    def validate(self, version: Optional[str] = None, check_latest: bool = True) -> bool:
        """Validate pushed Docker images in registry.

        Args:
            version: Specific version to validate (defaults to current pyproject.toml version)
            check_latest: Whether to verify latest tag matches expected version

        Returns:
            True if validation passes, False otherwise
        """
        try:
            # Get expected version from pyproject.toml
            expected_version = version or self._get_project_version()

            print(f"INFO: Validating Docker images for version {expected_version}", file=sys.stderr)
            print(f"INFO: Registry: {self.registry}", file=sys.stderr)
            print(f"INFO: Image: {self.image_name}", file=sys.stderr)
            print("", file=sys.stderr)

            # Validate versioned image
            print(f"INFO: Checking version tag: {expected_version}", file=sys.stderr)
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
                # Single-arch image
                config = version_info.get("config", {})
                digest = config.get("digest", "unknown")
                size_bytes = config.get("size", 0)
                size_mb = size_bytes / (1024 * 1024)
                print(f"INFO: Single-architecture image found", file=sys.stderr)
                print(f"   Digest: {digest}", file=sys.stderr)
                print(f"   Size: {size_mb:.1f} MB", file=sys.stderr)

                # Check if it's amd64 (though we can't easily tell from single manifest)
                # Assume single-arch in production is a problem
                print(f"⚠️  Single-architecture image - production requires linux/amd64", file=sys.stderr)

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

ENVIRONMENT VARIABLES:
    ECR_REGISTRY           ECR registry URL
    AWS_ACCOUNT_ID         AWS account ID (used to construct registry)
    AWS_DEFAULT_REGION     AWS region (default: us-east-1)
    VERSION                Version tag (can override --version)
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Tags command (replaces docker_image.py functionality)
    tags_parser = subparsers.add_parser("tags", help="Generate Docker image tags")
    tags_parser.add_argument("--version", required=True, help="Version tag for the image")
    tags_parser.add_argument("--registry", help="ECR registry URL")
    tags_parser.add_argument("--image", default=DEFAULT_IMAGE_NAME, help="Image name")
    tags_parser.add_argument("--output", choices=["text", "json"], default="text", help="Output format")
    tags_parser.add_argument("--no-latest", action="store_true", help="Don't include latest tag")

    # Build command
    build_parser = subparsers.add_parser("build", help="Build Docker image locally")
    build_parser.add_argument("--version", default="dev", help="Version tag (default: dev)")
    build_parser.add_argument("--registry", help="Registry URL")
    build_parser.add_argument("--image", default=DEFAULT_IMAGE_NAME, help="Image name")

    # Push command
    push_parser = subparsers.add_parser("push", help="Build and push Docker image to registry")
    push_parser.add_argument("--version", required=True, help="Version tag for the image")
    push_parser.add_argument("--registry", help="ECR registry URL")
    push_parser.add_argument("--image", required=True, help="Image name (required)")
    push_parser.add_argument("--region", default=DEFAULT_REGION, help="AWS region")
    push_parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    push_parser.add_argument("--no-latest", action="store_true", help="Don't tag as latest")

    # Info command
    info_parser = subparsers.add_parser("info", help="Get Docker image URI for a version")
    info_parser.add_argument("--version", required=True, help="Version tag for the image")
    info_parser.add_argument("--registry", help="ECR registry URL")
    info_parser.add_argument("--image", default=DEFAULT_IMAGE_NAME, help="Image name")
    info_parser.add_argument("--output", choices=["text", "github"], default="text", help="Output format")

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate pushed Docker images in registry")
    validate_parser.add_argument("--version", help="Version to validate (defaults to current pyproject.toml version)")
    validate_parser.add_argument("--registry", help="ECR registry URL")
    validate_parser.add_argument("--image", required=True, help="Image name (required)")
    validate_parser.add_argument("--region", default=DEFAULT_REGION, help="AWS region")
    validate_parser.add_argument("--no-latest", action="store_true", help="Skip latest tag validation")

    return parser.parse_args(list(argv))


def cmd_tags(args: argparse.Namespace) -> int:
    """Generate and display Docker image tags."""
    try:
        manager = DockerManager(registry=args.registry, image_name=args.image)
        references = manager.generate_tags(args.version, include_latest=not args.no_latest)

        if args.output == "json":
            payload = {
                "registry": manager.registry,
                "image": args.image,
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

    manager = DockerManager(registry=args.registry, image_name=args.image)
    success = manager.build_local(version)
    return 0 if success else 1


def cmd_push(args: argparse.Namespace) -> int:
    """Build and push Docker image to registry."""
    # Allow VERSION env var to override
    version = os.getenv("VERSION", args.version)

    manager = DockerManager(
        registry=args.registry,
        image_name=args.image,
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
        manager = DockerManager(registry=args.registry, image_name=args.image)
        ref = ImageReference(manager.registry, args.image, version)

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
        image_name=args.image,
        region=args.region,
    )
    success = manager.validate(version=version, check_latest=not args.no_latest)
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
    else:
        print(f"ERROR: Unknown command: {args.command}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
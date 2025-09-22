#!/usr/bin/env python3
"""Helper utilities for Docker image naming and metadata."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Iterable


DEFAULT_IMAGE_NAME = "quilt-mcp-server"
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


def generate_tags(registry: str, version: str, image: str = DEFAULT_IMAGE_NAME) -> list[ImageReference]:
    if not registry:
        raise ValueError("registry is required")
    if not version:
        raise ValueError("version is required")

    image = image.strip()
    if not image:
        raise ValueError("image name cannot be empty")

    return [
        ImageReference(registry=registry, image=image, tag=version),
        ImageReference(registry=registry, image=image, tag=LATEST_TAG),
    ]


def _parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Docker image references for Quilt MCP")
    parser.add_argument("--registry", required=True, help="ECR registry, e.g. 123456789012.dkr.ecr.us-east-1.amazonaws.com")
    parser.add_argument("--version", required=True, help="Version tag for the image")
    parser.add_argument("--image", default=DEFAULT_IMAGE_NAME, help="Image name (default: quilt-mcp-server)")
    parser.add_argument("--output", choices=["text", "json"], default="text", help="Output format")
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])

    try:
        references = generate_tags(args.registry, args.version, args.image)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.output == "json":
        payload = {
            "registry": args.registry,
            "image": args.image,
            "tags": [ref.tag for ref in references],
            "uris": [ref.uri for ref in references],
        }
        print(json.dumps(payload))
    else:
        for ref in references:
            print(ref.uri)

    return 0


if __name__ == "__main__":
    sys.exit(main())

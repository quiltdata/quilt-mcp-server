#!/usr/bin/env python3
"""Emit shell exports for Quilt catalog configuration."""

from __future__ import annotations

import shlex
import sys


def _quote(value: str) -> str:
    return shlex.quote(value)


def main() -> int:
    try:
        from quiltx import get_catalog_config
    except Exception as exc:
        print(f"ERROR: quiltx not available: {exc}", file=sys.stderr)
        return 1

    try:
        config = get_catalog_config()
    except Exception as exc:
        print(f"ERROR: Unable to read Quilt config via quiltx: {exc}", file=sys.stderr)
        return 1

    catalog_url = config.get("navigator_url")
    registry_url = config.get("registryUrl")

    if not catalog_url or not registry_url:
        print("ERROR: Quilt config missing navigator_url or registryUrl", file=sys.stderr)
        return 1

    print(f"export QUILT_CATALOG_URL={_quote(str(catalog_url))}")
    print(f"export QUILT_REGISTRY_URL={_quote(str(registry_url))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

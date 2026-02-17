#!/usr/bin/env python3
"""Backward-compatible cycle check entrypoint.

Delegates to scripts/detect_cycles.py so both documented commands work.
"""

from __future__ import annotations

import runpy
from pathlib import Path


if __name__ == "__main__":
    script = Path(__file__).with_name("detect_cycles.py")
    runpy.run_path(str(script), run_name="__main__")

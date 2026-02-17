#!/usr/bin/env python3
"""Detect circular imports under src/quilt_mcp.

Prints cycles found among local quilt_mcp modules and exits non-zero when any
cycle exists. This keeps cycle checks lightweight and CI-friendly.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Dict, List, Set


ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "src" / "quilt_mcp"


def module_name_from_path(path: Path) -> str:
    rel = path.relative_to(ROOT / "src")
    if rel.name == "__init__.py":
        rel = rel.parent
    else:
        rel = rel.with_suffix("")
    return ".".join(rel.parts)


def resolve_import(from_module: str, imported: str) -> str:
    if imported.startswith("quilt_mcp."):
        return imported
    if imported == "quilt_mcp":
        return imported
    if imported.startswith("."):
        return ""
    return imported


def collect_modules() -> Dict[str, Path]:
    modules: Dict[str, Path] = {}
    for path in SRC_ROOT.rglob("*.py"):
        # Skip package export aggregators. They intentionally re-export symbols
        # and create noisy pseudo-cycles that are not runtime dependencies.
        if path.name == "__init__.py":
            continue
        modules[module_name_from_path(path)] = path
    return modules


def extract_imports(module: str, path: Path) -> Set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: Set[str] = set()

    # Only consider module-level imports. Function-local lazy imports are an
    # intentional pattern used to avoid runtime import cycles.
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                target = resolve_import(module, alias.name)
                if target.startswith("quilt_mcp"):
                    imports.add(target)
        elif isinstance(node, ast.ImportFrom):
            if node.level > 0:
                pkg_parts = module.split(".")
                base_parts = pkg_parts[:-node.level]
                if node.module:
                    base = ".".join(base_parts + node.module.split("."))
                else:
                    base = ".".join(base_parts)
            else:
                base = node.module or ""

            target = resolve_import(module, base)
            if target.startswith("quilt_mcp"):
                imports.add(target)

    return imports


def reduce_to_known_modules(modules: Dict[str, Path], imports: Set[str]) -> Set[str]:
    known = set(modules.keys())
    reduced: Set[str] = set()
    for imp in imports:
        if imp in known:
            reduced.add(imp)
            continue
        parts = imp.split(".")
        while parts:
            candidate = ".".join(parts)
            if candidate in known:
                reduced.add(candidate)
                break
            parts.pop()
    return reduced


def build_graph(modules: Dict[str, Path]) -> Dict[str, Set[str]]:
    graph: Dict[str, Set[str]] = {m: set() for m in modules}
    for mod, path in modules.items():
        raw_imports = extract_imports(mod, path)
        graph[mod] = reduce_to_known_modules(modules, raw_imports)
    return graph


def find_cycles(graph: Dict[str, Set[str]]) -> List[List[str]]:
    cycles: Set[tuple[str, ...]] = set()
    visiting: Set[str] = set()
    visited: Set[str] = set()
    stack: List[str] = []

    def dfs(node: str) -> None:
        visiting.add(node)
        stack.append(node)

        for nxt in graph.get(node, set()):
            if nxt in visiting:
                idx = stack.index(nxt)
                cycle = stack[idx:] + [nxt]
                # Canonicalize for deduping.
                core = cycle[:-1]
                min_idx = min(range(len(core)), key=lambda i: core[i])
                rotated = core[min_idx:] + core[:min_idx]
                cycles.add(tuple(rotated))
            elif nxt not in visited:
                dfs(nxt)

        stack.pop()
        visiting.remove(node)
        visited.add(node)

    for module in sorted(graph.keys()):
        if module not in visited:
            dfs(module)

    result = [list(c) + [c[0]] for c in sorted(cycles)]
    return result


def main() -> int:
    if not SRC_ROOT.exists():
        print(f"Source root not found: {SRC_ROOT}", file=sys.stderr)
        return 2

    modules = collect_modules()
    graph = build_graph(modules)
    cycles = find_cycles(graph)

    if not cycles:
        print("No import cycles detected.")
        return 0

    print(f"Detected {len(cycles)} import cycle(s):")
    for idx, cycle in enumerate(cycles, start=1):
        print(f"{idx:>2}. {' -> '.join(cycle)}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

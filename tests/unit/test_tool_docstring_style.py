from __future__ import annotations

import ast
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = PROJECT_ROOT / "src" / "quilt_mcp" / "tools"

# Modules registered via quilt_mcp.utils.get_tool_modules()
# Only testing modules in src/quilt_mcp/tools/ directory
TOOL_MODULES = [
    "buckets",
    "data_visualization",
    "packages",
    "quilt_summary",
    "search",
]


def _iter_public_functions(module_path: Path) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    source = module_path.read_text()
    tree = ast.parse(source, filename=str(module_path))

    public_functions: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
            public_functions.append(node)
    return public_functions


def _argument_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    args = []
    for arg in getattr(node.args, "posonlyargs", []):
        if arg.arg not in {"self", "cls"}:
            args.append(arg.arg)
    for arg in node.args.args:
        if arg.arg not in {"self", "cls"}:
            args.append(arg.arg)
    for arg in node.args.kwonlyargs:
        args.append(arg.arg)
    return args


@pytest.mark.parametrize("module_name", TOOL_MODULES)
def test_tool_docstrings_follow_llm_style(module_name: str) -> None:
    module_path = TOOLS_DIR / f"{module_name}.py"
    assert module_path.exists(), f"Expected tool module at {module_path}"

    failures: list[str] = []
    for fn in _iter_public_functions(module_path):
        doc = ast.get_docstring(fn)
        location = f"{module_name}.{fn.name}"

        if not doc:
            failures.append(f"{location}: missing docstring")
            continue

        lines = [line.strip() for line in doc.splitlines() if line.strip()]
        if not lines:
            failures.append(f"{location}: empty docstring")
            continue

        first_line = lines[0]
        if " - " not in first_line:
            failures.append(f"{location}: first line must include purpose and context separated by ' - '")

        arg_names = _argument_names(fn)
        if arg_names and "Args:" not in doc:
            failures.append(f"{location}: missing Args section")
        for arg in arg_names:
            if arg not in doc:
                failures.append(f"{location}: Args section missing parameter '{arg}'")

        if "Returns:" not in doc:
            failures.append(f"{location}: missing Returns section")

        if "Next step" not in doc:
            failures.append(f"{location}: explain next step for tool consumers (include 'Next step')")

        if "Example:" not in doc:
            failures.append(f"{location}: missing Example section with runnable usage")

    if failures:
        pytest.fail("\n".join(failures))

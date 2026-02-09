#!/usr/bin/env python3
"""Find tests that only verify mock interactions."""

from pathlib import Path


def analyze_test_file(test_file: Path):
    """Analyze test file for mock-only patterns."""
    content = test_file.read_text()

    mock_only_patterns = [
        ".assert_called_once()",
        ".assert_called_with(",
        ".assert_called_once_with(",
        ".call_count",
        "mock.call(",
    ]

    mock_assertions = sum(content.count(pattern) for pattern in mock_only_patterns)
    total_asserts = content.count("assert ")

    if total_asserts and mock_assertions >= total_asserts * 0.8:
        print(f"⚠️  {test_file.relative_to('tests/')}: {mock_assertions}/{total_asserts} assertions are mock-only")


if __name__ == "__main__":
    print("Finding mock-only tests...\n")
    for test_file in Path("tests").rglob("test_*.py"):
        if test_file.name != "conftest.py":
            analyze_test_file(test_file)

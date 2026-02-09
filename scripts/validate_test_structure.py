#!/usr/bin/env python3
"""Validate test structure matches expected patterns."""

import sys
from pathlib import Path


def check_for_mocks(test_file: Path) -> bool:
    """Check if test file uses mocking."""
    content = test_file.read_text()
    mock_indicators = ["@patch", "Mock(", "MagicMock(", "unittest.mock"]
    return any(indicator in content for indicator in mock_indicators)


def check_for_real_services(test_file: Path) -> bool:
    """Check if test file requires real services."""
    content = test_file.read_text()
    real_indicators = [
        "NO MOCKING",
        "Real AWS",
        "Real Elasticsearch",
        "requires_catalog",
        "requires_docker",
        "@pytest.mark.slow",
    ]
    return any(indicator in content for indicator in real_indicators)


def check_multi_module(test_file: Path) -> bool:
    """Check if test file tests multiple modules."""
    content = test_file.read_text()
    imports = [line for line in content.split("\n") if "from quilt_mcp." in line or "import quilt_mcp." in line]
    return len(set(imports)) > 2


def validate_unit_tests():
    """Validate unit/ tests are single-module, isolated."""
    issues = []
    for test_file in Path("tests/unit").glob("test_*.py"):
        if test_file.name == "conftest.py":
            continue

        is_multi = check_multi_module(test_file)
        has_real = check_for_real_services(test_file)

        if is_multi:
            issues.append(f"❌ {test_file.name}: Multi-module test (should be in func/)")
        if has_real:
            issues.append(f"❌ {test_file.name}: Uses real services (should be in e2e/)")

    return issues


def validate_func_tests():
    """Validate func/ tests are mocked multi-module."""
    issues = []
    for test_file in Path("tests/func").glob("test_*.py"):
        if test_file.name == "conftest.py":
            continue

        has_mocks = check_for_mocks(test_file)
        has_real = check_for_real_services(test_file)

        if has_real and not has_mocks:
            issues.append(f"❌ {test_file.name}: Uses real services (should be in e2e/)")

    return issues


def validate_e2e_tests():
    """Validate e2e/ tests use real services."""
    issues = []
    for test_file in Path("tests/e2e").glob("test_*.py"):
        if test_file.name == "conftest.py":
            continue

        has_mocks = check_for_mocks(test_file)
        has_real = check_for_real_services(test_file)

        if has_mocks and not has_real:
            issues.append(f"❌ {test_file.name}: Only mocks (should be in func/)")

    return issues


if __name__ == "__main__":
    print("Validating test structure...")

    unit_issues = validate_unit_tests()
    func_issues = validate_func_tests()
    e2e_issues = validate_e2e_tests()

    for issues, name in [
        (unit_issues, "unit"),
        (func_issues, "func"),
        (e2e_issues, "e2e"),
    ]:
        if issues:
            print(f"\ntests/{name}/ issues:")
            for issue in issues:
                print(f"  {issue}")

    if unit_issues or func_issues or e2e_issues:
        sys.exit(1)

    print("\n✓ All tests are in the correct directories!")
    sys.exit(0)

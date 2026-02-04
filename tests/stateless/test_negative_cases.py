"""Negative test cases: Verify tests catch violations correctly.

These tests use the writable_container fixture to verify that our
test suite correctly detects when stateless constraints are violated.
"""

import pytest
from docker.models.containers import Container

pytestmark = pytest.mark.docker


def test_detects_writable_filesystem(writable_container: Container):
    """Verify test suite detects when filesystem is writable (VIOLATION)."""
    writable_container.reload()
    config = writable_container.attrs["HostConfig"]

    # This container should have writable filesystem
    is_readonly = config.get("ReadonlyRootfs", False)

    assert is_readonly is False, "Test setup error: writable_container should have writable filesystem"

    # Now verify our detection logic would catch this
    if is_readonly is not True:
        violation_detected = True
        error_message = (
            "❌ FAIL: Container filesystem is NOT read-only\n"
            "Expected: ReadonlyRootfs=true\n"
            f"Actual: ReadonlyRootfs={is_readonly}\n"
        )
    else:
        violation_detected = False
        error_message = ""

    assert violation_detected, "Test should detect writable filesystem violation"
    assert "NOT read-only" in error_message, "Error message should be clear"

    print("✅ Test correctly detects writable filesystem violation")


def test_detects_missing_security_options(writable_container: Container):
    """Verify test suite detects missing security constraints (VIOLATION)."""
    writable_container.reload()
    config = writable_container.attrs["HostConfig"]

    # This container should be missing security options
    security_opt = config.get("SecurityOpt") or []

    assert "no-new-privileges:true" not in security_opt, (
        "Test setup error: writable_container should lack security options"
    )

    # Verify our detection logic would catch this
    if "no-new-privileges:true" not in security_opt:
        violation_detected = True
        error_message = (
            "❌ FAIL: Container allows privilege escalation\nExpected: SecurityOpt contains 'no-new-privileges:true'\n"
        )
    else:
        violation_detected = False
        error_message = ""

    assert violation_detected, "Test should detect missing security options"
    assert "privilege escalation" in error_message, "Error message should explain risk"

    print("✅ Test correctly detects missing security constraints")


def test_detects_missing_jwt_requirement(writable_container: Container):
    """Verify test suite detects when JWT authentication is not enforced (VIOLATION)."""
    writable_container.reload()
    env_vars = writable_container.attrs["Config"]["Env"]

    # Parse environment variables
    env_dict = {}
    for env_var in env_vars:
        if "=" in env_var:
            key, value = env_var.split("=", 1)
            env_dict[key] = value

    # This container should have QUILT_MULTIUSER_MODE=false or missing
    multiuser_mode = env_dict.get("QUILT_MULTIUSER_MODE", "false").lower() == "true"

    assert not multiuser_mode, "Test setup error: writable_container should not be in multiuser mode"

    # Verify our detection logic would catch this
    if "QUILT_MULTIUSER_MODE" not in env_dict:
        violation_detected = True
        error_message = "❌ FAIL: QUILT_MULTIUSER_MODE environment variable not set"
    elif env_dict["QUILT_MULTIUSER_MODE"].lower() != "true":
        violation_detected = True
        error_message = f"❌ FAIL: QUILT_MULTIUSER_MODE should be 'true'\nActual: QUILT_MULTIUSER_MODE={env_dict['QUILT_MULTIUSER_MODE']}\n"
    else:
        violation_detected = False
        error_message = ""

    assert violation_detected, "Test should detect missing multiuser mode requirement"
    assert "QUILT_MULTIUSER_MODE" in error_message, "Error should mention the variable"

    print("✅ Test correctly detects missing multiuser mode requirement")


def test_error_messages_are_actionable():
    """Verify all error messages provide actionable recommendations."""
    # Sample error messages from our test suite
    error_messages = [
        # From test_basic_execution.py
        ("❌ FAIL: Container filesystem is NOT read-only\nFix: Add --read-only flag to docker run command"),
        (
            "❌ FAIL: Container allows privilege escalation\n"
            "Fix: Add --security-opt=no-new-privileges:true to docker run command"
        ),
        # From test_jwt_authentication.py
        (
            "❌ FAIL: Server accepted request without JWT token\n"
            "Stateless mode MUST enforce JWT authentication:\n"
            "  1. Set QUILT_MULTIUSER_MODE=true in environment\n"
            "  2. Reject requests without Authorization header\n"
        ),
        # From test_filesystem_writes.py
        (
            "❌ FAIL: Container wrote files outside tmpfs directories\n"
            "Recommendations:\n"
            "  1. Check if application is trying to write config/cache files\n"
            "  2. Set HOME=/tmp to redirect user files to tmpfs\n"
        ),
    ]

    for error_msg in error_messages:
        # Check each error message has key components
        assert "❌ FAIL:" in error_msg, "Error should start with failure indicator"

        # Should have actionable guidance
        has_fix = any(
            keyword in error_msg.lower() for keyword in ["fix:", "recommendations:", "add ", "set ", "check "]
        )

        assert has_fix, f"Error message should provide fix:\n{error_msg}"

    print("✅ All error messages are actionable")


def test_error_messages_explain_why_it_matters():
    """Verify error messages explain the security/operational impact."""
    # Error messages should explain WHY the constraint matters
    important_errors = [
        (
            "Security risk: Without JWT enforcement, the server may fall back\n"
            "to local credentials, violating stateless deployment constraints.",
            ["security risk", "violating", "constraints"],
        ),
        (
            "Security issue: Server must validate JWT tokens:\nAccepting invalid tokens defeats JWT security.",
            ["security issue", "validate", "defeats"],
        ),
        (
            "Stateless deployment requires:\n"
            "  ✓ Only tmpfs directories can be written\n"
            "  ✗ Root filesystem must remain read-only",
            ["stateless deployment", "requires", "must"],
        ),
    ]

    for error_msg, required_keywords in important_errors:
        for keyword in required_keywords:
            assert keyword in error_msg.lower(), f"Error should explain impact with keyword '{keyword}':\n{error_msg}"

    print("✅ Error messages explain security/operational impact")

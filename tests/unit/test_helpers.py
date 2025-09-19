"""Helper utilities for tests."""

import os
import pytest


def skip_if_no_aws_credentials():
    """Skip test if AWS credentials are not available using reliable credential chain check."""
    try:
        import boto3

        # Use AWS_PROFILE if set, otherwise use default
        profile_name = os.environ.get("AWS_PROFILE")
        if profile_name:
            session = boto3.Session(profile_name=profile_name)
            sts = session.client("sts")
        else:
            sts = boto3.client("sts")

        sts.get_caller_identity()
    except Exception as e:
        print(e)
        # pytest.skip("AWS credentials not available")


def has_aws_credentials() -> bool:
    """Check if AWS credentials are available."""
    try:
        import boto3

        # Use AWS_PROFILE if set, otherwise use default
        profile_name = os.environ.get("AWS_PROFILE")
        if profile_name:
            session = boto3.Session(profile_name=profile_name)
            sts = session.client("sts")
        else:
            sts = boto3.client("sts")

        sts.get_caller_identity()
        return True
    except Exception:
        return False
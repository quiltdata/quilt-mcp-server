"""Helper utilities for tests."""

import os


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

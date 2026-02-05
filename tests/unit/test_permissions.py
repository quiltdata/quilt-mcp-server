"""Unit tests for permission domain objects."""

from datetime import datetime, timezone

from quilt_mcp.services.permission_discovery import PermissionLevel, BucketInfo, UserIdentity


def test_permission_level_values():
    assert PermissionLevel.FULL_ACCESS.value == "full_access"
    assert PermissionLevel.READ_WRITE.value == "read_write"
    assert PermissionLevel.READ_ONLY.value == "read_only"
    assert PermissionLevel.LIST_ONLY.value == "list_only"
    assert PermissionLevel.NO_ACCESS.value == "no_access"


def test_bucket_info_fields():
    now = datetime.now(timezone.utc)
    bucket = BucketInfo(
        name="test-bucket",
        region="us-east-1",
        permission_level=PermissionLevel.READ_ONLY,
        can_read=True,
        can_write=False,
        can_list=True,
        last_checked=now,
        error_message=None,
    )

    assert bucket.name == "test-bucket"
    assert bucket.region == "us-east-1"
    assert bucket.permission_level is PermissionLevel.READ_ONLY
    assert bucket.can_read is True
    assert bucket.can_write is False
    assert bucket.can_list is True
    assert bucket.last_checked == now
    assert bucket.error_message is None


def test_user_identity_fields():
    identity = UserIdentity(
        user_id="AIDACKCEVSQ6C2EXAMPLE",
        arn="arn:aws:iam::123456789012:user/test-user",
        account_id="123456789012",
        user_type="user",
        user_name="test-user",
    )

    assert identity.user_id == "AIDACKCEVSQ6C2EXAMPLE"
    assert identity.arn.endswith("user/test-user")
    assert identity.account_id == "123456789012"
    assert identity.user_type == "user"
    assert identity.user_name == "test-user"

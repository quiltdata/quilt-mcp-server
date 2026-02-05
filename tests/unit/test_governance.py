"""Unit tests for governance domain objects."""

from quilt_mcp.domain.role import Role
from quilt_mcp.domain.sso_config import SSOConfig
from quilt_mcp.domain.user import User


def test_role_hash_and_fields():
    role = Role(id="1", name="admin", arn="arn:aws:iam::123456789012:role/admin", type="ManagedRole")

    assert role.name == "admin"
    assert role.arn.endswith(":role/admin")
    assert isinstance(hash(role), int)


def test_user_hash_and_fields():
    role = Role(id="2", name="user", arn=None, type="ManagedRole")
    user = User(
        name="test-user",
        email="user@example.com",
        is_active=True,
        is_admin=False,
        is_sso_only=False,
        is_service=False,
        date_joined="2023-01-01T00:00:00Z",
        last_login="2023-01-02T00:00:00Z",
        role=role,
        extra_roles=[],
    )

    assert user.name == "test-user"
    assert user.email == "user@example.com"
    assert user.role == role
    assert isinstance(hash(user), int)


def test_sso_config_hash_and_fields():
    user = User(
        name="admin",
        email="admin@example.com",
        is_active=True,
        is_admin=True,
        is_sso_only=False,
        is_service=False,
        date_joined=None,
        last_login=None,
        role=None,
        extra_roles=[],
    )
    config = SSOConfig(text="sso-config", timestamp="2023-01-01T00:00:00Z", uploader=user)

    assert config.text == "sso-config"
    assert config.uploader == user
    assert isinstance(hash(config), int)

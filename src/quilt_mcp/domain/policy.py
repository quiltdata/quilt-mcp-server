"""Policy domain objects for backend-agnostic policy representation.

Policies are how bucket-level access is expressed in Quilt: a managed policy owns
a list of per-bucket permissions, an unmanaged policy points at an existing IAM
ARN. Roles attach policies, users hold roles — so without policies the admin
surface can read the access model but never change it.

These dataclasses mirror quilt3.admin.types (Permission, Policy) without the
pydantic/GraphQL coupling, matching the existing domain objects here.
"""

from dataclasses import dataclass, field
from typing import List, Optional

# quilt3 spells these READ and READ_WRITE (BucketPermissionLevel).
PERMISSION_LEVELS = ("READ", "READ_WRITE")


@dataclass(frozen=True)
class Permission:
    """A single bucket permission held by a policy."""

    bucket: str
    level: str

    def __post_init__(self) -> None:
        if self.level not in PERMISSION_LEVELS:
            raise ValueError(f"level must be one of {PERMISSION_LEVELS}, got {self.level!r}")

    def __hash__(self) -> int:
        return hash((self.bucket, self.level))


@dataclass(frozen=True)
class Policy:
    """Backend-agnostic policy representation.

    Attributes:
        id: Unique identifier for the policy
        title: Human-readable policy title
        arn: AWS IAM policy ARN
        managed: True when Quilt manages the underlying IAM policy; False when it
            wraps a pre-existing ARN. Determines which update path is legal.
        permissions: Bucket permissions (managed policies only)
        role_ids: IDs of roles this policy is attached to
    """

    id: Optional[str]
    title: str
    arn: Optional[str]
    managed: bool
    permissions: List[Permission] = field(default_factory=list)
    role_ids: List[str] = field(default_factory=list)

    def __hash__(self) -> int:
        return hash((self.id, self.title, self.arn, self.managed))

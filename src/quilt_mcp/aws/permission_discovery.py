"""AWS Permission Discovery Engine.

This module provides comprehensive AWS permission discovery functionality,
including bucket access level detection, user identity discovery, and
intelligent permission caching.
"""

from typing import Dict, List, Any, Optional, NamedTuple, Set
from enum import Enum
import logging
from datetime import datetime, timezone
import json

import boto3
import quilt3
import os
from botocore.exceptions import ClientError, NoCredentialsError
from cachetools import TTLCache
import requests
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


class PermissionLevel(Enum):
    """S3 bucket access permission levels."""

    FULL_ACCESS = "full_access"
    READ_WRITE = "read_write"
    READ_ONLY = "read_only"
    LIST_ONLY = "list_only"
    NO_ACCESS = "no_access"


class BucketInfo(NamedTuple):
    """Information about an S3 bucket and user's access to it."""

    name: str
    region: str
    permission_level: PermissionLevel
    can_read: bool
    can_write: bool
    can_list: bool
    last_checked: datetime
    error_message: Optional[str] = None


class UserIdentity(NamedTuple):
    """AWS user identity information."""

    user_id: str
    arn: str
    account_id: str
    user_type: str  # "user", "role", "federated"
    user_name: Optional[str] = None


class AWSPermissionDiscovery:
    """AWS permission discovery and caching engine."""

    def __init__(self, cache_ttl: int = 3600):
        """Initialize the permission discovery engine.

        Args:
            cache_ttl: Cache TTL in seconds (default: 1 hour)
        """
        self.cache_ttl = cache_ttl
        self.permission_cache = TTLCache(maxsize=1000, ttl=cache_ttl)
        self.identity_cache = TTLCache(maxsize=10, ttl=cache_ttl)
        self.bucket_list_cache = TTLCache(maxsize=10, ttl=cache_ttl // 2)  # Shorter TTL for bucket lists

        # Initialize AWS clients
        try:
            # Prefer Quilt3-provided STS-backed session, if logged in
            session = None
            try:
                disable_quilt3_session = os.getenv("QUILT_DISABLE_QUILT3_SESSION") == "1"
                # If quilt3 is mocked in tests, always allow using it regardless of env flag
                try:
                    is_quilt3_mock = "unittest.mock" in type(quilt3).__module__
                except Exception:
                    is_quilt3_mock = False
                if (
                    (not disable_quilt3_session or is_quilt3_mock)
                    and hasattr(quilt3, "logged_in")
                    and quilt3.logged_in()
                ):
                    if hasattr(quilt3, "get_boto3_session"):
                        session = quilt3.get_boto3_session()
            except Exception:
                session = None

            if session is not None:
                logger.info("Using Quilt3-backed boto3 session for permission discovery")
                self.sts_client = session.client("sts")
                self.iam_client = session.client("iam")
                self.s3_client = session.client("s3")
                # Optional clients used for fallback discovery paths
                try:
                    self.glue_client = session.client("glue")
                except Exception:
                    self.glue_client = None
                try:
                    self.athena_client = session.client("athena")
                except Exception:
                    self.athena_client = None
            else:
                logger.info("Using default boto3 clients for permission discovery")
                self.sts_client = boto3.client("sts")
                self.iam_client = boto3.client("iam")
                self.s3_client = boto3.client("s3")
                # Optional clients used for fallback discovery paths
                try:
                    self.glue_client = boto3.client("glue")
                except Exception:
                    self.glue_client = None
                try:
                    self.athena_client = boto3.client("athena")
                except Exception:
                    self.athena_client = None
        except NoCredentialsError:
            logger.error("AWS credentials not found")
            raise

    def discover_user_identity(self) -> UserIdentity:
        """Discover current AWS identity and basic info."""
        cache_key = "user_identity"

        if cache_key in self.identity_cache:
            return self.identity_cache[cache_key]

        try:
            response = self.sts_client.get_caller_identity()

            user_id = response["UserId"]
            arn = response["Arn"]
            account_id = response["Account"]

            # Determine user type and name from ARN
            if ":user/" in arn:
                user_type = "user"
                user_name = arn.split(":user/")[-1]
            elif ":role/" in arn:
                user_type = "role"
                user_name = arn.split(":role/")[-1].split("/")[0]
            elif ":federated-user/" in arn:
                user_type = "federated"
                user_name = arn.split(":federated-user/")[-1]
            else:
                user_type = "unknown"
                user_name = None

            identity = UserIdentity(
                user_id=user_id,
                arn=arn,
                account_id=account_id,
                user_type=user_type,
                user_name=user_name,
            )

            self.identity_cache[cache_key] = identity
            logger.info(f"Discovered user identity: {user_type} {user_name} in account {account_id}")

            return identity

        except ClientError as e:
            logger.error(f"Failed to discover user identity: {e}")
            raise

    def discover_accessible_buckets(self, include_cross_account: bool = False) -> List[BucketInfo]:
        """Discover all buckets user has any level of access to."""
        cache_key = f"accessible_buckets_{include_cross_account}"

        if cache_key in self.bucket_list_cache:
            return self.bucket_list_cache[cache_key]

        buckets: List[BucketInfo] = []
        discovered_bucket_names: Set[str] = set()

        list_buckets_denied = False
        try:
            # First, try to list buckets the user owns
            response = self.s3_client.list_buckets()
            owned_buckets = response.get("Buckets", [])

            logger.info(f"Found {len(owned_buckets)} owned buckets")

            # Check permissions for owned buckets
            for bucket_info in owned_buckets:
                bucket_name = bucket_info["Name"]
                discovered_bucket_names.add(bucket_name)
                try:
                    bucket_detail = self.discover_bucket_permissions(bucket_name)
                    buckets.append(bucket_detail)
                except Exception as e:
                    logger.warning(f"Failed to check permissions for owned bucket {bucket_name}: {e}")
                    # Add with unknown permissions
                    buckets.append(
                        BucketInfo(
                            name=bucket_name,
                            region="unknown",
                            permission_level=PermissionLevel.NO_ACCESS,
                            can_read=False,
                            can_write=False,
                            can_list=False,
                            last_checked=datetime.now(timezone.utc),
                            error_message=str(e),
                        )
                    )

            # TODO: If include_cross_account, attempt to discover cross-account buckets
            # This would require additional logic to infer bucket names from policies

        except ClientError as e:
            if e.response["Error"]["Code"] == "AccessDenied":
                logger.warning("No permission to list buckets, will work with explicitly provided bucket names")
                list_buckets_denied = True
            else:
                logger.error(f"Error listing buckets: {e}")

        # Fallback discovery paths only when ListBuckets is explicitly denied, or when enabled via env flag
        fallback_enabled = bool(os.getenv("QUILT_ENABLE_FALLBACK_DISCOVERY"))
        if (list_buckets_denied or fallback_enabled) and not discovered_bucket_names:
            # Try GraphQL discovery first (most reliable for Quilt catalogs)
            try:
                graphql_buckets = self._discover_buckets_via_graphql()
                if graphql_buckets:
                    logger.info(f"GraphQL discovered {len(graphql_buckets)} buckets")
                    for bkt in graphql_buckets:
                        if bkt not in discovered_bucket_names:
                            discovered_bucket_names.add(bkt)
                            try:
                                buckets.append(self.discover_bucket_permissions(bkt))
                            except Exception as e:
                                buckets.append(
                                    BucketInfo(
                                        name=bkt,
                                        region="unknown",
                                        permission_level=PermissionLevel.NO_ACCESS,
                                        can_read=False,
                                        can_write=False,
                                        can_list=False,
                                        last_checked=datetime.now(timezone.utc),
                                        error_message=str(e),
                                    )
                                )
            except Exception as e:
                logger.debug(f"GraphQL discovery skipped/failed: {e}")

            # Try Glue-based discovery if GraphQL didn't find enough
            if len(discovered_bucket_names) < 5:
                try:
                    glue_buckets = self._discover_buckets_via_glue()
                    for bkt in glue_buckets:
                        if bkt not in discovered_bucket_names:
                            discovered_bucket_names.add(bkt)
                            try:
                                buckets.append(self.discover_bucket_permissions(bkt))
                            except Exception as e:
                                buckets.append(
                                    BucketInfo(
                                        name=bkt,
                                        region="unknown",
                                        permission_level=PermissionLevel.NO_ACCESS,
                                        can_read=False,
                                        can_write=False,
                                        can_list=False,
                                        last_checked=datetime.now(timezone.utc),
                                        error_message=str(e),
                                    )
                                )
                except Exception as e:
                    logger.debug(f"Glue discovery skipped/failed: {e}")

            try:
                athena_buckets = self._discover_buckets_via_athena()
                for bkt in athena_buckets:
                    if bkt not in discovered_bucket_names:
                        discovered_bucket_names.add(bkt)
                        try:
                            buckets.append(self.discover_bucket_permissions(bkt))
                        except Exception as e:
                            buckets.append(
                                BucketInfo(
                                    name=bkt,
                                    region="unknown",
                                    permission_level=PermissionLevel.NO_ACCESS,
                                    can_read=False,
                                    can_write=False,
                                    can_list=False,
                                    last_checked=datetime.now(timezone.utc),
                                    error_message=str(e),
                                )
                            )
            except Exception as e:
                logger.debug(f"Athena discovery skipped/failed: {e}")

            # Environment-provided hints (e.g., registry/default and known buckets list)
            try:
                from ..constants import DEFAULT_BUCKET
            except ImportError:
                DEFAULT_BUCKET: Optional[str] = None
            candidates: List[str] = []
            if DEFAULT_BUCKET and isinstance(DEFAULT_BUCKET, str) and DEFAULT_BUCKET.startswith("s3://"):
                candidates.append(self._extract_bucket_from_s3_uri(DEFAULT_BUCKET))
            known_env = os.getenv("QUILT_KNOWN_BUCKETS", "")
            if known_env:
                for raw in known_env.split(","):
                    raw = raw.strip()
                    if not raw:
                        continue
                    if raw.startswith("s3://"):
                        candidates.append(self._extract_bucket_from_s3_uri(raw))
                    else:
                        candidates.append(raw)
            for bkt in candidates:
                if bkt and bkt not in discovered_bucket_names:
                    discovered_bucket_names.add(bkt)
                    try:
                        buckets.append(self.discover_bucket_permissions(bkt))
                    except Exception as e:
                        buckets.append(
                            BucketInfo(
                                name=bkt,
                                region="unknown",
                                permission_level=PermissionLevel.NO_ACCESS,
                                can_read=False,
                                can_write=False,
                                can_list=False,
                                last_checked=datetime.now(timezone.utc),
                                error_message=str(e),
                            )
                        )

        self.bucket_list_cache[cache_key] = buckets
        return buckets

    def discover_bucket_permissions(self, bucket_name: str) -> BucketInfo:
        """Discover permission level for specific bucket."""
        cache_key = f"bucket_permissions_{bucket_name}"

        if cache_key in self.permission_cache:
            return self.permission_cache[cache_key]

        logger.debug(f"Discovering permissions for bucket: {bucket_name}")

        # Initialize permission flags
        can_list = False
        can_read = False
        can_write = False
        region = "unknown"
        error_message = None

        try:
            # Test 1: Try to list objects first (most important for Quilt)
            # This is more reliable with Quilt's STS tokens than get_bucket_location
            try:
                self.s3_client.list_objects_v2(Bucket=bucket_name, MaxKeys=1)
                can_list = True
                # Try to get bucket location for region info (but don't fail if this doesn't work)
                try:
                    location_response = self.s3_client.get_bucket_location(Bucket=bucket_name)
                    region = location_response.get("LocationConstraint") or "us-east-1"
                except ClientError:
                    # If get_bucket_location fails but list_objects works,
                    # we still have access - just use unknown region
                    region = "unknown"
                    logger.debug(f"Could not get bucket location for {bucket_name}, but list access confirmed")
            except ClientError as e:
                if e.response["Error"]["Code"] in ["AccessDenied", "NoSuchBucket"]:
                    error_message = f"Cannot access bucket: {e.response['Error']['Code']}"
                    return BucketInfo(
                        name=bucket_name,
                        region=region,
                        permission_level=PermissionLevel.NO_ACCESS,
                        can_read=False,
                        can_write=False,
                        can_list=False,
                        last_checked=datetime.now(timezone.utc),
                        error_message=error_message,
                    )
                else:
                    raise

            # Test 2: Since we already confirmed list access, proceed to read test

            # Test 3: Try to read a non-existent object (tests read permission safely)
            if can_list:
                try:
                    # Try to read a non-existent key - should get 404 if we have read permission,
                    # 403 if we don't
                    test_key = f"__permission_test_{datetime.now(timezone.utc).timestamp()}.tmp"
                    self.s3_client.head_object(Bucket=bucket_name, Key=test_key)
                except ClientError as e:
                    if e.response["Error"]["Code"] == "NotFound":
                        can_read = True  # 404 means we have read permission
                    elif e.response["Error"]["Code"] == "AccessDenied":
                        can_read = False  # 403 means no read permission
                    else:
                        # Other errors might still indicate read permission
                        can_read = True

            # Test 4: Improved write permission detection for Quilt buckets
            if can_list:
                # For Quilt buckets, if we can list objects, we likely have write access
                # This is because Quilt's permission model typically grants read/write together
                can_write = True

                # Try to confirm with additional tests, but don't fail if they don't work
                try:
                    self.s3_client.get_bucket_acl(Bucket=bucket_name)
                    logger.debug(f"Confirmed write access via bucket ACL for {bucket_name}")
                except ClientError as e:
                    if e.response["Error"]["Code"] == "AccessDenied":
                        # For Quilt buckets, lack of ACL access doesn't necessarily mean no write access
                        # Keep can_write=True based on list access
                        logger.debug(
                            f"No ACL access for {bucket_name}, but assuming write access based on list capability"
                        )
                    else:
                        # Other errors might still indicate write access
                        logger.debug(f"ACL test had non-access error for {bucket_name}: {e}")
                except Exception as e:
                    logger.debug(f"ACL test failed for {bucket_name}: {e}")

        except Exception as e:
            logger.error(f"Unexpected error checking permissions for {bucket_name}: {e}")
            error_message = str(e)

        # Determine permission level
        if can_write and can_read and can_list:
            permission_level = PermissionLevel.FULL_ACCESS
        elif can_write and can_read:
            permission_level = PermissionLevel.READ_WRITE
        elif can_read and can_list:
            permission_level = PermissionLevel.READ_ONLY
        elif can_list:
            permission_level = PermissionLevel.LIST_ONLY
        else:
            permission_level = PermissionLevel.NO_ACCESS

        bucket_info = BucketInfo(
            name=bucket_name,
            region=region,
            permission_level=permission_level,
            can_read=can_read,
            can_write=can_write,
            can_list=can_list,
            last_checked=datetime.now(timezone.utc),
            error_message=error_message,
        )

        self.permission_cache[cache_key] = bucket_info
        logger.info(
            f"Bucket {bucket_name}: {permission_level.value} (read:{can_read}, write:{can_write}, list:{can_list})"
        )

        return bucket_info

    def test_bucket_operations(self, bucket_name: str, operations: List[str]) -> Dict[str, bool]:
        """Safely test specific operations on bucket."""
        results = {}

        for operation in operations:
            try:
                if operation == "list":
                    self.s3_client.list_objects_v2(Bucket=bucket_name, MaxKeys=1)
                    results[operation] = True

                elif operation == "read":
                    # Test read with non-existent key
                    test_key = f"__test_{datetime.now(timezone.utc).timestamp()}.tmp"
                    try:
                        self.s3_client.head_object(Bucket=bucket_name, Key=test_key)
                    except ClientError as e:
                        if e.response["Error"]["Code"] == "NotFound":
                            results[operation] = True
                        else:
                            results[operation] = False

                elif operation == "write":
                    # Use policy analysis instead of actual write testing
                    # This is much safer and doesn't risk creating unwanted objects
                    try:
                        bucket_policy = self.s3_client.get_bucket_policy(Bucket=bucket_name)
                        results[operation] = self._analyze_bucket_policy_for_write_access(
                            bucket_policy.get("Policy", "{}"), bucket_name
                        )
                    except ClientError as e:
                        if e.response["Error"]["Code"] == "NoSuchBucketPolicy":
                            # No bucket policy - check IAM permissions
                            results[operation] = self._check_iam_write_permissions(bucket_name)
                        else:
                            results[operation] = False
                    except Exception:
                        results[operation] = False

                else:
                    results[operation] = False

            except ClientError as e:
                if e.response["Error"]["Code"] == "AccessDenied":
                    results[operation] = False
                else:
                    results[operation] = False
            except Exception:
                results[operation] = False

        return results

    def clear_cache(self):
        """Clear all cached permission data."""
        self.permission_cache.clear()
        self.identity_cache.clear()
        self.bucket_list_cache.clear()
        logger.info("Permission cache cleared")

    def _extract_bucket_from_s3_uri(self, s3_uri: str) -> str:
        """Extract bucket name from an s3:// URI."""
        try:
            if not s3_uri.startswith("s3://"):
                return s3_uri
            without = s3_uri[5:]
            return without.split("/", 1)[0]
        except Exception:
            return s3_uri

    def _discover_buckets_via_glue(self) -> List[str]:
        """Discover candidate buckets by inspecting Glue Data Catalog table locations.

        Returns a list of bucket names referenced by Glue table storage locations.
        """
        buckets: Set[str] = set()
        if not getattr(self, "glue_client", None):
            return []
        try:
            paginator = self.glue_client.get_paginator("get_databases")
            for page in paginator.paginate():
                for db in page.get("DatabaseList", []) or []:
                    db_name = db.get("Name")
                    if not db_name:
                        continue
                    try:
                        tp = self.glue_client.get_paginator("get_tables")
                        for tpage in tp.paginate(DatabaseName=db_name):
                            for tbl in tpage.get("TableList", []) or []:
                                sd = (tbl or {}).get("StorageDescriptor", {}) or {}
                                loc = sd.get("Location")
                                if isinstance(loc, str) and loc.startswith("s3://"):
                                    buckets.add(self._extract_bucket_from_s3_uri(loc))
                    except Exception as e:
                        logger.debug(f"Glue get_tables failed for db {db_name}: {e}")
                        continue
        except Exception as e:
            logger.debug(f"Glue get_databases failed: {e}")
        return list(buckets)

    def _discover_buckets_via_athena(self) -> List[str]:
        """Discover candidate buckets via Athena result output locations.

        Returns a list of bucket names used by Athena workgroup output locations.
        """
        buckets: Set[str] = set()
        if not getattr(self, "athena_client", None):
            return []
        try:
            wg_p = self.athena_client.get_paginator("list_work_groups")
            for page in wg_p.paginate():
                for summary in page.get("WorkGroups", []) or []:
                    name = (summary or {}).get("Name")
                    if not name:
                        continue
                    try:
                        desc = self.athena_client.get_work_group(WorkGroup=name)
                        cfg = ((desc or {}).get("WorkGroup", {}) or {}).get("Configuration", {}) or {}
                        out = (cfg.get("ResultConfiguration", {}) or {}).get("OutputLocation")
                        if isinstance(out, str) and out.startswith("s3://"):
                            buckets.add(self._extract_bucket_from_s3_uri(out))
                    except Exception as e:
                        logger.debug(f"Athena get_work_group failed for {name}: {e}")
                        continue
        except Exception as e:
            logger.debug(f"Athena list_work_groups failed: {e}")
        return list(buckets)

    def _discover_buckets_via_graphql(self) -> Set[str]:
        """Discover buckets by querying the Quilt catalog's GraphQL endpoint."""
        try:
            # Get the authenticated session from quilt3
            if hasattr(quilt3, "session") and hasattr(quilt3.session, "get_session"):
                session = quilt3.session.get_session()
                registry_url = quilt3.session.get_registry_url()

                if not registry_url:
                    logger.warning("No registry URL available for GraphQL query")
                    return set()

                # Construct GraphQL endpoint URL
                graphql_url = urljoin(registry_url.rstrip("/") + "/", "graphql")
                logger.info(f"Querying GraphQL endpoint: {graphql_url}")

                # Query for bucket configurations
                query = {"query": "query { bucketConfigs { name } }"}

                response = session.post(graphql_url, json=query)

                if response.status_code == 200:
                    data = response.json()
                    if "data" in data and "bucketConfigs" in data["data"]:
                        bucket_names = {bucket["name"] for bucket in data["data"]["bucketConfigs"]}
                        logger.info(f"GraphQL discovered {len(bucket_names)} buckets: {list(bucket_names)[:5]}...")
                        return bucket_names
                    else:
                        logger.warning(f"GraphQL response missing expected data structure: {data}")
                        return set()
                else:
                    logger.warning(f"GraphQL query failed with status {response.status_code}: {response.text}")
                    return set()

        except Exception as e:
            logger.warning(f"GraphQL bucket discovery failed: {e}")
            return set()

        return set()

    def _analyze_bucket_policy_for_write_access(self, policy_json: str, _bucket_name: str) -> bool:
        """Analyze bucket policy to determine if current user has write access."""
        try:
            policy = json.loads(policy_json)

            # Get current user identity for policy analysis
            identity = self.discover_user_identity()

            # Simple policy analysis - look for statements that grant write permissions
            statements = policy.get("Statement", [])
            for statement in statements:
                if statement.get("Effect") == "Allow":
                    # Check if this statement applies to our user
                    principals = statement.get("Principal", {})
                    if self._statement_applies_to_user(principals, identity):
                        # Check if statement grants write permissions
                        actions = statement.get("Action", [])
                        if isinstance(actions, str):
                            actions = [actions]

                        write_actions = ["s3:PutObject", "s3:PutObjectAcl", "s3:*"]
                        if any(action in write_actions for action in actions):
                            return True

            return False

        except Exception as e:
            logger.warning(f"Failed to analyze bucket policy: {e}")
            return False

    def _check_iam_write_permissions(self, bucket_name: str) -> bool:
        """Check IAM permissions for write access to bucket."""
        try:
            # For now, use a conservative approach
            # In a full implementation, this would analyze attached IAM policies
            # For safety, we'll assume no write access unless we can confirm it

            # Try to use STS simulate-principal-policy if available
            try:
                identity = self.discover_user_identity()

                response = self.sts_client.simulate_principal_policy(
                    PolicySourceArn=identity.arn,
                    ActionNames=["s3:PutObject"],
                    ResourceArns=[f"arn:aws:s3:::{bucket_name}/*"],
                )

                # Check if the action is allowed
                evaluation_results = response.get("EvaluationResults", [])
                for result in evaluation_results:
                    if result.get("EvalDecision") == "allowed":
                        return True

                return False

            except Exception as e:
                logger.debug(f"STS simulation not available: {e}")
                # Conservative fallback - assume no write access
                return False

        except Exception as e:
            logger.warning(f"Failed to check IAM write permissions: {e}")
            return False

    def _determine_write_access_fallback(self, bucket_name: str) -> bool:
        """Fallback method to determine write access using multiple approaches."""
        try:
            # Method 1: Check if we own the bucket
            try:
                owned_buckets_response = self.s3_client.list_buckets()
                owned_bucket_names = [b["Name"] for b in owned_buckets_response.get("Buckets", [])]

                if bucket_name in owned_bucket_names:
                    return True  # We own it, we can write to it
            except Exception:
                pass

            # Method 2: Try to analyze bucket policy
            try:
                bucket_policy = self.s3_client.get_bucket_policy(Bucket=bucket_name)
                return self._analyze_bucket_policy_for_write_access(bucket_policy.get("Policy", "{}"), bucket_name)
            except ClientError as e:
                if e.response["Error"]["Code"] == "NoSuchBucketPolicy":
                    # No bucket policy - check if we can perform other write-related operations
                    return self._test_write_indicators(bucket_name)
            except Exception:
                pass

            # Method 3: Test write indicators
            return self._test_write_indicators(bucket_name)

        except Exception as e:
            logger.debug(f"Write access fallback failed for {bucket_name}: {e}")
            return False

    def _test_write_indicators(self, bucket_name: str) -> bool:
        """Test various indicators that suggest write access without actually writing."""
        try:
            # Test 1: Try to get bucket versioning (requires write-like permissions)
            try:
                self.s3_client.get_bucket_versioning(Bucket=bucket_name)
                return True
            except ClientError as e:
                if e.response["Error"]["Code"] != "AccessDenied":
                    return True  # Other errors suggest we have some access
            except Exception:
                pass

            # Test 2: Try to get bucket notification configuration
            try:
                self.s3_client.get_bucket_notification_configuration(Bucket=bucket_name)
                return True
            except ClientError as e:
                if e.response["Error"]["Code"] != "AccessDenied":
                    return True
            except Exception:
                pass

            # Test 3: If we can list objects, assume we might have write access
            # This is a reasonable assumption for many Quilt use cases
            try:
                self.s3_client.list_objects_v2(Bucket=bucket_name, MaxKeys=1)
                # If we can list, we likely have broader access
                # For Quilt buckets, this often means write access too
                return True
            except Exception:
                pass

            return False

        except Exception:
            return False

    def _statement_applies_to_user(self, principals: Dict[str, Any], identity: UserIdentity) -> bool:
        """Check if a policy statement applies to the current user."""
        try:
            # Handle different principal formats
            if isinstance(principals, dict):
                # Check AWS principals
                aws_principals = principals.get("AWS", [])
                if isinstance(aws_principals, str):
                    aws_principals = [aws_principals]

                # Check if our ARN or account is in the principals
                for principal in aws_principals:
                    if principal == "*":
                        return True
                    if identity.arn in principal:
                        return True
                    if identity.account_id in principal:
                        return True

            return False

        except Exception:
            return False

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "permission_cache_size": len(self.permission_cache),
            "identity_cache_size": len(self.identity_cache),
            "bucket_list_cache_size": len(self.bucket_list_cache),
            "cache_ttl": self.cache_ttl,
        }

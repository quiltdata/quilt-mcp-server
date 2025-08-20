"""AWS Permission Discovery Engine.

This module provides comprehensive AWS permission discovery functionality,
including bucket access level detection, user identity discovery, and
intelligent permission caching.
"""

from typing import Dict, List, Any, Optional, NamedTuple
from enum import Enum
import asyncio
import logging
from datetime import datetime, timedelta
import json

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from cachetools import TTLCache

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
            self.sts_client = boto3.client('sts')
            self.iam_client = boto3.client('iam')
            self.s3_client = boto3.client('s3')
        except NoCredentialsError:
            logger.error("AWS credentials not found")
            raise
    
    async def discover_user_identity(self) -> UserIdentity:
        """Discover current AWS identity and basic info."""
        cache_key = "user_identity"
        
        if cache_key in self.identity_cache:
            return self.identity_cache[cache_key]
        
        try:
            response = self.sts_client.get_caller_identity()
            
            user_id = response['UserId']
            arn = response['Arn']
            account_id = response['Account']
            
            # Determine user type and name from ARN
            if ':user/' in arn:
                user_type = "user"
                user_name = arn.split(':user/')[-1]
            elif ':role/' in arn:
                user_type = "role"
                user_name = arn.split(':role/')[-1].split('/')[0]
            elif ':federated-user/' in arn:
                user_type = "federated"
                user_name = arn.split(':federated-user/')[-1]
            else:
                user_type = "unknown"
                user_name = None
            
            identity = UserIdentity(
                user_id=user_id,
                arn=arn,
                account_id=account_id,
                user_type=user_type,
                user_name=user_name
            )
            
            self.identity_cache[cache_key] = identity
            logger.info(f"Discovered user identity: {user_type} {user_name} in account {account_id}")
            
            return identity
            
        except ClientError as e:
            logger.error(f"Failed to discover user identity: {e}")
            raise
    
    async def discover_accessible_buckets(self, include_cross_account: bool = False) -> List[BucketInfo]:
        """Discover all buckets user has any level of access to."""
        cache_key = f"accessible_buckets_{include_cross_account}"
        
        if cache_key in self.bucket_list_cache:
            return self.bucket_list_cache[cache_key]
        
        buckets = []
        
        try:
            # First, try to list buckets the user owns
            response = self.s3_client.list_buckets()
            owned_buckets = response.get('Buckets', [])
            
            logger.info(f"Found {len(owned_buckets)} owned buckets")
            
            # Check permissions for owned buckets
            for bucket_info in owned_buckets:
                bucket_name = bucket_info['Name']
                try:
                    bucket_detail = await self.discover_bucket_permissions(bucket_name)
                    buckets.append(bucket_detail)
                except Exception as e:
                    logger.warning(f"Failed to check permissions for owned bucket {bucket_name}: {e}")
                    # Add with unknown permissions
                    buckets.append(BucketInfo(
                        name=bucket_name,
                        region="unknown",
                        permission_level=PermissionLevel.NO_ACCESS,
                        can_read=False,
                        can_write=False,
                        can_list=False,
                        last_checked=datetime.utcnow(),
                        error_message=str(e)
                    ))
            
            # TODO: If include_cross_account, attempt to discover cross-account buckets
            # This would require additional logic to infer bucket names from policies
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'AccessDenied':
                logger.warning("No permission to list buckets, will work with explicitly provided bucket names")
            else:
                logger.error(f"Error listing buckets: {e}")
        
        self.bucket_list_cache[cache_key] = buckets
        return buckets
    
    async def discover_bucket_permissions(self, bucket_name: str) -> BucketInfo:
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
            # Test 1: Try to get bucket location (also tests basic access)
            try:
                location_response = self.s3_client.get_bucket_location(Bucket=bucket_name)
                region = location_response.get('LocationConstraint') or 'us-east-1'
                can_list = True  # If we can get location, we have some access
            except ClientError as e:
                if e.response['Error']['Code'] in ['AccessDenied', 'NoSuchBucket']:
                    error_message = f"Cannot access bucket: {e.response['Error']['Code']}"
                else:
                    raise
            
            # Test 2: Try to list objects (tests list permission)
            if can_list:
                try:
                    self.s3_client.list_objects_v2(Bucket=bucket_name, MaxKeys=1)
                    can_list = True
                except ClientError as e:
                    if e.response['Error']['Code'] == 'AccessDenied':
                        can_list = False
                    else:
                        raise
            
            # Test 3: Try to read a non-existent object (tests read permission)
            if can_list:
                try:
                    # Try to read a non-existent key - should get 404 if we have read permission,
                    # 403 if we don't
                    test_key = f"__permission_test_{datetime.utcnow().timestamp()}.tmp"
                    self.s3_client.head_object(Bucket=bucket_name, Key=test_key)
                except ClientError as e:
                    if e.response['Error']['Code'] == 'NotFound':
                        can_read = True  # 404 means we have read permission
                    elif e.response['Error']['Code'] == 'AccessDenied':
                        can_read = False  # 403 means no read permission
                    else:
                        # Other errors might still indicate read permission
                        can_read = True
            
            # Test 4: Try a safe write test (tests write permission)
            if can_list:
                try:
                    # Try to put a small test object and immediately delete it
                    test_key = f"__permission_test_{datetime.utcnow().timestamp()}.tmp"
                    test_content = b"permission test"
                    
                    # Put test object
                    self.s3_client.put_object(
                        Bucket=bucket_name,
                        Key=test_key,
                        Body=test_content,
                        Metadata={'purpose': 'permission-test'}
                    )
                    
                    # Immediately delete it
                    self.s3_client.delete_object(Bucket=bucket_name, Key=test_key)
                    can_write = True
                    
                except ClientError as e:
                    if e.response['Error']['Code'] == 'AccessDenied':
                        can_write = False
                    else:
                        # Other errors might still indicate we don't have write permission
                        can_write = False
        
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
            last_checked=datetime.utcnow(),
            error_message=error_message
        )
        
        self.permission_cache[cache_key] = bucket_info
        logger.info(f"Bucket {bucket_name}: {permission_level.value} (read:{can_read}, write:{can_write}, list:{can_list})")
        
        return bucket_info
    
    async def test_bucket_operations(self, bucket_name: str, operations: List[str]) -> Dict[str, bool]:
        """Safely test specific operations on bucket."""
        results = {}
        
        for operation in operations:
            try:
                if operation == "list":
                    self.s3_client.list_objects_v2(Bucket=bucket_name, MaxKeys=1)
                    results[operation] = True
                    
                elif operation == "read":
                    # Test read with non-existent key
                    test_key = f"__test_{datetime.utcnow().timestamp()}.tmp"
                    try:
                        self.s3_client.head_object(Bucket=bucket_name, Key=test_key)
                    except ClientError as e:
                        if e.response['Error']['Code'] == 'NotFound':
                            results[operation] = True
                        else:
                            results[operation] = False
                    
                elif operation == "write":
                    # Safe write test
                    test_key = f"__permission_test_{datetime.utcnow().timestamp()}.tmp"
                    self.s3_client.put_object(
                        Bucket=bucket_name,
                        Key=test_key,
                        Body=b"test",
                        Metadata={'purpose': 'permission-test'}
                    )
                    self.s3_client.delete_object(Bucket=bucket_name, Key=test_key)
                    results[operation] = True
                    
                else:
                    results[operation] = False
                    
            except ClientError as e:
                if e.response['Error']['Code'] == 'AccessDenied':
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
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "permission_cache_size": len(self.permission_cache),
            "identity_cache_size": len(self.identity_cache),
            "bucket_list_cache_size": len(self.bucket_list_cache),
            "cache_ttl": self.cache_ttl
        }

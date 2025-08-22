"""S3 fallback backend for unified search.

This backend provides basic S3 list operations as a fallback when
Elasticsearch and GraphQL are unavailable.
"""

import time
from typing import Dict, List, Any, Optional
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from .base import SearchBackend, BackendType, BackendStatus, SearchResult, BackendResponse


class S3FallbackBackend(SearchBackend):
    """S3 fallback backend using basic list operations."""
    
    def __init__(self):
        super().__init__(BackendType.S3)
        self._s3_client = None
        self._check_s3_access()
    
    def _check_s3_access(self):
        """Check if S3 access is available."""
        try:
            self._s3_client = boto3.client('s3')
            # Test with a simple STS call to verify credentials
            sts_client = boto3.client('sts')
            sts_client.get_caller_identity()
            self._update_status(BackendStatus.AVAILABLE)
        except Exception as e:
            self._update_status(BackendStatus.ERROR, f"S3 access check failed: {e}")
    
    async def health_check(self) -> bool:
        """Check if S3 backend is healthy."""
        try:
            if not self._s3_client:
                self._s3_client = boto3.client('s3')
            
            # Simple health check with STS
            sts_client = boto3.client('sts')
            sts_client.get_caller_identity()
            
            self._update_status(BackendStatus.AVAILABLE)
            return True
        except Exception as e:
            self._update_status(BackendStatus.ERROR, f"S3 health check failed: {e}")
            return False
    
    async def search(
        self,
        query: str,
        scope: str = "global",
        target: str = "",
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 50
    ) -> BackendResponse:
        """Execute search using S3 list operations."""
        start_time = time.time()
        
        if self.status != BackendStatus.AVAILABLE:
            return BackendResponse(
                backend_type=self.backend_type,
                status=self.status,
                results=[],
                error_message=self.last_error
            )
        
        try:
            if scope == "bucket" and target:
                results = await self._search_bucket(query, target, filters, limit)
            else:
                # For global/catalog scope, we can't easily enumerate all buckets
                # Return empty results with explanation
                results = []
            
            query_time = (time.time() - start_time) * 1000
            
            return BackendResponse(
                backend_type=self.backend_type,
                status=BackendStatus.AVAILABLE,
                results=results,
                total=len(results),
                query_time_ms=query_time
            )
            
        except Exception as e:
            query_time = (time.time() - start_time) * 1000
            
            return BackendResponse(
                backend_type=self.backend_type,
                status=BackendStatus.ERROR,
                results=[],
                query_time_ms=query_time,
                error_message=str(e)
            )
    
    async def _search_bucket(self, query: str, bucket: str, filters: Optional[Dict[str, Any]], limit: int) -> List[SearchResult]:
        """Search within a specific bucket using list operations."""
        # Normalize bucket name
        bucket_name = bucket.replace('s3://', '').split('/')[0]
        
        # Extract prefix from query if it looks like a path
        prefix = ""
        if '/' in query and not any(op in query.lower() for op in ['find', 'search', 'get']):
            prefix = query
            query_terms = []
        else:
            query_terms = query.lower().split()
        
        try:
            # List objects with prefix
            paginator = self._s3_client.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(
                Bucket=bucket_name,
                Prefix=prefix,
                PaginationConfig={'MaxItems': limit * 2}  # Get more to allow filtering
            )
            
            results = []
            for page in page_iterator:
                contents = page.get('Contents', [])
                
                for obj in contents:
                    key = obj['Key']
                    
                    # Apply query term filtering
                    if query_terms and not any(term in key.lower() for term in query_terms):
                        continue
                    
                    # Apply filters
                    if not self._matches_filters(obj, filters):
                        continue
                    
                    # Create result
                    result = SearchResult(
                        id=f"s3://{bucket_name}/{key}",
                        type='file',
                        title=Path(key).name,
                        description=f"S3 object in {bucket_name}",
                        s3_uri=f"s3://{bucket_name}/{key}",
                        logical_key=key,
                        size=obj.get('Size', 0),
                        last_modified=obj.get('LastModified').isoformat() if obj.get('LastModified') else None,
                        metadata={
                            'bucket': bucket_name,
                            'storage_class': obj.get('StorageClass', 'STANDARD'),
                            'etag': obj.get('ETag', '')
                        },
                        score=self._calculate_relevance_score(key, query_terms),
                        backend="s3"
                    )
                    
                    results.append(result)
                    
                    if len(results) >= limit:
                        break
                
                if len(results) >= limit:
                    break
            
            # Sort by relevance score
            results.sort(key=lambda x: x.score, reverse=True)
            
            return results[:limit]
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchBucket':
                raise Exception(f"Bucket {bucket_name} does not exist")
            elif error_code == 'AccessDenied':
                raise Exception(f"Access denied to bucket {bucket_name}")
            else:
                raise Exception(f"S3 error: {e}")
    
    def _matches_filters(self, obj: Dict[str, Any], filters: Optional[Dict[str, Any]]) -> bool:
        """Check if S3 object matches the specified filters."""
        if not filters:
            return True
        
        # File extension filter
        if filters.get('file_extensions'):
            key = obj['Key']
            file_ext = Path(key).suffix.lower().lstrip('.')
            if file_ext not in filters['file_extensions']:
                return False
        
        # Size filters
        obj_size = obj.get('Size', 0)
        if filters.get('size_min') and obj_size < filters['size_min']:
            return False
        if filters.get('size_max') and obj_size > filters['size_max']:
            return False
        
        # Date filters (simplified - would need proper date parsing)
        if filters.get('created_after') or filters.get('created_before'):
            # For S3 fallback, we'll skip complex date filtering
            # This would be better handled by Elasticsearch
            pass
        
        return True
    
    def _calculate_relevance_score(self, key: str, query_terms: List[str]) -> float:
        """Calculate relevance score for S3 object based on key matching."""
        if not query_terms:
            return 0.5
        
        key_lower = key.lower()
        score = 0.0
        
        for term in query_terms:
            if term in key_lower:
                # Exact match in filename gets higher score
                if term in Path(key).name.lower():
                    score += 1.0
                else:
                    score += 0.5
        
        # Normalize by number of terms
        return min(score / len(query_terms), 1.0) if query_terms else 0.0

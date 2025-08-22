"""Enterprise GraphQL backend for unified search.

This backend leverages the existing Enterprise GraphQL search infrastructure
including ObjectsSearchContext and PackagesSearchContext.
"""

import json
import time
from typing import Dict, List, Any, Optional, Union

import requests
import quilt3
from ..core.query_parser import QueryAnalysis, QueryType
from .base import SearchBackend, BackendType, BackendStatus, SearchResult, BackendResponse


class EnterpriseGraphQLBackend(SearchBackend):
    """GraphQL backend using existing Enterprise search contexts."""
    
    def __init__(self):
        super().__init__(BackendType.GRAPHQL)
        self._registry_url = None
        self._session = None
        self._check_graphql_access()
    
    def _check_graphql_access(self):
        """Check if GraphQL endpoint is accessible."""
        try:
            # Get registry URL from quilt3 session
            self._registry_url = quilt3.session.get_registry_url()
            self._session = quilt3.session.get_session()
            
            if self._registry_url and self._session:
                # Test GraphQL endpoint availability
                graphql_url = f"{self._registry_url}/graphql"
                
                # Simple introspection query to test connectivity
                test_query = """
                query TestConnection {
                    __schema {
                        queryType {
                            name
                        }
                    }
                }
                """
                
                response = self._session.post(
                    graphql_url,
                    json={"query": test_query},
                    timeout=5
                )
                
                if response.status_code == 200:
                    self._update_status(BackendStatus.AVAILABLE)
                else:
                    self._update_status(BackendStatus.ERROR, f"GraphQL endpoint returned {response.status_code}")
            else:
                self._update_status(BackendStatus.UNAVAILABLE, "No registry URL or session available")
                
        except Exception as e:
            self._update_status(BackendStatus.ERROR, f"GraphQL access check failed: {e}")
    
    async def health_check(self) -> bool:
        """Check if GraphQL backend is healthy."""
        try:
            if not self._registry_url or not self._session:
                self._registry_url = quilt3.session.get_registry_url()
                self._session = quilt3.session.get_session()
            
            if not self._registry_url or not self._session:
                self._update_status(BackendStatus.UNAVAILABLE, "No GraphQL endpoint available")
                return False
            
            # Test with simple query
            graphql_url = f"{self._registry_url}/graphql"
            test_query = """
            query HealthCheck {
                __schema {
                    queryType {
                        name
                    }
                }
            }
            """
            
            response = self._session.post(
                graphql_url,
                json={"query": test_query},
                timeout=5
            )
            
            if response.status_code == 200:
                self._update_status(BackendStatus.AVAILABLE)
                return True
            else:
                self._update_status(BackendStatus.ERROR, f"GraphQL health check failed: {response.status_code}")
                return False
                
        except Exception as e:
            self._update_status(BackendStatus.ERROR, f"GraphQL health check error: {e}")
            return False
    
    async def search(
        self,
        query: str,
        scope: str = "global",
        target: str = "",
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 50
    ) -> BackendResponse:
        """Execute search using Enterprise GraphQL."""
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
                results = await self._search_bucket_objects(query, target, filters, limit)
            elif scope == "package" and target:
                results = await self._search_package_contents(query, target, filters, limit)
            else:
                # Global/catalog search - search both objects and packages
                object_results = await self._search_objects_global(query, filters, limit // 2)
                package_results = await self._search_packages_global(query, filters, limit // 2)
                results = object_results + package_results
            
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
    
    async def _search_bucket_objects(self, query: str, bucket: str, filters: Optional[Dict[str, Any]], limit: int) -> List[SearchResult]:
        """Search objects within a specific bucket using GraphQL."""
        # Build GraphQL query for bucket objects search
        graphql_query = """
        query SearchBucketObjects($bucket: String!, $searchString: String!, $first: Int!) {
            bucketConfigs(name: $bucket) {
                objects(searchString: $searchString, first: $first) {
                    edges {
                        node {
                            key
                            size
                            lastModified
                            contentType
                            etag
                        }
                    }
                    totalCount
                }
            }
        }
        """
        
        variables = {
            "bucket": bucket.replace('s3://', ''),
            "searchString": self._build_search_string(query, filters),
            "first": limit
        }
        
        result = await self._execute_graphql_query(graphql_query, variables)
        
        if result.get('errors'):
            raise Exception(f"GraphQL errors: {result['errors']}")
        
        return self._convert_bucket_objects_results(result, bucket)
    
    async def _search_packages_global(self, query: str, filters: Optional[Dict[str, Any]], limit: int) -> List[SearchResult]:
        """Search packages globally using GraphQL."""
        graphql_query = """
        query SearchPackages($searchString: String!, $first: Int!) {
            packages(searchString: $searchString, first: $first) {
                edges {
                    node {
                        name
                        lastModified
                        totalEntries
                        totalBytes
                        metadata
                    }
                }
                totalCount
            }
        }
        """
        
        variables = {
            "searchString": self._build_search_string(query, filters),
            "first": limit
        }
        
        result = await self._execute_graphql_query(graphql_query, variables)
        
        if result.get('errors'):
            raise Exception(f"GraphQL errors: {result['errors']}")
        
        return self._convert_packages_results(result)
    
    async def _search_objects_global(self, query: str, filters: Optional[Dict[str, Any]], limit: int) -> List[SearchResult]:
        """Search objects globally using GraphQL."""
        graphql_query = """
        query SearchObjects($searchString: String!, $first: Int!) {
            objects(searchString: $searchString, first: $first) {
                edges {
                    node {
                        key
                        size
                        lastModified
                        bucket
                        packageName
                        logicalKey
                    }
                }
                totalCount
            }
        }
        """
        
        variables = {
            "searchString": self._build_search_string(query, filters),
            "first": limit
        }
        
        result = await self._execute_graphql_query(graphql_query, variables)
        
        if result.get('errors'):
            raise Exception(f"GraphQL errors: {result['errors']}")
        
        return self._convert_objects_results(result)
    
    async def _search_package_contents(self, query: str, package_name: str, filters: Optional[Dict[str, Any]], limit: int) -> List[SearchResult]:
        """Search within a specific package using GraphQL."""
        # This would require package-specific GraphQL queries
        # For now, return empty results as this is complex to implement without full schema
        return []
    
    def _build_search_string(self, query: str, filters: Optional[Dict[str, Any]]) -> str:
        """Build search string from query and filters for GraphQL."""
        search_parts = [query]
        
        if not filters:
            return query
        
        # Add file extension filters
        if filters.get('file_extensions'):
            for ext in filters['file_extensions']:
                search_parts.append(f"*.{ext}")
        
        # Add size filters (basic - GraphQL may have limited size query support)
        if filters.get('size_min'):
            search_parts.append(f"size:>{filters['size_min']}")
        
        return " ".join(search_parts)
    
    async def _execute_graphql_query(self, query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a GraphQL query against the Enterprise endpoint."""
        if not self._registry_url or not self._session:
            raise Exception("GraphQL endpoint not available")
        
        graphql_url = f"{self._registry_url}/graphql"
        
        payload = {
            "query": query,
            "variables": variables
        }
        
        response = self._session.post(
            graphql_url,
            json=payload,
            timeout=30
        )
        
        if response.status_code != 200:
            raise Exception(f"GraphQL request failed: {response.status_code} - {response.text}")
        
        return response.json()
    
    def _convert_bucket_objects_results(self, graphql_result: Dict[str, Any], bucket: str) -> List[SearchResult]:
        """Convert GraphQL bucket objects results to standard format."""
        results = []
        
        data = graphql_result.get('data', {})
        bucket_configs = data.get('bucketConfigs', [])
        
        for bucket_config in bucket_configs:
            objects = bucket_config.get('objects', {})
            edges = objects.get('edges', [])
            
            for edge in edges:
                node = edge.get('node', {})
                
                result = SearchResult(
                    id=f"graphql-object-{node.get('key', '')}",
                    type='file',
                    title=node.get('key', '').split('/')[-1] if node.get('key') else 'Unknown',
                    description=f"Object in {bucket}",
                    s3_uri=f"s3://{bucket.replace('s3://', '')}/{node.get('key', '')}",
                    logical_key=node.get('key'),
                    size=node.get('size'),
                    last_modified=node.get('lastModified'),
                    metadata={
                        'bucket': bucket,
                        'content_type': node.get('contentType'),
                        'etag': node.get('etag')
                    },
                    score=1.0,  # GraphQL doesn't provide relevance scores
                    backend="graphql"
                )
                
                results.append(result)
        
        return results
    
    def _convert_packages_results(self, graphql_result: Dict[str, Any]) -> List[SearchResult]:
        """Convert GraphQL packages results to standard format."""
        results = []
        
        data = graphql_result.get('data', {})
        packages = data.get('packages', {})
        edges = packages.get('edges', [])
        
        for edge in edges:
            node = edge.get('node', {})
            
            result = SearchResult(
                id=f"graphql-package-{node.get('name', '')}",
                type='package',
                title=node.get('name', ''),
                description=f"Quilt package: {node.get('name', '')}",
                package_name=node.get('name'),
                size=node.get('totalBytes'),
                last_modified=node.get('lastModified'),
                metadata={
                    'total_entries': node.get('totalEntries'),
                    'total_bytes': node.get('totalBytes'),
                    'package_metadata': node.get('metadata', {})
                },
                score=1.0,  # GraphQL doesn't provide relevance scores
                backend="graphql"
            )
            
            results.append(result)
        
        return results
    
    def _convert_objects_results(self, graphql_result: Dict[str, Any]) -> List[SearchResult]:
        """Convert GraphQL objects results to standard format."""
        results = []
        
        data = graphql_result.get('data', {})
        objects = data.get('objects', {})
        edges = objects.get('edges', [])
        
        for edge in edges:
            node = edge.get('node', {})
            
            result = SearchResult(
                id=f"graphql-object-{node.get('key', '')}",
                type='file',
                title=node.get('key', '').split('/')[-1] if node.get('key') else 'Unknown',
                description=f"Object in {node.get('bucket', 'unknown bucket')}",
                s3_uri=f"s3://{node.get('bucket', '')}/{node.get('key', '')}",
                package_name=node.get('packageName'),
                logical_key=node.get('logicalKey') or node.get('key'),
                size=node.get('size'),
                last_modified=node.get('lastModified'),
                metadata={
                    'bucket': node.get('bucket'),
                    'package_name': node.get('packageName'),
                    'logical_key': node.get('logicalKey')
                },
                score=1.0,
                backend="graphql"
            )
            
            results.append(result)
        
        return results

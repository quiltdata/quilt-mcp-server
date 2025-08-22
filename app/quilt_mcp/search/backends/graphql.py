"""Enterprise GraphQL backend for unified search.

This backend leverages the existing Enterprise GraphQL search infrastructure
including ObjectsSearchContext and PackagesSearchContext.
"""

import json
import time
from typing import Dict, List, Any, Optional, Union
from urllib.parse import urljoin

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
                # Use the same URL construction as working bucket_objects_search_graphql
                graphql_url = urljoin(self._registry_url.rstrip("/") + "/", "graphql")
                
                # Test with a simple objects query like the working implementation
                test_query = """
                query TestConnection($bucket: String!) {
                    objects(bucket: $bucket, first: 1) {
                        edges {
                            node {
                                key
                            }
                        }
                    }
                }
                """
                
                # Use a test bucket that should exist
                variables = {"bucket": "quilt-example"}
                
                response = self._session.post(
                    graphql_url,
                    json={"query": test_query, "variables": variables},
                    timeout=5
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('data'):
                        self._update_status(BackendStatus.AVAILABLE)
                    else:
                        self._update_status(BackendStatus.UNAVAILABLE, "GraphQL endpoint exists but not responding correctly")
                elif response.status_code == 404:
                    self._update_status(BackendStatus.UNAVAILABLE, "GraphQL endpoint not available (404) - likely not an Enterprise catalog")
                elif response.status_code == 405:
                    self._update_status(BackendStatus.UNAVAILABLE, "GraphQL endpoint not accepting POST requests (405)")
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
        # Use the same GraphQL query pattern as the working bucket_objects_search_graphql
        graphql_query = """
        query SearchBucketObjects($bucket: String!, $filter: ObjectFilterInput, $first: Int!) {
            objects(bucket: $bucket, filter: $filter, first: $first) {
                edges {
                    node {
                        key
                        size
                        updated
                        contentType
                        extension
                        package {
                            name
                            topHash
                            tag
                        }
                    }
                    cursor
                }
                pageInfo {
                    endCursor
                    hasNextPage
                }
            }
        }
        """
        
        # Build filter from query and filters
        object_filter = self._build_graphql_filter(query, filters)
        
        variables = {
            "bucket": bucket.replace('s3://', ''),
            "filter": object_filter,
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
    
    def _build_graphql_filter(self, query: str, filters: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Build GraphQL filter object from query and filters."""
        graphql_filter = {}
        
        # Add key-based search if query contains terms
        if query and query.strip():
            # For simple text queries, use key_contains
            graphql_filter["key_contains"] = query
        
        # Add file extension filters
        if filters and filters.get('file_extensions'):
            # Use extension filter if available
            if len(filters['file_extensions']) == 1:
                graphql_filter["extension"] = filters['file_extensions'][0]
            else:
                # For multiple extensions, use key pattern matching
                ext_patterns = [f"*.{ext}" for ext in filters['file_extensions']]
                graphql_filter["key_contains"] = " OR ".join(ext_patterns)
        
        # Add size filters
        if filters:
            if filters.get('size_min'):
                graphql_filter["size_gte"] = filters['size_min']
            if filters.get('size_max'):
                graphql_filter["size_lte"] = filters['size_max']
        
        return graphql_filter
    
    async def _execute_graphql_query(self, query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a GraphQL query using the same method as bucket_objects_search_graphql."""
        if not self._registry_url or not self._session:
            raise Exception("GraphQL endpoint not available")
        
        # Use the same URL construction as working implementation
        graphql_url = urljoin(self._registry_url.rstrip("/") + "/", "graphql")
        
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
        
        result = response.json()
        
        # Check for GraphQL errors like the working implementation
        if "errors" in result:
            raise Exception(f"GraphQL errors: {json.dumps(result['errors'])}")
        
        return result
    
    def _convert_bucket_objects_results(self, graphql_result: Dict[str, Any], bucket: str) -> List[SearchResult]:
        """Convert GraphQL bucket objects results to standard format."""
        results = []
        
        # Use the same result structure as bucket_objects_search_graphql
        data = graphql_result.get('data', {})
        objects = data.get('objects', {})
        edges = objects.get('edges', [])
        
        for edge in edges:
            if not isinstance(edge, dict):
                continue
                
            node = edge.get('node', {})
            
            # Extract package information if available
            package_info = node.get('package', {})
            package_name = package_info.get('name') if package_info else None
            
            result = SearchResult(
                id=f"graphql-object-{node.get('key', '')}",
                type='file',
                title=node.get('key', '').split('/')[-1] if node.get('key') else 'Unknown',
                description=f"Object in {bucket}" + (f" (package: {package_name})" if package_name else ""),
                s3_uri=f"s3://{bucket.replace('s3://', '')}/{node.get('key', '')}",
                package_name=package_name,
                logical_key=node.get('key'),
                size=node.get('size'),
                last_modified=node.get('updated'),  # GraphQL uses 'updated' not 'lastModified'
                metadata={
                    'bucket': bucket,
                    'content_type': node.get('contentType'),
                    'extension': node.get('extension'),
                    'package': package_info
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
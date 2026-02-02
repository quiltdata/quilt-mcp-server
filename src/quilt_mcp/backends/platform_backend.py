"""Platform GraphQL backend implementation.

This module provides a concrete implementation of QuiltOps backed by the
Platform GraphQL API and JWT authentication claims.
"""

from __future__ import annotations

import json
import logging
import math
import os
from contextlib import contextmanager
from typing import List, Optional, Dict, Any

from quilt_mcp.ops.quilt_ops import QuiltOps
from quilt_mcp.ops.tabulator_mixin import TabulatorMixin
from quilt_mcp.ops.exceptions import AuthenticationError, BackendError, ValidationError, NotFoundError
from quilt_mcp.domain import (
    Package_Info,
    Content_Info,
    Bucket_Info,
    Auth_Status,
    Catalog_Config,
    Package_Creation_Result,
)
from quilt_mcp.runtime_context import (
    get_runtime_auth,
    get_runtime_claims,
    get_runtime_metadata,
    update_runtime_metadata,
)
from quilt_mcp.services.jwt_auth_service import JWTAuthService, JwtAuthServiceError
from quilt_mcp.services.jwt_decoder import JwtDecodeError, get_jwt_decoder
from quilt_mcp.utils import graphql_endpoint, normalize_url, get_dns_name_from_url, parse_s3_uri

logger = logging.getLogger(__name__)


class Platform_Backend(TabulatorMixin, QuiltOps):
    """Platform GraphQL backend implementation."""

    def __init__(self) -> None:
        self._auth_service = JWTAuthService()
        self._claims = self._load_claims()
        metadata = get_runtime_metadata()

        self._catalog_token = self._claims.get("catalog_token") or metadata.get("catalog_token")
        if not self._catalog_token:
            raise AuthenticationError("JWT claim 'catalog_token' is required for Platform backend")

        self._catalog_url = (
            self._claims.get("catalog_url") or metadata.get("catalog_url") or os.getenv("QUILT_CATALOG_URL")
        )
        self._registry_url = self._claims.get("registry_url") or metadata.get("registry_url")
        if not self._registry_url and self._catalog_url:
            self._registry_url = self._derive_registry_url(self._catalog_url)

        self._graphql_endpoint = os.getenv("QUILT_GRAPHQL_ENDPOINT")
        if not self._graphql_endpoint and self._registry_url:
            self._graphql_endpoint = graphql_endpoint(self._registry_url)

        if not self._graphql_endpoint:
            raise AuthenticationError(
                "GraphQL endpoint not configured. Set QUILT_GRAPHQL_ENDPOINT or include registry_url/catalog_url in JWT."
            )

        import requests

        self._requests = requests
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {self._catalog_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

        logger.info("Platform_Backend initialized")

    # ---------------------------------------------------------------------
    # GraphQL auth + endpoint helpers
    # ---------------------------------------------------------------------

    def get_graphql_endpoint(self) -> str:
        if not self._graphql_endpoint:
            raise AuthenticationError("GraphQL endpoint not configured")
        return self._graphql_endpoint

    def get_graphql_auth_headers(self) -> Dict[str, str]:
        if not self._catalog_token:
            raise AuthenticationError("Missing catalog_token for GraphQL authentication")
        return {"Authorization": f"Bearer {self._catalog_token}"}

    def execute_graphql_query(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
        registry: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            endpoint = self.get_graphql_endpoint()
            headers = self.get_graphql_auth_headers()
            payload: Dict[str, Any] = {"query": query}
            if variables:
                payload["variables"] = variables

            response = self._session.post(endpoint, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            result = response.json()
            if not isinstance(result, dict):
                raise BackendError("GraphQL response was not a JSON object")

            if "errors" in result:
                error_messages = [err.get("message", str(err)) for err in result.get("errors", [])]
                raise BackendError(f"GraphQL query failed: {'; '.join(error_messages)}")

            return result
        except self._requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status in {401, 403}:
                raise AuthenticationError("GraphQL query not authorized") from exc
            error_text = exc.response.text if exc.response is not None else str(exc)
            raise BackendError(f"GraphQL query failed: {error_text}") from exc
        except BackendError:
            raise
        except Exception as exc:
            raise BackendError(f"GraphQL query failed: {exc}") from exc

    # ---------------------------------------------------------------------
    # Auth + catalog
    # ---------------------------------------------------------------------

    def get_auth_status(self) -> Auth_Status:
        try:
            query = """
            query AuthStatus {
              me {
                name
                email
                isAdmin
              }
            }
            """
            result = self.execute_graphql_query(query)
            me = result.get("data", {}).get("me")
            is_authenticated = bool(me)

            catalog_url = self._catalog_url
            catalog_name = get_dns_name_from_url(catalog_url) if catalog_url else None

            return Auth_Status(
                is_authenticated=is_authenticated,
                logged_in_url=catalog_url,
                catalog_name=catalog_name,
                registry_url=self._registry_url,
            )
        except AuthenticationError:
            raise
        except Exception as exc:
            raise BackendError(f"Failed to get authentication status: {exc}") from exc

    def get_catalog_config(self, catalog_url: str) -> Catalog_Config:
        try:
            if not catalog_url or not isinstance(catalog_url, str):
                raise ValidationError("Invalid catalog URL: must be a non-empty string")

            normalized_url = normalize_url(catalog_url)
            config_url = f"{normalized_url}/config.json"
            response = self._session.get(config_url, timeout=10)
            response.raise_for_status()
            config_data = response.json()
            return self._transform_catalog_config(config_data)
        except ValidationError:
            raise
        except self._requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                raise NotFoundError(f"Catalog configuration not found at {catalog_url}") from exc
            if exc.response is not None and exc.response.status_code == 403:
                raise AuthenticationError(f"Access denied to catalog configuration at {catalog_url}") from exc
            raise BackendError(f"HTTP error fetching catalog config: {exc}") from exc
        except Exception as exc:
            raise BackendError(f"Platform backend get_catalog_config failed: {exc}") from exc

    def configure_catalog(self, catalog_url: str) -> None:
        try:
            if not catalog_url or not isinstance(catalog_url, str):
                raise ValidationError("Invalid catalog URL: must be a non-empty string")
            self._catalog_url = catalog_url
            update_runtime_metadata(catalog_url=catalog_url)
            if not self._registry_url:
                self._registry_url = self._derive_registry_url(catalog_url)
                update_runtime_metadata(registry_url=self._registry_url)
            if not os.getenv("QUILT_GRAPHQL_ENDPOINT") and self._registry_url:
                self._graphql_endpoint = graphql_endpoint(self._registry_url)
        except ValidationError:
            raise
        except Exception as exc:
            raise BackendError(f"Platform backend configure_catalog failed: {exc}") from exc

    def get_registry_url(self) -> Optional[str]:
        return self._registry_url

    # ---------------------------------------------------------------------
    # Read operations
    # ---------------------------------------------------------------------

    def list_buckets(self) -> List[Bucket_Info]:
        try:
            query = """
            query ListBuckets {
              bucketConfigs {
                name
              }
            }
            """
            result = self.execute_graphql_query(query)
            configs = result.get("data", {}).get("bucketConfigs") or []
            buckets: List[Bucket_Info] = []
            for entry in configs:
                name = entry.get("name")
                if not name:
                    continue
                buckets.append(
                    Bucket_Info(
                        name=name,
                        region="unknown",
                        access_level="unknown",
                        created_date=None,
                    )
                )
            return buckets
        except Exception as exc:
            raise BackendError(f"Platform backend list_buckets failed: {exc}") from exc

    def search_packages(self, query: str, registry: str) -> List[Package_Info]:
        try:
            bucket = self._extract_bucket_from_registry(registry)
            search_string = query.strip() if query else ""
            variables = {"buckets": [bucket], "searchString": search_string or None}

            gql = """
            query SearchPackages($buckets: [String!], $searchString: String) {
              searchPackages(buckets: $buckets, searchString: $searchString) {
                __typename
                ... on PackagesSearchResultSet {
                  firstPage(size: 1000, order: NEWEST) {
                    hits {
                      name
                      bucket
                      hash
                      modified
                      comment
                      meta
                    }
                  }
                }
                ... on EmptySearchResultSet {
                  _
                }
                ... on InvalidInput {
                  errors { path message name context }
                }
                ... on OperationError {
                  message
                  name
                  context
                }
              }
            }
            """
            result = self.execute_graphql_query(gql, variables=variables)
            payload = result.get("data", {}).get("searchPackages") or {}
            typename = payload.get("__typename")
            if typename in {"EmptySearchResultSet", None}:
                return []
            if typename == "InvalidInput":
                errors = payload.get("errors", [])
                message = "; ".join(err.get("message", "invalid input") for err in errors)
                raise ValidationError(f"Invalid search input: {message}")
            if typename == "OperationError":
                raise BackendError(payload.get("message", "Search operation failed"))

            hits = payload.get("firstPage", {}).get("hits", [])
            results: List[Package_Info] = []
            for hit in hits:
                results.append(self._transform_search_hit(hit, registry))
            return results
        except ValidationError:
            raise
        except Exception as exc:
            raise BackendError(
                f"Platform backend search_packages failed: {exc}",
                context={"query": query, "registry": registry},
            ) from exc

    def get_package_info(self, package_name: str, registry: str) -> Package_Info:
        try:
            bucket = self._extract_bucket_from_registry(registry)
            gql = """
            query PackageInfo($bucket: String!, $name: String!) {
              package(bucket: $bucket, name: $name) {
                bucket
                name
                modified
                revision(hashOrTag: "latest") {
                  hash
                  message
                  userMeta
                }
              }
            }
            """
            result = self.execute_graphql_query(gql, variables={"bucket": bucket, "name": package_name})
            package_data = result.get("data", {}).get("package")
            if not package_data:
                raise NotFoundError(f"Package not found: {package_name}")

            return self._transform_package_details(package_data, registry)
        except NotFoundError:
            raise
        except Exception as exc:
            raise BackendError(
                f"Platform backend get_package_info failed: {exc}",
                context={"package_name": package_name, "registry": registry},
            ) from exc

    def browse_content(self, package_name: str, registry: str, path: str = "") -> List[Content_Info]:
        try:
            bucket = self._extract_bucket_from_registry(registry)
            gql = """
            query BrowseContent($bucket: String!, $name: String!, $path: String!) {
              package(bucket: $bucket, name: $name) {
                revision(hashOrTag: "latest") {
                  dir(path: $path) {
                    path
                    size
                    children {
                      __typename
                      ... on PackageFile { path size physicalKey }
                      ... on PackageDir { path size }
                    }
                  }
                  file(path: $path) {
                    path
                    size
                    physicalKey
                  }
                }
              }
            }
            """
            result = self.execute_graphql_query(
                gql,
                variables={"bucket": bucket, "name": package_name, "path": path or ""},
            )
            revision = result.get("data", {}).get("package", {}).get("revision")
            if not revision:
                raise NotFoundError(f"Package not found: {package_name}")

            dir_info = revision.get("dir")
            file_info = revision.get("file")

            if dir_info:
                children = dir_info.get("children", [])
                return [self._transform_content_entry(entry) for entry in children]

            if file_info:
                return [self._transform_content_entry({"__typename": "PackageFile", **file_info})]

            raise NotFoundError(f"Path not found in package: {path}")
        except NotFoundError:
            raise
        except Exception as exc:
            raise BackendError(
                f"Platform backend browse_content failed: {exc}",
                context={"package_name": package_name, "registry": registry, "path": path},
            ) from exc

    def list_all_packages(self, registry: str) -> List[str]:
        try:
            bucket = self._extract_bucket_from_registry(registry)
            per_page = 100
            gql = """
            query ListPackages($bucket: String!, $page: Int!, $perPage: Int!) {
              packages(bucket: $bucket) {
                total
                page(number: $page, perPage: $perPage, order: NAME) {
                  name
                }
              }
            }
            """
            first = self.execute_graphql_query(gql, variables={"bucket": bucket, "page": 1, "perPage": per_page})
            pkg_list = first.get("data", {}).get("packages")
            if not pkg_list:
                return []
            total = pkg_list.get("total", 0)
            pages = max(1, math.ceil(total / per_page))
            names: List[str] = [item.get("name") for item in pkg_list.get("page", []) if item.get("name")]

            for page in range(2, pages + 1):
                data = self.execute_graphql_query(gql, variables={"bucket": bucket, "page": page, "perPage": per_page})
                page_items = data.get("data", {}).get("packages", {}).get("page", [])
                names.extend([item.get("name") for item in page_items if item.get("name")])

            return names
        except Exception as exc:
            raise BackendError(f"Platform backend list_all_packages failed: {exc}") from exc

    def diff_packages(
        self,
        package1_name: str,
        package2_name: str,
        registry: str,
        package1_hash: Optional[str] = None,
        package2_hash: Optional[str] = None,
    ) -> Dict[str, List[str]]:
        try:
            bucket = self._extract_bucket_from_registry(registry)
            gql = """
            query DiffPackages($bucket: String!, $name1: String!, $name2: String!, $hash1: String!, $hash2: String!, $max: Int!) {
              p1: package(bucket: $bucket, name: $name1) {
                revision(hashOrTag: $hash1) {
                  contentsFlatMap(max: $max)
                }
              }
              p2: package(bucket: $bucket, name: $name2) {
                revision(hashOrTag: $hash2) {
                  contentsFlatMap(max: $max)
                }
              }
            }
            """
            variables = {
                "bucket": bucket,
                "name1": package1_name,
                "name2": package2_name,
                "hash1": package1_hash or "latest",
                "hash2": package2_hash or "latest",
                "max": 10000,
            }
            result = self.execute_graphql_query(gql, variables=variables)
            map1 = result.get("data", {}).get("p1", {}).get("revision", {}).get("contentsFlatMap")
            map2 = result.get("data", {}).get("p2", {}).get("revision", {}).get("contentsFlatMap")
            if map1 is None or map2 is None:
                raise BackendError("Package contents too large to diff (contentsFlatMap returned null)")

            keys1 = set(map1.keys())
            keys2 = set(map2.keys())
            added = sorted(keys2 - keys1)
            deleted = sorted(keys1 - keys2)
            modified: List[str] = []
            for key in sorted(keys1 & keys2):
                if not self._entries_equal(map1.get(key), map2.get(key)):
                    modified.append(key)

            return {"added": added, "deleted": deleted, "modified": modified}
        except Exception as exc:
            raise BackendError(
                f"Platform backend diff_packages failed: {exc}",
                context={"package1_name": package1_name, "package2_name": package2_name},
            ) from exc

    # ---------------------------------------------------------------------
    # Content URLs
    # ---------------------------------------------------------------------

    def get_content_url(self, package_name: str, registry: str, path: str) -> str:
        try:
            bucket = self._extract_bucket_from_registry(registry)
            gql = """
            query ContentUrl($bucket: String!, $name: String!, $path: String!) {
              package(bucket: $bucket, name: $name) {
                revision(hashOrTag: "latest") {
                  file(path: $path) {
                    physicalKey
                  }
                }
              }
            }
            """
            result = self.execute_graphql_query(gql, variables={"bucket": bucket, "name": package_name, "path": path})
            file_info = result.get("data", {}).get("package", {}).get("revision", {}).get("file")
            if not file_info:
                raise NotFoundError(f"File not found: {path}")

            physical_key = file_info.get("physicalKey")
            if not physical_key:
                raise BackendError("Missing physicalKey for file")

            bucket_name, key, version_id = parse_s3_uri(physical_key)
            client = self.get_boto3_client("s3")
            params: Dict[str, Any] = {"Bucket": bucket_name, "Key": key}
            if version_id:
                params["VersionId"] = version_id

            return str(client.generate_presigned_url("get_object", Params=params, ExpiresIn=3600))
        except NotFoundError:
            raise
        except Exception as exc:
            raise BackendError(
                f"Platform backend get_content_url failed: {exc}",
                context={"package_name": package_name, "registry": registry, "path": path},
            ) from exc

    # ---------------------------------------------------------------------
    # Write operations (quilt3 Package)
    # ---------------------------------------------------------------------

    def get_boto3_client(self, service_name: str, region: Optional[str] = None) -> Any:
        try:
            session = self._auth_service.get_session()
            return session.client(service_name, region_name=region)
        except JwtAuthServiceError as exc:
            raise AuthenticationError(str(exc)) from exc
        except Exception as exc:
            raise BackendError(f"Failed to create boto3 client for {service_name}: {exc}") from exc

    def create_package_revision(
        self,
        package_name: str,
        s3_uris: List[str],
        metadata: Optional[Dict] = None,
        registry: Optional[str] = None,
        message: str = "Package created via QuiltOps",
        auto_organize: bool = True,
        copy: bool = False,
    ) -> Package_Creation_Result:
        try:
            self._validate_package_creation_inputs(package_name, s3_uris)

            import quilt3

            with self._with_aws_credentials():
                package = quilt3.Package()
                for s3_uri in s3_uris:
                    logical_key = self._extract_logical_key(s3_uri, auto_organize=auto_organize)
                    package.set(logical_key, s3_uri)

                if metadata:
                    package.set_meta(metadata)

                if not copy:
                    top_hash = package.push(
                        package_name,
                        registry=registry,
                        message=message,
                        selector_fn=lambda _logical_key, _entry: False,
                    )
                else:
                    top_hash = package.push(package_name, registry=registry, message=message)

            effective_registry = registry or "s3://unknown-registry"
            catalog_url = self._build_catalog_url(package_name, effective_registry)

            if not top_hash:
                return Package_Creation_Result(
                    package_name=package_name,
                    top_hash="",
                    registry=effective_registry,
                    catalog_url=catalog_url,
                    file_count=len(s3_uris),
                    success=False,
                )

            return Package_Creation_Result(
                package_name=package_name,
                top_hash=str(top_hash),
                registry=effective_registry,
                catalog_url=catalog_url,
                file_count=len(s3_uris),
                success=True,
            )
        except ValidationError:
            raise
        except Exception as exc:
            raise BackendError(
                f"Platform backend create_package_revision failed: {exc}",
                context={"package_name": package_name, "registry": registry},
            ) from exc

    def update_package_revision(
        self,
        package_name: str,
        s3_uris: List[str],
        registry: str,
        metadata: Optional[Dict] = None,
        message: str = "Package updated via QuiltOps",
        auto_organize: bool = False,
        copy: str = "none",
    ) -> Package_Creation_Result:
        try:
            self._validate_package_update_inputs(package_name, s3_uris, registry)

            import quilt3

            with self._with_aws_credentials():
                existing_pkg = quilt3.Package.browse(package_name, registry=registry)
                updated_pkg = existing_pkg

                added_files = []
                for s3_uri in s3_uris:
                    if not s3_uri.startswith("s3://"):
                        continue
                    without_scheme = s3_uri[5:]
                    if "/" not in without_scheme:
                        continue
                    bucket, key = without_scheme.split("/", 1)
                    if not key or key.endswith("/"):
                        continue

                    logical_path = key if auto_organize else key.split("/")[-1]
                    updated_pkg.set(logical_path, s3_uri)
                    added_files.append({"logical_path": logical_path, "source": s3_uri})

                if metadata:
                    combined: Dict[str, Any] = {}
                    try:
                        combined.update(existing_pkg.meta)
                    except Exception:
                        pass
                    combined.update(metadata)
                    updated_pkg.set_meta(combined)

                if copy == "all":
                    selector_fn = lambda _logical_key, _entry: True
                else:
                    selector_fn = lambda _logical_key, _entry: False

                push_result = updated_pkg.push(
                    package_name,
                    registry=registry,
                    message=message,
                    selector_fn=selector_fn,
                    force=True,
                )

            if hasattr(push_result, "top_hash"):
                top_hash = push_result.top_hash
            else:
                top_hash = str(push_result) if push_result else ""

            catalog_url = self._build_catalog_url(package_name, registry)
            if not top_hash:
                return Package_Creation_Result(
                    package_name=package_name,
                    top_hash="",
                    registry=registry,
                    catalog_url=catalog_url,
                    file_count=len(added_files),
                    success=False,
                )

            return Package_Creation_Result(
                package_name=package_name,
                top_hash=top_hash,
                registry=registry,
                catalog_url=catalog_url,
                file_count=len(added_files),
                success=True,
            )
        except ValidationError:
            raise
        except Exception as exc:
            raise BackendError(
                f"Platform backend update_package_revision failed: {exc}",
                context={"package_name": package_name, "registry": registry},
            ) from exc

    # ---------------------------------------------------------------------
    # Admin operations
    # ---------------------------------------------------------------------

    @property
    def admin(self):
        raise NotImplementedError("Platform admin operations not yet implemented")

    # ---------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------

    def _load_claims(self) -> Dict[str, Any]:
        claims = get_runtime_claims()
        if claims:
            return claims

        runtime_auth = get_runtime_auth()
        if runtime_auth and runtime_auth.access_token:
            decoder = get_jwt_decoder()
            try:
                return decoder.decode(runtime_auth.access_token)
            except JwtDecodeError as exc:
                raise AuthenticationError(f"Invalid JWT: {exc.detail}") from exc

        return {}

    def _derive_registry_url(self, catalog_url: str) -> Optional[str]:
        if not catalog_url:
            return None
        if "nightly.quilttest.com" in catalog_url:
            return catalog_url.replace("nightly.quilttest.com", "nightly-registry.quilttest.com")
        if "quiltdata.com" in catalog_url:
            return catalog_url.replace("quiltdata.com", "registry.quiltdata.com")
        return None

    def _transform_catalog_config(self, config_data: Dict[str, Any]) -> Catalog_Config:
        try:
            region = config_data.get("region", "")
            if not region:
                raise BackendError("Missing required field 'region' in catalog configuration")

            api_gateway_endpoint = config_data.get("apiGatewayEndpoint", "")
            if not api_gateway_endpoint:
                raise BackendError("Missing required field 'apiGatewayEndpoint' in catalog configuration")

            registry_url = config_data.get("registryUrl", "")
            if not registry_url:
                raise BackendError("Missing required field 'registryUrl' in catalog configuration")

            analytics_bucket = config_data.get("analyticsBucket", "")
            if not analytics_bucket:
                raise BackendError("Missing required field 'analyticsBucket' in catalog configuration")

            stack_prefix = ""
            analytics_bucket_lower = analytics_bucket.lower()
            if "-analyticsbucket" in analytics_bucket_lower:
                analyticsbucket_pos = analytics_bucket_lower.find("-analyticsbucket")
                stack_prefix = analytics_bucket[:analyticsbucket_pos]
            else:
                stack_prefix = analytics_bucket.split("-")[0] if "-" in analytics_bucket else analytics_bucket

            tabulator_data_catalog = f"quilt-{stack_prefix}-tabulator"

            return Catalog_Config(
                region=region,
                api_gateway_endpoint=api_gateway_endpoint,
                registry_url=registry_url,
                analytics_bucket=analytics_bucket,
                stack_prefix=stack_prefix,
                tabulator_data_catalog=tabulator_data_catalog,
            )
        except BackendError:
            raise
        except Exception as exc:
            raise BackendError(f"Catalog configuration transformation failed: {exc}") from exc

    def _transform_search_hit(self, hit: Dict[str, Any], registry: str) -> Package_Info:
        name = hit.get("name") or ""
        bucket = hit.get("bucket") or self._extract_bucket_from_registry(registry)
        top_hash = hit.get("hash") or ""
        modified = self._normalize_package_datetime(hit.get("modified"))

        meta = self._parse_meta(hit.get("meta"))
        description = self._extract_description(meta, hit.get("comment"))
        tags = self._extract_tags_from_meta(meta)

        return Package_Info(
            name=name,
            description=description,
            tags=tags,
            modified_date=modified,
            registry=registry,
            bucket=bucket,
            top_hash=top_hash,
        )

    def _transform_package_details(self, package_data: Dict[str, Any], registry: str) -> Package_Info:
        revision = package_data.get("revision") or {}
        meta = self._parse_meta(revision.get("userMeta"))
        description = self._extract_description(meta, revision.get("message"))
        tags = self._extract_tags_from_meta(meta)
        modified = self._normalize_package_datetime(package_data.get("modified"))

        return Package_Info(
            name=package_data.get("name", ""),
            description=description,
            tags=tags,
            modified_date=modified,
            registry=registry,
            bucket=package_data.get("bucket", self._extract_bucket_from_registry(registry)),
            top_hash=revision.get("hash", ""),
        )

    def _transform_content_entry(self, entry: Dict[str, Any]) -> Content_Info:
        typename = entry.get("__typename") or "PackageFile"
        path = entry.get("path") or ""
        size = self._normalize_size(entry.get("size"))
        if typename == "PackageDir":
            content_type = "directory"
        else:
            content_type = "file"

        return Content_Info(
            path=path,
            size=size,
            type=content_type,
            modified_date=None,
            download_url=None,
        )

    def _entries_equal(self, entry1: Any, entry2: Any) -> bool:
        if entry1 is None or entry2 is None:
            return False
        if not isinstance(entry1, dict) or not isinstance(entry2, dict):
            return bool(entry1 == entry2)
        return (
            entry1.get("hash") == entry2.get("hash")
            and entry1.get("size") == entry2.get("size")
            and entry1.get("physicalKey") == entry2.get("physicalKey")
        )

    def _normalize_package_datetime(self, datetime_value: Any) -> str:
        if datetime_value is None:
            return "None"
        if hasattr(datetime_value, "isoformat"):
            return str(datetime_value.isoformat())
        return str(datetime_value)

    def _normalize_size(self, size: Any) -> Optional[int]:
        if size is None:
            return None
        try:
            return int(size)
        except (ValueError, TypeError):
            return None

    def _extract_description(self, meta: Optional[Dict[str, Any]], fallback: Optional[str]) -> Optional[str]:
        if isinstance(meta, dict):
            desc = meta.get("description")
            if desc is not None:
                return str(desc)
        return str(fallback) if fallback else None

    def _extract_tags_from_meta(self, meta: Optional[Dict[str, Any]]) -> List[str]:
        if not isinstance(meta, dict):
            return []
        tags = meta.get("tags") or meta.get("keywords") or []
        if isinstance(tags, list):
            return [str(tag) for tag in tags if tag is not None]
        if isinstance(tags, str):
            return [tags]
        return []

    def _parse_meta(self, meta: Any) -> Optional[Dict[str, Any]]:
        if meta is None:
            return None
        if isinstance(meta, dict):
            return meta
        if isinstance(meta, str):
            try:
                parsed = json.loads(meta)
                return parsed if isinstance(parsed, dict) else None
            except json.JSONDecodeError:
                return None
        return None

    def _extract_bucket_from_registry(self, registry: str) -> str:
        if not registry:
            return ""
        if registry.startswith("s3://"):
            return registry.replace("s3://", "").split("/")[0]
        if registry.startswith("http://") or registry.startswith("https://"):
            return registry.split("//", 1)[-1].split("/")[0]
        return registry.split("/")[0]

    def _validate_package_creation_inputs(self, package_name: str, s3_uris: List[str]) -> None:
        import re

        if not package_name or not isinstance(package_name, str):
            raise ValidationError("Package name must be a non-empty string", {"field": "package_name"})

        if not re.match(r"^[^/]+/[^/]+$", package_name):
            raise ValidationError("Package name must be in 'user/package' format", {"field": "package_name"})

        if not s3_uris or not isinstance(s3_uris, list):
            raise ValidationError("S3 URIs must be a non-empty list", {"field": "s3_uris"})

        for i, s3_uri in enumerate(s3_uris):
            if not isinstance(s3_uri, str) or not s3_uri.startswith("s3://"):
                raise ValidationError(
                    f"Invalid S3 URI at index {i}: must start with 's3://'",
                    {"field": "s3_uris", "index": i, "uri": s3_uri},
                )
            parts = s3_uri[5:].split("/", 1)
            if len(parts) < 2 or not parts[0] or not parts[1]:
                raise ValidationError(
                    f"Invalid S3 URI at index {i}: must include bucket and key",
                    {"field": "s3_uris", "index": i, "uri": s3_uri},
                )

    def _validate_package_update_inputs(self, package_name: str, s3_uris: List[str], registry: str) -> None:
        import re

        if not package_name or not isinstance(package_name, str):
            raise ValidationError("Package name must be a non-empty string", {"field": "package_name"})

        if not re.match(r"^[^/]+/[^/]+$", package_name):
            raise ValidationError("Package name must be in 'user/package' format", {"field": "package_name"})

        if not registry or not isinstance(registry, str):
            raise ValidationError("Registry must be a non-empty string", {"field": "registry"})

        if not registry.startswith("s3://"):
            raise ValidationError("Registry must be an S3 URI starting with 's3://'", {"field": "registry"})

        if not s3_uris or not isinstance(s3_uris, list):
            raise ValidationError("S3 URIs must be a non-empty list", {"field": "s3_uris"})

        has_valid_uri = any(
            isinstance(uri, str) and uri.startswith("s3://") and "/" in uri[5:] and not uri.endswith("/")
            for uri in s3_uris
        )
        if not has_valid_uri:
            raise ValidationError(
                "No potentially valid S3 URIs found in list",
                {
                    "field": "s3_uris",
                    "note": "URIs must be strings starting with 's3://' and include bucket and key",
                },
            )

    def _extract_logical_key(self, s3_uri: str, auto_organize: bool = True) -> str:
        if auto_organize:
            parts = s3_uri[5:].split("/", 1)
            if len(parts) >= 2:
                return parts[1]
            return s3_uri.split("/")[-1]
        return s3_uri.split("/")[-1]

    def _build_catalog_url(self, package_name: str, registry: str) -> Optional[str]:
        try:
            if self._catalog_url:
                bucket = self._extract_bucket_from_registry(registry)
                base = normalize_url(self._catalog_url)
                return f"{base}/b/{bucket}/packages/{package_name}"
        except Exception:
            return None
        return None

    @contextmanager
    def _with_aws_credentials(self):
        old_env = {
            "AWS_ACCESS_KEY_ID": os.environ.get("AWS_ACCESS_KEY_ID"),
            "AWS_SECRET_ACCESS_KEY": os.environ.get("AWS_SECRET_ACCESS_KEY"),
            "AWS_SESSION_TOKEN": os.environ.get("AWS_SESSION_TOKEN"),
            "AWS_DEFAULT_REGION": os.environ.get("AWS_DEFAULT_REGION"),
        }
        try:
            session = self._auth_service.get_session()
            creds = session.get_credentials()
            if creds is None:
                yield
                return
            frozen = creds.get_frozen_credentials()
            os.environ["AWS_ACCESS_KEY_ID"] = frozen.access_key
            os.environ["AWS_SECRET_ACCESS_KEY"] = frozen.secret_key
            if frozen.token:
                os.environ["AWS_SESSION_TOKEN"] = frozen.token
            if session.region_name:
                os.environ["AWS_DEFAULT_REGION"] = session.region_name
            yield
        finally:
            for key, value in old_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

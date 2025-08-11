from typing import Any, Dict, List
import quilt3
import os
import tempfile
import datetime
import re
from mcp.server.fastmcp import FastMCP


# Initialize FastMCP server
mcp = FastMCP("quilt")

# Check if running in Lambda (read-only filesystem environment)
def is_lambda_environment() -> bool:
    """Check if we're running in AWS Lambda environment."""
    return bool(os.environ.get('AWS_LAMBDA_FUNCTION_NAME'))

@mcp.tool()
def auth_check() -> Dict[str, Any]:
    """
    Check Quilt authentication status and provide setup guidance.
    
    Returns:
        Dictionary with authentication status and setup instructions
    """
    try:
        # Check if logged in
        logged_in_url = quilt3.logged_in()
        
        if logged_in_url:
            return {
                "status": "authenticated",
                "catalog_url": logged_in_url,
                "message": "Successfully authenticated to Quilt catalog",
                "search_available": True
            }
        else:
            return {
                "status": "not_authenticated", 
                "message": "Not logged in to Quilt catalog",
                "search_available": False,
                "setup_instructions": [
                    "1. Configure catalog: quilt3 config https://open.quiltdata.com",
                    "2. Login: quilt3 login", 
                    "3. Follow the browser authentication flow"
                ]
            }
    except Exception as e:
        return {
            "status": "error",
            "error": f"Failed to check authentication: {str(e)}",
            "setup_instructions": [
                "1. Configure catalog: quilt3 config https://open.quiltdata.com",
                "2. Login: quilt3 login"
            ]
        }


@mcp.tool()
def filesystem_check() -> Dict[str, Any]:
    """
    Check if the current environment has filesystem write access needed for Quilt operations.
    
    Returns:
        Dictionary with filesystem access status and environment information
    """
    result = {
        "is_lambda": is_lambda_environment(),
        "home_directory": os.path.expanduser("~"),
        "temp_directory": tempfile.gettempdir(),
        "current_directory": os.getcwd()
    }
    
    # Test write access to home directory
    home_dir = os.path.expanduser("~")
    try:
        test_file = os.path.join(home_dir, ".quilt_test_write")
        with open(test_file, 'w') as f:
            f.write("test")
        os.remove(test_file)
        result["home_writable"] = True
        result["home_write_error"] = None
    except Exception as e:
        result["home_writable"] = False
        result["home_write_error"] = str(e)
    
    # Test write access to temp directory
    try:
        with tempfile.NamedTemporaryFile(delete=True) as f:
            f.write(b"test")
        result["temp_writable"] = True
        result["temp_write_error"] = None
    except Exception as e:
        result["temp_writable"] = False
        result["temp_write_error"] = str(e)
    
    # Overall assessment (ensure tools_available reflects capabilities)
    if result["home_writable"]:
        result["status"] = "full_access"
        result["message"] = "Full filesystem access available - all Quilt tools should work"
        result["tools_available"] = [
            "auth_check",
            "filesystem_check",
            "packages_list",
            "packages_search",
            "package_browse",
            "package_contents_search",
            "package_create",
            "package_add",
        ]
    elif result["temp_writable"]:
        result["status"] = "limited_access"
        result["message"] = "Limited filesystem access - Quilt tools may work with proper configuration"
        result["tools_available"] = [
            "auth_check",
            "filesystem_check",
            "packages_list",
            "package_browse",
            "package_contents_search",
        ]
        result["recommendation"] = "Try setting QUILT_CONFIG_DIR environment variable to /tmp"
    else:
        result["status"] = "read_only"
        result["message"] = "Read-only filesystem - most Quilt tools will not work"
        result["tools_available"] = ["auth_check", "filesystem_check"]
    
    return result


@mcp.tool()
def packages_list(
    registry: str = "s3://quilt-example",
    prefix: str = "",
    limit: int = 12,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """
    List packages in a Quilt registry with pagination support.
    
    Args:
        registry: S3 bucket URL for the Quilt registry
        prefix: Optional prefix to filter package names
        limit: Maximum number of packages to return (default: 12)
        offset: Number of packages to skip for pagination (default: 0)
    
    Returns:
        List of package metadata dictionaries with pagination info
    """
    try:
        packages = []
        all_package_names = []
        
        # First, get all package names and apply prefix filter
        for pkg_name in quilt3.list_packages(registry=registry):
            # Apply prefix filter if provided (skip empty strings)
            if prefix and prefix.strip() and not pkg_name.startswith(prefix):
                continue
            all_package_names.append(pkg_name)
        
        # Calculate pagination bounds
        total_packages = len(all_package_names)
        start_idx = offset
        end_idx = min(offset + limit, total_packages)
        
        # Process only the requested slice of packages
        paginated_names = all_package_names[start_idx:end_idx]
        
        for pkg_name in paginated_names:
            # Best-effort metadata fetch (ignore failures silently)
            meta: Dict[str, Any] | None = None
            try:
                pkg = quilt3.Package.browse(pkg_name, registry=registry)
                meta = pkg.meta  # type: ignore[attr-defined]
            except Exception:
                meta = None
            entry: Dict[str, Any] = {"name": pkg_name, "registry": registry}
            if meta:
                entry["metadata"] = meta
            packages.append(entry)
        
        # Add pagination metadata
        result = {
            "packages": packages,
            "pagination": {
                "total": total_packages,
                "offset": offset,
                "limit": limit,
                "returned": len(packages),
                "has_more": end_idx < total_packages
            }
        }
        
        return [result]
    except Exception as e:
        return [{"error": f"Failed to list packages: {str(e)}"}]


@mcp.tool()
def packages_search(
    query: str, 
    registry: str = "s3://quilt-example",
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Search for packages in a Quilt registry using text search.
    
    Args:
        query: Search terms to find packages
        registry: S3 bucket URL for the Quilt registry
        limit: Maximum number of results to return
    
    Returns:
        List of package metadata dictionaries
    """
    try:
        # Configure the registry for this search
        quilt3.config(navigator_url=registry.replace('s3://', 'https://') + '/')
        results = quilt3.search(query, limit=limit)
        return results
    except Exception as e:
        error_msg = str(e)
        
        # Check for authentication-related errors and provide helpful guidance
        if "Invalid URL" in error_msg and "No scheme supplied" in error_msg:
            return [{
                "error": "Search failed: Quilt catalog not configured",
                "solution": "Please run these commands to enable search:\n1. quilt3 config https://open.quiltdata.com\n2. quilt3 login",
                "details": f"Original error: {error_msg}"
            }]
        elif "401" in error_msg or "403" in error_msg or "Unauthorized" in error_msg or "authentication" in error_msg.lower():
            return [{
                "error": "Search failed: Authentication required",
                "solution": "Please login to the Quilt catalog:\n1. quilt3 config https://open.quiltdata.com\n2. quilt3 login",
                "details": f"Original error: {error_msg}"
            }]
        elif "search" in error_msg.lower() and "endpoint" in error_msg.lower():
            return [{
                "error": "Search failed: Search endpoint not available", 
                "solution": "This registry may not support search, or you need to login:\n1. quilt3 config https://open.quiltdata.com\n2. quilt3 login",
                "details": f"Original error: {error_msg}"
            }]
        else:
            # Generic error with suggestion
            return [{
                "error": f"Search failed: {error_msg}",
                "suggestion": "If this is an authentication issue, try: quilt3 login"
            }]


@mcp.tool()
def package_browse(
    package_name: str,
    registry: str = "s3://quilt-example",
    hash_or_tag: str = ""
) -> Dict[str, Any]:
    """
    Browse a specific package in a Quilt registry.
    
    Args:
        package_name: Name of the package to browse
        registry: S3 bucket URL for the Quilt registry
        hash_or_tag: Specific version hash or tag (optional, defaults to latest)
    
    Returns:
        Package metadata and file listing
    """
    try:
        if hash_or_tag:
            pkg = quilt3.Package.browse(package_name, registry=registry, top_hash=hash_or_tag)
        else:
            pkg = quilt3.Package.browse(package_name, registry=registry)

        # Get package structure
        files = []
        for key in pkg:
            try:
                entry = pkg[key]
                files.append({
                    "path": key,
                    "size": getattr(entry, "size", None),
                    "hash": getattr(entry, "hash", None),
                    "meta": getattr(entry, "meta", {})
                })
            except Exception as e:
                files.append({
                    "path": key,
                    "error": f"Failed to read entry: {str(e)}"
                })

        # Try to get metadata, but don't fail if it's not accessible
        try:  # metadata access is optional; fall back to empty dict
            metadata = pkg.meta
        except Exception:
            metadata = {}

        return {
            "name": package_name,
            "registry": registry,
            "hash": pkg.top_hash if hasattr(pkg, 'top_hash') else None,
            "metadata": metadata,
            "files": files
        }
    except Exception as e:
        return {"error": f"Failed to browse package '{package_name}': {str(e)}"}


@mcp.tool()
def package_contents_search(
    package_name: str,
    query: str,
    registry: str = "s3://quilt-example",
    hash_or_tag: str = ""
) -> List[Dict[str, Any]]:
    """
    Search within the contents of a specific package.
    
    Args:
        package_name: Name of the package to search within
        query: Search terms to find files/metadata
        registry: S3 bucket URL for the Quilt registry
        hash_or_tag: Specific version hash or tag (optional, defaults to latest)
    
    Returns:
        List of matching files and metadata
    """
    try:
        if hash_or_tag:
            pkg = quilt3.Package.browse(package_name, registry=registry, top_hash=hash_or_tag)
        else:
            pkg = quilt3.Package.browse(package_name, registry=registry)

        matches = []
        query_lower = query.lower()

        # Search in package metadata
        try:
            pkg_meta_str = str(pkg.meta).lower()
            if query_lower in pkg_meta_str:
                matches.append({
                    "type": "package_metadata",
                    "path": "",
                    "match_type": "metadata",
                    "metadata": pkg.meta
                })
        except Exception:
            pass  # Skip metadata search failures silently

        # Search in file paths and metadata
        for key in pkg:
            try:
                entry = pkg[key]

                # Search in file path
                if query_lower in key.lower():
                    matches.append({
                        "type": "file_path",
                        "path": key,
                        "match_type": "path",
                        "size": getattr(entry, "size", None),
                        "hash": getattr(entry, "hash", None),
                        "metadata": getattr(entry, "meta", {})
                    })

                # Search in file metadata
                file_meta = getattr(entry, "meta", {})
                if file_meta and query_lower in str(file_meta).lower():
                    matches.append({
                        "type": "file_metadata",
                        "path": key,
                        "match_type": "metadata",
                        "size": getattr(entry, "size", None),
                        "hash": getattr(entry, "hash", None),
                        "metadata": file_meta
                    })

            except Exception:
                continue

        return matches
    except Exception as e:
        return [{"error": f"Failed to search package contents: {str(e)}"}]


    # ---------------------------- Bucket / Object Tools ----------------------------

    def _normalize_bucket(uri_or_name: str) -> str:
        if uri_or_name.startswith("s3://"):
            return uri_or_name[5:].split('/', 1)[0]
        return uri_or_name


    @mcp.tool()
    def bucket_objects_list(
        bucket: str = "s3://quilt-example",
        prefix: str = "",
        max_keys: int = 100,
        continuation_token: str = ""
    ) -> Dict[str, Any]:
        """List raw S3 objects in a bucket (NOT Quilt packages).

        Args:
            bucket: Bucket name or s3://bucket URI
            prefix: Key prefix filter
            max_keys: Page size (1-1000, capped internally)
            continuation_token: Pass token from previous response for next page
        """
        import boto3  # local import for easier test patching

        bkt = _normalize_bucket(bucket)
        max_keys = max(1, min(max_keys, 1000))
        client = boto3.client("s3")
        params: Dict[str, Any] = {"Bucket": bkt, "MaxKeys": max_keys}
        if prefix:
            params["Prefix"] = prefix
        if continuation_token:
            params["ContinuationToken"] = continuation_token
        try:
            resp = client.list_objects_v2(**params)
        except Exception as e:
            return {"error": f"Failed to list objects: {e}", "bucket": bkt}
        objects: List[Dict[str, Any]] = []
        for item in resp.get("Contents", []) or []:
            objects.append({
                "key": item.get("Key"),
                "size": item.get("Size"),
                "last_modified": str(item.get("LastModified")),
                "etag": item.get("ETag"),
                "storage_class": item.get("StorageClass"),
            })
        return {
            "bucket": bkt,
            "prefix": prefix,
            "objects": objects,
            "truncated": resp.get("IsTruncated", False),
            "next_token": resp.get("NextContinuationToken", ""),
            "key_count": resp.get("KeyCount", len(objects)),
            "max_keys": max_keys,
        }


    @mcp.tool()
    def bucket_object_info(
        s3_uri: str,
    ) -> Dict[str, Any]:
        """Return HEAD/metadata information for a single S3 object."""
        import boto3
        if not s3_uri.startswith("s3://"):
            return {"error": "s3_uri must start with s3://"}
        without = s3_uri[5:]
        if '/' not in without:
            return {"error": "s3_uri must include a key after the bucket/"}
        bucket, key = without.split('/', 1)
        client = boto3.client("s3")
        try:
            head = client.head_object(Bucket=bucket, Key=key)
        except Exception as e:
            return {"error": f"Failed to head object: {e}", "bucket": bucket, "key": key}
        return {
            "bucket": bucket,
            "key": key,
            "size": head.get("ContentLength"),
            "content_type": head.get("ContentType"),
            "etag": head.get("ETag"),
            "last_modified": str(head.get("LastModified")),
            "metadata": head.get("Metadata", {}),
            "storage_class": head.get("StorageClass"),
            "cache_control": head.get("CacheControl"),
        }


    @mcp.tool()
    def bucket_object_text(
        s3_uri: str,
        max_bytes: int = 65536,
        encoding: str = "utf-8"
    ) -> Dict[str, Any]:
        """Download a small text object, returning (possibly truncated) content.

        Args:
            s3_uri: Full s3://bucket/key URI
            max_bytes: Maximum bytes to read
            encoding: Text encoding to decode
        """
        import boto3
        if not s3_uri.startswith("s3://"):
            return {"error": "s3_uri must start with s3://"}
        without = s3_uri[5:]
        if '/' not in without:
            return {"error": "s3_uri must include a key after the bucket/"}
        bucket, key = without.split('/', 1)
        client = boto3.client("s3")
        try:
            obj = client.get_object(Bucket=bucket, Key=key)
            body = obj["Body"].read(max_bytes + 1)
        except Exception as e:
            return {"error": f"Failed to get object: {e}", "bucket": bucket, "key": key}
        truncated = len(body) > max_bytes
        if truncated:
            body = body[:max_bytes]
        try:
            text = body.decode(encoding, errors="replace")
        except Exception as e:
            return {"error": f"Decode failed: {e}", "bucket": bucket, "key": key}
        return {
            "bucket": bucket,
            "key": key,
            "encoding": encoding,
            "truncated": truncated,
            "max_bytes": max_bytes,
            "text": text,
        }


# Tools are automatically registered when the module is imported
# due to the @mcp.tool decorators above


def _collect_objects_into_package(
    pkg: "quilt3.Package",
    s3_uris: List[str],
    flatten: bool,
    warnings: List[str]
) -> List[Dict[str, Any]]:
    """Internal helper to add S3 objects to a Package with collision avoidance."""
    added: List[Dict[str, Any]] = []
    for uri in s3_uris:
        if not uri.startswith("s3://"):
            warnings.append(f"Skipping non-S3 URI: {uri}")
            continue
        without_scheme = uri[5:]
        if '/' not in without_scheme:
            warnings.append(f"Skipping bucket-only URI (no key): {uri}")
            continue
        bucket, key = without_scheme.split('/', 1)
        if not key or key.endswith('/'):
            warnings.append(f"Skipping URI that appears to be a 'directory': {uri}")
            continue
        logical_path = os.path.basename(key) if flatten else key
        original_logical_path = logical_path
        counter = 1
        while logical_path in pkg:
            logical_path = f"{counter}_{original_logical_path}"
            counter += 1
        try:
            pkg.set(logical_path, uri)
            added.append({"logical_path": logical_path, "source": uri})
        except Exception as e:  # pragma: no cover - defensive
            warnings.append(f"Failed to add {uri}: {e}")
            continue
    return added


@mcp.tool()
def package_create(
    s3_uris: List[str] = None,  # type: ignore
    registry: str = "s3://quilt-example",
    metadata: Dict[str, Any] = None,  # type: ignore
    message: str = "Created via package_create tool",
    package_name: str = "",
    flatten: bool = True
) -> Dict[str, Any]:
    """Create and push a new Quilt package from existing S3 objects.

    Arguments mirror package_add for symmetry. Avoids mutable defaults by using None sentinels.
    """
    if s3_uris is None:
        s3_uris = []
    if metadata is None:
        metadata = {}
    warnings: List[str] = []
    if not s3_uris:
        return {"error": "No S3 URIs provided"}
    # Autogenerate name if missing
    if not package_name:
        ts = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        safe_first = re.sub(r"[^A-Za-z0-9_.-]", "-", os.path.basename(s3_uris[0].rstrip('/')) or "data")[:40]
        package_name = f"pkg-{safe_first}-{ts}"
    pkg = quilt3.Package()
    added = _collect_objects_into_package(pkg, s3_uris, flatten, warnings)
    if not added:
        return {"error": "No valid S3 objects were added to the package", "warnings": warnings}
    if metadata:
        try:
            pkg.set_meta(metadata)
        except Exception as e:  # pragma: no cover
            warnings.append(f"Failed to set metadata: {e}")
    try:
        top_hash = pkg.push(package_name, registry=registry, message=message)
    except Exception as e:
        return {"error": f"Failed to push package: {e}", "package_name": package_name, "warnings": warnings}
    return {
        "status": "success",
        "action": "created",
        "package_name": package_name,
        "registry": registry,
        "top_hash": top_hash,
        "entries_added": len(added),
        "files": added,
        "metadata_provided": bool(metadata),
        "warnings": warnings,
        "message": message,
    }


@mcp.tool()
def package_add(
    s3_uris: List[str] = None,  # type: ignore
    registry: str = "s3://quilt-example",
    metadata: Dict[str, Any] = None,  # type: ignore
    message: str = "Added objects via package_add tool",
    package_name: str = "",
    flatten: bool = True
) -> Dict[str, Any]:
    """Add S3 objects to an existing Quilt package (creates new revision).

    package_name is required; if omitted an error is returned (use package_new instead).
    """
    if s3_uris is None:
        s3_uris = []
    if metadata is None:
        metadata = {}
    if not s3_uris:
        return {"error": "No S3 URIs provided"}
    if not package_name:
        return {"error": "package_name is required for package_add"}
    warnings: List[str] = []
    # Browse existing package
    try:
        existing_pkg = quilt3.Package.browse(package_name, registry=registry)
    except Exception as e:
        return {"error": f"Failed to browse existing package '{package_name}': {e}"}
    # Start a new package object and copy over existing entries (shallow copy)
    new_pkg = quilt3.Package()
    try:
        for key in existing_pkg:
            entry = existing_pkg[key]
            try:
                source_uri = getattr(entry, "physical_keys", [None])[0]
                if source_uri and source_uri.startswith("s3://"):
                    new_pkg.set(key, source_uri, meta=getattr(entry, "meta", None))
                else:  # fallback: reference by entry logical path may not be supported, so skip
                    warnings.append(f"Skipped entry without S3 source: {key}")
            except Exception as inner_e:  # pragma: no cover
                warnings.append(f"Failed to copy entry {key}: {inner_e}")
    except Exception as e:  # pragma: no cover
        warnings.append(f"Failed iterating existing package: {e}")
    # Add new objects
    added = _collect_objects_into_package(new_pkg, s3_uris, flatten, warnings)
    if not added:
        return {"error": "No new S3 objects were added", "warnings": warnings}
    # Merge metadata if provided: overlay onto existing package metadata
    if metadata:
        try:
            # Combine dicts (metadata overwrites existing keys)
            combined = {}
            try:
                combined.update(existing_pkg.meta)  # type: ignore[arg-type]
            except Exception:
                pass
            combined.update(metadata)
            new_pkg.set_meta(combined)
        except Exception as e:  # pragma: no cover
            warnings.append(f"Failed to set merged metadata: {e}")
    try:
        top_hash = new_pkg.push(package_name, registry=registry, message=message)
    except Exception as e:
        return {"error": f"Failed to push updated package: {e}", "package_name": package_name, "warnings": warnings}
    return {
        "status": "success",
        "action": "updated",
        "package_name": package_name,
        "registry": registry,
        "top_hash": top_hash,
        "new_entries_added": len(added),
        "files_added": added,
        "warnings": warnings,
        "message": message,
        "metadata_added": bool(metadata),
    }

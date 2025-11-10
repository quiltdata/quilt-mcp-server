"""Authentication and filesystem access tools."""

from __future__ import annotations

from typing import Annotated, Optional
from urllib.parse import quote

from pydantic import Field

from quilt_mcp.models import (
    CatalogUriError,
    CatalogUriSuccess,
    CatalogUrlError,
    CatalogUrlSuccess,
)
from quilt_mcp.services.auth_metadata import (
    _extract_bucket_from_registry,
    _extract_catalog_name_from_url,
    _get_catalog_host_from_config,
    _get_catalog_info,
    auth_status as _auth_status,
    catalog_info as _catalog_info,
    configure_catalog as _configure_catalog,
    filesystem_status as _filesystem_status,
)


def catalog_url(
    registry: Annotated[
        str,
        Field(
            description="Target registry as S3 URI or bare bucket name",
            examples=["s3://my-bucket", "my-bucket"],
        ),
    ],
    package_name: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Optional package name in namespace/name format for direct package view",
            examples=["team/dataset", "user/analysis"],
        ),
    ] = None,
    path: Annotated[
        str,
        Field(
            default="",
            description="Optional path inside the bucket or package for deep links",
            examples=["data/metrics.csv", "reports/"],
        ),
    ] = "",
    catalog_host: Annotated[
        str,
        Field(
            default="",
            description="Optional override for catalog host (auto-detected if not provided)",
            examples=["catalog.example.com", "https://catalog.example.com"],
        ),
    ] = "",
) -> CatalogUrlSuccess | CatalogUrlError:
    """Generate Quilt catalog URL - Quilt authentication and catalog navigation workflows

    WORKFLOW:
        1. Detect or accept the catalog host and assemble the fully qualified URL.
        2. Return structured metadata (bucket, view type, path) so follow-up tools can reason about the link.
        3. Pair with ``auth.catalog_uri`` when the user also needs the Quilt+ URI representation.

    Args:
        registry: Target registry, either ``s3://bucket`` or bare bucket name.
        package_name: Optional ``namespace/package`` for direct package view navigation.
        path: Optional path inside the bucket or package for deep links (e.g., ``data/metrics.csv``).
        catalog_host: Optional override for the catalog host when auto-detection is unavailable.

    Returns:
        CatalogUrlSuccess with URL metadata when successful, or CatalogUrlError on failure.

        Success response:
        {
            "success": True,
            "status": "success",
            "catalog_url": "https://catalog.example.com/b/bucket/packages/ns/pkg/tree/latest/data",
            "view_type": "package",
            "bucket": "bucket",
            "package_name": "ns/pkg",
            "path": "data",
            "catalog_host": "catalog.example.com"
        }

    Next step:
        Share ``result.catalog_url`` with the user or feed it into the next navigation helper (for example
        ``auth.catalog_uri`` or messaging back to the MCP client).

    Example:
        ```python
        from quilt_mcp.tools import catalog

        result = catalog.catalog_url(
            registry="s3://example-bucket",
            package_name="team/forecast",
            path="reports/summary.pdf",
        )
        if isinstance(result, CatalogUrlSuccess):
            print(result.catalog_url)
        ```
    """
    try:
        bucket = _extract_bucket_from_registry(registry)

        # Auto-detect catalog host if not provided
        host = catalog_host if catalog_host else ""
        if not host:
            detected_host = _get_catalog_host_from_config()
            if not detected_host:
                return CatalogUrlError(
                    error="Could not determine catalog host. Please provide catalog_host parameter or ensure Quilt is configured."
                )
            host = detected_host

        # Ensure catalog_host has https protocol
        if not host.startswith("http"):
            host = f"https://{host}"

        # Build URL based on whether it's a package or bucket view
        if package_name:
            # Package view: https://{catalog_host}/b/{bucket}/packages/{package_name}/tree/latest/{path}
            url_parts = [
                host.rstrip("/"),
                "b",
                bucket,
                "packages",
                package_name,
                "tree",
                "latest",
            ]
            if path:
                # URL encode the path components
                path_parts = [quote(part, safe="") for part in path.strip("/").split("/") if part]
                url_parts.extend(path_parts)
            url = "/".join(url_parts)
            view_type = "package"
        else:
            # Bucket view: https://{catalog_host}/b/{bucket}/tree/{path}
            url_parts = [host.rstrip("/"), "b", bucket, "tree"]
            if path:
                # URL encode the path components
                path_parts = [quote(part, safe="") for part in path.strip("/").split("/") if part]
                url_parts.extend(path_parts)
            url = "/".join(url_parts)
            view_type = "bucket"

        # Clean catalog host for response
        clean_catalog_host = host.replace("https://", "").replace("http://", "") if host else None

        return CatalogUrlSuccess(
            catalog_url=url,
            view_type=view_type,  # type: ignore[arg-type]  # view_type is runtime-determined Literal
            bucket=bucket,
            package_name=package_name,
            path=path,
            catalog_host=clean_catalog_host,
        )

    except Exception as e:
        return CatalogUrlError(error=f"Failed to generate catalog URL: {e}")


def catalog_uri(
    registry: Annotated[
        str,
        Field(
            description="Registry backing the URI as S3 URI or bucket name",
            examples=["s3://my-bucket", "my-bucket"],
        ),
    ],
    package_name: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Optional package name in namespace/name format",
        ),
    ] = None,
    path: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Optional path fragment to include in the URI",
        ),
    ] = None,
    top_hash: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Optional immutable package hash to lock the reference",
        ),
    ] = None,
    tag: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Optional human-friendly tag (ignored when top_hash is provided)",
        ),
    ] = None,
    catalog_host: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Optional catalog hostname hint to embed in the fragment",
        ),
    ] = None,
) -> CatalogUriSuccess | CatalogUriError:
    """Build Quilt+ URI - Quilt authentication and catalog navigation workflows

    WORKFLOW:
        1. Normalize the registry to ``quilt+s3://{bucket}``.
        2. Append package fragments (``package``, ``path``, ``catalog``) based on the supplied context.
        3. Return the URI so downstream tools or clients can reference the same package version consistently.

    Args:
        registry: Registry backing the URI (``s3://bucket`` or bucket name).
        package_name: Optional ``namespace/package`` for linking to a specific package.
        path: Optional package or bucket path fragment to include in the URI.
        top_hash: Optional immutable package hash to lock the reference to a revision.
        tag: Optional human-friendly tag (ignored when ``top_hash`` is provided).
        catalog_host: Optional catalog hostname hint to embed in the fragment.

    Returns:
        CatalogUriSuccess with the computed Quilt+ URI when successful, or CatalogUriError on failure.

        Success response:
        {
            "success": True,
            "status": "success",
            "quilt_plus_uri": "quilt+s3://example-bucket#package=team/pkg@1111abcd&path=data/raw",
            "bucket": "example-bucket",
            "package_name": "team/pkg",
            "path": "data/raw",
            "top_hash": "1111abcd",
            "tag": null,
            "catalog_host": "catalog.example.com"
        }

    Next step:
        Combine ``result.quilt_plus_uri`` with ``catalog.catalog_url`` when the user needs both shareable link formats,
        or return it directly so the client can persist the protocol URI.

    Example:
        ```python
        from quilt_mcp.tools import catalog

        result = catalog.catalog_uri(
            registry="s3://example-bucket",
            package_name="team/forecast",
            top_hash="1111abcd",
            path="models/best.pkl",
        )
        if isinstance(result, CatalogUriSuccess):
            print(result.quilt_plus_uri)
        ```
    """
    try:
        bucket = _extract_bucket_from_registry(registry)

        # Start building URI: quilt+s3://bucket
        uri_parts = [f"quilt+s3://{bucket}"]

        # Build fragment parameters
        fragment_params = []

        if package_name:
            # Add version specifier to package name if provided
            package_spec = package_name
            if top_hash:
                package_spec += f"@{top_hash}"
            elif tag:
                package_spec += f":{tag}"
            fragment_params.append(f"package={package_spec}")

        if path:
            fragment_params.append(f"path={path}")

        # Auto-detect catalog host if not provided
        host = catalog_host
        if not host:
            host = _get_catalog_host_from_config()

        if host:
            # Remove protocol if present
            clean_host = host.replace("https://", "").replace("http://", "")
            fragment_params.append(f"catalog={clean_host}")

        # Add fragment if we have any parameters
        if fragment_params:
            uri_parts.append("#" + "&".join(fragment_params))

        quilt_plus_uri = "".join(uri_parts)

        # Clean catalog host for response
        clean_catalog_host = host.replace("https://", "").replace("http://", "") if host else None

        return CatalogUriSuccess(
            quilt_plus_uri=quilt_plus_uri,
            bucket=bucket,
            package_name=package_name,
            path=path,
            top_hash=top_hash,
            tag=tag,
            catalog_host=clean_catalog_host,
        )

    except Exception as e:
        return CatalogUriError(error=f"Failed to generate Quilt+ URI: {e}")


# The following functions delegate to service layer and don't need Pydantic migration
# as they simply pass through dict responses from the service layer


def catalog_configure(catalog_url: str) -> dict:
    """Configure Quilt catalog URL - Quilt authentication and catalog navigation workflows

    WORKFLOW:
        1. Map friendly catalog names (demo, sandbox, open) to their canonical URLs if applicable.
        2. Validate that the provided/resolved URL includes an HTTP(S) scheme.
        3. Persist the catalog setting through ``QuiltService.set_config``.
        4. Return confirmation and recommended actions (login, status check, exploration tools).

    Args:
        catalog_url: Full catalog URL (e.g., ``https://demo.quiltdata.com``) or friendly name (e.g., ``demo``).

    Returns:
        Dict with ``status``, the normalized catalog URL, and follow-up instructions for login verification.

        Response format:
        {
            "status": "success",
            "catalog_url": "https://demo.quiltdata.com",
            "configured_url": "https://demo.quiltdata.com",
            "next_steps": ["Login with: quilt3 login", "..."]
        }

    Next step:
        Run ``quilt3 login`` (or instruct the user to do so) and confirm connectivity via ``auth.auth_status()``.

    Example:
        ```python
        from quilt_mcp.tools import catalog

        # Using a full URL
        outcome = catalog.catalog_configure("https://nightly.quilttest.com")

        # Using a friendly name
        outcome = catalog.catalog_configure("demo")

        if outcome["status"] == "success":
            login_hint = outcome["next_steps"][0]
        ```
    """
    return _configure_catalog(catalog_url)


def catalog_info() -> dict:
    """Retrieve catalog metadata - Quilt authentication introspection workflows

    Returns:
        Dict describing the active Quilt catalog: authentication status, catalog URLs, region, and
        tabulator configuration when available.

    Next step:
        Feed the returned metadata into downstream helpers (for example, Tabulator queries or catalog URL builders)
        or surface the catalog URLs directly to the end user.

    Example:
        ```python
        from quilt_mcp.tools import catalog

        metadata = catalog.catalog_info()
        if metadata.get("status") == "success":
            print(metadata["catalog_url"])
        ```
    """
    return _catalog_info()


def auth_status() -> dict:
    """Check Quilt authentication status - Quilt authentication introspection workflows

    Returns:
        Dict capturing whether the user is logged in, which profile is active, and any URLs that require sign-in.

    Next step:
        Relay the status to the user or trigger a follow-up action (such as prompting a login) when `is_authenticated`
        is False.

    Example:
        ```python
        from quilt_mcp.tools import catalog

        status = catalog.auth_status()
        if not status.get("is_authenticated"):
            print("Next step: run quilt3 login")
        ```
    """
    return _auth_status()


def filesystem_status() -> dict:
    """Inspect filesystem access - Quilt authentication and local environment workflows

    Returns:
        Dict summarizing filesystem accessibility, including whether Quilt can read and write to configured paths.

    Next step:
        Communicate the readiness back to the user or adjust follow-up operations if local filesystem access is
        restricted.

    Example:
        ```python
        from quilt_mcp.tools import catalog

        fs = catalog.filesystem_status()
        print(f"Next step: confirm access to {fs['root_path']}")
        ```
    """
    return _filesystem_status()

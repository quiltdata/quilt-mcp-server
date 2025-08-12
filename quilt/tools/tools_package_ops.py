from __future__ import annotations
from typing import Any, Dict, List
import os, datetime, re
import quilt3
from .. import mcp
from ..constants import DEFAULT_REGISTRY

# Internal helper replicated from monolith (will be removed there)

def _collect_objects_into_package(pkg: "quilt3.Package", s3_uris: List[str], flatten: bool, warnings: List[str]) -> List[Dict[str, Any]]:
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
        except Exception as e:
            warnings.append(f"Failed to add {uri}: {e}")
            continue
    return added

@mcp.tool()
def package_create(s3_uris: List[str] = [], registry: str = DEFAULT_REGISTRY, metadata: Dict[str, Any] = {}, message: str = "Created via package_create tool", package_name: str = "", flatten: bool = True) -> Dict[str, Any]:
    if not s3_uris: s3_uris = []
    if not metadata: metadata = {}
    warnings: List[str] = []
    if not s3_uris: return {"error": "No S3 URIs provided"}
    if not package_name:
        ts = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        safe_first = re.sub(r"[^A-Za-z0-9_.-]", "-", os.path.basename(s3_uris[0].rstrip('/')) or "data")[:40]
        package_name = f"pkg-{safe_first}-{ts}"
    pkg = quilt3.Package()
    added = _collect_objects_into_package(pkg, s3_uris, flatten, warnings)
    if not added: return {"error": "No valid S3 objects were added to the package", "warnings": warnings}
    if metadata:
        try: pkg.set_meta(metadata)
        except Exception as e: warnings.append(f"Failed to set metadata: {e}")
    try: top_hash = pkg.push(package_name, registry=registry, message=message)
    except Exception as e: return {"error": f"Failed to push package: {e}", "package_name": package_name, "warnings": warnings}
    return {"status": "success", "action": "created", "package_name": package_name, "registry": registry, "top_hash": top_hash, "entries_added": len(added), "files": added, "metadata_provided": bool(metadata), "warnings": warnings, "message": message}

@mcp.tool()
def package_update(s3_uris: List[str] = [], registry: str = DEFAULT_REGISTRY, metadata: Dict[str, Any] = {}, message: str = "Added objects via package_update tool", package_name: str = "", flatten: bool = True) -> Dict[str, Any]:
    if not s3_uris: s3_uris = []
    if not metadata: metadata = {}
    if not s3_uris: return {"error": "No S3 URIs provided"}
    if not package_name: return {"error": "package_name is required for package_update"}
    warnings: List[str] = []
    try: existing_pkg = quilt3.Package.browse(package_name, registry=registry)
    except Exception as e: return {"error": f"Failed to browse existing package '{package_name}': {e}", "package_name": package_name}
    new_pkg = quilt3.Package()
    try:
        for key in existing_pkg:
            entry = existing_pkg[key]
            try:
                source_uri = getattr(entry, "physical_keys", [None])[0]
                if source_uri and source_uri.startswith("s3://"):
                    new_pkg.set(key, source_uri, meta=getattr(entry, "meta", None))
                else:
                    warnings.append(f"Skipped entry without S3 source: {key}")
            except Exception as inner_e:
                warnings.append(f"Failed to copy entry {key}: {inner_e}")
    except Exception as e:
        warnings.append(f"Failed iterating existing package: {e}")
    added = _collect_objects_into_package(new_pkg, s3_uris, flatten, warnings)
    if not added: return {"error": "No new S3 objects were added", "warnings": warnings}
    if metadata:
        try:
            combined = {}
            try: combined.update(existing_pkg.meta)  # type: ignore[arg-type]
            except Exception: pass
            combined.update(metadata)
            new_pkg.set_meta(combined)
        except Exception as e: warnings.append(f"Failed to set merged metadata: {e}")
    try: top_hash = new_pkg.push(package_name, registry=registry, message=message)
    except Exception as e: return {"error": f"Failed to push updated package: {e}", "package_name": package_name, "warnings": warnings}
    return {"status": "success", "action": "updated", "package_name": package_name, "registry": registry, "top_hash": top_hash, "new_entries_added": len(added), "files_added": added, "warnings": warnings, "message": message, "metadata_added": bool(metadata)}

@mcp.tool()
def package_delete(package_name: str, registry: str = DEFAULT_REGISTRY) -> Dict[str, Any]:
    """Delete a package from the registry."""
    if not package_name:
        return {"error": "package_name is required for package deletion"}
    
    try:
        quilt3.delete_package(package_name, registry=registry)
        return {
            "status": "success", 
            "action": "deleted", 
            "package_name": package_name, 
            "registry": registry,
            "message": f"Package {package_name} deleted successfully"
        }
    except Exception as e:
        return {
            "error": f"Failed to delete package '{package_name}': {e}", 
            "package_name": package_name,
            "registry": registry
        }

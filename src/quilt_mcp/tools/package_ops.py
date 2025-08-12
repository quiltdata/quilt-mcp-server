from __future__ import annotations
from typing import Any, Dict, List
import os
import quilt3
from ..server import mcp
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
def package_create(package_name: str, s3_uris: List[str], registry: str = DEFAULT_REGISTRY, metadata: Dict[str, Any] = {}, message: str = "Created via package_create tool", flatten: bool = True) -> Dict[str, Any]:
    """Create a new Quilt package from S3 objects.
    
    Args:
        package_name: Name for the new package (e.g., "username/package-name")
        s3_uris: List of S3 URIs to include in the package
        registry: Quilt registry URL (default: DEFAULT_REGISTRY)
        metadata: Optional metadata dict to attach to the package
        message: Commit message for package creation (default: "Created via package_create tool")
        flatten: Use only filenames as logical paths instead of full S3 keys (default: True)
    
    Returns:
        Dict with creation status, package details, and list of files added.
    """
    if not metadata: metadata = {}
    warnings: List[str] = []
    
    # Debug logging
    import json
    debug_info = {
        "package_name": package_name,
        "s3_uris": s3_uris,
        "s3_uris_type": type(s3_uris).__name__,
        "s3_uris_len": len(s3_uris) if s3_uris else "None/Empty"
    }
    print(f"DEBUG package_create input: {json.dumps(debug_info, indent=2)}")
    
    if not s3_uris: return {"error": "No S3 URIs provided", "debug": debug_info}
    if not package_name: return {"error": "Package name is required", "debug": debug_info}
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
def package_update(package_name: str, s3_uris: List[str], registry: str = DEFAULT_REGISTRY, metadata: Dict[str, Any] = {}, message: str = "Added objects via package_update tool", flatten: bool = True) -> Dict[str, Any]:
    """Update an existing Quilt package by adding new S3 objects.
    
    Args:
        package_name: Name of the existing package to update (e.g., "username/package-name")
        s3_uris: List of S3 URIs to add to the package
        registry: Quilt registry URL (default: DEFAULT_REGISTRY)
        metadata: Optional metadata dict to merge with existing package metadata
        message: Commit message for package update (default: "Added objects via package_update tool")
        flatten: Use only filenames as logical paths instead of full S3 keys (default: True)
    
    Returns:
        Dict with update status, package details, and list of files added.
    """
    if not metadata: metadata = {}
    if not s3_uris: return {"error": "No S3 URIs provided"}
    if not package_name: return {"error": "package_name is required for package_update"}
    warnings: List[str] = []
    try: existing_pkg = quilt3.Package.browse(package_name, registry=registry)
    except Exception as e: return {"error": f"Failed to browse existing package '{package_name}': {e}", "package_name": package_name}
    # Use the existing package as the base instead of creating a new one
    updated_pkg = existing_pkg
    added = _collect_objects_into_package(updated_pkg, s3_uris, flatten, warnings)
    if not added: return {"error": "No new S3 objects were added", "warnings": warnings}
    if metadata:
        try:
            combined = {}
            try: combined.update(existing_pkg.meta)  # type: ignore[arg-type]
            except Exception: pass
            combined.update(metadata)
            updated_pkg.set_meta(combined)
        except Exception as e: warnings.append(f"Failed to set merged metadata: {e}")
    try: top_hash = updated_pkg.push(package_name, registry=registry, message=message)
    except Exception as e: return {"error": f"Failed to push updated package: {e}", "package_name": package_name, "warnings": warnings}
    return {"status": "success", "action": "updated", "package_name": package_name, "registry": registry, "top_hash": top_hash, "new_entries_added": len(added), "files_added": added, "warnings": warnings, "message": message, "metadata_added": bool(metadata)}

@mcp.tool()
def package_delete(package_name: str, registry: str = DEFAULT_REGISTRY) -> Dict[str, Any]:
    """Delete a Quilt package from the registry.
    
    Args:
        package_name: Name of the package to delete (e.g., "username/package-name")
        registry: Quilt registry URL (default: DEFAULT_REGISTRY)
    
    Returns:
        Dict with deletion status and confirmation message.
    """
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

from __future__ import annotations
from typing import Any, Dict
import quilt3
from .. import mcp, is_lambda_environment
import os, tempfile

@mcp.tool()
def auth_check() -> Dict[str, Any]:
    try:
        logged_in_url = quilt3.logged_in()
        if logged_in_url:
            return {"status": "authenticated", "catalog_url": logged_in_url, "message": "Successfully authenticated to Quilt catalog", "search_available": True}
        return {"status": "not_authenticated", "message": "Not logged in to Quilt catalog", "search_available": False, "setup_instructions": ["1. Configure catalog: quilt3 config https://open.quiltdata.com", "2. Login: quilt3 login", "3. Follow the browser authentication flow"]}
    except Exception as e:
        return {"status": "error", "error": f"Failed to check authentication: {e}", "setup_instructions": ["1. Configure catalog: quilt3 config https://open.quiltdata.com", "2. Login: quilt3 login"]}

@mcp.tool()
def filesystem_check() -> Dict[str, Any]:
    result: Dict[str, Any] = {"is_lambda": is_lambda_environment(), "home_directory": os.path.expanduser("~"), "temp_directory": tempfile.gettempdir(), "current_directory": os.getcwd()}
    # Home write
    try:
        test_file = os.path.join(result["home_directory"], ".quilt_test_write")
        with open(test_file, 'w') as f: f.write("test")
        os.remove(test_file); result["home_writable"] = True
    except Exception as e:
        result["home_writable"] = False; result["home_write_error"] = str(e)
    # Temp write
    try:
        import tempfile as _tf
        with _tf.NamedTemporaryFile(delete=True) as f: f.write(b"test")
        result["temp_writable"] = True
    except Exception as e:
        result["temp_writable"] = False; result["temp_write_error"] = str(e)
    if result.get("home_writable"):
        result.update(status="full_access", message="Full filesystem access available - all Quilt tools should work", tools_available=["auth_check","filesystem_check","packages_list","packages_search","package_browse","package_contents_search","package_create","package_add","bucket_objects_list","bucket_object_info","bucket_object_text","bucket_objects_put","bucket_object_fetch"])
    elif result.get("temp_writable"):
        result.update(status="limited_access", message="Limited filesystem access - Quilt tools may work with proper configuration", tools_available=["auth_check","filesystem_check","packages_list","package_browse","package_contents_search"], recommendation="Try setting QUILT_CONFIG_DIR environment variable to /tmp")
    else:
        result.update(status="read_only", message="Read-only filesystem - most Quilt tools will not work", tools_available=["auth_check","filesystem_check"])
    return result

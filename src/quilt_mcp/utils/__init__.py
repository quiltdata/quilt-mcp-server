"""Shared utilities for Quilt MCP tools."""

# Re-export common utilities for backward compatibility
from quilt_mcp.utils.common import (
    parse_s3_uri,
    normalize_url,
    graphql_endpoint,
    get_dns_name_from_url,
    fix_url,
    generate_signed_url,
    create_mcp_server,
    get_tool_modules,
    register_tools,
    get_s3_client,
    get_sts_client,
    validate_package_name,
    format_error_response,
    suppress_stdout,
    create_configured_server,
    build_http_app,
    run_server,
    get_jwt_from_auth_config,
    extract_jwt_claims_unsafe,
)

# Re-export formatting utilities
from quilt_mcp.utils.formatting import (
    format_as_table,
    should_use_table_format,
    enhance_result_with_table_format,
    format_athena_results_as_table,
    format_users_as_table,
    format_roles_as_table,
    format_tabulator_results_as_table,
)

# Re-export validators for backward compatibility
from quilt_mcp.utils.validators import (
    validate_package_structure,
    validate_metadata_compliance,
    validate_package_naming,
)

__all__ = [
    # Common utilities
    "parse_s3_uri",
    "normalize_url",
    "graphql_endpoint",
    "get_dns_name_from_url",
    "fix_url",
    "generate_signed_url",
    "create_mcp_server",
    "get_tool_modules",
    "register_tools",
    "get_s3_client",
    "get_sts_client",
    "validate_package_name",
    "format_error_response",
    "suppress_stdout",
    "create_configured_server",
    "build_http_app",
    "run_server",
    "get_jwt_from_auth_config",
    "extract_jwt_claims_unsafe",
    # Formatting utilities
    "format_as_table",
    "should_use_table_format",
    "enhance_result_with_table_format",
    "format_athena_results_as_table",
    "format_users_as_table",
    "format_roles_as_table",
    "format_tabulator_results_as_table",
    # Validators
    "validate_package_structure",
    "validate_metadata_compliance",
    "validate_package_naming",
]

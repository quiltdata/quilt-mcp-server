"""
Test Scenarios for MCP Tool Optimization

This module provides comprehensive test scenarios that simulate real-world
usage patterns for MCP tool optimization and performance analysis.
"""

from typing import Dict, Any, List
from .testing import Scenario, ScenarioStep, ScenarioType


def create_package_creation_scenarios() -> List[Scenario]:
    """Create test scenarios for package creation workflows."""

    scenarios = []

    # Basic package creation workflow
    basic_scenario = Scenario(
        name="basic_package_creation",
        description="Create a simple package from S3 files",
        scenario_type=ScenarioType.PACKAGE_CREATION,
        expected_total_time=15.0,
        expected_call_count=4,
        steps=[
            ScenarioStep(
                tool_name="auth_status",
                args={},
                description="Check authentication status",
            ),
            ScenarioStep(
                tool_name="bucket_objects_list",
                args={"bucket": "s3://quilt-sandbox-bucket", "max_keys": 10},
                description="List available files",
            ),
            ScenarioStep(
                tool_name="create_package_enhanced",
                args={
                    "name": "test/basic-package",
                    "files": ["s3://quilt-sandbox-bucket/sample.csv"],
                    "description": "Test package for optimization",
                },
                description="Create package with enhanced tool",
            ),
            ScenarioStep(
                tool_name="package_validate",
                args={"package_name": "test/basic-package"},
                description="Validate created package",
            ),
        ],
        success_criteria=["package_created", "validation_passed"],
        tags=["basic", "package_creation", "validation"],
    )
    scenarios.append(basic_scenario)

    # Bulk package creation from S3
    bulk_scenario = Scenario(
        name="bulk_package_from_s3",
        description="Create package from entire S3 bucket/prefix",
        scenario_type=ScenarioType.PACKAGE_CREATION,
        expected_total_time=30.0,
        expected_call_count=5,
        steps=[
            ScenarioStep(
                tool_name="auth_status",
                args={},
                description="Check authentication status",
            ),
            ScenarioStep(
                tool_name="bucket_objects_list",
                args={
                    "bucket": "s3://quilt-sandbox-bucket",
                    "prefix": "data/",
                    "max_keys": 100,
                },
                description="List files in data directory",
            ),
            ScenarioStep(
                tool_name="aws_permissions_discover",
                args={"check_buckets": ["quilt-sandbox-bucket"]},
                description="Verify permissions for bulk operation",
            ),
            ScenarioStep(
                tool_name="package_create_from_s3",
                args={
                    "source_bucket": "s3://quilt-sandbox-bucket",
                    "package_name": "test/bulk-package",
                    "source_prefix": "data/",
                    "description": "Bulk package from S3 data",
                },
                description="Create package from S3 bucket",
            ),
            ScenarioStep(
                tool_name="package_browse",
                args={"package_name": "test/bulk-package", "recursive": True},
                description="Browse created package structure",
            ),
        ],
        success_criteria=["package_created", "files_organized", "structure_valid"],
        tags=["bulk", "s3_import", "organization"],
    )
    scenarios.append(bulk_scenario)

    return scenarios


def create_data_discovery_scenarios() -> List[Scenario]:
    """Create test scenarios for data discovery workflows."""

    scenarios = []

    # Package exploration workflow
    exploration_scenario = Scenario(
        name="package_exploration",
        description="Discover and explore available packages",
        scenario_type=ScenarioType.DATA_DISCOVERY,
        expected_total_time=10.0,
        expected_call_count=4,
        steps=[
            ScenarioStep(
                tool_name="packages_list",
                args={"limit": 20},
                description="List available packages",
            ),
            ScenarioStep(
                tool_name="unified_search",
                args={"query": "dataset", "limit": 10, "scope": "catalog"},
                description="Search for dataset packages",
            ),
            ScenarioStep(
                tool_name="package_browse",
                args={"package_name": "examples/wellcome-data", "recursive": False},
                description="Browse package structure",
            ),
            ScenarioStep(
                tool_name="unified_search",
                args={"query": "*.csv", "scope": "package", "target": "examples/wellcome-data"},
                description="Search for CSV files in package",
            ),
        ],
        success_criteria=["packages_found", "structure_explored", "files_located"],
        tags=["discovery", "exploration", "search"],
    )
    scenarios.append(exploration_scenario)

    # Bucket exploration workflow
    bucket_exploration_scenario = Scenario(
        name="bucket_exploration",
        description="Explore S3 bucket contents and structure",
        scenario_type=ScenarioType.DATA_DISCOVERY,
        expected_total_time=8.0,
        expected_call_count=3,
        steps=[
            ScenarioStep(
                tool_name="bucket_objects_list",
                args={"bucket": "s3://quilt-sandbox-bucket", "max_keys": 50},
                description="List bucket objects",
            ),
            ScenarioStep(
                tool_name="unified_search",
                args={"query": "*.json", "scope": "bucket", "target": "s3://quilt-sandbox-bucket"},
                description="Search for JSON files",
            ),
            ScenarioStep(
                tool_name="bucket_object_info",
                args={"s3_uri": "s3://quilt-sandbox-bucket/README.md"},
                description="Get object metadata",
            ),
        ],
        success_criteria=["objects_listed", "files_found", "metadata_retrieved"],
        tags=["bucket", "exploration", "metadata"],
    )
    scenarios.append(bucket_exploration_scenario)

    return scenarios


def create_athena_querying_scenarios() -> List[Scenario]:
    """Create test scenarios for Athena querying workflows."""

    scenarios = []

    # Database discovery and querying
    athena_discovery_scenario = Scenario(
        name="athena_discovery_and_query",
        description="Discover databases and execute queries",
        scenario_type=ScenarioType.ATHENA_QUERYING,
        expected_total_time=20.0,
        expected_call_count=5,
        steps=[
            ScenarioStep(
                tool_name="athena_workgroups_list",
                args={},
                description="List available workgroups",
            ),
            ScenarioStep(
                tool_name="athena_databases_list",
                args={},
                description="List available databases",
            ),
            ScenarioStep(
                tool_name="athena_tables_list",
                args={"database_name": "default"},
                description="List tables in default database",
            ),
            ScenarioStep(
                tool_name="athena_table_schema",
                args={"database_name": "default", "table_name": "sample_table"},
                description="Get table schema",
            ),
            ScenarioStep(
                tool_name="athena_query_execute",
                args={
                    "query": "SELECT * FROM default.sample_table LIMIT 10",
                    "max_results": 10,
                },
                description="Execute sample query",
            ),
        ],
        success_criteria=["databases_found", "tables_listed", "query_executed"],
        tags=["athena", "discovery", "querying"],
    )
    scenarios.append(athena_discovery_scenario)

    return scenarios


def create_permission_discovery_scenarios() -> List[Scenario]:
    """Create test scenarios for permission discovery workflows."""

    scenarios = []

    # Comprehensive permission discovery
    permission_scenario = Scenario(
        name="comprehensive_permission_discovery",
        description="Discover AWS permissions and bucket access",
        scenario_type=ScenarioType.PERMISSION_DISCOVERY,
        expected_total_time=15.0,
        expected_call_count=4,
        steps=[
            ScenarioStep(
                tool_name="aws_permissions_discover",
                args={"include_cross_account": False},
                description="Discover AWS permissions",
            ),
            ScenarioStep(
                tool_name="list_available_resources",
                args={},
                description="List available resources",
            ),
            ScenarioStep(
                tool_name="bucket_access_check",
                args={"bucket_name": "quilt-sandbox-bucket"},
                description="Check specific bucket access",
            ),
            ScenarioStep(
                tool_name="bucket_recommendations_get",
                args={"operation_type": "package_creation"},
                description="Get bucket recommendations",
            ),
        ],
        success_criteria=[
            "permissions_discovered",
            "access_verified",
            "recommendations_provided",
        ],
        tags=["permissions", "security", "access_control"],
    )
    scenarios.append(permission_scenario)

    return scenarios


def create_metadata_management_scenarios() -> List[Scenario]:
    """Create test scenarios for metadata management workflows."""

    scenarios = []

    # Metadata template usage
    metadata_scenario = Scenario(
        name="metadata_template_workflow",
        description="Use metadata templates for package creation",
        scenario_type=ScenarioType.METADATA_MANAGEMENT,
        expected_total_time=12.0,
        expected_call_count=5,
        steps=[
            ScenarioStep(
                tool_name="list_metadata_templates",
                args={},
                description="List available metadata templates",
            ),
            ScenarioStep(
                tool_name="get_metadata_template",
                args={"template_name": "genomics"},
                description="Get genomics metadata template",
            ),
            ScenarioStep(
                tool_name="create_metadata_from_template",
                args={
                    "template_name": "genomics",
                    "description": "Genomics dataset for testing",
                    "custom_fields": {"organism": "human", "genome_build": "GRCh38"},
                },
                description="Create metadata from template",
            ),
            ScenarioStep(
                tool_name="validate_metadata_structure",
                args={
                    "metadata": {
                        "description": "Genomics dataset for testing",
                        "organism": "human",
                        "genome_build": "GRCh38",
                    },
                    "template_name": "genomics",
                },
                description="Validate metadata structure",
            ),
            ScenarioStep(
                tool_name="show_metadata_examples",
                args={},
                description="Show metadata usage examples",
            ),
        ],
        success_criteria=["templates_listed", "metadata_created", "validation_passed"],
        tags=["metadata", "templates", "validation"],
    )
    scenarios.append(metadata_scenario)

    return scenarios


def create_governance_admin_scenarios() -> List[Scenario]:
    """Create test scenarios for governance and admin workflows."""

    scenarios = []

    # User management workflow
    user_management_scenario = Scenario(
        name="user_management_workflow",
        description="Manage users and roles in Quilt catalog",
        scenario_type=ScenarioType.GOVERNANCE_ADMIN,
        expected_total_time=18.0,
        expected_call_count=4,
        steps=[
            ScenarioStep(
                tool_name="governance_users_list",
                args={"limit": 20},
                description="List catalog users",
            ),
            ScenarioStep(
                tool_name="governance_roles_list",
                args={},
                description="List available roles",
            ),
            ScenarioStep(
                tool_name="governance_user_info",
                args={"username": "test-user"},
                description="Get user information",
            ),
            ScenarioStep(
                tool_name="governance_sso_config_get",
                args={},
                description="Get SSO configuration",
            ),
        ],
        success_criteria=["users_listed", "roles_retrieved", "config_accessed"],
        tags=["governance", "admin", "user_management"],
    )
    scenarios.append(user_management_scenario)

    return scenarios


def create_all_test_scenarios() -> List[Scenario]:
    """Create all test scenarios for comprehensive optimization testing."""

    all_scenarios = []

    # Add scenarios from each category
    all_scenarios.extend(create_package_creation_scenarios())
    all_scenarios.extend(create_data_discovery_scenarios())
    all_scenarios.extend(create_athena_querying_scenarios())
    all_scenarios.extend(create_permission_discovery_scenarios())
    all_scenarios.extend(create_metadata_management_scenarios())
    all_scenarios.extend(create_governance_admin_scenarios())

    return all_scenarios


def create_optimization_challenge_scenarios() -> List[Scenario]:
    """Create challenging scenarios specifically designed to test optimization."""

    scenarios = []

    # Inefficient workflow that needs optimization
    inefficient_scenario = Scenario(
        name="inefficient_workflow_challenge",
        description="Intentionally inefficient workflow to test optimization",
        scenario_type=ScenarioType.PACKAGE_CREATION,
        expected_total_time=45.0,  # Should be optimizable to ~20s
        expected_call_count=10,  # Should be optimizable to ~6 calls
        steps=[
            ScenarioStep(
                tool_name="auth_status",
                args={},
                description="Check auth (redundant call 1)",
            ),
            ScenarioStep(
                tool_name="auth_status",
                args={},
                description="Check auth again (redundant call 2)",
            ),
            ScenarioStep(
                tool_name="packages_list",
                args={"limit": 1000},  # Inefficient: too many results
                description="List all packages (inefficient)",
            ),
            ScenarioStep(
                tool_name="bucket_objects_list",
                args={
                    "bucket": "s3://quilt-sandbox-bucket",
                    "max_keys": 1000,
                },  # Inefficient
                description="List all objects (inefficient)",
            ),
            ScenarioStep(
                tool_name="bucket_objects_list",
                args={
                    "bucket": "s3://quilt-sandbox-bucket",
                    "prefix": "data/",
                },  # Better approach
                description="List objects with prefix (better)",
            ),
            ScenarioStep(
                tool_name="package_browse",
                args={
                    "package_name": "examples/wellcome-data",
                    "recursive": True,
                },  # Slow
                description="Full recursive browse (slow)",
            ),
            ScenarioStep(
                tool_name="package_browse",
                args={
                    "package_name": "examples/wellcome-data",
                    "recursive": False,
                },  # Faster
                description="Top-level browse (faster)",
            ),
            ScenarioStep(
                tool_name="create_package_enhanced",
                args={
                    "name": "test/optimized-package",
                    "files": ["s3://quilt-sandbox-bucket/data/sample.csv"],
                    "description": "Package for optimization testing",
                },
                description="Create package",
            ),
            ScenarioStep(
                tool_name="package_validate",
                args={"package_name": "test/optimized-package"},
                description="Validate package",
            ),
            ScenarioStep(
                tool_name="auth_status",
                args={},
                description="Check auth again (redundant call 3)",
            ),
        ],
        success_criteria=["package_created", "optimization_opportunities_identified"],
        tags=["optimization", "challenge", "inefficient", "redundant"],
    )
    scenarios.append(inefficient_scenario)

    # Complex multi-step workflow
    complex_scenario = Scenario(
        name="complex_multi_step_workflow",
        description="Complex workflow with multiple optimization opportunities",
        scenario_type=ScenarioType.DATA_DISCOVERY,
        expected_total_time=35.0,
        expected_call_count=8,
        steps=[
            ScenarioStep(
                tool_name="unified_search",
                args={"query": "genomics", "limit": 50, "scope": "catalog"},
                description="Search for genomics packages",
            ),
            ScenarioStep(
                tool_name="package_browse",
                args={
                    "package_name": "genomics/example",
                    "recursive": True,
                    "max_depth": 0,
                },
                description="Deep browse (could be optimized with max_depth)",
            ),
            ScenarioStep(
                tool_name="unified_search",
                args={"query": "*", "scope": "package", "target": "genomics/example"},
                description="Search all contents (could be combined with browse)",
            ),
            ScenarioStep(
                tool_name="unified_search",
                args={"query": "genomics", "scope": "bucket", "target": "s3://quilt-sandbox-bucket"},
                description="Search bucket for genomics files",
            ),
            ScenarioStep(
                tool_name="athena_databases_list",
                args={},
                description="List Athena databases",
            ),
            ScenarioStep(
                tool_name="athena_tables_list",
                args={"database_name": "genomics_db"},
                description="List genomics tables",
            ),
            ScenarioStep(
                tool_name="athena_query_execute",
                args={
                    "query": "SELECT * FROM genomics_db.samples",  # Missing LIMIT
                    "max_results": 1000,
                },
                description="Query without LIMIT (inefficient)",
            ),
            ScenarioStep(
                tool_name="create_package_enhanced",
                args={
                    "name": "genomics/analysis-results",
                    "files": ["s3://quilt-sandbox-bucket/genomics/results.vcf"],
                    "metadata_template": "genomics",
                    "description": "Genomics analysis results",
                },
                description="Create genomics package",
            ),
        ],
        success_criteria=["data_discovered", "package_created", "queries_executed"],
        tags=["complex", "multi_step", "genomics", "optimization"],
    )
    scenarios.append(complex_scenario)

    return scenarios


# Export all scenario creation functions
__all__ = [
    "create_package_creation_scenarios",
    "create_data_discovery_scenarios",
    "create_athena_querying_scenarios",
    "create_permission_discovery_scenarios",
    "create_metadata_management_scenarios",
    "create_governance_admin_scenarios",
    "create_all_test_scenarios",
    "create_optimization_challenge_scenarios",
]

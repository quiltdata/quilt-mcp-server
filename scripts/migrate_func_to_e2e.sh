#!/bin/bash
set -euo pipefail

FUNC_TO_E2E=(
    "test_tabulator_integration.py"
    "test_athena.py"
    "test_elasticsearch_package_scope.py"
    "test_elasticsearch_package_scope_extended.py"
    "test_elasticsearch_index_discovery.py"
    "test_elasticsearch_index_discovery_async.py"
    "test_docker_container.py"
    "test_docker_container_mcp.py"
    "test_s3_package_integration.py"
    "test_search_catalog_real_data.py"
    "test_integration.py"
    "test_integration_package_diff.py"
    "test_search_catalog_integration.py"
    "test_bucket_tools_basic.py"
    "test_bucket_tools_text.py"
    "test_bucket_tools_versions.py"
    "test_bucket_tools_version_edge_cases.py"
    "test_packages_integration.py"
)

for file in "${FUNC_TO_E2E[@]}"; do
    if [ -f "tests/func/$file" ]; then
        git mv "tests/func/$file" "tests/e2e/$file"
        echo "✓ Moved func → e2e: $file"
    fi
done

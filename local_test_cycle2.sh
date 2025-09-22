#!/bin/bash
set -e
cd /Users/ernest/GitHub/quilt-mcp-server

echo "=== CYCLE 2: LOCAL TESTING ==="
export PYTHONPATH=src

echo "Running sync..."
uv sync --group test

echo "Testing just our fixed file first..."
echo "Running a simple test to check imports work..."
uv run pytest tests/test_mcp_resources.py::TestGovernanceService::test_governance_service_creation -v

if [ $? -eq 0 ]; then
    echo "✅ Basic test passed, running full suite..."
    uv run pytest tests/test_mcp_resources.py -v --tb=short
else
    echo "❌ Basic test failed, checking imports..."
    uv run python -c "
import sys
sys.path.insert(0, 'src')
try:
    from quilt_mcp.tools.governance import GovernanceService
    print('✅ Governance import works')
except Exception as e:
    print(f'❌ Governance import failed: {e}')

try:
    from quilt_mcp.tools.unified_package import list_available_resources
    print('✅ Unified package import works')
except Exception as e:
    print(f'❌ Unified package import failed: {e}')
"
fi
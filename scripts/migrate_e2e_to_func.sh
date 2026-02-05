#!/bin/bash
set -euo pipefail

E2E_TO_FUNC=(
    "test_tabulator.py"
    "test_error_recovery.py"
    "test_optimization.py"
    "test_formatting_integration.py"
    "test_quilt_summary.py"
    "test_backend_status.py"
    "test_governance_integration.py"
    "test_backend_lazy_init.py"
    "test_readme.py"
)

for file in "${E2E_TO_FUNC[@]}"; do
    if [ -f "tests/e2e/$file" ]; then
        git mv "tests/e2e/$file" "tests/func/$file"
        echo "✓ Moved e2e → func: $file"
    fi
done

if [ -f "tests/e2e/test_selector_debug.py" ]; then
    git rm "tests/e2e/test_selector_debug.py"
    echo "✓ Deleted empty: test_selector_debug.py"
fi

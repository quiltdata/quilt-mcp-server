#!/bin/bash
set -euo pipefail

UNIT_TO_E2E=(
    "test_health_integration.py"
    "test_optimization_integration.py"
    "test_main.py"
    "test_error_recovery.py"
)

for file in "${UNIT_TO_E2E[@]}"; do
    if [ -f "tests/unit/$file" ]; then
        git mv "tests/unit/$file" "tests/e2e/$file"
        echo "✓ Moved unit → e2e: $file"
    fi
done

#!/bin/bash
set -euo pipefail

UNIT_TO_FUNC=(
    "test_data_visualization.py"
    "test_workflow_orchestration.py"
)

for file in "${UNIT_TO_FUNC[@]}"; do
    if [ -f "tests/unit/$file" ]; then
        git mv "tests/unit/$file" "tests/func/$file"
        echo "✓ Moved unit → func: $file"
    fi
done

#!/bin/bash
set -e
cd /Users/ernest/GitHub/quilt-mcp-server

echo "=== CYCLE 2: CHECKING PR STATUS AFTER CYCLE 1 ==="

echo "Current branch:"
git branch --show-current

echo "Checking PR #189 status..."
gh pr checks 189 --watch

echo "If there are still failures, let's see the details..."
gh pr checks 189
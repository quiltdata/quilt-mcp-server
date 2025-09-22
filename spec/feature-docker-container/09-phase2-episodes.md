<!-- markdownlint-disable MD013 -->
# Phase 2 Episodes — Publishing Automation

## Episode 1 — Add Release Tests (Red)
- Introduce automated checks/assertions that fail when container publish step is missing (e.g., scripted validation in CI workflow tests).

## Episode 2 — Implement ECR Publish (Green)
- Update workflows/scripts to log in to ECR, tag, and push the image.
- Ensure version extraction comes from a single source of truth (e.g., `scripts/version.py`).

## Episode 3 — Harden Automation (Refactor)
- Refine scripts for retryability, error handling, and maintainability.
- Keep documentation inline with actual automation commands.


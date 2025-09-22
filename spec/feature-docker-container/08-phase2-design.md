<!-- markdownlint-disable MD013 -->
# Phase 2 Design — Publishing Automation

## Objectives
1. Automate container image tagging and publishing to AWS ECR.
2. Align image lifecycle with existing release process.

## Key Tasks
1. Extend GitHub Actions or release scripts to build the Docker image using the new Dockerfile.
2. Authenticate with AWS ECR using repository secrets and push versioned + `latest` tags.
3. Ensure CI verifies image integrity (digest, tag naming) before release.
4. Provide fallback or dry-run workflows for local validation without AWS access.

## Dependencies & Inputs
- Phase 1 Dockerfile and automation.
- Existing release workflows (`.github/workflows/push.yml`, `scripts/release.sh`).
- AWS credentials/secrets configured in CI environment.

## Acceptance
- Release pipeline demonstrates published Docker image in target ECR repository.
- Documentation references canonical image tags/URIs.


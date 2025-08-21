# Phase 3: Catalog-Push (ECR Registry) Specification

## Overview

Phase 3 handles pushing Docker images to Amazon ECR (Elastic Container Registry) and validates the remote registry operations.

## Requirements

### Functional Requirements

- **ECR Authentication**: Automated login using AWS CLI credentials
- **Image Push**: Upload Docker images to ECR with git SHA tags
- **Registry Management**: Auto-create ECR repositories if needed
- **Image Validation**: Pull and test images from ECR

### Quality Requirements

- **Push Success**: Images successfully uploaded to ECR
- **Pull Validation**: Images can be retrieved and run from ECR
- **Consistency**: ECR image matches local build exactly
- **Health Checking**: ECR containers pass same health checks as local

### Technical Requirements

- **AWS Authentication**: Valid AWS credentials configured
- **ECR Registry**: Auto-constructed from AWS account and region
- **Repository**: `quilt-mcp` repository in ECR
- **Tagging**: Git SHA tags for version consistency
- **Testing Port**: Container runs on port 8002 for testing

## Validation Process

The SPEC-compliant validation follows this 6-step process:

1. **Preconditions** (`make init`): Check AWS CLI, Docker, credentials
2. **Execution** (`make push`): Push image to ECR (auto-creates repo)
3. **Testing** (`make test`): Pull from ECR and run health checks
4. **Verification** (`make verify`): Validate MCP endpoint from ECR image
5. **Zero** (`make zero`): Stop ECR test containers
6. **Config** (`make config`): Generate `.config` with ECR details

## Success Criteria

- ✅ ECR login successful
- ✅ Image pushed to ECR registry
- ✅ ECR repository created if needed
- ✅ Image can be pulled from ECR
- ✅ ECR container passes health checks
- ✅ MCP endpoint responds from ECR image
- ✅ `.config` file generated with ECR metadata

## Files and Structure

```text
catalog-push/
├── Makefile           # Phase-specific build targets
├── SPEC.md           # This specification
└── catalog-push.sh   # Core phase script
```

## ECR Specifications

- **Registry Format**: `<account>.dkr.ecr.<region>.amazonaws.com`
- **Repository**: `quilt-mcp`
- **Image URI**: `<registry>/quilt-mcp:<git-sha>`
- **Visibility**: Private repository
- **Testing Port**: 8002 for ECR image validation

## Environment Variables

- `ECR_REGISTRY`: Auto-constructed ECR registry URL
- `ECR_REPOSITORY`: Repository name (default: quilt-mcp)
- `AWS_DEFAULT_REGION`: AWS region for ECR operations
- `AWS_ACCOUNT_ID`: AWS account ID (optional, auto-detected)
- `VERBOSE`: Enable detailed output

## AWS Permissions Required

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ecr:GetAuthorizationToken",
                "ecr:BatchCheckLayerAvailability",
                "ecr:GetDownloadUrlForLayer",
                "ecr:BatchGetImage",
                "ecr:InitiateLayerUpload",
                "ecr:UploadLayerPart",
                "ecr:CompleteLayerUpload",
                "ecr:PutImage",
                "ecr:CreateRepository",
                "ecr:DescribeRepositories",
                "ecr:DescribeImages"
            ],
            "Resource": "*"
        }
    ]
}
```

## Common Issues

- **AWS Credentials**: Ensure AWS CLI is configured
- **Permissions**: ECR push/pull permissions required
- **Repository Creation**: Auto-created on first push
- **Region Mismatch**: ECR registry must match AWS region
- **Network Connectivity**: ECR requires internet access
- **Tag Conflicts**: Git SHA ensures unique tags

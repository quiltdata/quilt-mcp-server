# Quilt MCP Server - Claude Code Configuration

This repository contains a secure MCP (Model Context Protocol) server for accessing Quilt data. All code and configurations are designed for defensive security purposes only.

## Repository Overview

**Purpose**: Deploy and manage a Claude-compatible MCP server for Quilt data access with JWT authentication
**Tech Stack**: Python, AWS CDK, Docker, ECS Fargate, Application Load Balancer, ECR
**Security**: JWT authentication, IAM roles, secure credential management

## Architecture

This project uses a **4-phase deployment pipeline**:

```tree
fast-mcp-server/
├── app/           # Phase 1: Local MCP server (Python)
├── build-docker/  # Phase 2: Docker containerization  
├── catalog-push/  # Phase 3: ECR registry operations
├── deploy-aws/    # Phase 4: ECS/ALB deployment
└── shared/        # Common utilities (validation, testing)
```


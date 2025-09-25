# MCP Unified Authentication Strategy & Implementation

## Overview

This directory contains comprehensive specifications for unifying authentication across Quilt's MCP server to support both web and desktop clients using a single remote AWS-hosted server.

## Problem Statement

Currently, Quilt's MCP server has inconsistent authentication patterns:
- **Web clients** fail authentication for many tools due to JWT processing issues
- **Desktop clients** cannot use the remote MCP server due to credential passing limitations
- **Different tools** use different authentication methods, creating maintenance overhead
- **Permission mapping** gaps between JWT claims and AWS permissions

## Solution

A unified authentication architecture that:
- Uses **AWS credentials as the single source of truth** for all AWS operations
- Provides a **unified authentication service** that handles both client types
- Implements **tool-specific authentication patterns** for different categories
- Supports **both web and desktop clients** through the same remote server

## Documents

### 1. [Strategy Document](./unified-mcp-authentication-strategy.md)
**High-level strategy and business requirements**

- Executive summary and current state analysis
- Tool categories and authentication requirements
- Proposed unified authentication strategy
- Implementation plan with phases
- Security considerations and success metrics
- Migration strategy and rollout plan

### 2. [Implementation Specification](./mcp-unified-auth-implementation-spec.md)
**Detailed technical implementation requirements**

- Core design principles and architecture
- Detailed implementation requirements for each component
- Tool category implementation patterns
- Configuration requirements and environment variables
- Testing requirements and migration strategy
- Performance and security requirements

### 3. [Architecture Diagram](./unified-auth-architecture-diagram.md)
**Visual representation of the unified authentication architecture**

- Mermaid diagram showing complete authentication flow
- Component relationships and data flow
- Client type detection and processing
- Tool category mappings to AWS services
- Implementation phases and benefits

## Key Components

### Unified Authentication Service
- **Client Type Detection**: Automatically identifies web vs desktop clients
- **JWT Processing**: Enhanced JWT token parsing with AWS role extraction
- **Desktop Integration**: quilt3 credential processing for desktop clients
- **Credential Management**: AWS session factory with refresh logic

### Tool Categories
1. **S3 Bucket Operations**: Direct AWS S3 operations
2. **Package Operations**: Quilt package management (S3 + Quilt API)
3. **Athena/Glue Operations**: AWS Athena and Glue operations
4. **Search Operations**: Quilt API search operations
5. **Permission Operations**: AWS IAM permission discovery

### Authentication Flows
- **Web Client**: JWT Token → AWS Role Extraction → AWS Session
- **Desktop Client**: quilt3 Credentials → AWS Credentials → AWS Session
- **Unified**: Both flows result in consistent AWS session for tools

## Implementation Plan

### Phase 1: Core Service (Week 1)
- Implement `UnifiedAuthService` class
- Enhance JWT token processing
- Create tool authentication helpers
- Add unit tests

### Phase 2: Tool Migration (Week 2)
- Migrate all tool categories to unified auth
- Implement tool-specific authentication patterns
- Add integration tests
- Validate security and performance

### Phase 3: Desktop Integration (Week 3)
- Implement desktop client support
- Add credential passing via MCP protocol
- Update desktop client configurations
- Add end-to-end tests

### Phase 4: Optimization (Week 4)
- Performance tuning and optimization
- Security validation and hardening
- Documentation and monitoring setup
- Production deployment

## Success Criteria

### Functional Requirements
- **Web clients**: 95%+ successful authentication
- **Desktop clients**: 95%+ successful authentication
- **All tools**: Work with both client types
- **Permission enforcement**: Correct and consistent

### Performance Requirements
- **Authentication time**: <500ms
- **Tool execution time**: <2s average
- **Error rate**: <1% of requests
- **Availability**: 99.9% uptime

### User Experience
- **Setup time**: <5 minutes for new users
- **Error messages**: Clear and actionable
- **Documentation**: Complete and up-to-date

## Next Steps

1. **Review and approve** the strategy and implementation documents
2. **Create implementation tickets** for Phase 1 components
3. **Set up development environment** and testing infrastructure
4. **Begin implementation** of core unified authentication service

## Contact

For questions or clarifications about this specification, please contact the Quilt MCP development team.

---

**Status**: Ready for implementation
**Last Updated**: 2025-01-25
**Version**: 1.0

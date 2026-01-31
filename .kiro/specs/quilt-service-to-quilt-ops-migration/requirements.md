# Requirements Document

## Introduction

This specification defines the migration from QuiltService to QuiltOps across the MCP codebase. The goal is to replace the current QuiltService abstraction with the existing QuiltOps domain-driven interface, providing cleaner abstractions while maintaining all existing functionality.

## Glossary

- **QuiltService**: Current service implementation that directly wraps quilt3 library operations
- **QuiltOps**: Existing domain-driven abstraction layer that provides backend-agnostic Quilt operations
- **QuiltOpsFactory**: Factory class that creates appropriate QuiltOps backend instances
- **Quilt3_Backend**: Backend implementation using the quilt3 Python library
- **Domain_Objects**: Backend-agnostic data structures (Package_Info, Content_Info, etc.)
- **MCP_Tools**: The 84+ tools that currently use QuiltService methods

## Requirements

### Requirement 1: QuiltService Usage Discovery

**User Story:** As a developer, I want to identify all QuiltService usage patterns, so that I can ensure complete migration coverage.

#### Acceptance Criteria

1. WHEN analyzing the codebase, THE System SHALL identify all QuiltService method calls across all files
2. WHEN cataloging usage patterns, THE System SHALL document the specific methods used and their call contexts
3. WHEN documenting patterns, THE System SHALL identify which methods have direct QuiltOps equivalents
4. WHEN finding special cases, THE System SHALL flag methods that require custom migration logic
5. THE System SHALL create a comprehensive mapping of QuiltService methods to QuiltOps methods

### Requirement 2: QuiltOps Method Implementation

**User Story:** As a developer, I want QuiltOps to provide equivalent methods for all QuiltService functionality, so that migration can be completed without feature loss.

#### Acceptance Criteria

1. WHEN QuiltService.list_packages() is called, THE QuiltOps SHALL provide search_packages() that returns Package_Info objects
2. WHEN QuiltService.browse_package() is called, THE QuiltOps SHALL provide browse_content() that returns Content_Info objects
3. WHEN QuiltService.create_package_revision() is called, THE QuiltOps SHALL provide create_package() that handles package creation
4. WHEN QuiltService authentication methods are called, THE QuiltOpsFactory SHALL provide equivalent authentication validation
5. WHEN QuiltService session methods are called, THE System SHALL maintain session access for GraphQL operations
6. WHEN QuiltService admin methods are called, THE QuiltOps SHALL provide equivalent admin functionality
7. THE QuiltOps SHALL return domain objects instead of raw quilt3 objects for all operations

### Requirement 3: MCP Tool Migration

**User Story:** As a developer, I want all MCP tools to use QuiltOps instead of QuiltService, so that the codebase uses consistent abstractions.

#### Acceptance Criteria

1. WHEN migrating packages.py, THE System SHALL replace QuiltService calls with QuiltOpsFactory.create() and appropriate QuiltOps methods
2. WHEN migrating search.py, THE System SHALL replace QuiltService session access with QuiltOpsFactory authentication validation
3. WHEN migrating athena_service.py, THE System SHALL replace QuiltService.create_botocore_session() with QuiltOps equivalent
4. WHEN migrating tabulator_service.py, THE System SHALL replace QuiltService admin methods with QuiltOps admin methods
5. WHEN migrating governance_service.py, THE System SHALL replace QuiltService admin access with QuiltOps admin access
6. WHEN migrating auth_metadata.py, THE System SHALL replace QuiltService authentication methods with QuiltOpsFactory methods
7. THE System SHALL ensure all migrated tools maintain identical external behavior

### Requirement 4: Response Format Compatibility

**User Story:** As a developer, I want migrated tools to return the same response formats, so that existing integrations continue to work.

#### Acceptance Criteria

1. WHEN QuiltOps returns Package_Info objects, THE System SHALL transform them to match current string list format where needed
2. WHEN QuiltOps returns Content_Info objects, THE System SHALL transform them to match current dictionary format where needed
3. WHEN QuiltOps returns domain objects, THE System SHALL preserve all fields that existing tools expect
4. WHEN error conditions occur, THE System SHALL maintain the same error response formats
5. THE System SHALL ensure stdout suppression patterns are preserved during migration

### Requirement 5: QuiltService Removal

**User Story:** As a developer, I want QuiltService completely removed from the codebase, so that there is only one abstraction layer for Quilt operations.

#### Acceptance Criteria

1. WHEN all tools are migrated, THE System SHALL remove the QuiltService class definition
2. WHEN removing QuiltService, THE System SHALL remove all QuiltService imports from **init**.py files
3. WHEN cleaning up imports, THE System SHALL remove unused QuiltService import statements from all files
4. WHEN validating removal, THE System SHALL ensure no remaining references to QuiltService exist in the codebase
5. THE System SHALL ensure all tests pass after QuiltService removal

### Requirement 6: Backward Compatibility Preservation

**User Story:** As a developer, I want the migration to preserve all existing functionality, so that no features are lost during the transition.

#### Acceptance Criteria

1. WHEN tools use authentication, THE System SHALL maintain the same authentication behavior through QuiltOpsFactory
2. WHEN tools access sessions for GraphQL, THE System SHALL preserve session access patterns for non-domain operations
3. WHEN tools use admin functionality, THE System SHALL maintain admin method availability through QuiltOps
4. WHEN tools handle errors, THE System SHALL preserve existing error handling patterns
5. WHEN tools suppress stdout, THE System SHALL maintain stdout suppression during QuiltOps operations
6. THE System SHALL ensure all existing MCP tool functionality works identically after migration

### Requirement 7: Import and Dependency Updates

**User Story:** As a developer, I want clean import statements after migration, so that the codebase has clear dependency relationships.

#### Acceptance Criteria

1. WHEN updating imports, THE System SHALL replace QuiltService imports with QuiltOpsFactory imports
2. WHEN adding new imports, THE System SHALL import domain objects (Package_Info, Content_Info) where needed
3. WHEN cleaning imports, THE System SHALL remove unused QuiltService-related imports
4. WHEN updating **init**.py files, THE System SHALL remove QuiltService from **all** exports
5. THE System SHALL ensure all import statements are valid and functional after migration

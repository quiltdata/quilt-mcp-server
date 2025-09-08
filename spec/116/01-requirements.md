# Requirements: Streamline MCP Tools Architecture

**Issue**: [#116 - Streamline Tools](https://github.com/quiltdata/quilt-mcp-server/issues/116)  
**Type**: Architecture Enhancement  
**Priority**: Medium

## Problem Statement

The Quilt MCP Server needs **"a minimal, orthogonal set of tools that span the core use cases"** rather than the current proliferating architecture. The goal is to create tools that are **"atomic based on their input and output schema"** to efficiently serve the essential data management workflows.

Current challenges:
- **16+ tool modules** scattered across directories without focus on core use cases
- **Tool proliferation** that obscures the essential Quilt data management capabilities  
- **Missing focus on core workflows**: catalog access, package read/write, search, visualization, querying, and tabulation
- **Overlapping functionality** that should be consolidated into atomic, purpose-driven tools
- **Complex discovery** when users need simple access to the 7 core use cases

The system should prioritize delivering streamlined tools for the **core Quilt use cases** rather than comprehensive coverage of every possible operation.

## User Stories

### Core Use Case Focus
1. **As a data analyst**, I want **catalog access tools** so that **I can authenticate, list available buckets, and discover tables/datasets across Quilt catalogs**
2. **As a data scientist**, I want **package read/write/delete tools** so that **I can efficiently access and modify Quilt package data and metadata**
   1. And parallel for objects
3. **As a researcher**, I want **search tools** so that **I can find packages and objects across multiple Quilt catalogs**
4. **As a data explorer**, I want **visualization tools** so that **I can create charts and graphs from Quilt package data**
5. **As a business user**, I want **Athena SQL search tools** so that **I can use familiar SQL syntax to query Quilt data with proper table discovery**
6. **As a dashboard creator**, I want **tabulator table tools** so that **I can create flexible, interactive data tables**

### Developer Experience
8. **As a developer**, I want **atomic, orthogonal tools** so that **each tool has clear input/output schemas and single responsibilities**
9. **As a maintainer**, I want **minimal tool set** so that **I can focus maintenance on core use cases rather than comprehensive edge cases**

## Acceptance Criteria

1. **Core Use Case Coverage** - All 7 core use cases (catalog access, package read/write, search, visualization, longitudinal querying, Athena SQL, tabulation) have dedicated, atomic tools
2. **Minimal Tool Set** - Tools are consolidated to focus on core use cases, with non-essential tools archived or removed
3. **Atomic Design** - Each tool is atomic based on input/output schema with single, clear responsibility
4. **Orthogonal Architecture** - Tools are orthogonal (non-overlapping) in functionality and scope
5. **Clear Tool Boundaries** - No functional overlap between catalog access, package operations, search, visualization, querying, and tabulation tools
6. **Schema-Driven Design** - Each tool has well-defined input and output schemas that align with Quilt data structures
7. **Core Workflow Optimization** - Tools are optimized for the most common Quilt data management workflows
8. **Archive Legacy Tools** - Non-core tools are properly archived with deprecation notices and migration guidance
9. **Performance Focus** - Core tools maintain or improve performance for essential operations
10. **Documentation Alignment** - Tool documentation focuses on core use case examples and workflows

## Implementation Approach

1. **Core Use Case Mapping** - Map existing tools to the 7 core use cases and identify which tools serve each use case
2. **Tool Audit and Classification** - Classify existing tools as core, redundant, or non-essential based on use case alignment
3. **Atomic Tool Design** - Design new atomic tools with clear input/output schemas for each core use case
4. **Archive Strategy** - Identify tools to be archived/removed that don't align with core use cases
5. **Migration Plan** - Create migration path for users of archived tools to core use case tools
6. **Core Tool Implementation** - Implement the minimal, orthogonal tool set focused on the 7 core use cases
7. **Validation and Testing** - Ensure core use cases are fully covered with optimal performance

## Success Criteria

- **Core Use Case Focus** - All 7 core use cases are optimally served by atomic, purpose-built tools
- **Minimal Toolset** - Reduced from 16+ tools to focused set aligned with core Quilt workflows
- **Clear Tool Purpose** - Each tool has single responsibility based on atomic input/output schema
- **Improved Discoverability** - Users can easily find the right tool for their core data management workflow
- **Archived Non-Core Tools** - Non-essential tools are properly archived with migration guidance to core alternatives

## Open Questions

1. **Which existing tools map to each of the 7 core use cases** (catalog access, package read/write, search, visualization, longitudinal querying, Athena SQL, tabulation)?
2. **What are the specific input/output schemas** that should define the atomic nature of each core use case tool?
3. **Which current tools should be archived** versus consolidated into the core use case tools?
4. **How should visualization tools integrate** with Quilt package data structures for optimal chart/graph creation?
5. **What specific Athena SQL capabilities** are most important for the SQL search use case?
6. **How should tabulator table tools balance** flexibility with performance for large Quilt datasets?
7. **What migration strategy is preferred** for users currently depending on tools that will be archived?
8. **Are there any existing tools that already exemplify** the desired atomic, orthogonal design principles?
9. **What specific performance benchmarks** should be maintained or improved for core use case tools?
10. **How should the longitudinal querying tools handle** time series analysis across different package structures?

## Notes

This requirements document is based on GitHub issue #116 which calls for **"a minimal, orthogonal set of tools that span the core use cases"** with tools that are **"atomic based on their input and output schema"**. 

The focus is on creating a purpose-driven toolset that efficiently handles the 7 core Quilt use cases rather than comprehensive coverage of all possible operations. The approach prioritizes archiving or consolidating non-essential tools to achieve a streamlined, maintainable architecture focused on core data management workflows.
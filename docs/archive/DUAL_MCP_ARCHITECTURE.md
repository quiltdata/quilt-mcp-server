# Dual MCP Server Architecture: Quilt + Benchling Integration

## Overview

This document describes the implementation of a dual MCP (Model Context Protocol) server architecture that combines the Quilt MCP server with the Benchling MCP server to enable comprehensive laboratory data management and analysis workflows.

## Architecture Components

### 1. Quilt MCP Server
**Repository**: `fast-mcp-server` (this repository)
**Purpose**: Data catalog, package management, search, and analytics

**Key Capabilities**:
- Package creation, browsing, and management
- S3 bucket and object search
- AWS Athena/Glue integration for SQL analytics
- Tabulator integration for cross-package querying
- Visualization and summarization tools
- Permission discovery and validation

**Available Tools** (prefix: `mcp_quilt_`):
- `packages_search`, `package_browse`, `package_create_from_s3`
- `bucket_objects_search`, `bucket_objects_list`
- `athena_databases_list`, `athena_tables_list`, `athena_query_execute`
- `tabulator_tables_list`, `tabulator_table_create`
- `generate_package_visualizations`, `generate_quilt_summarize_json`
- `aws_permissions_discover`

### 2. Benchling MCP Server
**Repository**: `quiltdata/benchling_mcp` (private)
**Purpose**: Laboratory notebook, sequence, and project management

**Key Capabilities**:
- Laboratory notebook entry management
- DNA/RNA/protein sequence handling
- Project and folder organization
- Entity search across Benchling platform
- Sequence creation and annotation

**Available Tools** (prefix: `benchling_`):
- `get_entries`, `get_entry_by_id`
- `get_dna_sequences`, `get_dna_sequence_by_id`
- `get_rna_sequences`, `get_aa_sequences`
- `get_projects`, `get_folders`
- `search_entities`
- `create_dna_sequence`, `create_folder`

## Integration Benefits

### Federated Data Access
- **Cross-system queries**: Join Benchling experimental data with Quilt analytical results
- **Unified search**: Search across both laboratory notebooks and data packages
- **Provenance tracking**: Maintain lineage from experimental design through analysis

### Workflow Orchestration
- **NGS Lifecycle**: Link FASTQ packages in Quilt to library entities in Benchling
- **QC Management**: Propagate quality control flags between systems
- **Protocol Awareness**: Track experimental protocols alongside analytical pipelines

### Enhanced Analytics
- **Text-to-SQL**: Generate queries that span both Benchling results tables and Quilt Tabulator views
- **Literature Enrichment**: Annotate gene lists from analysis with experimental context
- **Cohort Building**: Create analysis cohorts based on experimental metadata

## Configuration

### Cursor MCP Configuration
```json
{
  "mcpServers": {
    "quilt": {
      "command": "/path/to/fast-mcp-server/.venv/bin/python",
      "args": ["/path/to/fast-mcp-server/app/main.py"],
      "env": {
        "PYTHONPATH": "/path/to/fast-mcp-server/app",
        "FASTMCP_TRANSPORT": "stdio",
        "QUILT_CATALOG_DOMAIN": "demo.quiltdata.com",
        "QUILT_DEFAULT_BUCKET": "s3://your-bucket"
      }
    },
    "benchling": {
      "command": "uvx",
      "args": ["benchling-mcp", "stdio"],
      "env": {
        "BENCHLING_API_KEY": "your_api_key_here",
        "BENCHLING_DOMAIN": "yourcompany.benchling.com"
      }
    }
  }
}
```

### Environment Variables Required

**Quilt MCP**:
- `QUILT_CATALOG_DOMAIN`: Your Quilt catalog domain
- `QUILT_DEFAULT_BUCKET`: Default S3 bucket for operations
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`: AWS credentials

**Benchling MCP**:
- `BENCHLING_API_KEY`: Your Benchling API key
- `BENCHLING_DOMAIN`: Your Benchling domain (e.g., "yourcompany.benchling.com")

## Use Case Examples

### 1. Federated Discovery (SB001)
**Query**: "Which genes are highly expressed in samples S1–S20 and do they correlate with ELISA protein levels?"

**Workflow**:
1. `benchling_search_entities` - Find ELISA results in Benchling
2. `mcp_quilt_athena_tables_list` - Discover expression tables in Tabulator
3. `mcp_quilt_athena_query_execute` - Execute federated SQL query
4. Return correlation analysis with provenance

### 2. NGS Lifecycle Management (SB004)
**Query**: "Package FASTQs under s3://runs/2025-06-01/ and link to Library L-789"

**Workflow**:
1. `benchling_search_entities` - Validate Library L-789 exists
2. `mcp_quilt_package_create_from_s3` - Create Quilt package from FASTQ files
3. `mcp_quilt_create_metadata_from_template` - Add Benchling entity links to metadata
4. `benchling_get_projects` - Update project with package reference

### 3. Protocol Awareness (SB010)
**Query**: "Show protocol template/version for NB-456 and diff vs version 5"

**Workflow**:
1. `benchling_get_entry_by_id` - Fetch notebook entry NB-456
2. Extract protocol template and version information
3. `mcp_quilt_package_diff` - Compare with historical package versions
4. Generate human-readable change summary

## Testing Strategy

### Test Case Structure
Each test case now includes both MCP servers:

```json
{
  "mcp_tools": [
    "benchling_get_entries",
    "benchling_search_entities", 
    "mcp_quilt_athena_query_execute",
    "mcp_quilt_package_create_from_s3"
  ]
}
```

### Validation Approach
1. **Unit Testing**: Test each MCP server independently
2. **Integration Testing**: Test cross-server workflows
3. **End-to-End Testing**: Validate complete user stories
4. **Performance Testing**: Ensure acceptable latency for federated queries

## Implementation Status

### ✅ Available
- Quilt MCP server with full functionality
- Benchling MCP server with core laboratory data access
- Dual MCP configuration in Cursor
- Updated test cases with realistic tool mappings

### 🚧 In Progress
- Cross-server workflow orchestration
- Enhanced error recovery for federated operations
- Performance optimization for complex queries

### 📋 Future Development
- Webhook integration for event-driven workflows
- Local indexing for offline capabilities
- Enhanced visualization for cross-system data
- Multi-model support for different analysis contexts

## Error Handling

### Cross-Server Dependencies
- Graceful degradation when one server is unavailable
- Clear error messages indicating which system failed
- Fallback workflows using available systems only

### Authentication Issues
- Separate credential validation for each system
- Clear guidance on required permissions
- Fallback to read-only operations when appropriate

## Performance Considerations

### Query Optimization
- Minimize cross-server round trips
- Cache frequently accessed metadata
- Use parallel requests where possible

### Data Transfer
- Stream large result sets
- Compress data between systems
- Implement pagination for large queries

## Security

### Credential Management
- Separate API keys for each system
- Environment variable isolation
- Audit logging for cross-system operations

### Data Access Control
- Respect permissions from both systems
- Implement least-privilege access patterns
- Log all cross-system data access

## Monitoring and Observability

### Metrics
- Query latency per system
- Cross-server operation success rates
- Error rates and types
- Resource utilization

### Logging
- Structured logging with correlation IDs
- Cross-system operation tracing
- Performance metrics collection
- Error context preservation

## Conclusion

The dual MCP architecture enables powerful federated workflows that combine laboratory data management (Benchling) with analytical data operations (Quilt). This integration provides scientists and bioinformaticians with seamless access to both experimental context and analytical results, enabling more comprehensive and reproducible research workflows.

The architecture is designed to be extensible, allowing for additional MCP servers to be integrated as needed for specific organizational requirements or specialized tools.


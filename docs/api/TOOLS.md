<!-- markdownlint-disable MD013 -->
# MCP Tools Reference

This document provides comprehensive documentation for all 84+ MCP tools available in the Quilt MCP Server,
organized by functionality and use case.

## 🚀 Quick Reference

| Category | Tools | Purpose |
|----------|-------|---------|
| **[Authentication](#-authentication--authorization)** | 8 tools | Auth status, catalog configuration, filesystem checks |
| **[Package Management](#-package-management)** | 15 tools | Create, browse, search, and manage Quilt packages |
| **[S3 Operations](#️-s3-operations)** | 12 tools | Direct S3 bucket and object operations |
| **[Search & Discovery](#-search--discovery)** | 8 tools | Multi-backend search across systems |
| **[Analytics & SQL](#-analytics--sql)** | 12 tools | Athena queries, Tabulator tables, data analysis |
| **[Workflow Management](#-workflow-management)** | 8 tools | Multi-step workflows and orchestration |
| **[Metadata & Templates](#️-metadata--templates)** | 13 tools | Metadata templates, validation, and utilities |
| **[Permissions & Security](#-permissions--security)** | 6 tools | AWS permissions, bucket access validation |
| **[Administration](#-administration)** | 17 tools | User management, role management, SSO configuration |

## 🔐 Authentication & Authorization

### Core Authentication Tools

#### `auth_status`

Check current Quilt authentication status with comprehensive information.

```python
# Basic usage
result = await mcp_client.call_tool(\"auth_status\", {})

# Response structure
{
    \"success\": true,
    \"authenticated\": true,
    \"catalog_name\": \"demo.quiltdata.com\",
    \"user_info\": {
        \"username\": \"user@example.com\",
        \"roles\": [\"user\"]
    },
    \"permissions\": [\"read\", \"write\"],
    \"next_steps\": [\"Ready to use Quilt tools\"]
}
```

**Use Cases:**

- Verify authentication before operations
- Debug authentication issues
- Check user permissions and roles

#### `catalog_info`

Get detailed information about the current Quilt catalog configuration.

```python
result = await mcp_client.call_tool(\"catalog_info\", {})

# Response includes
{
    \"catalog_name\": \"demo.quiltdata.com\",
    \"catalog_url\": \"https://demo.quiltdata.com\",
    \"registry_url\": \"s3://quilt-example\",
    \"authentication_status\": \"authenticated\",
    \"configuration_source\": \"environment\"
}
```

#### `filesystem_status`

Check filesystem permissions and environment capabilities.

```python
result = await mcp_client.call_tool(\"filesystem_status\", {})

# Provides detailed environment analysis
{
    \"status\": \"full_access\",
    \"home_writable\": true,
    \"temp_writable\": true,
    \"tools_available\": [\"auth_status\", \"packages_list\", ...],
    \"recommendations\": []
}
```

### Configuration Tools

#### `configure_catalog`

Configure Quilt catalog URL for the session.

```python
result = await mcp_client.call_tool(\"configure_catalog\", {
    \"catalog_url\": \"https://your-catalog.quiltdata.com\"
})
```

#### `catalog_name`

Get the name of the current Quilt catalog.

```python
result = await mcp_client.call_tool(\"catalog_name\", {})
# Returns: {\"catalog_name\": \"demo.quiltdata.com\"}
```

#### `switch_catalog`

Switch to a different Quilt catalog by name.

```python
result = await mcp_client.call_tool(\"switch_catalog\", {
    \"catalog_name\": \"production.quiltdata.com\"
})
```

#### `catalog_url`

Get the URL for the current Quilt catalog.

```python
result = await mcp_client.call_tool("catalog_url", {})
# Returns: {"catalog_url": "https://demo.quiltdata.com"}
```

#### `catalog_uri`

Get the URI for the current Quilt catalog (includes registry).

```python
result = await mcp_client.call_tool("catalog_uri", {})
# Returns: {"catalog_uri": "quilt+s3://quilt-example"}
```

## 📦 Package Management

### Core Package Operations

#### `package_browse`

Browse package contents with enhanced file information and tree structure.

```python
# Basic browsing
result = await mcp_client.call_tool(\"package_browse\", {
    \"package_name\": \"genomics/ccle-rnaseq\",
    \"registry\": \"s3://quilt-example\",
    \"recursive\": true,
    \"include_file_info\": true,
    \"include_signed_urls\": true
})

# Advanced options
result = await mcp_client.call_tool(\"package_browse\", {
    \"package_name\": \"genomics/ccle-rnaseq\",
    \"max_depth\": 2,           # Limit directory depth
    \"top\": 100,               # Limit number of entries
    \"include_file_info\": true  # Include sizes, types, dates
})

# Response structure
{
    \"success\": true,
    \"package_name\": \"genomics/ccle-rnaseq\",
    \"file_tree\": {
        \"data/\": {
            \"type\": \"directory\",
            \"files\": {
                \"sample_001.fastq.gz\": {
                    \"size\": 1048576,
                    \"type\": \"file\",
                    \"last_modified\": \"2024-08-01T10:30:00Z\",
                    \"download_url\": \"https://...\"
                }
            }
        }
    },
    \"total_files\": 150,
    \"total_size\": \"2.5 GB\"
}
```

**Use Cases:**

- Explore package structure before downloading
- Validate package contents after creation
- Generate file listings for documentation

#### `packages_list`

List packages in a registry with filtering and search capabilities.

```python
# List all packages
result = await mcp_client.call_tool(\"packages_list\", {
    \"registry\": \"s3://quilt-example\",
    \"limit\": 50
})

# Filter by prefix
result = await mcp_client.call_tool(\"packages_list\", {
    \"registry\": \"s3://quilt-example\",
    \"prefix\": \"genomics/\",
    \"limit\": 20
})

# Response structure
{
    \"success\": true,
    \"packages\": [
        {
            \"name\": \"genomics/ccle-rnaseq\",
            \"created\": \"2024-08-01T10:30:00Z\",
            \"modified\": \"2024-08-15T14:20:00Z\",
            \"size\": \"2.5 GB\",
            \"files\": 150
        }
    ],
    \"total_count\": 25,
    \"registry\": \"s3://quilt-example\"
}
```

#### `packages_search`

Search packages by content and metadata using Elasticsearch.

```python
# Content search
result = await mcp_client.call_tool(\"packages_search\", {
    \"query\": \"RNA-seq genomics human\",
    \"registry\": \"s3://quilt-example\",
    \"limit\": 10
})

# Advanced search with filters
result = await mcp_client.call_tool(\"packages_search\", {
    \"query\": \"genomics\",
    \"from_\": 0,
    \"limit\": 20
})
```

### Package Creation Tools

#### `create_package_enhanced` (Recommended)

Advanced package creation with metadata templates and intelligent validation.

```python
# Basic package creation
result = await mcp_client.call_tool(\"create_package_enhanced\", {
    \"name\": \"genomics/study-001\",
    \"files\": [
        \"s3://source-bucket/data/sample_001.fastq.gz\",
        \"s3://source-bucket/data/sample_002.fastq.gz\"
    ],
    \"description\": \"RNA-seq analysis for study 001\",
    \"metadata_template\": \"genomics\"
})

# Advanced creation with custom metadata
result = await mcp_client.call_tool(\"create_package_enhanced\", {
    \"name\": \"ml/model-training-v2\",
    \"files\": [\"s3://bucket/models/\", \"s3://bucket/data/\"],
    \"metadata_template\": \"ml\",
    \"metadata\": {
        \"model_type\": \"transformer\",
        \"training_data\": \"ImageNet-1K\",
        \"accuracy\": 0.94
    },
    \"auto_organize\": true,
    \"dry_run\": false
})

# Response structure
{
    \"success\": true,
    \"package_name\": \"genomics/study-001\",
    \"package_uri\": \"quilt+s3://quilt-example#package=genomics/study-001\",
    \"catalog_url\": \"https://demo.quiltdata.com/b/quilt-example/packages/genomics/study-001\",
    \"files_added\": 2,
    \"total_size\": \"1.2 GB\",
    \"metadata_template\": \"genomics\",
    \"organization\": {
        \"data/\": 2
    },
    \"next_steps\": [
        \"View package: https://demo.quiltdata.com/b/quilt-example/packages/genomics/study-001\",
        \"Browse contents: package_browse('genomics/study-001')\",
        \"Validate integrity: package_validate('genomics/study-001')\"
    ]
}
```

**Metadata Templates Available:**

- `standard`: General-purpose metadata
- `genomics`: Genomic data with organism, genome build, etc.
- `ml`: Machine learning models and datasets
- `research`: Research data with study information
- `analytics`: Business analytics and reporting data

#### `package_create_from_s3`

Create packages from entire S3 buckets or prefixes with intelligent organization.

```python
# Create from S3 bucket
result = await mcp_client.call_tool(\"package_create_from_s3\", {
    \"source_bucket\": \"s3://raw-data-bucket\",
    \"package_name\": \"processed/batch-2024-08\",
    \"source_prefix\": \"2024/08/\",
    \"description\": \"August 2024 data processing batch\",
    \"auto_organize\": true,
    \"generate_readme\": true,
    \"metadata_template\": \"analytics\"
})

# Advanced options
result = await mcp_client.call_tool(\"package_create_from_s3\", {
    \"source_bucket\": \"s3://genomics-raw\",
    \"package_name\": \"genomics/ccle-batch-1\",
    \"include_patterns\": [\"*.fastq.gz\", \"*.vcf\"],
    \"exclude_patterns\": [\"*temp*\", \"*.log\"],
    \"confirm_structure\": false,
    \"dry_run\": false
})
```

#### `create_package` (Unified Interface)

Simplified package creation interface that handles everything automatically.

```python
# Simple creation
result = await mcp_client.call_tool(\"create_package\", {
    \"name\": \"team/dataset\",
    \"files\": [\"s3://bucket/file1.csv\", \"s3://bucket/file2.json\"],
    \"description\": \"Team dataset for analysis\"
})

# With auto-organization
result = await mcp_client.call_tool(\"create_package\", {
    \"name\": \"research/experiment-1\",
    \"files\": [\"s3://bucket/data/\"],
    \"auto_organize\": true,
    \"target_registry\": \"s3://my-quilt-bucket\"
})
```

### Package Validation and Management

#### `package_validate`

Validate package integrity and accessibility with comprehensive checks.

```python
# Basic validation
result = await mcp_client.call_tool(\"package_validate\", {
    \"package_name\": \"genomics/study-001\",
    \"check_integrity\": true,
    \"check_accessibility\": true
})

# Response structure
{
    \"success\": true,
    \"package_name\": \"genomics/study-001\",
    \"validation_results\": {
        \"integrity_check\": {
            \"passed\": true,
            \"files_checked\": 150,
            \"files_valid\": 150,
            \"issues\": []
        },
        \"accessibility_check\": {
            \"passed\": true,
            \"files_accessible\": 150,
            \"files_inaccessible\": 0,
            \"issues\": []
        }
    },
    \"recommendations\": [],
    \"overall_status\": \"healthy\"
}
```

#### `package_contents_search`

Search within a specific package's contents by filename or path.

```python
result = await mcp_client.call_tool(\"package_contents_search\", {
    \"package_name\": \"genomics/ccle-rnaseq\",
    \"query\": \"sample_001\",
    \"registry\": \"s3://quilt-example\",
    \"include_signed_urls\": true
})

# Response includes matching files with download URLs
{
    \"success\": true,
    \"matches\": [
        {
            \"logical_key\": \"data/sample_001.fastq.gz\",
            \"s3_uri\": \"s3://quilt-example/.../sample_001.fastq.gz\",
            \"size\": 1048576,
            \"download_url\": \"https://...\"
        }
    ]
}
```

#### `package_update_metadata`

Update package metadata without recreating the entire package.

```python
result = await mcp_client.call_tool(\"package_update_metadata\", {
    \"package_name\": \"genomics/study-001\",
    \"metadata\": {
        \"analysis_complete\": true,
        \"results_published\": \"2024-08-27\",
        \"doi\": \"10.1234/example.2024\"
    },
    \"merge_with_existing\": true
})
```

## 🗄️ S3 Operations

### Bucket Operations

#### `bucket_objects_list`

List objects in S3 buckets with filtering and pagination.

```python
# Basic listing
result = await mcp_client.call_tool(\"bucket_objects_list\", {
    \"bucket\": \"s3://my-data-bucket\",
    \"max_keys\": 100,
    \"include_signed_urls\": true
})

# With prefix filtering
result = await mcp_client.call_tool(\"bucket_objects_list\", {
    \"bucket\": \"s3://my-data-bucket\",
    \"prefix\": \"genomics/2024/\",
    \"max_keys\": 50,
    \"continuation_token\": \"\"  # For pagination
})

# Response structure
{
    \"success\": true,
    \"bucket_name\": \"my-data-bucket\",
    \"objects\": [
        {
            \"key\": \"genomics/2024/sample_001.fastq.gz\",
            \"size\": 1048576,
            \"last_modified\": \"2024-08-01T10:30:00Z\",
            \"etag\": \"abc123...\",
            \"download_url\": \"https://...\"
        }
    ],
    \"count\": 25,
    \"is_truncated\": false,
    \"next_continuation_token\": null
}
```

#### `bucket_objects_search`

Search objects using Elasticsearch with advanced query capabilities.

```python
# Text search
result = await mcp_client.call_tool(\"bucket_objects_search\", {
    \"bucket\": \"s3://my-data-bucket\",
    \"query\": \"RNA-seq fastq\",
    \"limit\": 20
})

# Advanced query with filters
result = await mcp_client.call_tool(\"bucket_objects_search\", {
    \"bucket\": \"s3://my-data-bucket\",
    \"query\": {
        \"bool\": {
            \"must\": [
                {\"match\": {\"key\": \"genomics\"}},
                {\"range\": {\"size\": {\"gte\": 1000000}}}
            ]
        }
    },
    \"limit\": 10
})
```

#### `bucket_objects_search_graphql`

Search bucket objects using GraphQL with rich filtering capabilities.

```python
result = await mcp_client.call_tool(\"bucket_objects_search_graphql\", {
    \"bucket\": \"s3://my-data-bucket\",
    \"object_filter\": {
        \"key_contains\": \"genomics\",
        \"size_gte\": 1000000,
        \"modified_after\": \"2024-01-01\"
    },
    \"first\": 50
})
```

### Object Operations

#### `bucket_object_info`

Get detailed metadata for a specific S3 object.

```python
result = await mcp_client.call_tool(\"bucket_object_info\", {
    \"s3_uri\": \"s3://my-bucket/data/sample.fastq.gz\"
})

# Response includes comprehensive metadata
{
    \"success\": true,
    \"s3_uri\": \"s3://my-bucket/data/sample.fastq.gz\",
    \"size\": 1048576,
    \"content_type\": \"application/gzip\",
    \"etag\": \"abc123...\",
    \"last_modified\": \"2024-08-01T10:30:00Z\",
    \"metadata\": {
        \"sample_id\": \"SAMPLE_001\",
        \"experiment\": \"RNA_SEQ_001\"
    },
    \"storage_class\": \"STANDARD\"
}
```

#### `bucket_object_text`

Read text content from S3 objects with encoding support.

```python
# Read text file
result = await mcp_client.call_tool(\"bucket_object_text\", {
    \"s3_uri\": \"s3://my-bucket/data/metadata.csv\",
    \"max_bytes\": 65536,
    \"encoding\": \"utf-8\"
})

# Response includes decoded content
{
    \"success\": true,
    \"content\": \"sample_id,condition,treatment\\nSAMPLE_001,control,none\\n...\",
    \"size\": 1024,
    \"encoding\": \"utf-8\",
    \"truncated\": false
}
```

#### `bucket_object_fetch`

Fetch binary or text data from S3 objects.

```python
# Fetch binary data
result = await mcp_client.call_tool(\"bucket_object_fetch\", {
    \"s3_uri\": \"s3://my-bucket/data/image.png\",
    \"max_bytes\": 65536,
    \"base64_encode\": true
})

# Response includes base64-encoded data
{
    \"success\": true,
    \"data\": \"iVBORw0KGgoAAAANSUhEUgAA...\",  # Base64 encoded
    \"size\": 2048,
    \"content_type\": \"image/png\",
    \"encoding\": \"base64\"
}
```

#### `bucket_object_link`

Generate presigned URLs for downloading S3 objects.

```python
result = await mcp_client.call_tool(\"bucket_object_link\", {
    \"s3_uri\": \"s3://my-bucket/data/large_file.fastq.gz\",
    \"expiration\": 3600  # 1 hour
})

# Response includes presigned URL
{
    \"success\": true,
    \"download_url\": \"https://my-bucket.s3.amazonaws.com/data/large_file.fastq.gz?X-Amz-Algorithm=...\",
    \"expires_at\": \"2024-08-27T15:30:00Z\",
    \"expiration_seconds\": 3600
}
```

#### `bucket_objects_put`

Upload multiple objects to S3 buckets.

```python
# Upload text and binary data
result = await mcp_client.call_tool(\"bucket_objects_put\", {
    \"bucket\": \"s3://my-bucket\",
    \"items\": [
        {
            \"key\": \"data/metadata.csv\",
            \"text\": \"sample_id,condition\\nSAMPLE_001,control\",
            \"content_type\": \"text/csv\"
        },
        {
            \"key\": \"data/binary_file.dat\",
            \"data\": \"iVBORw0KGgoAAAANSUhEUgAA...\",  # Base64
            \"content_type\": \"application/octet-stream\",
            \"metadata\": {\"experiment\": \"EXP_001\"}
        }
    ]
})

# Response includes upload results
{
    \"success\": true,
    \"uploaded\": 2,
    \"failed\": 0,
    \"results\": [
        {
            \"key\": \"data/metadata.csv\",
            \"success\": true,
            \"s3_uri\": \"s3://my-bucket/data/metadata.csv\",
            \"size\": 45
        }
    ]
}
```

## 🔍 Search & Discovery

### Unified Search System

#### `unified_search` (Primary Search Tool)

Intelligent multi-backend search across Quilt catalogs, packages, and S3 buckets.

```python
# Natural language search
result = await mcp_client.call_tool(\"unified_search\", {
    \"query\": \"RNA-seq data from human samples\",
    \"scope\": \"global\",
    \"limit\": 50,
    \"include_metadata\": true
})

# Scoped search within specific package
result = await mcp_client.call_tool(\"unified_search\", {
    \"query\": \"README files\",
    \"scope\": \"package\",
    \"target\": \"genomics/ccle-rnaseq\",
    \"limit\": 10
})

# Search with filters
result = await mcp_client.call_tool(\"unified_search\", {
    \"query\": \"large genomics files\",
    \"filters\": {
        \"file_extensions\": [\"fastq.gz\", \"vcf\"],
        \"size_gt\": \"100MB\",
        \"date_after\": \"2024-01-01\"
    },
    \"backends\": [\"elasticsearch\", \"graphql\"],
    \"explain_query\": true
})

# Response structure
{
    \"success\": true,
    \"query\": \"RNA-seq data from human samples\",
    \"results\": [
        {
            \"title\": \"Human RNA-seq Dataset - CCLE\",
            \"description\": \"Comprehensive RNA sequencing data...\",
            \"source\": \"package\",
            \"package_name\": \"genomics/ccle-rnaseq\",
            \"score\": 0.95,
            \"metadata\": {
                \"organism\": \"human\",
                \"data_type\": \"RNA-seq\",
                \"samples\": 1019
            },
            \"url\": \"https://demo.quiltdata.com/b/quilt-example/packages/genomics/ccle-rnaseq\"
        }
    ],
    \"total_results\": 25,
    \"backends_used\": [\"graphql\", \"elasticsearch\"],
    \"execution_time_ms\": 245,
    \"query_explanation\": {
        \"parsed_query\": \"RNA-seq AND human AND samples\",
        \"backend_selection\": \"Selected GraphQL for package metadata, Elasticsearch for content search\"
    }
}
```

**Search Scopes:**

- `global`: Search across all systems
- `catalog`: Current catalog only
- `package`: Specific package (requires target)
- `bucket`: Specific S3 bucket (requires target)

**Backend Options:**

- `auto`: Intelligent backend selection (default)
- `graphql`: GraphQL API for structured queries
- `elasticsearch`: Full-text search
- `s3`: Direct S3 object search

#### `search_suggest`

Get intelligent search suggestions based on partial queries.

```python
result = await mcp_client.call_tool(\"search_suggest\", {
    \"partial_query\": \"RNA\",
    \"context\": \"genomics research\",
    \"suggestion_types\": [\"auto\"],
    \"limit\": 10
})

# Response includes suggestions
{
    \"success\": true,
    \"suggestions\": [
        {
            \"query\": \"RNA-seq data\",
            \"type\": \"query_completion\",
            \"confidence\": 0.9,
            \"description\": \"Search for RNA sequencing datasets\"
        },
        {
            \"query\": \"RNA expression profiles\",
            \"type\": \"query_expansion\",
            \"confidence\": 0.8
        }
    ]
}
```

#### `search_explain`

Explain how a search query would be processed and executed.

```python
result = await mcp_client.call_tool(\"search_explain\", {
    \"query\": \"large CSV files in genomics packages\",
    \"scope\": \"global\"
})

# Response includes detailed explanation
{
    \"success\": true,
    \"query_analysis\": {
        \"parsed_terms\": [\"large\", \"CSV\", \"files\", \"genomics\", \"packages\"],
        \"filters_detected\": {\"file_extension\": \"csv\", \"size\": \"large\"},
        \"scope_analysis\": \"Global search across all backends\"
    },
    \"backend_selection\": {
        \"selected_backends\": [\"graphql\", \"elasticsearch\"],
        \"reasoning\": \"GraphQL for package metadata, Elasticsearch for file content\"
    },
    \"execution_plan\": [
        \"Parse query for filters and terms\",
        \"Execute GraphQL query for packages matching 'genomics'\",
        \"Execute Elasticsearch query for CSV files\",
        \"Merge and rank results by relevance\"
    ]
}
```

## 📊 Analytics & SQL

### AWS Athena Integration

#### `athena_query_execute`

Execute SQL queries against data using AWS Athena.

```python
# Basic SQL query
result = await mcp_client.call_tool(\"athena_query_execute\", {
    \"query\": \"SELECT sample_id, expression_level FROM genomics_db.rna_seq WHERE organism = 'human' LIMIT 10\",
    \"database_name\": \"genomics_db\",
    \"max_results\": 1000
})

# Advanced query with output formatting
result = await mcp_client.call_tool(\"athena_query_execute\", {
    \"query\": \"SELECT COUNT(*) as total_samples, AVG(expression_level) as avg_expression FROM genomics_db.rna_seq GROUP BY condition\",
    \"output_format\": \"json\",
    \"use_quilt_auth\": true
})

# Response structure
{
    \"success\": true,
    \"query\": \"SELECT sample_id, expression_level FROM...\",
    \"results\": [
        {\"sample_id\": \"SAMPLE_001\", \"expression_level\": 12.5},
        {\"sample_id\": \"SAMPLE_002\", \"expression_level\": 8.3}
    ],
    \"row_count\": 10,
    \"execution_time_ms\": 1250,
    \"data_scanned_bytes\": 1048576,
    \"query_execution_id\": \"abc123-def456-789\"
}
```

**Important SQL Syntax Notes:**

- Use **double quotes** for table/column names: `\"table-with-hyphens\"`
- **No backticks** - Athena uses Presto/Trino SQL syntax
- Example: `SELECT * FROM \"genomics-db\".\"rna-seq\" WHERE \"sample-id\" = 'value'`

#### `athena_databases_list`

List available databases in AWS Glue Data Catalog.

```python
result = await mcp_client.call_tool(\"athena_databases_list\", {
    \"catalog_name\": \"AwsDataCatalog\"
})

# Response includes database information
{
    \"success\": true,
    \"databases\": [
        {
            \"name\": \"genomics_db\",
            \"description\": \"Genomics research database\",
            \"location\": \"s3://genomics-data/\",
            \"parameters\": {}
        }
    ],
    \"count\": 5
}
```

#### `athena_tables_list`

List tables in a specific database with schema information.

```python
result = await mcp_client.call_tool(\"athena_tables_list\", {
    \"database_name\": \"genomics_db\",
    \"table_pattern\": \"rna_*\"  # Optional pattern filter
})

# Response includes table details
{
    \"success\": true,
    \"tables\": [
        {
            \"name\": \"rna_seq\",
            \"type\": \"EXTERNAL_TABLE\",
            \"location\": \"s3://genomics-data/rna_seq/\",
            \"columns\": [
                {\"name\": \"sample_id\", \"type\": \"string\"},
                {\"name\": \"expression_level\", \"type\": \"double\"}
            ],
            \"partitions\": [\"year\", \"month\"]
        }
    ]
}
```

#### `athena_table_schema`

Get detailed schema information for a specific table.

```python
result = await mcp_client.call_tool(\"athena_table_schema\", {
    \"database_name\": \"genomics_db\",
    \"table_name\": \"rna_seq\"
})

# Response includes comprehensive schema
{
    \"success\": true,
    \"table_name\": \"rna_seq\",
    \"columns\": [
        {
            \"name\": \"sample_id\",
            \"type\": \"string\",
            \"comment\": \"Unique sample identifier\"
        }
    ],
    \"partition_keys\": [
        {\"name\": \"year\", \"type\": \"string\"},
        {\"name\": \"month\", \"type\": \"string\"}
    ],
    \"table_type\": \"EXTERNAL_TABLE\",
    \"location\": \"s3://genomics-data/rna_seq/\",
    \"input_format\": \"org.apache.hadoop.mapred.TextInputFormat\",
    \"output_format\": \"org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat\"
}
```

#### `athena_query_validate`

Validate SQL query syntax without executing it.

```python
result = await mcp_client.call_tool(\"athena_query_validate\", {
    \"query\": \"SELECT sample_id, AVG(expression_level) FROM genomics_db.rna_seq GROUP BY sample_id\"
})

# Response includes validation results
{
    \"success\": true,
    \"valid\": true,
    \"suggestions\": [
        \"Consider adding LIMIT clause for large result sets\",
        \"Query will scan approximately 100MB of data\"
    ],
    \"estimated_cost\": \"$0.005\",
    \"estimated_runtime\": \"2-5 seconds\"
}
```

#### `athena_query_history`

Retrieve query execution history from Athena.

```python
result = await mcp_client.call_tool(\"athena_query_history\", {
    \"max_results\": 20,
    \"status_filter\": \"SUCCEEDED\",
    \"start_time\": \"2024-08-01T00:00:00Z\"
})

# Response includes query history
{
    \"success\": true,
    \"queries\": [
        {
            \"query_execution_id\": \"abc123-def456\",
            \"query\": \"SELECT COUNT(*) FROM genomics_db.rna_seq\",
            \"status\": \"SUCCEEDED\",
            \"execution_time_ms\": 1250,
            \"data_scanned_bytes\": 1048576,
            \"submission_time\": \"2024-08-27T10:30:00Z\"
        }
    ]
}
```

#### `athena_workgroups_list`

List available Athena workgroups.

```python
result = await mcp_client.call_tool(\"athena_workgroups_list\", {
    \"use_quilt_auth\": true
})

# Response includes workgroup information
{
    \"success\": true,
    \"workgroups\": [
        {
            \"name\": \"primary\",
            \"description\": \"Default workgroup\",
            \"state\": \"ENABLED\",
            \"configuration\": {
                \"result_location\": \"s3://athena-results/\",
                \"enforce_workgroup_configuration\": false
            }
        }
    ]
}
```

### Quilt Tabulator Integration

#### `tabulator_tables_list`

List Quilt Tabulator tables for SQL querying across packages.

```python
result = await mcp_client.call_tool(\"tabulator_tables_list\", {
    \"bucket_name\": \"quilt-example\"
})

# Response includes table configurations
{
    \"success\": true,
    \"tables\": [
        {
            \"name\": \"genomics_samples\",
            \"description\": \"Aggregated genomics sample metadata\",
            \"schema\": [
                {\"name\": \"sample_id\", \"type\": \"STRING\"},
                {\"name\": \"organism\", \"type\": \"STRING\"},
                {\"name\": \"tissue_type\", \"type\": \"STRING\"}
            ],
            \"package_pattern\": \"genomics/.*\",
            \"logical_key_pattern\": \"metadata\\\\.csv$\"
        }
    ],
    \"count\": 3
}
```

#### `tabulator_table_create`

Create or update Tabulator tables by supplying the YAML configuration used by Quilt.

```python
yaml_config = """
parser:
  format: csv
  header: true
  delimiter: "\t"
schema:
  - name: sample_id
    type: STRING
  - name: gene
    type: STRING
  - name: tpm
    type: FLOAT
source:
  type: quilt-packages
  package_name: ^nextflow/(?P<study_id>.+)$
  logical_key: quantification/genes/(?P<sample_id>[^/]+)_genes\.sf
"""

result = await mcp_client.call_tool("tabulator_table_create", {
    "bucket_name": "nextflowtower",
    "table_name": "sail-nextflow",
    "config_yaml": yaml_config,
})
```

#### `tabulator_table_query`

Run a tabulator query and return formatted rows. Supports optional filters, column selection, and pagination controls (`limit`, `offset`).

```python
result = await mcp_client.call_tool("tabulator_table_query", {
    "bucket_name": "nextflowtower",
    "table_name": "sail-nextflow",
    "limit": 20,
    "filters": {"sample_id": "22008R-31-01_S28"}
})

print(result["formatted_table"])
```

#### `tabulator_table_preview`

Preview the first N rows (default 10) of a tabulator table.

```python
preview = await mcp_client.call_tool("tabulator_table_preview", {
    "bucket_name": "nextflowtower",
    "table_name": "sail-nextflow",
    "limit": 5
})

print(preview["preview_table"])
```

#### `tabulator_open_query_status` / `tabulator_open_query_toggle`

Manage Tabulator open query feature for broader access.

```python
# Check status
status = await mcp_client.call_tool(\"tabulator_open_query_status\", {})

# Enable open query
result = await mcp_client.call_tool(\"tabulator_open_query_toggle\", {
    \"enabled\": true
})
```

#### `tabulator_table_delete`

Delete an existing Tabulator table.

```python
result = await mcp_client.call_tool("tabulator_table_delete", {
    "bucket_name": "quilt-example",
    "table_name": "deprecated_table"
})
```

#### `tabulator_table_rename`

Rename an existing Tabulator table.

```python
result = await mcp_client.call_tool("tabulator_table_rename", {
    "bucket_name": "quilt-example",
    "table_name": "old_table_name",
    "new_table_name": "new_table_name"
})
```

## 🔧 Workflow Management

### Workflow Orchestration

#### `workflow_create`

Create multi-step workflows for complex operations.

```python
result = await mcp_client.call_tool(\"workflow_create\", {
    \"workflow_id\": \"genomics-processing-001\",
    \"name\": \"Genomics Data Processing Pipeline\",
    \"description\": \"Process raw genomics data through QC, alignment, and analysis\",
    \"metadata\": {
        \"project\": \"CCLE\",
        \"data_type\": \"RNA-seq\"
    }
})

# Response includes workflow details
{
    \"success\": true,
    \"workflow_id\": \"genomics-processing-001\",
    \"status\": \"created\",
    \"created_at\": \"2024-08-27T10:30:00Z\",
    \"steps\": [],
    \"metadata\": {\"project\": \"CCLE\", \"data_type\": \"RNA-seq\"}
}
```

#### `workflow_add_step`

Add steps to existing workflows.

```python
result = await mcp_client.call_tool(\"workflow_add_step\", {
    \"workflow_id\": \"genomics-processing-001\",
    \"step_id\": \"quality_control\",
    \"description\": \"Run FastQC on raw sequencing data\",
    \"step_type\": \"automated\",
    \"dependencies\": [],  # No dependencies for first step
    \"metadata\": {
        \"tool\": \"FastQC\",
        \"version\": \"0.11.9\"
    }
})

# Add dependent step
result = await mcp_client.call_tool(\"workflow_add_step\", {
    \"workflow_id\": \"genomics-processing-001\",
    \"step_id\": \"alignment\",
    \"description\": \"Align reads to reference genome\",
    \"step_type\": \"automated\",
    \"dependencies\": [\"quality_control\"],
    \"metadata\": {
        \"tool\": \"STAR\",
        \"reference_genome\": \"GRCh38\"
    }
})
```

#### `workflow_update_step`

Update step status and results.

```python
result = await mcp_client.call_tool(\"workflow_update_step\", {
    \"workflow_id\": \"genomics-processing-001\",
    \"step_id\": \"quality_control\",
    \"status\": \"completed\",
    \"result\": {
        \"files_processed\": 24,
        \"quality_score\": 0.95,
        \"output_location\": \"s3://results/qc/\"
    }
})
```

#### `workflow_get_status`

Get comprehensive workflow status.

```python
result = await mcp_client.call_tool(\"workflow_get_status\", {
    \"workflow_id\": \"genomics-processing-001\"
})

# Response includes detailed status
{
    \"success\": true,
    \"workflow_id\": \"genomics-processing-001\",
    \"name\": \"Genomics Data Processing Pipeline\",
    \"status\": \"in_progress\",
    \"progress\": {
        \"completed_steps\": 1,
        \"total_steps\": 3,
        \"percentage\": 33.3
    },
    \"steps\": [
        {
            \"step_id\": \"quality_control\",
            \"status\": \"completed\",
            \"started_at\": \"2024-08-27T10:35:00Z\",
            \"completed_at\": \"2024-08-27T10:45:00Z\"
        }
    ],
    \"next_steps\": [\"alignment\"]
}
```

#### `workflow_list_all`

List all workflows with summary information.

```python
result = await mcp_client.call_tool(\"workflow_list_all\", {})

# Response includes workflow summaries
{
    \"success\": true,
    \"workflows\": [
        {
            \"workflow_id\": \"genomics-processing-001\",
            \"name\": \"Genomics Data Processing Pipeline\",
            \"status\": \"in_progress\",
            \"created_at\": \"2024-08-27T10:30:00Z\",
            \"steps_completed\": 1,
            \"steps_total\": 3
        }
    ],
    \"count\": 5
}
```

#### `workflow_template_apply`

Apply pre-defined workflow templates.

```python
result = await mcp_client.call_tool(\"workflow_template_apply\", {
    \"template_name\": \"genomics_rnaseq_pipeline\",
    \"workflow_id\": \"rnaseq-batch-2024-08\",
    \"params\": {
        \"input_bucket\": \"s3://raw-genomics-data\",
        \"output_bucket\": \"s3://processed-genomics-data\",
        \"reference_genome\": \"GRCh38\",
        \"sample_count\": 96
    }
})

# Creates workflow with pre-configured steps
{
    \"success\": true,
    \"workflow_id\": \"rnaseq-batch-2024-08\",
    \"template_applied\": \"genomics_rnaseq_pipeline\",
    \"steps_created\": 6,
    \"estimated_duration\": \"4-6 hours\"
}
```

## 🏷️ Metadata & Templates

### Metadata Templates

#### `list_metadata_templates`

List available metadata templates with descriptions.

```python
result = await mcp_client.call_tool(\"list_metadata_templates\", {})

# Response includes template information
{
    \"success\": true,
    \"templates\": {
        \"standard\": {
            \"description\": \"General-purpose metadata template\",
            \"fields\": [\"title\", \"description\", \"keywords\", \"created_by\"],
            \"use_cases\": [\"General data packages\", \"Mixed content\"]
        },
        \"genomics\": {
            \"description\": \"Genomics and bioinformatics data\",
            \"fields\": [\"organism\", \"genome_build\", \"data_type\", \"sequencing_platform\"],
            \"use_cases\": [\"RNA-seq\", \"DNA-seq\", \"Variant calling\", \"GWAS\"]
        },
        \"ml\": {
            \"description\": \"Machine learning models and datasets\",
            \"fields\": [\"model_type\", \"training_data\", \"accuracy\", \"framework\"],
            \"use_cases\": [\"Model training\", \"Dataset preparation\", \"Experiment tracking\"]
        }
    }
}
```

#### `get_metadata_template`

Get a specific metadata template with optional custom fields.

```python
# Get genomics template
result = await mcp_client.call_tool(\"get_metadata_template\", {
    \"template_name\": \"genomics\",
    \"custom_fields\": {
        \"study_id\": \"CCLE_2024\",
        \"principal_investigator\": \"Dr. Smith\"
    }
})

# Response includes complete metadata structure
{
    \"success\": true,
    \"template_name\": \"genomics\",
    \"metadata\": {
        \"title\": \"\",
        \"description\": \"\",
        \"organism\": \"\",
        \"genome_build\": \"\",
        \"data_type\": \"\",
        \"sequencing_platform\": \"\",
        \"study_id\": \"CCLE_2024\",
        \"principal_investigator\": \"Dr. Smith\",
        \"created_at\": \"2024-08-27T10:30:00Z\",
        \"template_version\": \"1.0\"
    }
}
```

#### `create_metadata_from_template`

Create metadata using a template - simplified interface.

```python
result = await mcp_client.call_tool(\"create_metadata_from_template\", {
    \"template_name\": \"genomics\",
    \"description\": \"Human RNA-seq data from CCLE cell lines\",
    \"custom_fields\": {
        \"organism\": \"Homo sapiens\",
        \"genome_build\": \"GRCh38\",
        \"data_type\": \"RNA-seq\",
        \"sequencing_platform\": \"Illumina NovaSeq\"
    }
})

# Returns complete metadata ready for package creation
{
    \"success\": true,
    \"metadata\": {
        \"title\": \"Human RNA-seq data from CCLE cell lines\",
        \"description\": \"Human RNA-seq data from CCLE cell lines\",
        \"organism\": \"Homo sapiens\",
        \"genome_build\": \"GRCh38\",
        \"data_type\": \"RNA-seq\",
        \"sequencing_platform\": \"Illumina NovaSeq\",
        \"created_at\": \"2024-08-27T10:30:00Z\"
    },
    \"template_used\": \"genomics\"
}
```

#### `validate_metadata_structure`

Validate metadata structure and provide improvement suggestions.

```python
result = await mcp_client.call_tool(\"validate_metadata_structure\", {
    \"metadata\": {
        \"title\": \"My Dataset\",
        \"organism\": \"human\",  # Should be \"Homo sapiens\"
        \"data_type\": \"rna\"     # Should be \"RNA-seq\"
    },
    \"template_name\": \"genomics\"
})

# Response includes validation results and suggestions
{
    \"success\": true,
    \"valid\": false,
    \"issues\": [
        {
            \"field\": \"organism\",
            \"issue\": \"Non-standard organism name\",
            \"suggestion\": \"Use 'Homo sapiens' instead of 'human'\"
        },
        {
            \"field\": \"data_type\",
            \"issue\": \"Abbreviated data type\",
            \"suggestion\": \"Use 'RNA-seq' instead of 'rna'\"
        }
    ],
    \"missing_fields\": [\"genome_build\", \"sequencing_platform\"],
    \"score\": 0.6
}
```

### Utility and Helper Tools

#### `quick_start`

Get quick start information and common usage patterns.

```python
result = await mcp_client.call_tool("quick_start", {})

# Response includes getting started guide and common patterns
{
    "success": true,
    "quick_start_guide": {
        "authentication": ["auth_status", "catalog_info"],
        "data_exploration": ["packages_search", "package_browse"],
        "package_creation": ["create_package_enhanced", "package_validate"]
    },
    "common_workflows": [...],
    "next_steps": [...]
}
```

#### `show_metadata_examples`

Show examples of metadata structures for different use cases.

```python
result = await mcp_client.call_tool("show_metadata_examples", {})

# Response includes metadata examples for different domains
{
    "success": true,
    "examples": {
        "genomics": {...},
        "ml": {...},
        "research": {...}
    }
}
```

#### `list_available_resources`

List available resources and capabilities in the current environment.

```python
result = await mcp_client.call_tool("list_available_resources", {})

# Response includes available catalogs, registries, and capabilities
{
    "success": true,
    "catalogs": [...],
    "registries": [...],
    "capabilities": [...],
    "permissions": [...]
}
```

### Quilt Summary Files

#### `create_quilt_summary_files`

Create comprehensive Quilt summary files for packages.

```python
result = await mcp_client.call_tool(\"create_quilt_summary_files\", {
    \"package_name\": \"genomics/ccle-rnaseq\",
    \"package_metadata\": {
        \"title\": \"CCLE RNA-seq Dataset\",
        \"organism\": \"Homo sapiens\",
        \"data_type\": \"RNA-seq\"
    },
    \"organized_structure\": {
        \"data/\": [
            {\"name\": \"sample_001.fastq.gz\", \"size\": 1048576},
            {\"name\": \"sample_002.fastq.gz\", \"size\": 1048576}
        ]
    },
    \"readme_content\": \"# CCLE RNA-seq Dataset\\n\\nThis package contains...\",
    \"source_info\": {
        \"source_bucket\": \"s3://ccle-data\",
        \"created_by\": \"genomics-pipeline\"
    }
})

# Response includes generated files
{
    \"success\": true,
    \"files_created\": {
        \"quilt_summarize.json\": {
            \"size\": 2048,
            \"content\": {\"package_name\": \"genomics/ccle-rnaseq\", ...}
        },
        \"README.md\": {
            \"size\": 1024,
            \"content\": \"# CCLE RNA-seq Dataset\\n\\n...\"
        },
        \"visualizations\": {
            \"file_distribution.png\": {\"size\": 4096, \"type\": \"chart\"}
        }
    }
}
```

#### `generate_quilt_summarize_json`

Generate machine-readable package summary following Quilt standards.

```python
result = await mcp_client.call_tool(\"generate_quilt_summarize_json\", {
    \"package_name\": \"genomics/study-001\",
    \"package_metadata\": {\"organism\": \"Homo sapiens\"},
    \"organized_structure\": {\"data/\": [...]},
    \"readme_content\": \"# Study 001\\n...\",
    \"source_info\": {\"created_by\": \"researcher\"}
})

# Returns structured JSON summary
{
    \"success\": true,
    \"quilt_summarize\": {
        \"package\": {
            \"name\": \"genomics/study-001\",
            \"created_at\": \"2024-08-27T10:30:00Z\",
            \"metadata\": {\"organism\": \"Homo sapiens\"}
        },
        \"structure\": {
            \"total_files\": 150,
            \"total_size\": \"2.5 GB\",
            \"file_types\": {\"fastq.gz\": 100, \"csv\": 50}
        },
        \"readme\": \"# Study 001\\n...\",
        \"visualizations\": [...]
    }
}
```

## 🔒 Permissions & Security

### AWS Permissions Discovery

#### `aws_permissions_discover`

Discover comprehensive AWS permissions for the current user/role.

```python
# Basic permission discovery
result = await mcp_client.call_tool(\"aws_permissions_discover\", {
    \"force_refresh\": false,
    \"include_cross_account\": false
})

# Detailed discovery with specific buckets
result = await mcp_client.call_tool(\"aws_permissions_discover\", {
    \"check_buckets\": [\"my-data-bucket\", \"shared-genomics-data\"],
    \"include_cross_account\": true,
    \"force_refresh\": true
})

# Response includes comprehensive permission analysis
{
    \"success\": true,
    \"user_identity\": {
        \"user_id\": \"AIDACKCEVSQ6C2EXAMPLE\",
        \"account\": \"123456789012\",
        \"arn\": \"arn:aws:iam::123456789012:user/researcher\"
    },
    \"bucket_permissions\": {
        \"my-data-bucket\": {
            \"read\": true,
            \"write\": true,
            \"list\": true,
            \"delete\": false,
            \"access_level\": \"read_write\"
        },
        \"shared-genomics-data\": {
            \"read\": true,
            \"write\": false,
            \"list\": true,
            \"delete\": false,
            \"access_level\": \"read_only\"
        }
    },
    \"service_permissions\": {
        \"s3\": [\"GetObject\", \"PutObject\", \"ListBucket\"],
        \"athena\": [\"StartQueryExecution\", \"GetQueryResults\"],
        \"glue\": [\"GetDatabase\", \"GetTable\"]
    },
    \"recommendations\": [
        \"You have full access to my-data-bucket for package creation\",
        \"Consider requesting write access to shared-genomics-data for collaboration\"
    ]
}
```

#### `bucket_access_check`

Check specific access permissions for a bucket.

```python
result = await mcp_client.call_tool(\"bucket_access_check\", {
    \"bucket_name\": \"genomics-research-data\",
    \"operations\": [\"read\", \"write\", \"list\", \"delete\"]
})

# Response includes detailed access report
{
    \"success\": true,
    \"bucket_name\": \"genomics-research-data\",
    \"access_results\": {
        \"read\": {
            \"allowed\": true,
            \"test_result\": \"Successfully read test object\",
            \"permissions\": [\"s3:GetObject\"]
        },
        \"write\": {
            \"allowed\": false,
            \"test_result\": \"Access denied: s3:PutObject\",
            \"required_permissions\": [\"s3:PutObject\"]
        },
        \"list\": {
            \"allowed\": true,
            \"test_result\": \"Successfully listed objects\",
            \"permissions\": [\"s3:ListBucket\"]
        }
    },
    \"overall_access\": \"read_only\",
    \"recommendations\": [
        \"Request s3:PutObject permission for package creation\",
        \"Contact bucket owner for write access\"
    ]
}
```

#### `bucket_recommendations_get`

Get smart bucket recommendations based on permissions and context.

```python
result = await mcp_client.call_tool(\"bucket_recommendations_get\", {
    \"operation_type\": \"package_creation\",
    \"source_bucket\": \"s3://raw-data\",
    \"user_context\": {
        \"department\": \"genomics\",
        \"project\": \"ccle\"
    }
})

# Response includes categorized recommendations
{
    \"success\": true,
    \"recommendations\": {
        \"primary\": [
            {
                \"bucket\": \"s3://genomics-packages\",
                \"access_level\": \"read_write\",
                \"rationale\": \"Full access, genomics-focused, department bucket\",
                \"confidence\": 0.95
            }
        ],
        \"secondary\": [
            {
                \"bucket\": \"s3://shared-research-data\",
                \"access_level\": \"read_write\",
                \"rationale\": \"Cross-department collaboration bucket\",
                \"confidence\": 0.7
            }
        ],
        \"not_recommended\": [
            {
                \"bucket\": \"s3://production-data\",
                \"reason\": \"Production bucket, read-only access\",
                \"access_level\": \"read_only\"
            }
        ]
    },
    \"context_analysis\": {
        \"operation_type\": \"package_creation\",
        \"required_permissions\": [\"read\", \"write\", \"list\"],
        \"department_match\": true
    }
}
```

## 👥 Administration

### User Management

#### `admin_users_list`

List all users in the registry with detailed information.

```python
result = await mcp_client.call_tool(\"admin_users_list\", {})

# Response includes formatted user table
{
    \"success\": true,
    \"users\": [
        {
            \"name\": \"researcher@example.com\",
            \"email\": \"researcher@example.com\",
            \"role\": \"user\",
            \"extra_roles\": [\"genomics_team\"],
            \"active\": true,
            \"admin\": false,
            \"last_login\": \"2024-08-27T10:30:00Z\"
        }
    ],
    \"count\": 25,
    \"formatted_table\": \"Name                    Email                   Role    Active  Admin\\n...\"
}
```

#### `admin_user_create`

Create new users in the registry.

```python
result = await mcp_client.call_tool(\"admin_user_create\", {
    \"name\": \"new.researcher@example.com\",
    \"email\": \"new.researcher@example.com\",
    \"role\": \"user\",
    \"extra_roles\": [\"genomics_team\", \"data_analysts\"]
})

# Response includes user creation details
{
    \"success\": true,
    \"user_created\": {
        \"name\": \"new.researcher@example.com\",
        \"email\": \"new.researcher@example.com\",
        \"role\": \"user\",
        \"extra_roles\": [\"genomics_team\", \"data_analysts\"],
        \"active\": true,
        \"admin\": false
    },
    \"next_steps\": [
        \"User can now log in to the catalog\",
        \"Send welcome email with login instructions\",
        \"Add user to relevant project teams\"
    ]
}
```

#### `admin_user_get`

Get detailed information about a specific user.

```python
result = await mcp_client.call_tool(\"admin_user_get\", {
    \"name\": \"researcher@example.com\"
})

# Response includes comprehensive user information
{
    \"success\": true,
    \"user\": {
        \"name\": \"researcher@example.com\",
        \"email\": \"researcher@example.com\",
        \"role\": \"user\",
        \"extra_roles\": [\"genomics_team\"],
        \"active\": true,
        \"admin\": false,
        \"created_at\": \"2024-01-15T09:00:00Z\",
        \"last_login\": \"2024-08-27T10:30:00Z\",
        \"login_count\": 156,
        \"packages_created\": 23,
        \"recent_activity\": [
            \"Created package genomics/study-042\",
            \"Browsed package shared/reference-data\"
        ]
    }
}
```

#### `admin_user_set_role`

Set primary and extra roles for a user.

```python
result = await mcp_client.call_tool(\"admin_user_set_role\", {
    \"name\": \"researcher@example.com\",
    \"role\": \"power_user\",
    \"extra_roles\": [\"genomics_team\", \"data_analysts\", \"package_reviewers\"],
    \"append\": false  # Replace existing extra roles
})
```

#### `admin_user_set_active`

Set user active status (enable/disable account).

```python
# Disable user account
result = await mcp_client.call_tool(\"admin_user_set_active\", {
    \"name\": \"former.employee@example.com\",
    \"active\": false
})

# Re-enable user account
result = await mcp_client.call_tool(\"admin_user_set_active\", {
    \"name\": \"returning.researcher@example.com\",
    \"active\": true
})
```

### Role Management

#### `admin_roles_list`

List all available roles with detailed information.

```python
result = await mcp_client.call_tool(\"admin_roles_list\", {})

# Response includes role information
{
    \"success\": true,
    \"roles\": [
        {
            \"name\": \"user\",
            \"description\": \"Standard user with basic package access\",
            \"permissions\": [\"read_packages\", \"create_packages\"],
            \"user_count\": 45
        },
        {
            \"name\": \"power_user\",
            \"description\": \"Advanced user with additional permissions\",
            \"permissions\": [\"read_packages\", \"create_packages\", \"manage_metadata\"],
            \"user_count\": 12
        },
        {
            \"name\": \"admin\",
            \"description\": \"Administrator with full system access\",
            \"permissions\": [\"*\"],
            \"user_count\": 3
        }
    ],
    \"formatted_table\": \"Role        Description                           Users\\n...\"
}
```

### SSO Configuration

#### `admin_sso_config_get`

Get current SSO configuration.

```python
result = await mcp_client.call_tool(\"admin_sso_config_get\", {})

# Response includes SSO configuration
{
    \"success\": true,
    \"sso_configured\": true,
    \"provider\": \"SAML\",
    \"configuration\": {
        \"entity_id\": \"https://catalog.example.com\",
        \"sso_url\": \"https://sso.example.com/saml\",
        \"certificate\": \"-----BEGIN CERTIFICATE-----\\n...\"
    },
    \"status\": \"active\"
}
```

#### `admin_sso_config_set`

Configure SSO settings.

```python
result = await mcp_client.call_tool(\"admin_sso_config_set\", {
    \"config\": \"\"\"
    <EntityDescriptor xmlns=\"urn:oasis:names:tc:SAML:2.0:metadata\" 
                      entityID=\"https://catalog.example.com\">
        <SPSSODescriptor>
            ...
        </SPSSODescriptor>
    </EntityDescriptor>
    \"\"\"
})
```

#### `admin_sso_config_remove`

Remove SSO configuration.

```python
result = await mcp_client.call_tool("admin_sso_config_remove", {})
```

### Advanced User Management

#### `admin_user_delete`

Delete a user from the registry.

```python
result = await mcp_client.call_tool("admin_user_delete", {
    "name": "former.employee@example.com"
})
```

#### `admin_user_set_email`

Update a user's email address.

```python
result = await mcp_client.call_tool("admin_user_set_email", {
    "name": "researcher@example.com",
    "email": "researcher.new@example.com"
})
```

#### `admin_user_set_admin`

Set or remove admin privileges for a user.

```python
result = await mcp_client.call_tool("admin_user_set_admin", {
    "name": "researcher@example.com",
    "admin": true
})
```

#### `admin_user_reset_password`

Reset a user's password.

```python
result = await mcp_client.call_tool("admin_user_reset_password", {
    "name": "researcher@example.com"
})
```

#### `admin_user_add_roles`

Add roles to a user.

```python
result = await mcp_client.call_tool("admin_user_add_roles", {
    "name": "researcher@example.com",
    "roles": ["genomics_team", "data_analysts"]
})
```

#### `admin_user_remove_roles`

Remove roles from a user.

```python
result = await mcp_client.call_tool("admin_user_remove_roles", {
    "name": "researcher@example.com",
    "roles": ["old_team"],
    "fallback": "user"  # Optional fallback role if all roles are removed
})
```

### Tabulator Administration

#### `admin_tabulator_open_query_get`

Get Tabulator open query configuration.

```python
result = await mcp_client.call_tool("admin_tabulator_open_query_get", {})
```

#### `admin_tabulator_open_query_set`

Set Tabulator open query configuration.

```python
result = await mcp_client.call_tool("admin_tabulator_open_query_set", {
    "enabled": true
})
```

## 🚀 Getting Started Examples

### Common Workflows

#### 1. Explore Available Data

```python
# Start by checking authentication
auth_result = await mcp_client.call_tool(\"auth_status\", {})

# List available packages
packages = await mcp_client.call_tool(\"packages_list\", {
    \"registry\": \"s3://quilt-example\",
    \"limit\": 20
})

# Search for specific data
search_results = await mcp_client.call_tool(\"unified_search\", {
    \"query\": \"genomics RNA-seq human\",
    \"limit\": 10
})

# Browse a specific package
package_contents = await mcp_client.call_tool(\"package_browse\", {
    \"package_name\": \"genomics/ccle-rnaseq\",
    \"recursive\": true,
    \"include_file_info\": true
})
```

#### 2. Create a New Package

```python
# Create package with genomics template
result = await mcp_client.call_tool(\"create_package_enhanced\", {
    \"name\": \"genomics/my-study\",
    \"files\": [
        \"s3://my-data/sample_001.fastq.gz\",
        \"s3://my-data/sample_002.fastq.gz\",
        \"s3://my-data/metadata.csv\"
    ],
    \"description\": \"RNA-seq analysis for cancer cell lines\",
    \"metadata_template\": \"genomics\",
    \"metadata\": {
        \"organism\": \"Homo sapiens\",
        \"genome_build\": \"GRCh38\",
        \"data_type\": \"RNA-seq\",
        \"sequencing_platform\": \"Illumina NovaSeq\"
    }
})

# Validate the created package
validation = await mcp_client.call_tool(\"package_validate\", {
    \"package_name\": \"genomics/my-study\"
})
```

#### 3. Analyze Data with SQL

```python
# List available databases
databases = await mcp_client.call_tool(\"athena_databases_list\", {})

# List tables in genomics database
tables = await mcp_client.call_tool(\"athena_tables_list\", {
    \"database_name\": \"genomics_db\"
})

# Execute analysis query
results = await mcp_client.call_tool(\"athena_query_execute\", {
    \"query\": \"\"\"
    SELECT 
        sample_id, 
        AVG(expression_level) as avg_expression,
        COUNT(*) as gene_count
    FROM genomics_db.rna_seq 
    WHERE organism = 'Homo sapiens' 
    GROUP BY sample_id 
    ORDER BY avg_expression DESC 
    LIMIT 10
    \"\"\",
    \"database_name\": \"genomics_db\"
})
```

#### 4. Set Up Workflow

```python
# Create workflow
workflow = await mcp_client.call_tool(\"workflow_create\", {
    \"workflow_id\": \"data-processing-pipeline\",
    \"name\": \"Genomics Data Processing\",
    \"description\": \"End-to-end genomics data processing\"
})

# Add processing steps
qc_step = await mcp_client.call_tool(\"workflow_add_step\", {
    \"workflow_id\": \"data-processing-pipeline\",
    \"step_id\": \"quality_control\",
    \"description\": \"Quality control analysis\",
    \"step_type\": \"automated\"
})

alignment_step = await mcp_client.call_tool(\"workflow_add_step\", {
    \"workflow_id\": \"data-processing-pipeline\",
    \"step_id\": \"alignment\",
    \"description\": \"Read alignment to reference\",
    \"dependencies\": [\"quality_control\"]
})

# Monitor workflow progress
status = await mcp_client.call_tool(\"workflow_get_status\", {
    \"workflow_id\": \"data-processing-pipeline\"
})
```

## 🔧 Tool Categories Summary

| Category | Primary Tools | Use Cases |
|----------|---------------|-----------|
| **Authentication** | `auth_status`, `catalog_info`, `filesystem_status` | Setup, troubleshooting, environment validation |
| **Package Management** | `create_package_enhanced`, `package_browse`, `packages_search` | Data organization, exploration |
| **S3 Operations** | `bucket_objects_list`, `bucket_object_info`, `unified_search` | Direct data access, file operations |
| **Search & Discovery** | `unified_search`, `search_suggest`, `packages_search` | Finding data, content discovery |
| **Analytics** | `athena_query_execute`, `tabulator_tables_list` | Data analysis, SQL queries |
| **Workflows** | `workflow_create`, `workflow_add_step`, `workflow_get_status` | Process orchestration, automation |
| **Metadata** | `get_metadata_template`, `validate_metadata_structure` | Data documentation, standardization |
| **Permissions** | `aws_permissions_discover`, `bucket_access_check` | Security, access validation |
| **Administration** | `admin_users_list`, `admin_user_create`, `admin_roles_list` | User management, role management |

This comprehensive tool reference provides everything needed to effectively use the Quilt MCP Server
for bioinformatics and data management workflows. Each tool is designed to work together as part
of a cohesive data management ecosystem.

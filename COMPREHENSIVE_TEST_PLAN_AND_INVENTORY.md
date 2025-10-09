# Comprehensive MCP Tool Testing Plan & Inventory

**Date**: October 9, 2025  
**Version**: v0.6.74  
**Status**: Active Testing Phase

---

## Table of Contents

1. [Tool Inventory & Actions](#tool-inventory--actions)
2. [Testing Status Matrix](#testing-status-matrix)
3. [Untested Actions - Test Queries](#untested-actions---test-queries)
4. [Scientific End-to-End Scenarios](#scientific-end-to-end-scenarios)
5. [Visualization Testing Plan](#visualization-testing-plan)
6. [Systematic Testing Schedule](#systematic-testing-schedule)

---

## Tool Inventory & Actions

### 1. **auth** (Authentication & Configuration)
- ✅ `status` - Check authentication status
- ⬜ `catalog_info` - Get catalog configuration info
- ⬜ `catalog_name` - Get current catalog name
- ⬜ `catalog_uri` - Generate Quilt+ URI
- ⬜ `catalog_url` - Generate catalog URL
- ⬜ `configure_catalog` - Configure catalog URL
- ⬜ `filesystem_status` - Check filesystem permissions
- ⬜ `switch_catalog` - Switch to different catalog

**Tested**: 1/8 actions (12.5%)

---

### 2. **buckets** (S3 Bucket Operations)
- ✅ `discover` - Discover accessible buckets with permissions
- ⬜ `object_fetch` - Fetch binary/text data from S3 object
- ⬜ `object_info` - Get metadata for S3 object
- ⬜ `object_link` - Generate presigned URL
- ⬜ `object_text` - Read text content from S3 object
- ⬜ `objects_put` - Upload multiple objects to S3

**Tested**: 1/6 actions (16.7%)

---

### 3. **packaging** (Package Management)
- ✅ `browse` - Browse package contents (via unified test)
- ⬜ `create` - Create new package
- ⬜ `create_from_s3` - Create package from S3 bucket contents
- ⬜ `metadata_templates` - List available metadata templates
- ⬜ `get_template` - Get specific metadata template

**Tested**: 1/5 actions (20%)

---

### 4. **search** (Unified Search)
- ✅ `unified_search` - Search packages, objects, or across catalog (bucket filtering tested)
- ⬜ `discover` - Discover search capabilities
- ⬜ `suggest` - Get search suggestions
- ⬜ `explain` - Explain how query would be processed

**Tested**: 1/4 actions (25%)

---

### 5. **admin** (Catalog Administration)

**User Management (7 actions)**:
- ✅ `users_list` - List all catalog users
- ⬜ `user_get` - Get user details
- ⬜ `user_create` - Create new user ← **TEST THIS**
- ⬜ `user_delete` - Delete user
- ⬜ `user_set_email` - Update user email
- ⬜ `user_set_admin` - Grant/revoke admin privileges
- ⬜ `user_set_active` - Activate/deactivate user

**Policy Management (7 actions)**:
- ✅ `policies_list` - List all policies
- ⬜ `policy_get` - Get policy details
- ⬜ `policy_create_managed` - Create managed policy (bucket permissions)
- ⬜ `policy_create_unmanaged` - Create unmanaged policy (IAM ARN)
- ⬜ `policy_update_managed` - Update managed policy
- ⬜ `policy_update_unmanaged` - Update unmanaged policy
- ⬜ `policy_delete` - Delete policy

**Role Management (4 actions)**:
- ✅ `roles_list` - List all IAM roles
- ⬜ `role_get` - Get role details
- ⬜ `role_create` - Create IAM role
- ⬜ `role_delete` - Delete IAM role

**SSO & Tabulator (5 actions)**:
- ⬜ `sso_config_get` - Get SSO configuration
- ⬜ `sso_config_set` - Update SSO configuration
- ⬜ `tabulator_list` - List tabulator tables (admin view)
- ⬜ `tabulator_create` - Create tabulator table (admin)
- ⬜ `tabulator_delete` - Delete tabulator table (admin)
- ⬜ `tabulator_open_query_get` - Get open query setting
- ⬜ `tabulator_open_query_set` - Set open query setting

**Tested**: 3/23 actions (13%)

---

### 6. **tabulator** (Tabulator Table Operations)
- ✅ `tables_list` - List tabulator tables in bucket
- ⬜ `tables_overview` - Get overview of all tables across buckets
- ⬜ `table_create` - Create new tabulator table
- ⬜ `table_delete` - Delete tabulator table
- ⬜ `table_rename` - Rename tabulator table
- ⬜ `table_get` - Get table configuration
- ⚠️ `table_query` - Query table data (405 error on demo)
- ⚠️ `table_preview` - Preview table rows (405 error on demo)
- ⬜ `open_query_status` - Check open query mode
- ⬜ `open_query_toggle` - Toggle open query mode

**Tested**: 1/10 actions (10%)  
**Blocked**: 2/10 actions (20%)

---

### 7. **athena_glue** (AWS Athena & Glue)
- ⬜ `databases_list` - List Athena/Glue databases
- ⬜ `tables_list` - List tables in database
- ⬜ `table_schema` - Get table schema details
- ⬜ `workgroups_list` - List Athena workgroups
- ⬜ `query_execute` - Execute SQL query
- ⬜ `query_history` - Retrieve query history
- ⬜ `query_validate` - Validate SQL syntax

**Tested**: 0/7 actions (0%)  
**Note**: Requires AWS IAM permissions (not available via JWT on demo)

---

### 8. **permissions** (Permission Management)
- ⬜ `discover` - Discover accessible buckets with permission levels
- ⬜ `check` - Check specific permissions
- ⬜ `test` - Test permission configurations

**Tested**: 0/3 actions (0%)

---

### 9. **quilt_summary** (Visualization & Summaries)
- ⬜ `create_files` - Create all Quilt summary files
- ⬜ `generate_viz` - Generate comprehensive visualizations
- ⬜ `generate_multi_viz` - Generate multi-format visualizations (NEW)
- ⬜ `generate_json` - Generate quilt_summarize.json

**Tested**: 0/4 actions (0%) ← **HIGH PRIORITY FOR TESTING**

---

### 10. **metadata_examples** (Metadata Helpers)
- ⬜ `from_template` - Create metadata from template
- ⬜ `fix_issues` - Get guidance for fixing metadata issues
- ⬜ `show_examples` - Show metadata usage examples

**Tested**: 0/3 actions (0%)

---

### 11. **workflow_orchestration** (Workflow Management)
- ⬜ `create` - Create new workflow
- ⬜ `add_step` - Add step to workflow
- ⬜ `update_step` - Update step status
- ⬜ `get_status` - Get workflow status
- ⬜ `list_all` - List all workflows
- ⬜ `template_apply` - Apply workflow template

**Tested**: 0/6 actions (0%)

---

## Testing Status Matrix

| Tool | Total Actions | Tested | Untested | Blocked | Coverage % |
|------|---------------|--------|----------|---------|------------|
| auth | 8 | 1 | 7 | 0 | 12.5% |
| buckets | 6 | 1 | 5 | 0 | 16.7% |
| packaging | 5 | 1 | 4 | 0 | 20% |
| search | 4 | 1 | 3 | 0 | 25% |
| admin | 23 | 3 | 20 | 0 | 13% |
| tabulator | 10 | 1 | 7 | 2 | 10% |
| athena_glue | 7 | 0 | 7 | 0 | 0% |
| permissions | 3 | 0 | 3 | 0 | 0% |
| quilt_summary | 4 | 0 | 4 | 0 | **0%** |
| metadata_examples | 3 | 0 | 3 | 0 | 0% |
| workflow_orchestration | 6 | 0 | 6 | 0 | 0% |
| **TOTAL** | **79** | **9** | **68** | **2** | **11.4%** |

---

## Untested Actions - Test Queries

### Priority 1: Admin User Management

#### Test 1: Create New User
```
"Create a new test user named 'test-qurator-user' with email 'test-qurator@example.com' 
and assign them the ZSDiscovery role"
```

**Expected**: User created successfully, appears in user list

---

#### Test 2: Get User Details
```
"Get detailed information about the user 'test-qurator-user'"
```

**Expected**: Returns user details including roles, email, last login

---

#### Test 3: Update User Email
```
"Update the email for user 'test-qurator-user' to 'updated-qurator@example.com'"
```

**Expected**: Email updated successfully

---

#### Test 4: Deactivate User
```
"Deactivate the user 'test-qurator-user'"
```

**Expected**: User marked as inactive

---

#### Test 5: Delete Test User
```
"Delete the user 'test-qurator-user'"
```

**Expected**: User removed from catalog

---

### Priority 2: Package Operations

#### Test 6: Create Package from Files
```
"Create a package called 'demo-team/test-dataset' with the first 3 CSV files from 
the nextflow/A549 package. Include metadata with description 'Test dataset for 
Qurator validation' and tags 'test', 'validation'"
```

**Expected**: Package created with files and metadata

---

#### Test 7: Get Metadata Template
```
"Show me the 'genomics' metadata template and explain what fields it includes"
```

**Expected**: Returns genomics template with field descriptions

---

### Priority 3: Bucket Operations

#### Test 8: Get Object Info
```
"Get detailed information about the file 'quantification/genes/22008R-31-01_S28_genes.sf' 
in the nextflow/A549 package"
```

**Expected**: Returns file size, last modified, content type, etc.

---

#### Test 9: Generate Presigned URL
```
"Generate a presigned download URL for 'quantification/genes/22008R-31-01_S28_genes.sf' 
in the nextflow/A549 package that expires in 1 hour"
```

**Expected**: Returns presigned URL

---

### Priority 4: Search Capabilities

#### Test 10: Search Discovery
```
"What search capabilities are available in this catalog?"
```

**Expected**: Lists search backends, scopes, and features

---

#### Test 11: Search Suggestions
```
"Give me search suggestions for 'genom'"
```

**Expected**: Returns suggestions like "genomics", "genome", etc.

---

### Priority 5: Auth & Configuration

#### Test 12: Catalog Info
```
"Show me information about the current catalog configuration"
```

**Expected**: Returns catalog URL, name, features, version info

---

#### Test 13: Generate Catalog URL
```
"Generate a catalog URL for viewing the nextflow/A549 package"
```

**Expected**: Returns URL like `https://demo.quiltdata.com/b/nextflowtower/packages/nextflow/A549/tree/latest`

---

## Scientific End-to-End Scenarios

### Scenario 1: RNA-seq Data Discovery & Analysis

**Goal**: Find, analyze, and visualize RNA-seq data

**Query**:
```
"I'm looking for RNA-seq gene expression data. Search the nextflowtower bucket for 
packages with quantification results, then analyze the nextflow/A549 package structure. 
Tell me what genes show the highest expression (TPM > 100) and create a visualization 
showing the distribution of TPM values across genes. Finally, create a summary document 
with key findings."
```

**Expected Tools Used**:
1. `search.unified_search` - Find RNA-seq packages
2. `packaging.browse` - Analyze package structure
3. `tabulator.table_query` - Query gene expression data (if endpoint available)
4. `quilt_summary.generate_viz` - Create TPM distribution visualization
5. `quilt_summary.create_files` - Generate summary document

**Success Criteria**:
- ✅ Finds relevant packages
- ✅ Identifies quantification files
- ✅ Extracts high-TPM genes
- ✅ Creates histogram/distribution chart
- ✅ Generates comprehensive summary

---

### Scenario 2: Cross-Study Sample Analysis

**Goal**: Compare samples across multiple studies

**Query**:
```
"I want to compare gene expression patterns across different studies in the nextflowtower 
bucket. List all studies (packages starting with 'nextflow/'), identify common genes 
across studies, and create a comparative visualization showing how expression levels 
differ between studies for the top 10 most variable genes."
```

**Expected Tools Used**:
1. `search.unified_search` - Find all nextflow/* packages
2. `packaging.browse` - Examine each package
3. `tabulator.table_query` - Extract gene expression data
4. `quilt_summary.generate_viz` - Create comparative heatmap/bar chart
5. `packaging.create` - Create summary package with findings

**Success Criteria**:
- ✅ Identifies all relevant studies
- ✅ Finds common genes across studies
- ✅ Calculates variance metrics
- ✅ Creates multi-study visualization
- ✅ Packages results for sharing

---

### Scenario 3: Quality Control & Validation

**Goal**: Validate data quality and identify issues

**Query**:
```
"Analyze the quality of RNA-seq data in the nextflowtower bucket. For each package, 
check: 1) Are all required files present? 2) Do gene expression values look reasonable? 
3) Are there any outlier samples? Create a QC report with visualizations showing 
sample distributions and flag any potential issues."
```

**Expected Tools Used**:
1. `search.unified_search` - Find all packages
2. `packaging.browse` - Check file completeness
3. `tabulator.table_query` - Extract expression data
4. `quilt_summary.generate_viz` - Create QC plots (boxplots, PCA)
5. `metadata_examples.from_template` - Create structured QC metadata
6. `packaging.create` - Package QC report

**Success Criteria**:
- ✅ Validates file structure
- ✅ Identifies missing files
- ✅ Detects outliers
- ✅ Creates QC visualizations
- ✅ Generates actionable report

---

### Scenario 4: Metadata Enrichment & Discovery

**Goal**: Enhance package discoverability through metadata

**Query**:
```
"Examine the nextflow/A549 package and enrich it with comprehensive metadata. 
Extract information about: organism (human), cell line (A549), experiment type 
(RNA-seq), data format (Salmon quantification), and number of samples. Create 
a detailed metadata file following the genomics template, add appropriate tags, 
and update the package with this metadata to improve searchability."
```

**Expected Tools Used**:
1. `packaging.browse` - Analyze package contents
2. `metadata_examples.show_examples` - Learn metadata best practices
3. `metadata_examples.from_template` - Use genomics template
4. `packaging.create` - Update package with metadata
5. `search.unified_search` - Verify improved searchability

**Success Criteria**:
- ✅ Extracts relevant metadata from files
- ✅ Uses appropriate template
- ✅ Validates metadata structure
- ✅ Updates package successfully
- ✅ Package is more discoverable

---

### Scenario 5: Collaborative Research Workflow

**Goal**: Share analysis results with team

**Query**:
```
"I've analyzed the nextflow/A549 RNA-seq data. Create a shareable research package 
that includes: 1) The top 50 differentially expressed genes, 2) Visualizations 
(volcano plot, heatmap, expression distribution), 3) A README explaining the analysis, 
4) Metadata with tags for easy discovery. Name it 'demo-team/a549-rnaseq-analysis' 
and make sure it follows best practices for collaborative research."
```

**Expected Tools Used**:
1. `tabulator.table_query` - Extract gene data
2. `quilt_summary.generate_multi_viz` - Create all visualizations
3. `metadata_examples.from_template` - Use research template
4. `packaging.create` - Create analysis package
5. `permissions.discover` - Check sharing permissions

**Success Criteria**:
- ✅ Creates comprehensive analysis package
- ✅ Includes multiple visualization formats
- ✅ Has clear documentation
- ✅ Follows metadata standards
- ✅ Is properly tagged for discovery

---

## Visualization Testing Plan

### Test Group 1: Basic Visualizations

#### Test V1: File Type Distribution
```
"Analyze the nextflow/A549 package and create a pie chart showing the distribution 
of file types (CSV, SF, JSON, etc.)"
```

**Expected Output**:
- Pie chart PNG image
- Entry in quilt_summarize.json with widget config
- Counts for each file type

**Validation**:
- ✅ Chart is readable
- ✅ Colors are distinct
- ✅ Percentages are accurate
- ✅ Legend is clear

---

#### Test V2: Folder Structure Visualization
```
"Create a treemap showing the folder structure and relative sizes in the 
nextflow/A549 package"
```

**Expected Output**:
- Treemap PNG showing nested folders
- Size information for each folder
- Interactive widget config in JSON

**Validation**:
- ✅ Hierarchy is clear
- ✅ Sizes are proportional
- ✅ Labels are readable
- ✅ Color coding makes sense

---

#### Test V3: File Size Distribution
```
"Show me a histogram of file sizes in the nextflow/A549 package"
```

**Expected Output**:
- Histogram PNG with appropriate bins
- Statistics (mean, median, outliers)
- Data table with size ranges

**Validation**:
- ✅ Bins are reasonable
- ✅ Outliers are highlighted
- ✅ Axes are labeled
- ✅ Scale is appropriate

---

### Test Group 2: Multi-Format Visualizations

#### Test V4: Package Overview Dashboard
```
"Create a comprehensive overview dashboard for the nextflow/A549 package with 
multiple visualizations: file type pie chart, folder treemap, size histogram, 
and metadata summary"
```

**Expected Output**:
- Multiple PNG visualizations
- Dashboard widget config
- Unified quilt_summarize.json
- README with embedded images

**Validation**:
- ✅ All charts generated
- ✅ Layout is organized
- ✅ Charts are cohesive
- ✅ Dashboard is navigable

---

#### Test V5: Genomic Visualization (RNA-seq specific)
```
"Create genomic-specific visualizations for the nextflow/A549 package: 
gene expression distribution, sample quality metrics, and TPM value heatmap"
```

**Expected Output**:
- Expression distribution histogram
- QC metrics bar chart
- TPM heatmap for top genes
- Genomic metadata in JSON

**Validation**:
- ✅ Uses genomic color schemes
- ✅ Shows biologically relevant metrics
- ✅ Heatmap is interpretable
- ✅ Includes statistical annotations

---

### Test Group 3: Interactive & Advanced

#### Test V6: Multi-Format Output
```
"Generate visualizations for the nextflow/A549 package in multiple formats: 
PNG for viewing, SVG for publication, and HTML for interactive exploration"
```

**Expected Output**:
- Same chart in PNG, SVG, and HTML formats
- Format-appropriate widget configs
- Guidelines for each format's use case

**Validation**:
- ✅ PNG is web-optimized
- ✅ SVG is vector-quality
- ✅ HTML is interactive
- ✅ All formats match

---

#### Test V7: Visualization with Custom Metadata
```
"Create visualizations for the nextflow/A549 package using the 'genomics' 
metadata template with custom fields for experiment date, researcher, and 
publication status. Include this metadata in the visualization titles and 
annotations."
```

**Expected Output**:
- Visualizations with custom metadata annotations
- Template-based color scheme
- Metadata-aware widget configs

**Validation**:
- ✅ Custom fields appear in charts
- ✅ Metadata is formatted correctly
- ✅ Template styling is applied
- ✅ Annotations are clear

---

### Test Group 4: Error Handling & Edge Cases

#### Test V8: Empty Package Visualization
```
"Try to create visualizations for an empty or very small package"
```

**Expected**: Graceful error handling with helpful message

---

#### Test V9: Large Package Visualization
```
"Create visualizations for a package with 1000+ files"
```

**Expected**: Performance optimization, appropriate aggregation

---

#### Test V10: Missing Data Handling
```
"Create visualizations for a package with incomplete metadata"
```

**Expected**: Use defaults, clearly indicate missing data

---

## Systematic Testing Schedule

### Phase 1: Foundation (Day 1)
**Time**: 2-3 hours  
**Focus**: Admin, Auth, Basic Package Operations

1. ✅ **Admin Users** (Test 1-5):
   - Create user
   - Get user details
   - Update email
   - Deactivate user
   - Delete user

2. **Auth Operations** (Test 12-13):
   - Get catalog info
   - Generate URLs

3. **Package Basics** (Test 6-7):
   - Create package
   - Get metadata template

**Success Criteria**: User lifecycle works, packages can be created

---

### Phase 2: Discovery & Access (Day 2)
**Time**: 2-3 hours  
**Focus**: Search, Buckets, Permissions

4. **Search Capabilities** (Test 10-11):
   - Search discovery
   - Search suggestions

5. **Bucket Operations** (Test 8-9):
   - Object info
   - Presigned URLs

6. **Permissions**:
   - Discover permissions
   - Check access levels

**Success Criteria**: Full discovery workflow works end-to-end

---

### Phase 3: Visualizations (Day 3-4)
**Time**: 4-6 hours  
**Focus**: Comprehensive Visualization Testing

7. **Basic Viz** (Test V1-V3):
   - File type charts
   - Folder treemaps
   - Size histograms

8. **Multi-Format** (Test V4-V5):
   - Dashboard creation
   - Genomic visualizations

9. **Advanced** (Test V6-V7):
   - Multiple output formats
   - Custom metadata integration

10. **Edge Cases** (Test V8-V10):
    - Error handling
    - Performance limits
    - Missing data

**Success Criteria**: All visualization types work, handle edge cases gracefully

---

### Phase 4: Scientific Scenarios (Day 5)
**Time**: 4-6 hours  
**Focus**: End-to-End Scientific Workflows

11. **Scenario 1**: RNA-seq Discovery & Analysis
12. **Scenario 2**: Cross-Study Comparison
13. **Scenario 3**: Quality Control
14. **Scenario 4**: Metadata Enrichment
15. **Scenario 5**: Collaborative Research

**Success Criteria**: Complex multi-tool workflows complete successfully, produce scientifically meaningful results

---

### Phase 5: Advanced Operations (Day 6)
**Time**: 3-4 hours  
**Focus**: Remaining Untested Tools

16. **Policy & Role Management**:
    - Create policy
    - Create role
    - Assign role to user

17. **Workflow Orchestration**:
    - Create workflow
    - Track multi-step process

18. **Metadata Examples**:
    - Fix metadata issues
    - Show examples

**Success Criteria**: All major tool categories have >50% action coverage

---

## Execution Strategy

### For Each Test:

1. **Run Browser Test**:
   - Navigate to demo.quiltdata.com
   - Open Qurator
   - Submit test query
   - Wait for completion

2. **Document Results**:
   - ✅ Success with screenshot
   - ⚠️ Partial success with notes
   - ❌ Failure with error details

3. **Verify Output**:
   - Check tool calls
   - Verify response format
   - Validate data accuracy
   - Confirm user experience

4. **Update Coverage**:
   - Mark action as tested
   - Update coverage percentage
   - Note any issues

### Success Metrics:

- **Coverage Target**: 80% of actions tested by end of Phase 5
- **Quality Target**: 90% of tests pass without issues
- **Scientific Target**: All 5 scenarios complete end-to-end
- **Visualization Target**: All 10 viz tests produce usable output

---

## Next Steps

1. **Start with Admin User Test** (Test 1):
   - Open browser to demo.quiltdata.com
   - Test user creation workflow
   - Document results

2. **Continue Systematically**:
   - Follow test schedule
   - One phase at a time
   - Document everything

3. **Track Progress**:
   - Update this document
   - Create test results spreadsheet
   - Note blockers and issues

4. **Report Findings**:
   - Daily summary of completed tests
   - Issues discovered
   - Coverage improvements
   - Recommendations for fixes

---

## Appendix: Quick Test Commands

```bash
# Run unit tests for specific tools
PYTHONPATH=src uv run pytest tests/unit/test_governance.py -v
PYTHONPATH=src uv run pytest tests/unit/test_visualization.py -v
PYTHONPATH=src uv run pytest tests/unit/test_quilt_summary.py -v

# Run E2E tests
PYTHONPATH=src uv run pytest tests/e2e/ -v

# Check tool registration
PYTHONPATH=src python -c "from quilt_mcp.utils import get_module_wrappers; print(get_module_wrappers().keys())"
```


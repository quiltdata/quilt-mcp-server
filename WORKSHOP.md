# Quilt MCP Workshop Guide

Welcome! This workshop will teach you how to use the Quilt MCP (Model Context Protocol) server with Claude to query, visualize, and package your data.

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
   - [Option A: Claude Desktop (Recommended)](#option-a-claude-desktop-recommended)
   - [Option B: VS Code with Continue](#option-b-vs-code-with-continue)
3. [Verify Installation](#verify-installation)
4. [Getting Started](#getting-started)
5. [Workshop Exercises](#workshop-exercises)
6. [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before starting, ensure you have:

- [ ] **Python 3.11+** installed ([Download Python](https://www.python.org/downloads/))
- [ ] **VS Code** installed ([Download](https://code.visualstudio.com))
- [ ] **AWS credentials** configured with access to:
  - S3 buckets
  - Athena (for queries)
  - AWS Glue (data catalog)
  - **Amazon Bedrock** with Claude models enabled
- [ ] **AWS IAM permissions** for:
  - `s3:ListBucket`, `s3:GetObject`, `s3:PutObject`
  - `athena:*` (StartQueryExecution, GetQueryResults, etc.)
  - `glue:GetDatabase`, `glue:GetTable`
  - `bedrock:InvokeModel` (for Claude on Bedrock)

### Check Your Python Version

```bash
python --version
# Should show: Python 3.11.x or higher
```

### Verify AWS Credentials

```bash
aws sts get-caller-identity
# Should show your AWS account info
```

If not configured, run:
```bash
aws configure
# Enter your AWS Access Key ID, Secret Access Key, and region
```

---

## Installation

We'll set up Claude Code in VS Code using the Continue extension with Amazon Bedrock.

### Step 1: Install VS Code

If you don't have VS Code installed:

1. Download from [code.visualstudio.com](https://code.visualstudio.com)
2. Install for your operating system
3. Launch VS Code

### Step 2: Install Continue Extension

1. Open VS Code
2. Open Extensions view:
   - **Mac**: Press `Cmd+Shift+X`
   - **Windows/Linux**: Press `Ctrl+Shift+X`
3. Search for **"Continue"**
4. Click **Install** on the Continue extension by Continue
5. Wait for installation to complete

### Step 3: Install `uv` (Python Package Manager)

**macOS/Linux**:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows** (PowerShell as Administrator):
```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Verify installation**:
```bash
uvx --version
```

### Step 4: Install Quilt MCP Server

**One-Line Installation**:
```bash
uvx --from quilt-mcp quilt-mcp
```

This command tests the installation. You should see:
```
Quilt MCP Server starting...
```

Press `Ctrl+C` to stop it. ✅

### Step 5: Configure Continue with Claude on Bedrock

1. **Open Continue Config**:
   - Press `Cmd+Shift+P` (Mac) or `Ctrl+Shift+P` (Windows/Linux)
   - Type "Continue: Open Config"
   - Press Enter

2. **Replace the config with this**:

```json
{
  "models": [
    {
      "title": "Claude 3.5 Sonnet (Bedrock)",
      "provider": "bedrock",
      "model": "anthropic.claude-3-5-sonnet-20241022-v2:0",
      "region": "us-east-1"
    }
  ],
  "mcpServers": {
    "quilt": {
      "command": "uvx",
      "args": ["--from", "quilt-mcp", "quilt-mcp"],
      "env": {
        "AWS_REGION": "us-east-1",
        "AWS_PROFILE": "default"
      }
    }
  }
}
```

3. **Customize** (if needed):
   - Change `region` to your AWS region
   - Change `AWS_PROFILE` to your AWS profile name
   - Change `AWS_REGION` in env to match

4. **Save the file** (`Cmd+S` or `Ctrl+S`)

### Step 6: Restart VS Code

1. **Quit VS Code completely**:
   - **Mac**: Press `Cmd+Q`
   - **Windows/Linux**: Close all windows or `Alt+F4`

2. **Relaunch VS Code**

3. **Open Continue sidebar**:
   - Click the Continue icon in the left sidebar (looks like a chat bubble)
   - Or press `Cmd+L` (Mac) or `Ctrl+L` (Windows/Linux)

---

## Verify Installation

Test that everything is working in VS Code with Continue:

### Test 1: Check Tools Available

1. **Open Continue chat**:
   - Click Continue icon in left sidebar
   - Or press `Cmd+L` (Mac) or `Ctrl+L` (Windows/Linux)

2. **Type this message**:
   ```
   What Quilt tools do you have available?
   ```

3. **Expected response**:
   Claude should list tools like:
   - `bucket_discover`
   - `package_create`
   - `athena_query_execute`
   - `tabulator_bucket_query`
   - `create_data_visualization`
   - etc.

### Test 2: Quick Health Check

**Type this**:
```
Can you check if Quilt MCP is working by listing my available S3 buckets?
```

**Expected result**:
- You should see a list of your S3 buckets
- Claude will actually call the `bucket_discover` tool
- Results appear in the chat

**If you see your buckets, you're all set! 🎉**

### Troubleshooting

If tools aren't available:

1. **Check Continue config**:
   - `Cmd+Shift+P` → "Continue: Open Config"
   - Verify `mcpServers` section exists

2. **Check AWS credentials**:
   ```bash
   aws sts get-caller-identity
   ```

3. **Restart VS Code completely** (Cmd+Q or Alt+F4, then relaunch)

4. **Check Continue logs**:
   - Open VS Code Developer Tools: `Help` → `Toggle Developer Tools`
   - Look for MCP connection errors in Console tab

---

## Getting Started

### Understanding Quilt MCP

Quilt MCP gives Claude the ability to:

1. **Discover Data**: Find S3 buckets and browse their contents
2. **Query Data**: Use Athena or Tabulator to query data catalogs
3. **Create Packages**: Bundle data, metadata, and visualizations
4. **Visualize**: Generate interactive charts and dashboards

### Basic Concepts

- **Bucket**: An S3 bucket containing your data
- **Package**: A versioned bundle of files with metadata
- **Catalog**: Quilt's web interface for browsing packages
- **Athena**: AWS service for SQL queries on S3 data
- **Tabulator**: Quilt's fast query engine for package metadata

---

## Workshop Exercises

### Exercise 1: Discover Your Data (5 minutes)

Let's explore what data you have available.

**Prompt**:
```
Show me what S3 buckets are available in my AWS account.
```

**Follow-up**:
```
Browse the contents of [bucket-name] and show me the top-level folders.
```

**What you'll learn**: How to navigate your S3 data landscape.

---

### Exercise 2: Query Data with Athena (10 minutes)

Now let's query some data using SQL.

#### Prerequisites
- You have an Athena database configured
- Your data is cataloged in AWS Glue

**Prompt**:
```
List the databases available in Athena.
```

**Then**:
```
Show me the tables in the [database-name] database.
```

**Query your data**:
```
Query the [table-name] table in [database-name] and show me the first 10 rows.
```

**Example with filtering**:
```
Query the genomics_db.rna_seq table for genes BRCA1, TP53, and MYC. 
Show me sample_id, gene_name, and expression_level columns.
```

**What you'll learn**: How to explore and query structured data.

---

### Exercise 3: Search Package Metadata with Tabulator (10 minutes)

Tabulator provides fast searches across package metadata.

**Prompt**:
```
Search for packages in bucket [bucket-name] that contain the word "analysis" 
in their metadata.
```

**Explore package contents**:
```
Show me what files are in the [namespace/package-name] package.
```

**Query package metadata**:
```
Find all packages in [bucket-name] created in the last 30 days.
```

**What you'll learn**: How to find and explore Quilt packages.

---

### Exercise 4: Create a Simple Package (15 minutes)

Let's create your first Quilt package!

#### Step 1: Create a README

**Prompt**:
```
Create a README file for a new package called "workshop/my-first-package". 
The README should explain that this is a test package created during the 
Quilt MCP workshop and include today's date.
```

#### Step 2: Upload Files to S3

**Prompt**:
```
Upload this README to S3 bucket [your-bucket] with key "workshop/README.md".
```

#### Step 3: Create the Package

**Prompt**:
```
Create a Quilt package named "workshop/my-first-package" in bucket [your-bucket] 
that includes the README file I just uploaded at s3://[your-bucket]/workshop/README.md.
Add metadata with tags: ["workshop", "test"] and description: "My first Quilt package".
```

**What you'll learn**: The basic package creation workflow.

---

### Exercise 5: Advanced Query → Visualize → Package (30 minutes)

This is our capstone exercise! We'll query data, create a visualization, and package everything together.

#### Scenario
You're analyzing RNA-seq gene expression data and want to create an interactive visualization package.

#### Step 1: Query the Data

**Prompt**:
```
Query the genomics_db.rna_seq table using Athena. 
Get sample_id, gene_name, and expression_level for genes: BRCA1, TP53, MYC.
Save the results.
```

#### Step 2: Create a Visualization

**Prompt**:
```
Using the query results, create an interactive box plot showing expression_level 
by gene_name, grouped by sample_id. Use the "genomics" color scheme.
```

> **Note**: This uses the new `create_data_visualization` tool which generates ECharts JSON for interactive plots in the Quilt catalog.

#### Step 3: Create a Comprehensive README

**Prompt**:
```
Create a detailed README for this analysis package that includes:
1. Title: "RNA-Seq Gene Expression Analysis"
2. Overview of what genes were analyzed
3. Summary statistics from the data
4. Description of the visualization
5. Data source information
6. Creation date and author
```

#### Step 4: Upload Everything to S3

**Prompt**:
```
Upload the following files to s3://[your-bucket]/workshop/rna-analysis/:
1. The visualization files (quilt_summarize.json, boxplot JSON, and data CSV)
2. The README markdown file
3. The original query results as CSV
```

#### Step 5: Create the Final Package

**Prompt**:
```
Create a Quilt package named "workshop/rna-seq-analysis" that includes:
- The visualization files (so it renders in Quilt catalog)
- The README
- The raw query results
Add metadata with:
- tags: ["workshop", "rna-seq", "genomics", "visualization"]
- description: "RNA-seq expression analysis with interactive visualization"
- workflow: "Athena query → visualization → package"
```

#### Step 6: Verify in Quilt Catalog

Open your Quilt catalog in a browser:
```
https://[your-quilt-catalog-url]/b/[bucket]/packages/workshop/rna-seq-analysis
```

You should see:
- ✅ Interactive box plot rendered at the top
- ✅ README with analysis description
- ✅ Raw data available for download
- ✅ Metadata tags and description

**What you'll learn**: The complete workflow from query to publishable analysis package.

---

## Example Prompts Library

Here are more prompts you can try:

### Data Discovery

```
What buckets do I have access to?
```

```
Show me the largest files in [bucket-name].
```

```
Find all CSV files in s3://[bucket]/data/ folder.
```

### Querying

```
Show me the schema for table [table-name] in [database-name].
```

```
Count the number of rows in [database].[table].
```

```
Query [database].[table] and group by [column], showing counts.
```

### Package Management

```
List all packages in [bucket-name] under the "genomics" namespace.
```

```
Show me the most recently updated package in [bucket].
```

```
Get the file list for package [namespace/package-name].
```

### Visualization & Analysis

```
Create a scatter plot from [data-source] showing correlation between [x-column] and [y-column].
```

```
Make a bar chart from the query results showing [metric] by [category].
```

```
Generate a box plot visualization with the genomics color scheme.
```

### Combined Workflows

```
Find all packages tagged with "RNA-seq", query their metadata, 
and create a summary report.
```

```
Query the latest data from [table], create a visualization, 
and package it with a generated README.
```

```
Search for analysis packages created this week, download their 
results, and create a comparative visualization.
```

---

## Troubleshooting

### Issue: Continue doesn't see MCP tools

**Symptoms**: Claude responds "I don't have access to Quilt tools" or tools list is empty

**Solutions**:
1. **Verify Continue configuration**:
   - Open config: `Cmd+Shift+P` → "Continue: Open Config"
   - Check `mcpServers` section exists and is valid JSON
   - Verify `command`, `args`, and `env` are correct

2. **Check `uv` installation**:
   ```bash
   uvx --version
   ```
   If not found, reinstall `uv`

3. **Restart VS Code completely**:
   - **Mac**: `Cmd+Q` (not just close window!)
   - **Windows/Linux**: Close all windows or `Alt+F4`
   - Relaunch VS Code

4. **Check Developer Console**:
   - `Help` → `Toggle Developer Tools`
   - Look for MCP errors in Console tab

5. **Test MCP server manually**:
   ```bash
   uvx --from quilt-mcp quilt-mcp
   ```
   Should start without errors

### Issue: AWS authentication errors

**Symptoms**: "Access Denied" or "Credentials not found"

**Solutions**:
1. Verify AWS credentials: `aws sts get-caller-identity`
2. Check AWS_PROFILE in MCP config matches your profile
3. Ensure your IAM user has permissions for S3, Athena, Glue
4. Try setting credentials explicitly:
   ```json
   "env": {
     "AWS_ACCESS_KEY_ID": "your-key",
     "AWS_SECRET_ACCESS_KEY": "your-secret",
     "AWS_REGION": "us-east-1"
   }
   ```

### Issue: Athena queries fail

**Symptoms**: "Database not found" or "Table not found"

**Solutions**:
1. Verify database exists: Ask Claude to list Athena databases
2. Check table names: Ask Claude to show tables in database
3. Ensure Athena has an output location configured in AWS
4. Verify IAM permissions for Athena and Glue

### Issue: Package creation fails

**Symptoms**: "Package creation failed" or "S3 upload error"

**Solutions**:
1. Verify bucket exists and you have write permissions
2. Check bucket name doesn't have typos
3. Ensure files were uploaded to S3 before creating package
4. Try uploading files and creating package in separate steps

### Issue: Visualizations don't render

**Symptoms**: Package creates but no visualization appears

**Solutions**:
1. Verify `quilt_summarize.json` was uploaded to package root
2. Check that visualization JSON files are in the package
3. Ensure file paths in `quilt_summarize.json` match actual files
4. Open browser console in Quilt catalog to check for errors

### Need More Help?

- **Documentation**: [docs.quilt.bio](https://docs.quilt.bio)
- **GitHub Issues**: [github.com/quiltdata/quilt-mcp-server](https://github.com/quiltdata/quilt-mcp-server)
- **Quilt Support**: support@quiltdata.io

---

## Best Practices

### 1. Organize Your Packages

Use consistent naming:
```
[team]/[project]-[type]
Examples:
  - genomics/rna-seq-analysis
  - ml/model-training-v1
  - research/experiment-001
```

### 2. Always Include READMEs

Every package should have a README that explains:
- What data is included
- How it was generated
- Who created it
- When it was created

### 3. Use Metadata Tags

Tag packages for easy discovery:
```
tags: ["domain", "data-type", "project", "status"]
Examples:
  - ["genomics", "rna-seq", "cancer-study", "published"]
  - ["ml", "training-data", "model-v2", "production"]
```

### 4. Visualize Your Results

Include visualizations in packages:
- Makes data more accessible
- Tells the story of your analysis
- Enables quick insights without downloading

### 5. Version Your Work

Quilt automatically versions packages:
- Each push creates a new version
- Previous versions remain accessible
- Use version hashes for reproducibility

---

## Next Steps

After completing this workshop:

1. **Explore Your Data**: Use the discovery tools to map your data landscape
2. **Create Real Packages**: Package your actual analysis results
3. **Build Dashboards**: Create multi-visualization packages for reports
4. **Automate Workflows**: Use Quilt MCP in scripts or CI/CD pipelines
5. **Share Knowledge**: Teach your team to use Quilt packages

### Advanced Topics

- **Event-Driven Packaging**: Automatically create packages on data arrival
- **Package Lineage**: Track data provenance and dependencies
- **Cross-Account Access**: Share packages across AWS accounts
- **Custom Metadata Schemas**: Define schemas for your domain
- **Integration with Notebooks**: Use Quilt in Jupyter notebooks

---

## Workshop Feedback

We'd love to hear from you! After completing the workshop:

- What worked well?
- What was confusing?
- What features would you like to see?
- How will you use Quilt MCP in your work?

Share feedback at: workshops@quiltdata.io

---

## Appendix: Quick Reference

### Common Commands

**Discover buckets**:
```
Show me my S3 buckets
```

**Query with Athena**:
```
Query [database].[table] and show me [columns]
```

**Search packages**:
```
Find packages in [bucket] tagged with "[tag]"
```

**Create package**:
```
Create package [namespace/name] in [bucket] with files [s3-uris]
```

**Get package contents**:
```
Show me what's in package [namespace/name]
```

### Configuration Template

```json
{
  "mcpServers": {
    "quilt": {
      "command": "uvx",
      "args": ["--from", "quilt-mcp", "quilt-mcp"],
      "env": {
        "AWS_REGION": "us-east-1",
        "AWS_PROFILE": "default",
        "QUILT_CATALOG_URL": "https://your-catalog-url.com"
      }
    }
  }
}
```

### Useful AWS CLI Commands

```bash
# List buckets
aws s3 ls

# List Athena databases
aws athena list-databases --catalog-name AwsDataCatalog

# Check IAM identity
aws sts get-caller-identity

# Test S3 access
aws s3 ls s3://your-bucket/
```

---

**Happy Data Packaging! 🎉**


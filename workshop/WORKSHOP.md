# Quilt MCP Workshop Guide

Welcome! This workshop will teach you how to use the Quilt MCP (Model Context Protocol) server with **Claude on Amazon Bedrock** to query, visualize, and package your data.

**🏢 Deployment Model**: This workshop uses **MCP with Claude on Amazon Bedrock**. Choose your environment:
- **VS Code + Continue**: Full IDE integration with Bedrock (recommended for this workshop)
- **Terminal + MCP Inspector**: Web-based testing interface for MCP tools

All data stays within your AWS account. No data leaves your infrastructure.

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
   - [Option A: VS Code + Continue (Recommended)](#option-a-vs-code--continue-recommended)
   - [Option B: Terminal + MCP Inspector](#option-b-terminal--mcp-inspector)
3. [Verify Installation](#verify-installation)
4. [Getting Started](#getting-started)
5. [Workshop Exercises](#workshop-exercises)
6. [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before starting, ensure you have:

- [ ] **Python 3.11+** installed ([Download Python](https://www.python.org/downloads/))
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

If not configured, your instructor will provide credentials.

---

## Installation

Choose your preferred environment:

### Option A: VS Code + Continue (Recommended)

This is the **recommended option** for this workshop - full IDE integration with all Quilt MCP tools.

#### Step 1: Install VS Code

1. Download from [code.visualstudio.com](https://code.visualstudio.com)
2. Install for your operating system
3. Launch VS Code

#### Step 2: Install Continue Extension

1. Open VS Code
2. Open Extensions view:
   - **Mac**: Press `Cmd+Shift+X`
   - **Windows/Linux**: Press `Ctrl+Shift+X`
3. Search for **"Continue"**
4. Click **Install** on the Continue extension
5. Wait for installation to complete

#### Step 3: Install Quilt MCP Server

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

**Test Quilt MCP**:
```bash
uvx --from quilt-mcp quilt-mcp
```

Press `Ctrl+C` to stop it. ✅

#### Step 4: Configure Continue with Bedrock + MCP

1. **Open Continue Config**:
   - Press `Cmd+Shift+P` (Mac) or `Ctrl+Shift+P` (Windows/Linux)
   - Type "Continue: Open config.json"
   - Press Enter

2. **Replace the config with this**:

```json
{
  "models": [
    {
      "title": "Claude Sonnet 4.5 (Bedrock)",
      "provider": "bedrock",
      "model": "anthropic.claude-sonnet-4-5-20250929-v1:0",
      "region": "us-east-1"
    }
  ],
  "mcpServers": {
    "quilt": {
      "command": "uvx",
      "args": ["--from", "quilt-mcp", "quilt-mcp"],
      "env": {
        "AWS_REGION": "us-east-1",
        "AWS_PROFILE": "default",
        "QUILT_CATALOG_URL": "https://demo.quiltdata.com"
      }
    }
  }
}
```

3. **Customize** (if your instructor provides different values):
   - Change `region` to your AWS region
   - Change `AWS_PROFILE` to your AWS profile name
   - Change `QUILT_CATALOG_URL` to your Quilt catalog

4. **Save the file** (`Cmd+S` or `Ctrl+S`)

#### Step 5: Restart VS Code

1. **Quit VS Code completely**:
   - **Mac**: Press `Cmd+Q`
   - **Windows/Linux**: Close all windows or `Alt+F4`

2. **Relaunch VS Code**

3. **Open Continue sidebar**:
   - Click the Continue icon in the left sidebar
   - Or press `Cmd+L` (Mac) or `Ctrl+L` (Windows/Linux)

---

### Option B: Terminal + MCP Inspector

If you prefer terminal-based work, use MCP Inspector to test Quilt MCP tools via a web interface.

#### Step 1: Install Prerequisites

**Install uv (Python package manager)**:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Install MCP Inspector** (requires Node.js):
```bash
npm install -g @modelcontextprotocol/inspector
```

#### Step 2: Test Quilt MCP Server

```bash
uvx --from quilt-mcp quilt-mcp
```

You should see: `Quilt MCP Server starting...`

Press `Ctrl+C` to stop. ✅

#### Step 3: Start MCP Inspector

```bash
npx @modelcontextprotocol/inspector uvx --from quilt-mcp quilt-mcp
```

This will:
1. Start the Quilt MCP server
2. Open a web interface at `http://localhost:5173`
3. Show all available Quilt MCP tools

#### Step 4: Test in Web Interface

In the MCP Inspector web UI:

1. **View Available Tools**: See all Quilt MCP tools listed
2. **Test a Tool**: Click on `bucket_objects_list`
3. **Enter Parameters**:
   ```json
   {
     "bucket": "s3://quilt-example"
   }
   ```
4. **Execute**: Click "Run" and see results

✅ You can now test any Quilt MCP tool through the web interface!

**Note**: For actual workshop exercises with Claude, you'll need to use Python with boto3 to call Bedrock directly. The MCP Inspector is useful for testing tools, but doesn't include Claude integration.

---

## Verify Installation

### For VS Code + Continue Users

#### Test 1: Check Tools Available

1. **Open Continue sidebar**:
   - Click Continue icon in left sidebar
   - Or press `Cmd+L` (Mac) or `Ctrl+L` (Windows/Linux)

2. **Type this message**:
   ```
   What MCP tools do you have available?
   ```

3. **Expected response**:
   Claude should list Quilt MCP tools including:
   - `mcp_quilt-mcp-server_auth_status` - Check authentication
   - `mcp_quilt-mcp-server_bucket_objects_list` - List S3 objects
   - `mcp_quilt-mcp-server_packages_search` - Search packages
   - `mcp_quilt-mcp-server_create_data_visualization` - Create visualizations
   - And many more...

✅ **Success**: If you see the tools listed, you're ready!

#### Test 2: Query Your Data

**Try this prompt**:
```
Can you check my authentication status and tell me what Quilt catalog I'm connected to?
```

**Expected response**:
Claude should use the `auth_status` tool and tell you:
- Whether you're authenticated
- Your catalog URL
- Your AWS region

✅ **Success**: If Claude responds with your catalog info, everything works!

### For MCP Inspector Users

1. **Open MCP Inspector**: Should be running at `http://localhost:5173`
2. **View Tools**: All Quilt MCP tools should be listed
3. **Test a Tool**: Click any tool and try executing it
4. **See Results**: Tool output appears in the interface

✅ **Success**: If you can execute tools and see results, MCP is working!

---

## Troubleshooting

### Issue: Continue doesn't see MCP tools

**Symptoms**: Claude responds "I don't have access to Quilt tools" or tools list is empty

**Solutions**:

1. **Verify Continue configuration**:
   - Press `Cmd+Shift+P` → "Continue: Open config.json"
   - Check that `mcpServers` section exists
   - Verify JSON syntax is correct (no trailing commas, proper quotes)

2. **Check AWS credentials**:
   ```bash
   aws sts get-caller-identity
   ```

3. **Restart VS Code completely**:
   - Quit completely: `Cmd+Q` (Mac) or `Alt+F4` (Windows)
   - Relaunch VS Code
   - Wait 10 seconds for Continue to initialize

4. **Check Continue logs**:
   - Open VS Code: `Help` → `Toggle Developer Tools`
   - Go to Console tab
   - Look for MCP connection errors or warnings

### Issue: "Could not connect to MCP server"

**Solutions**:

1. **Test MCP server manually**:
   ```bash
   uvx --from quilt-mcp quilt-mcp
   ```
   Should start without errors. Press Ctrl+C to stop.

2. **Check Python version**:
   ```bash
   python --version
   # Must be 3.11 or higher
   ```

3. **Reinstall uv**:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

### Issue: AWS authentication errors

**Symptoms**: "Access Denied" or "Invalid credentials"

**Solutions**:

1. **Verify AWS credentials**:
   ```bash
   aws sts get-caller-identity
   ```

2. **Check AWS profile**:
   ```bash
   aws configure list
   ```

3. **Contact instructor** for credentials if needed

---

## Getting Started

Now that everything is installed, let's learn the basics!

### Understanding the Workflow

```
You (in Claude) → Quilt MCP Server → Your Data (S3, Athena, Quilt)
                                    ↓
                              Claude sees & processes
```

### Key Capabilities

1. **Explore Data**: List files, search packages, query databases
2. **Analyze Data**: Run Athena queries, create visualizations
3. **Package Data**: Create Quilt packages with metadata and README files
4. **Share Results**: Generate shareable packages in your Quilt catalog

### Your First Query

**Try this** (in Claude terminal or VS Code):

```
List the CSV files in the s3://quilt-example bucket
```

Claude will:
1. Use `bucket_objects_list` tool
2. Filter for `.csv` files
3. Show you the results

**Expected output**:
- List of CSV files with sizes and paths
- Summary of how many files found

---

## Workshop Exercises

### Exercise 1: Explore Your Data (10 minutes)

**Goal**: Learn to search and explore data in S3 and Quilt packages.

#### 1.1 List Files in a Bucket

**Prompt**:
```
List all files in s3://quilt-example bucket. Show me the file types and sizes.
```

**What Claude does**:
- Calls `bucket_objects_list`
- Analyzes file extensions
- Summarizes sizes

**Expected result**: Table of files with types and sizes

---

#### 1.2 Search for Packages

**Prompt**:
```
Search for packages related to "genomics" or "RNA-seq" in the Quilt catalog
```

**What Claude does**:
- Calls `packages_search` with your query
- Returns matching packages

**Expected result**: List of genomics/RNA-seq packages

---

#### 1.3 Browse Package Contents

**Prompt**:
```
Show me what's inside the [package-name] package
```

Replace `[package-name]` with a package from the search results.

**What Claude does**:
- Calls `package_browse`
- Shows directory structure
- Lists files with metadata

**Expected result**: Directory tree of package contents

---

### Exercise 2: Query and Analyze Data (15 minutes)

**Goal**: Use Athena to query data and understand results.

#### 2.1 List Available Databases

**Prompt**:
```
What Athena databases do I have access to?
```

**What Claude does**:
- Calls `athena_databases_list`
- Shows available databases

**Expected result**: List of Glue databases

---

#### 2.2 Explore a Database

**Prompt**:
```
Show me the tables in the [database-name] database and their schemas
```

**What Claude does**:
- Calls `athena_tables_list` or uses Glue
- Shows table names and column info

**Expected result**: List of tables with schemas

---

#### 2.3 Run a Query

**Prompt**:
```
Query the [table-name] table and show me the first 10 rows
```

**What Claude does**:
- Constructs SQL query
- Calls `athena_query_execute`
- Formats results as table

**Expected result**: Query results in a formatted table

---

### Exercise 3: Create Visualizations (20 minutes)

**Goal**: Generate visualizations from your data.

#### 3.1 Prepare Data

**Prompt**:
```
Query [table-name] and get sample data for genes and their expression values
```

**What Claude does**:
- Runs Athena query
- Formats data

**Expected result**: Sample dataset ready for visualization

---

#### 3.2 Create a Visualization

**Prompt**:
```
Create a box plot visualization of gene expression values grouped by gene name. 
Use the genomics color scheme.
```

**What Claude does**:
- Calls `create_data_visualization`
- Generates ECharts config
- Creates supporting files (data CSV, quilt_summarize.json)

**Expected result**: 
- Visualization configuration
- Data files ready for upload

---

#### 3.3 Upload and Package

**Prompt**:
```
Upload these visualization files to s3://[your-bucket]/analysis/ and create a 
package called "workshop/gene-expression-analysis"
```

**What Claude does**:
1. Calls `bucket_objects_put` to upload files
2. Calls `package_create` to create package
3. Returns package URL

**Expected result**: New package created with visualization

---

### Exercise 4: Create a Complete Analysis Package (20 minutes)

**Goal**: Combine everything - query data, create visualizations, and package results.

#### The Challenge

Create a complete analysis package that includes:
1. A README explaining the analysis
2. Query results (CSV)
3. A visualization
4. Metadata describing the data source

#### Step-by-Step

**Prompt 1**: Plan the analysis
```
I want to analyze [dataset description]. Help me plan what queries to run, 
what visualizations to create, and how to structure the package.
```

**Prompt 2**: Execute queries
```
Run the queries we planned and save the results as CSV files
```

**Prompt 3**: Create visualization
```
Create a [plot type] visualization of [data description]
```

**Prompt 4**: Generate README
```
Write a README.md for this analysis package that explains:
- What data was analyzed
- What queries were run
- What the visualization shows
- How to interpret the results
```

**Prompt 5**: Package everything
```
Create a package called "workshop/[your-name]-analysis" with:
- The README
- The query results CSV
- The visualization files
Use the research metadata template.
```

**Expected result**: 
- Complete package in Quilt catalog
- Professional documentation
- Shareable analysis

#### View Your Package

Open your Quilt catalog in a browser:
```
https://[your-quilt-catalog-url]/b/[bucket]/packages/workshop/[your-name]-analysis
```

You should see:
- 📄 README.md (rendered)
- 📊 Interactive visualization
- 📁 Data files
- 📋 Metadata

✅ **Congratulations!** You've created a complete, reproducible analysis package!

---

## Advanced Topics

### Custom Metadata Templates

Create packages with specialized metadata:

**Prompt**:
```
Create a package using the genomics metadata template. Include:
- Organism: Human
- Genome build: GRCh38
- Assay type: RNA-seq
```

### Query Optimization

Get help writing efficient queries:

**Prompt**:
```
I need to query a large table ([table-name]). Can you help me write an 
optimized query that filters by [condition] and only selects the columns I need?
```

### Workflow Automation

Plan multi-step workflows:

**Prompt**:
```
Create a workflow to:
1. Query raw data from Athena
2. Filter and aggregate the results
3. Create 3 different visualizations (scatter, box plot, bar chart)
4. Package everything with documentation
Guide me through each step.
```

---

## Best Practices

### 1. Be Specific in Prompts

❌ **Vague**: "Show me some data"

✅ **Specific**: "List CSV files in s3://quilt-example bucket larger than 1MB"

### 2. Describe What You Want, Not How

❌ **Too Technical**: "Call bucket_objects_list with prefix 'data/' and max_keys=100"

✅ **Natural**: "Show me all files in the data/ folder"

Claude knows which tools to use!

### 3. Ask for Explanations

Add to any prompt:
```
...and explain what you're doing at each step
```

### 4. Iterate and Refine

If results aren't quite right:
```
That's close, but can you [specific change]?
```

---

## Troubleshooting

### Issue: Slow queries

**Solution**: Ask Claude to optimize:
```
That query was slow. Can you rewrite it to be more efficient?
```

### Issue: Unclear results

**Solution**: Ask for formatting:
```
Can you format those results as a table with columns for [x, y, z]?
```

### Issue: Package creation fails

**Check**:
1. File paths are correct
2. S3 bucket has write permissions
3. Files were uploaded successfully

**Ask Claude**:
```
The package creation failed. Can you check what went wrong and try again?
```

---

## Need More Help?

- **Documentation**: [docs.quiltdata.com](https://docs.quiltdata.com)
- **GitHub Issues**: [github.com/quiltdata/quilt-mcp-server](https://github.com/quiltdata/quilt-mcp-server)
- **Quilt Support**: support@quiltdata.io
- **During Workshop**: Ask your instructor!

---

## Workshop Completion Checklist

By the end of this workshop, you should be able to:

- [ ] List and search files in S3 buckets
- [ ] Search and browse Quilt packages
- [ ] Query data using Athena
- [ ] Create data visualizations
- [ ] Package analysis results with documentation
- [ ] Share packages via Quilt catalog

🎉 **Congratulations on completing the Quilt MCP Workshop!**

---

## Appendix: Quick Reference

### Common Prompts

**List files**:
```
List files in s3://[bucket]/[prefix]
```

**Search packages**:
```
Search for packages containing "[keyword]"
```

**Query data**:
```
Query [table] and show [columns] where [condition]
```

**Create visualization**:
```
Create a [plot-type] of [data] using [color-scheme] colors
```

**Create package**:
```
Create a package called "[namespace]/[name]" with these files: [list]
```

### Tool Categories

**Authentication & Discovery**:
- `auth_status` - Check connection and credentials
- `catalog_info` - Get catalog details

**Data Exploration**:
- `bucket_objects_list` - List S3 files
- `bucket_objects_search` - Search S3 by content
- `packages_search` - Find packages
- `package_browse` - View package contents

**Querying**:
- `athena_query_execute` - Run SQL queries
- `athena_databases_list` - List databases
- `athena_table_schema` - Get table info

**Visualization**:
- `create_data_visualization` - Generate charts

**Packaging**:
- `package_create` - Create new package
- `package_update` - Add to existing package
- `bucket_objects_put` - Upload files to S3

---

*This workshop guide was created for the Quilt MCP Server with Claude Code on Amazon Bedrock*

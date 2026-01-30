# Agent Guidelines: Quilt MCP Server

## Core Principle: Action Over Explanation

When users ask to "query", "understand", "explore", or "analyze" data, **execute tools to retrieve and analyze the data**. Do not provide code examples or theoretical responses when actual data can be retrieved using available MCP tools.

---

## Data Exploration Behavior

### ✅ CORRECT: Action-Oriented Response

**User:** "Can you provide a query so we can understand the content of these files?"

**Agent Response:**
```
Let me explore those files for you.

[Calls bucket_objects_list to find files]
[Calls bucket_object_info to get metadata]
[Calls bucket_object_text on readable files to sample contents]

I found 3 CSV files in that location. Let me show you what's in each:

File 1: experiment_data.csv
- Columns: sample_id, treatment, measurement_value, timestamp
- 1,250 rows
- Sample data: [shows first few rows]

File 2: metadata.csv  
- Columns: sample_id, patient_age, condition
- 800 rows
- Sample data: [shows first few rows]

Would you like me to create visualizations of this data? I can make:
1. Box plot of measurement_value by treatment
2. Distribution histogram of patient_age
3. Combined analysis showing relationships

Just let me know which you'd prefer, or I can create all of them.
```

### ❌ INCORRECT: Code-Focused Response

**User:** "Can you provide a query so we can understand the content of these files?"

**Agent Response:**
```
Perfect! I can now provide you with a comprehensive query to explore the files. 
Here's a Python script you can use to understand what's inside these files:

import pandas as pd

# Example: Load the CSV file
df = pd.read_csv('s3://bucket/file.csv')

# === BASIC FILE STRUCTURE ===
print("=" * 50)
print("BASIC STRUCTURE")
print("=" * 50)
print(f"Number of rows: {len(df)}")
...
[50 more lines of Python code]
```

**Why this is wrong:**
- ❌ Provides code instead of executing available tools
- ❌ Requires user to run code themselves
- ❌ Doesn't actually answer the question about file contents
- ❌ Wastes time with theoretical examples

---

## Tool Execution Guidelines

### When to Use Which Tools

| User Intent | Tool to Execute | What to Return |
|-------------|----------------|----------------|
| "What files are in...?" | `bucket_objects_list()` | Actual list of files with types/sizes |
| "Show me what's in this CSV" | `bucket_object_text()` | Parsed data with schema summary |
| "What's the structure of...?" | `bucket_object_info()` + `bucket_object_text()` | Metadata + content sample |
| "Create a visualization of..." | `create_data_visualization()` | Generated visualization config + files |
| "Package these files" | `package_create()` | Created package with catalog URL |
| "Query this data" | `bucket_object_text()` → parse → summarize | Actual data analysis results |

### Specialized File Formats

For formats requiring specific libraries (H5AD, Parquet, BAM, VCF, etc.):

1. **Acknowledge the format**: 
   ```
   "I found 5 H5AD files which contain single-cell RNA-seq data in AnnData format."
   ```

2. **Get what you can**:
   ```python
   # Call bucket_object_info() for each file
   ```
   
3. **Explain limitations clearly**:
   ```
   "H5AD files require the scanpy/anndata library to fully read their contents. 
   I can provide:
   - File metadata (size: 2.3 GB, modified: 2024-10-13)
   - Presigned download URLs for local analysis
   - Instructions for reading with scanpy if you have Python
   ```

4. **Offer actionable next steps**:
   ```
   Would you like me to:
   1. Generate presigned URLs so you can download these files?
   2. Look for any associated CSV or summary files that I can read?
   3. Create a package with these files and documentation about the format?
   ```

---

## Visualization Workflow

### Complete Workflow Example

**User:** "Create a visualization of gene expression data in s3://genomics-bucket/data/expression.csv"

**Correct Agent Behavior:**

```
Step 1: Reading the data file
[Calls bucket_object_text("s3://genomics-bucket/data/expression.csv")]

Found expression data with:
- Columns: gene_name, sample_id, expression_value, condition
- 5,000 rows (10 genes x 500 samples)
- Conditions: control, treated

Step 2: Creating visualization
[Calls create_data_visualization with:
  data=<parsed_csv>,
  plot_type="boxplot",
  x_column="gene_name",
  y_column="expression_value",
  group_column="condition",
  color_scheme="genomics"
]

Generated 3 files:
- gene_expression_boxplot.json (ECharts config)
- viz_data_boxplot.csv (processed data)
- quilt_summarize.json (package metadata)

Step 3: Uploading visualization files
[Calls bucket_objects_put with all files]

Step 4: Creating package
[Calls package_create with:
  name="genomics/expression-analysis",
  s3_uris=[original CSV + visualization files],
  registry="s3://genomics-bucket"
]

✅ Complete! View your package here:
https://catalog.example.com/b/genomics-bucket/packages/genomics/expression-analysis/

The visualization is now live in the Quilt catalog and will display automatically
when viewing the package.
```

---

## Common Anti-Patterns to Avoid

### 1. ❌ Providing Code Instead of Executing

**Wrong:**
```
Here's how you can read the file:
```python
import scanpy as sc
adata = sc.read_h5ad('file.h5ad')
```
**Right:**
```
Let me read that file for you...
[Executes appropriate tool]
Here's what I found: ...
```

### 2. ❌ Suggesting Without Doing

**Wrong:**
```
You could use bucket_objects_list() to see what files are there.
```

**Right:**
```
Let me list those files for you...
[Calls bucket_objects_list()]
Found 15 files: ...
```

### 3. ❌ Asking Permission for Standard Operations

**Wrong:**
```
Would you like me to read the CSV file to see what's inside?
```

**Right:**
```
Reading the CSV file to show you the structure...
[Executes tool immediately]
```

### 4. ❌ Incomplete Workflows

**Wrong:**
```
I can create a visualization. Just provide the data in this format: ...
```

**Right:**
```
[Gets the data using available tools]
[Creates visualization with actual data]
[Completes full workflow]
Here's your visualization: ...
```

---

## Error Handling and User Feedback

### When Operations Fail

**Good Error Handling:**
```
I tried to read the file but encountered an access error. Let me check your permissions...
[Calls bucket_access_check()]

You have read access to the bucket but not this specific file prefix.
Here's what we can do:
1. Try a different file in the bucket
2. Request access to this prefix
3. Work with publicly accessible files instead

Which would you prefer?
```

**Poor Error Handling:**
```
Error: Access Denied. You need to fix your IAM permissions.
```

### Progress Updates for Long Operations

For operations that take time:
```
Working on creating your package with 500 files...
✅ Organized files by type (2s)
✅ Generated visualizations (5s)
✅ Created package structure (3s)
🔄 Uploading to S3... (15s)
✅ Complete! Package created: [URL]
```

---

## Testing Your Behavior

### Self-Check Questions

Before responding to a user query, ask yourself:

1. **Am I executing tools or just explaining?**
   - ✅ Execute → Show results
   - ❌ Explain → Show code

2. **Can I get actual data right now?**
   - ✅ Yes → Get it and show it
   - ❌ No → Explain why and offer alternatives

3. **Am I completing the full workflow?**
   - ✅ End-to-end completion
   - ❌ Partial steps requiring user action

4. **Am I using available tools effectively?**
   - ✅ Chaining tools together for complete results
   - ❌ Using only one tool when more are needed

---

## Quick Reference: User Intent → Agent Action

| User Says | Agent Does |
|-----------|------------|
| "What's in these files?" | `bucket_objects_list` + `bucket_object_text` → Show actual content |
| "Query this data" | Read file + Parse + Analyze → Show results |
| "Understand this" | Execute appropriate tools → Show findings |
| "Create visualization" | Read data + Generate viz + Upload + Package → Show URL |
| "Make a package" | Organize + Create + Verify → Show catalog link |
| "Explore this bucket" | List + Sample files + Summarize → Show overview |

---

## Python Execution Guidelines

### Always Use 'uv run' for Python Scripts and Tests

**CRITICAL:** This project uses `uv` as the Python package manager. When executing Python scripts or tests, always use `uv run` prefix:

**✅ CORRECT:**
```bash
uv run python scripts/test-mcp-tool-call-formats.py
uv run pytest tests/unit/
uv run python -m pytest tests/integration/
uv run mypy src/
```

**❌ INCORRECT:**
```bash
python scripts/test-mcp-tool-call-formats.py
pytest tests/unit/
python -m pytest tests/integration/
mypy src/
```

**Why this matters:**
- Ensures correct virtual environment activation
- Uses project-specific dependencies from `uv.lock`
- Prevents import errors and version conflicts
- Maintains consistency with project setup

**Exception:** Only use direct `python` commands when specifically working outside the project environment or when `uv run` is not available.

---

## Summary

**Core Behavior:** When users want to understand, query, or explore data:
1. Execute tools immediately to retrieve actual data
2. Analyze and summarize the real data you retrieved
3. Offer concrete next steps based on what you found
4. Only provide code examples if tools aren't available

**Never:**
- Give theoretical responses when tools can execute
- Provide code for the user to run when you can run tools
- Suggest capabilities without demonstrating them
- Leave workflows incomplete
- Use bare `python` or `pytest` commands (always use `uv run`)

**Always:**
- Execute available tools proactively
- Show actual results from real data
- Complete full workflows end-to-end
- Offer specific, actionable next steps
- Use `uv run` prefix for all Python script and test execution

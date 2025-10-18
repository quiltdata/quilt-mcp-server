# Quilt MCP Quick Reference Card

**Print this page and keep it handy during the workshop!**

---

## 🚀 One-Line Installation

```bash
uvx --from quilt-mcp quilt-mcp
```

---

## ⚙️ Configuration (VS Code with Continue)

**Open Continue Config**:
- Press `Cmd+Shift+P` (Mac) or `Ctrl+Shift+P` (Win/Linux)
- Type "Continue: Open Config"
- Press Enter

**Replace with this**:
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

**Then**: 
1. Save (Cmd+S / Ctrl+S)
2. Restart VS Code completely (Cmd+Q / Alt+F4, then relaunch)

---

## ✅ Verify Installation

**In VS Code Continue chat** (Cmd+L / Ctrl+L):

```
What Quilt tools do you have available?
```

Expected: List of tools (bucket_discover, package_create, athena_query_execute, etc.)

---

## 📖 Essential Prompts

### Discovery

```
Show me my S3 buckets
```

```
Browse the contents of [bucket-name]
```

```
Find all CSV files in s3://[bucket]/[prefix]/
```

### Querying

```
List the databases available in Athena
```

```
Show me the tables in the [database-name] database
```

```
Query [database].[table] and show me the first 10 rows
```

```
Query [database].[table] for [conditions] and show me [columns]
```

### Package Operations

```
Search for packages in [bucket] that contain "[keyword]"
```

```
Show me what files are in package [namespace/package-name]
```

```
Create package [namespace/name] in [bucket] with files [s3-uris]
```

### Visualization

```
Create an interactive box plot from the query results showing 
[y-column] by [x-column], grouped by [group-column]
```

```
Make a scatter plot from [data-source] showing [x] vs [y]
```

---

## 🎯 Complete Workflow Example

```
Step 1: Query the genomics_db.rna_seq table for genes BRCA1, TP53, MYC.
        Get sample_id, gene_name, and expression_level columns.

Step 2: Create an interactive box plot showing expression_level by gene_name,
        grouped by sample_id. Use the "genomics" color scheme.

Step 3: Create a README for this analysis package explaining what we analyzed.

Step 4: Upload the visualization files, README, and query results to 
        s3://[bucket]/workshop/rna-analysis/

Step 5: Create a Quilt package named "workshop/rna-seq-analysis" that includes
        all the uploaded files. Add metadata with tags: ["workshop", "rna-seq"]
```

---

## 🔧 Troubleshooting

| Problem | Solution |
|---------|----------|
| Tools not available | Restart VS Code completely (Cmd+Q / Alt+F4) |
| "Credentials not found" | Run `aws configure` |
| "Database not found" | List databases first, check spelling |
| "Package creation failed" | Verify files uploaded to S3 first |
| Viz doesn't render | Check quilt_summarize.json uploaded |
| Continue not responding | Check Developer Tools (Help → Toggle Developer Tools) |

### Quick Checks

```bash
# Verify Python
python --version  # Should be 3.11+

# Verify AWS
aws sts get-caller-identity

# Verify uv
uvx --help

# Test S3 access
aws s3 ls
```

---

## 📊 Data Types Supported

| Format | Extension | Example Use |
|--------|-----------|-------------|
| CSV | .csv | Tabular data |
| TSV | .tsv | Tab-separated data |
| Parquet | .parquet | Compressed columnar data |
| JSON | .json | Structured data |
| Excel | .xlsx | Spreadsheet data |
| Markdown | .md | Documentation |

---

## 🎨 Color Schemes

For visualizations, use these themes:

- `genomics` - Green/teal palette
- `ml` - Red/coral/blue palette
- `research` - Purple/pink/orange palette
- `analytics` - Green/blue/yellow palette
- `default` - Standard matplotlib colors

---

## 📝 Package Naming Best Practices

**Format**: `namespace/package-name`

**Examples**:
- `genomics/rna-seq-analysis`
- `ml/model-training-v1`
- `research/experiment-001`
- `team/project-results`

---

## 🏷️ Metadata Tags

Use consistent tags for discoverability:

**Example**:
```
tags: ["domain", "data-type", "project", "status"]

Specific:
tags: ["genomics", "rna-seq", "cancer-study", "published"]
tags: ["ml", "training-data", "model-v2", "production"]
tags: ["workshop", "test", "tutorial"]
```

---

## 🆘 Help Resources

- **Workshop Guide**: Full documentation
- **Quilt Docs**: [docs.quilt.bio](https://docs.quilt.bio)
- **GitHub**: [github.com/quiltdata/quilt-mcp-server](https://github.com/quiltdata/quilt-mcp-server)
- **Support**: support@quiltdata.io

---

## 💡 Pro Tips

1. **Always create READMEs** - Future you will thank you
2. **Use descriptive names** - `genomics/rna-seq-analysis` not `data1`
3. **Add metadata tags** - Makes packages discoverable
4. **Include visualizations** - Makes data more accessible
5. **Test queries small** - Run `LIMIT 10` first
6. **Upload before packaging** - Verify S3 uploads succeeded
7. **Check Quilt catalog** - Verify packages render correctly

---

## 🎓 After the Workshop

Try these on your own:

- [ ] Query your own data with Athena
- [ ] Create a package with your analysis results
- [ ] Generate a custom visualization
- [ ] Share a package with your team
- [ ] Set up automated packaging workflow

---

**Happy Data Packaging! 📦**


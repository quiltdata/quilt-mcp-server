# Customer Prompts: Package Creation & Visualization

## Quick Start Prompts

Copy and paste these prompts when working with Quilt MCP Server through Claude or other LLM interfaces.

---

## 📦 Package Creation Prompts

### Scenario 1: Create Package from Existing S3 Files

**Prompt:**
```
I need to create a Quilt package from files that are already in S3.

My files are at:
- s3://my-bucket/data/experiment_results.csv
- s3://my-bucket/data/sample_metadata.json
- s3://my-bucket/docs/protocol.md

Please create a package named "research/experiment-001" with these files.
Use the "research" metadata template and organize the files automatically.
```

**What the LLM will do:**
- Call `package_create()` with your S3 URIs
- Generate README and visualizations automatically
- Return package details with catalog URL

---

### Scenario 2: Create Package from Entire S3 Prefix (Bulk Import)

**Prompt:**
```
I have a lot of data files in S3 at s3://my-data-bucket/experiments/exp-2024-Q4/

Please create a Quilt package named "team/q4-2024-experiment" from all files 
in that prefix. Use the genomics template and generate a comprehensive README 
with visualizations.
```

**What the LLM will do:**
- Call `package_create_from_s3()` for bulk import
- Discover all files in the prefix automatically
- Organize by file type (data/, docs/, etc.)
- Generate visualizations showing file distribution

---

### Scenario 3: Create Package from Local Files (Two-Step)

**Prompt:**
```
I have local CSV files that I need to package in Quilt:
- experiment_data.csv (contains: sample_id, measurement_1, measurement_2)
- sample_info.csv (contains: sample_id, condition, treatment)

Please:
1. Upload these files to the "my-work-bucket" S3 bucket under "experiments/batch-05/"
2. Create a Quilt package named "lab/batch-05-analysis"
3. Use the ML metadata template
4. Generate visualizations showing the data distribution
```

**What the LLM will do:**
- Use `bucket_objects_put()` to upload your files
- Use `package_create()` to create the package from S3 URIs
- Apply ML template
- Generate visualizations automatically

---

### Scenario 4: Create Package with Custom Metadata

**Prompt:**
```
Create a package named "analytics/monthly-report-oct-2024" from:
- s3://reports-bucket/october/sales_data.parquet
- s3://reports-bucket/october/customer_insights.json

Add custom metadata:
- project: "Q4 Performance Review"
- owner: "analytics-team"
- reporting_period: "2024-10"
- data_classification: "internal"

Use the analytics template and include visualizations.
```

**What the LLM will do:**
- Create package with custom metadata merged into template
- Generate visualizations
- Include all metadata in package

---

## 📊 Visualization Prompts

### Scenario 5: Generate Visualizations for Existing Package

**Prompt:**
```
I have a package named "research/experiment-001" and I want to see 
visualizations of its contents.

Please show me:
- What file types are in the package
- How files are organized by folder
- Size distribution of files
- A summary dashboard
```

**What the LLM will do:**
- Browse the package to get structure
- Generate visualizations showing:
  - Pie chart of file types
  - Bar chart of folder distribution
  - Histogram of file sizes
  - Summary statistics dashboard

---

### Scenario 6: Create Package with Specific Visualization Style

**Prompt:**
```
Create a package named "genomics/rnaseq-batch-12" from 
s3://genomics-data/batch-12/

Use the genomics metadata template and make sure the visualizations
use the genomics color scheme (greens/teals).

Include:
- File type distribution chart
- Folder organization view
- Size analysis
- Interactive dashboard for the catalog
```

**What the LLM will do:**
- Create package with genomics template
- Apply genomics color scheme to visualizations
- Generate all requested visualization types
- Include dashboard structure for catalog UI

---

## 🎯 Advanced Prompts

### Scenario 7: Dry Run / Preview Before Creating

**Prompt:**
```
I want to preview what a package would look like before actually creating it.

Please show me a preview of a package from s3://my-bucket/project-alpha/
named "team/project-alpha".

Don't create it yet - just show me:
- How files would be organized
- What the README would say
- What visualizations would be generated
- Total size and file count
```

**What the LLM will do:**
- Call package creation with `dry_run=True`
- Show preview of structure, README, visualizations
- No actual package created

---

### Scenario 8: Create Package with Exclude Patterns

**Prompt:**
```
Create a package from s3://data-bucket/project-x/ but exclude:
- Any files with "temp" or "test" in the name
- All .log files
- Files in any "__pycache__" folders

Name it "production/project-x-v1" and use standard template.
```

**What the LLM will do:**
- Use `package_create_from_s3()` with `exclude_patterns`
- Filter out unwanted files
- Create clean package with only production files

---

### Scenario 9: Update Existing Package with New Files

**Prompt:**
```
I have an existing package "research/experiment-001" and I want to add new files:
- s3://my-bucket/data/followup_results.csv
- s3://my-bucket/docs/final_report.pdf

Please create a new version of the package with these additional files.
Keep all existing files and regenerate visualizations to include the new data.
```

**What the LLM will do:**
- Browse existing package to get current files
- Combine with new files
- Create new package revision
- Update visualizations

---

### Scenario 10: Package with Multiple Data Types

**Prompt:**
```
Create a comprehensive package named "multimodal/study-2024" from:

CSV data:
- s3://data/patient_demographics.csv
- s3://data/clinical_measurements.csv

Images:
- s3://data/scans/*.png (all PNG files in this folder)

Documents:
- s3://data/study_protocol.pdf
- s3://data/consent_forms.pdf

Notebooks:
- s3://data/analysis.ipynb

Use research template and create visualizations showing:
- File types breakdown (should show: CSV, PNG, PDF, IPYNB)
- Folder organization
- Size distribution by file type
```

**What the LLM will do:**
- Import all file types
- Organize by type (data/, images/, docs/, notebooks/)
- Generate comprehensive visualizations
- Create detailed README

---

## 🔧 Troubleshooting Prompts

### If Upload Fails

**Prompt:**
```
I tried to create a package but got an error about permissions.

Please:
1. Check my AWS permissions for bucket "my-bucket"
2. Show me what permissions I need
3. Suggest how to fix the issue
```

### If Package Creation Is Slow

**Prompt:**
```
I'm trying to package s3://big-data-bucket/large-dataset/ which has thousands of files.

Can you:
1. Tell me how many files are there
2. Show me the total size
3. Suggest if I should use filters to reduce the dataset
4. Start the package creation with status updates
```

### If Visualizations Don't Look Right

**Prompt:**
```
I created a package but the visualizations show wrong file counts.

My package is "team/dataset-123". Please:
1. Check the package structure
2. Regenerate visualizations
3. Show me the file type breakdown
```

---

## 💡 Pro Tips for Best Results

### Tip 1: Be Specific About Structure
```
Good: "Organize files into data/, docs/, and notebooks/ folders"
Better: "Auto-organize files by type using the standard folder structure"
```

### Tip 2: Specify Metadata Template
```
Available templates:
- standard: General purpose packages
- genomics: Genomics/biology data
- ml: Machine learning datasets
- research: Academic research data
- analytics: Business analytics data
```

### Tip 3: Use Dry Run First
```
"First show me a preview (dry run) of the package structure, then if it looks 
good, create the actual package."
```

### Tip 4: Request Specific Visualizations
```
"Generate visualizations showing:
- File type distribution (pie chart)
- Folder structure (bar chart)
- File size histogram
- Summary statistics dashboard"
```

---

## 📋 Complete Example: End-to-End Workflow

**Comprehensive Prompt:**
```
I need to create a well-documented Quilt package for our Q4 2024 experiment.

Source data:
- Local files: experiment_raw_data.csv, sample_metadata.json
- Already in S3: s3://lab-data/protocols/exp_protocol.pdf

Steps I need:
1. Upload my local files to s3://lab-data/experiments/q4-2024/
2. Create a package named "research-lab/q4-2024-experiment"
3. Include all files (uploaded + existing protocol)
4. Use the "research" metadata template
5. Add custom metadata:
   - experiment_id: "EXP-2024-Q4-001"
   - pi_name: "Dr. Smith"
   - completion_date: "2024-10-15"
6. Generate comprehensive visualizations showing:
   - File types and sizes
   - Folder organization
   - Interactive dashboard
7. Create a detailed README explaining the experiment
8. Show me the catalog URL where I can view the package

Please walk me through each step and confirm before proceeding.
```

---

## 🎓 Learning Prompts

### Explore What's Possible

**Prompt:**
```
I'm new to Quilt. Can you show me:
1. What package creation tools are available?
2. A simple example of creating a package
3. How to add visualizations
4. Where to view the package after creation
```

### Understand Your Data

**Prompt:**
```
I have data at s3://my-bucket/project-data/ but I'm not sure what's there.

Can you:
1. List the files and show their types
2. Calculate total size
3. Suggest how to organize it into a package
4. Recommend which metadata template to use
```

---

## 🔗 Quick Reference

| Task | Recommended Tool | Key Parameters |
|------|-----------------|----------------|
| Create from specific S3 files | `package_create()` | `files`, `name` |
| Bulk import from S3 prefix | `package_create_from_s3()` | `source_bucket`, `source_prefix` |
| Upload then package | `bucket_objects_put()` → `package_create()` | `bucket`, `items`, then `files` |
| Preview before creating | Any with `dry_run=True` | `dry_run=True` |
| Custom metadata | Any | `metadata` parameter |
| Exclude files | `package_create_from_s3()` | `exclude_patterns` |

---

## 📞 Getting Help

If a prompt doesn't work as expected, try:

**Debug Prompt:**
```
Something went wrong with my package creation. The error message was: [paste error]

Can you:
1. Explain what went wrong
2. Show me the correct parameters
3. Try again with the right format
```

**Clarification Prompt:**
```
I don't understand the response about [specific part].

Can you explain:
- What that means
- What I should do next
- An example of the right way to do it
```

---

## 🚀 Ready to Start?

Pick the scenario that matches your use case, copy the prompt, and customize it with your:
- Bucket names
- File paths
- Package names
- Metadata values

The LLM will handle the rest! 🎉


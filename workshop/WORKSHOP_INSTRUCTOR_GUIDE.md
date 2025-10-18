# Quilt MCP Workshop - Instructor Guide

## Workshop Overview

**Duration**: 90 minutes  
**Level**: Beginner to Intermediate  
**Prerequisites**: Basic AWS knowledge, Python installed  
**Format**: Hands-on, instructor-led

## Learning Objectives

By the end of this workshop, participants will be able to:

1. ✅ Install and configure Quilt MCP with Claude Desktop
2. ✅ Discover and browse S3 data using natural language
3. ✅ Query data with Athena using conversational prompts
4. ✅ Create Quilt packages with metadata and documentation
5. ✅ Generate interactive visualizations for packages
6. ✅ Execute the complete workflow: Query → Visualize → Package

## Pre-Workshop Setup (Day Before)

### For Participants

Send participants this checklist **24 hours before**:

```markdown
# Pre-Workshop Checklist

Please complete these steps before the workshop:

- [ ] Install Python 3.11+ (https://www.python.org/downloads/)
- [ ] Install Claude Desktop (https://claude.ai/download)
- [ ] Configure AWS credentials (`aws configure`)
- [ ] Verify AWS access: Run `aws sts get-caller-identity`
- [ ] Install `uv`: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- [ ] Test `uv`: Run `uvx --help`

If you encounter issues, arrive 15 minutes early for help.
```

### For Instructor

1. **Prepare Sample Data**:
   - Create a test S3 bucket: `quilt-workshop-[date]`
   - Upload sample CSV files (RNA-seq data works well)
   - Set up an Athena database with test tables
   - Pre-create a few example packages

2. **Test Environment**:
   - Verify Quilt MCP installation works on your machine
   - Test all workshop prompts end-to-end
   - Prepare backup AWS credentials (in case participants have issues)
   - Have troubleshooting FAQ ready

3. **Screen Sharing Setup**:
   - Large font in Claude Desktop (for visibility)
   - Close unnecessary applications
   - Have AWS Console open in separate browser tab
   - Have Quilt catalog open for showing results

4. **Backup Plans**:
   - Pre-recorded demo videos (if live demo fails)
   - Alternative MCP configuration (VS Code option)
   - Sample MCP responses (if network issues occur)

## Workshop Timeline

### Introduction (10 minutes)

**Topics to cover**:
- What is MCP (Model Context Protocol)?
- Why Quilt MCP? (Data discovery, query, packaging)
- What we'll build today (Query → Visualize → Package)

**Demo**:
Show completed example from Exercise 5 (RNA-seq analysis package) in Quilt catalog.

**Key Points**:
- "MCP gives Claude the ability to interact with your AWS data"
- "Today you'll create an analysis package with interactive visualizations"
- "Everything we do will be through natural language - no code required"

---

### Installation & Setup (15 minutes)

**Walk through**:

1. **Install Quilt MCP** (5 min)
   ```bash
   uvx --from quilt-mcp quilt-mcp
   ```
   
2. **Configure Claude Desktop** (10 min)
   - Show config file location for each OS
   - Copy-paste configuration
   - Restart Claude Desktop
   - Verify 🔌 icon appears

**Common Issues**:
- Config file in wrong location → Show for each OS
- JSON syntax errors → Use validator (jsonlint.com)
- AWS credentials → Run `aws configure`

**Checkpoint**: Everyone should see MCP tools when they ask:
```
What Quilt tools do you have available?
```

---

### Exercise 1: Data Discovery (10 minutes)

**Objective**: Get comfortable with natural language data exploration.

**Instructor Demo** (3 min):
```
Show me what S3 buckets are available in my AWS account.
```

**Guided Practice** (5 min):
Participants try:
```
Browse the contents of [workshop-bucket] and show me the top-level folders.
```

**Discussion** (2 min):
- Q: "What other discovery questions could you ask?"
- A: File sizes, file types, recent files, etc.

**Key Takeaway**: "You can explore your data by asking questions in plain English"

---

### Exercise 2: Querying with Athena (15 minutes)

**Objective**: Learn to query structured data conversationally.

**Instructor Demo** (5 min):

1. List databases:
   ```
   List the databases available in Athena.
   ```

2. Show tables:
   ```
   Show me the tables in the genomics_db database.
   ```

3. Query data:
   ```
   Query the rna_seq table and show me the first 10 rows.
   ```

**Guided Practice** (8 min):

Participants execute:
```
Query the genomics_db.rna_seq table for genes BRCA1, TP53, and MYC.
Show me sample_id, gene_name, and expression_level columns.
```

**Discussion** (2 min):
- Q: "How is this different from writing SQL directly?"
- Q: "When would you use this vs traditional SQL tools?"

**Key Takeaway**: "Claude translates your intent into proper SQL queries"

---

### Exercise 3: Package Search (10 minutes)

**Objective**: Understand Tabulator for package discovery.

**Instructor Demo** (4 min):
```
Search for packages in [workshop-bucket] that contain "analysis" in their metadata.
```

**Guided Practice** (4 min):
```
Show me what files are in the genomics/example-package package.
```

**Discussion** (2 min):
- Tabulator vs Athena: When to use each?
- Package metadata: Why it matters

**Key Takeaway**: "Packages make data discoverable and reusable"

---

### Break (5 minutes)

Give participants time to catch up or troubleshoot.

---

### Exercise 4: Create a Simple Package (15 minutes)

**Objective**: Understand the basic packaging workflow.

**Instructor Demo** (5 min):

Show complete workflow:
1. Create README
2. Upload to S3
3. Create package
4. View in Quilt catalog

**Guided Practice** (10 min):

Participants create their first package:
```
Create a README file for a new package called "workshop/my-first-package".
The README should explain that this is a test package created during the
Quilt MCP workshop and include today's date.
```

Then upload and package it.

**Checkpoint**: Everyone should have a package visible in Quilt catalog.

**Key Takeaway**: "Packages bundle data with documentation and metadata"

---

### Exercise 5: Complete Workflow (30 minutes)

**Objective**: Execute the full Query → Visualize → Package workflow.

**Instructor Demo** (10 min):

Walk through each step slowly:

1. **Query data** (3 min):
   ```
   Query the genomics_db.rna_seq table using Athena.
   Get sample_id, gene_name, and expression_level for genes: BRCA1, TP53, MYC.
   ```

2. **Create visualization** (3 min):
   ```
   Using the query results, create an interactive box plot showing 
   expression_level by gene_name, grouped by sample_id. 
   Use the "genomics" color scheme.
   ```
   
   **Note**: This generates ECharts JSON + quilt_summarize.json

3. **Create README** (2 min):
   ```
   Create a detailed README for this analysis package...
   ```

4. **Upload and package** (2 min):
   ```
   Upload all files and create package workshop/rna-seq-analysis
   ```

**Guided Practice** (18 min):

Participants execute the same workflow with guidance.

**Circulate and help**:
- Check that queries are returning data
- Verify visualizations are generated
- Ensure uploads succeed
- Troubleshoot AWS permission issues

**Showcase** (2 min):

Open the package in Quilt catalog and highlight:
- ✅ Interactive box plot at top
- ✅ README with analysis description
- ✅ Raw data available
- ✅ Metadata tags

**Key Takeaway**: "This workflow lets you publish analysis results as interactive packages"

---

### Wrap-up & Q&A (10 minutes)

**Review**:
- What we learned (5 capabilities)
- What you created (packages with visualizations)
- Where to go next (advanced topics)

**Discussion**:
- Q: "How would you use this in your work?"
- Q: "What other data sources would you want to connect?"

**Resources**:
- Workshop materials: [GitHub repo]
- Documentation: docs.quilt.bio
- Support: support@quiltdata.io

**Next Steps**:
- Explore your own data
- Create real analysis packages
- Share packages with your team
- Integrate into workflows

---

## Troubleshooting During Workshop

### Problem: MCP not connecting

**Quick Fix**:
1. Check config file syntax (common: missing comma)
2. Verify file path is correct for OS
3. Force quit and restart Claude Desktop
4. Check AWS credentials

**Workaround**: Have participants pair up, share screen with working setup.

### Problem: AWS permission denied

**Quick Fix**:
1. Verify `aws sts get-caller-identity` works
2. Check IAM permissions (S3, Athena, Glue)
3. Try different AWS profile

**Workaround**: Use instructor's AWS account temporarily, have participant watch.

### Problem: Athena query fails

**Quick Fix**:
1. Verify database/table exists
2. Check Athena output location configured
3. Try simpler query first

**Workaround**: Use pre-run query results, skip to visualization step.

### Problem: Package creation fails

**Quick Fix**:
1. Verify bucket exists and is accessible
2. Check S3 upload succeeded first
3. Verify S3 URIs are correct

**Workaround**: Use pre-created package, focus on visualization.

### Problem: Visualization doesn't render

**Quick Fix**:
1. Check quilt_summarize.json was uploaded
2. Verify file paths match
3. Refresh Quilt catalog page

**Workaround**: Show pre-made example, explain what they should see.

---

## Post-Workshop Follow-up

### Immediately After

**Send participants**:
1. Workshop recording link (if recorded)
2. Completed example package URLs
3. Feedback survey link
4. Link to advanced documentation

### Email Template

```
Subject: Quilt MCP Workshop - Thank You & Resources

Hi everyone,

Thank you for attending the Quilt MCP workshop today!

Here are the resources we covered:

📚 Workshop Guide: [link to WORKSHOP.md]
🎥 Recording: [link]
📦 Example Packages: [Quilt catalog links]
📖 Documentation: https://docs.quilt.bio

Next Steps:
1. Complete Exercise 5 if you didn't finish
2. Try the example prompts with your own data
3. Create a real analysis package for your work

Questions? Reply to this email or contact support@quiltdata.io

Happy data packaging!
[Your name]
```

### One Week Later

Send follow-up with:
- Advanced tutorial links
- New feature announcements
- Community Slack/Discord invite
- Office hours schedule

---

## Workshop Variations

### Shorter Version (45 minutes)

Focus on:
- Installation (10 min)
- Data discovery (5 min)
- Query with Athena (10 min)
- Complete workflow demo by instructor (15 min)
- Q&A (5 min)

Skip: Exercises 3 & 4

### Longer Version (2 hours)

Add:
- Advanced querying (joins, aggregations)
- Multi-visualization dashboards
- Custom metadata schemas
- Package versioning and lineage
- Integration with notebooks

### Domain-Specific

**For Genomics**:
- Use RNA-seq, GWAS, or variant data
- Show IGV genome browser integration
- Discuss data sharing compliance

**For Machine Learning**:
- Use model training data
- Show model versioning
- Discuss experiment tracking

**For Business Analytics**:
- Use sales/customer data
- Show dashboard creation
- Discuss report automation

---

## Materials Checklist

Before workshop:

- [ ] WORKSHOP.md printed or easily accessible
- [ ] Sample AWS account configured
- [ ] Test data uploaded to S3
- [ ] Athena database and tables created
- [ ] Example packages pre-created
- [ ] Claude Desktop configured on presentation machine
- [ ] Quilt catalog open in browser
- [ ] AWS Console open in browser
- [ ] Troubleshooting FAQ printed
- [ ] Backup credentials ready
- [ ] Screen sharing tested
- [ ] Font sizes increased for visibility
- [ ] Timer/agenda visible to participants

---

## Success Metrics

Track these during/after workshop:

- **Setup Success Rate**: % who get MCP working
- **Completion Rate**: % who finish Exercise 5
- **Time to First Package**: Average time to create first package
- **Questions Asked**: Common confusion points
- **Post-Workshop Usage**: % who create packages in next 30 days

---

## Feedback Collection

Ask participants (anonymous survey):

1. **Clarity** (1-5): Was the workshop easy to follow?
2. **Usefulness** (1-5): Will you use Quilt MCP in your work?
3. **Pace** (too slow / just right / too fast)
4. **What worked well?** (open-ended)
5. **What could be improved?** (open-ended)
6. **What features would you like to see?** (open-ended)

---

## Tips for Success

1. **Start on Time**: Respect everyone's schedule
2. **Encourage Questions**: "No question is too basic"
3. **Circulate During Exercises**: Help individuals proactively
4. **Celebrate Small Wins**: Cheer when people succeed
5. **Show Real Examples**: Use actual data from your domain
6. **Be Patient with Setup**: First 15 minutes are hardest
7. **Have Backup Plans**: Something will go wrong
8. **Make it Fun**: This is powerful technology!

---

**Good luck with your workshop! 🎉**


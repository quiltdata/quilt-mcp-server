# Quilt MCP Workshop Materials

This directory contains everything you need to run or participate in a Quilt MCP workshop.

## 📁 Workshop Files

| File | Purpose | Audience |
|------|---------|----------|
| **WORKSHOP.md** | Main workshop guide with exercises | Participants |
| **WORKSHOP_QUICK_REFERENCE.md** | One-page reference card | Participants (print!) |
| **WORKSHOP_INSTRUCTOR_GUIDE.md** | Detailed teaching guide | Instructors |
| **WORKSHOP_PRE_EVENT_EMAIL.md** | Pre-workshop setup email | Organizers |

## 🎯 Quick Start

### For Participants

1. **Before the workshop**: Complete setup in `WORKSHOP.md` → [Installation](#installation)
2. **During the workshop**: Follow along with `WORKSHOP.md` exercises
3. **Keep handy**: Print `WORKSHOP_QUICK_REFERENCE.md` for easy reference

### For Instructors

1. **Review**: Read `WORKSHOP_INSTRUCTOR_GUIDE.md` thoroughly
2. **Prepare**: Set up sample data and test environment (see Pre-Workshop Setup)
3. **Send**: Email `WORKSHOP_PRE_EVENT_EMAIL.md` content to participants 24h before
4. **Deliver**: Follow the 90-minute timeline in the instructor guide

## 📚 Workshop Overview

**Duration**: 90 minutes  
**Level**: Beginner to Intermediate  
**Format**: Hands-on, instructor-led

**Learning Objectives**:
- Install and configure Quilt MCP with Claude Desktop
- Discover and query AWS data using natural language
- Create Quilt packages with visualizations and documentation
- Execute complete workflow: Query → Visualize → Package

## 🛠️ Prerequisites

Participants need:
- Python 3.11+
- AWS account with S3/Athena/Glue access
- Claude Desktop installed
- AWS credentials configured

See `WORKSHOP.md` for detailed prerequisites.

## 📅 Workshop Structure

### Part 1: Setup & Discovery (25 minutes)
- Installation and configuration (15 min)
- Data discovery with S3 (10 min)

### Part 2: Querying & Searching (25 minutes)
- Athena queries (15 min)
- Package search with Tabulator (10 min)

### Part 3: Creating & Packaging (40 minutes)
- Simple package creation (15 min)
- Complete workflow: Query → Visualize → Package (30 min)

## 🎓 Exercises

### Exercise 1: Discover Your Data
Learn to browse S3 buckets and explore data using natural language.

### Exercise 2: Query with Athena
Execute SQL queries conversationally and explore results.

### Exercise 3: Search Package Metadata
Find and explore existing Quilt packages with Tabulator.

### Exercise 4: Create Simple Package
Bundle files with documentation and metadata into your first package.

### Exercise 5: Complete Workflow (Capstone)
Query RNA-seq data, create interactive visualization, and publish as package.

## 🔧 Technology Stack

- **MCP (Model Context Protocol)**: Extends Claude with tool capabilities
- **Quilt MCP Server**: Provides AWS data access tools
- **Claude Desktop**: AI assistant with MCP support
- **Amazon Bedrock**: Claude model hosting (optional)
- **AWS Services**: S3, Athena, Glue, Quilt Catalog

## 📊 Sample Data

The workshop uses RNA-seq gene expression data as examples:
- Genes: BRCA1, TP53, MYC
- Metrics: expression_level, sample_id
- Format: CSV tables in Athena

**Setting up sample data** (instructors):
```sql
CREATE EXTERNAL TABLE IF NOT EXISTS genomics_db.rna_seq (
  sample_id STRING,
  gene_name STRING,
  expression_level DOUBLE
)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ','
LOCATION 's3://your-workshop-bucket/rna_seq_data/'
```

## 🎯 Expected Outcomes

By the end of the workshop, participants will have:

1. ✅ Quilt MCP installed and configured
2. ✅ Queried data from Athena using natural language
3. ✅ Created at least 2 Quilt packages
4. ✅ Generated an interactive visualization (ECharts box plot)
5. ✅ Published a complete analysis package viewable in Quilt catalog

## 🆘 Common Issues & Solutions

### MCP Not Connecting
**Symptoms**: No 🔌 icon, Claude doesn't see tools  
**Fix**: Verify config file location, restart Claude Desktop

### AWS Authentication
**Symptoms**: "Access Denied" errors  
**Fix**: Run `aws configure`, check IAM permissions

### Athena Queries Fail
**Symptoms**: "Database not found"  
**Fix**: List databases first, verify spelling, check Athena setup

### Visualization Doesn't Render
**Symptoms**: Package creates but no viz appears  
**Fix**: Verify quilt_summarize.json uploaded, check file paths

See `WORKSHOP.md` → [Troubleshooting](#troubleshooting) for more.

## 📖 Additional Resources

**Documentation**:
- Quilt Docs: https://docs.quilt.bio
- MCP Specification: https://modelcontextprotocol.io
- Quilt MCP GitHub: https://github.com/quiltdata/quilt-mcp-server

**Support**:
- Email: support@quiltdata.io
- GitHub Issues: https://github.com/quiltdata/quilt-mcp-server/issues
- Documentation: https://docs.quilt.bio

**Advanced Topics**:
- Event-driven packaging
- Package lineage and provenance
- Cross-account access
- Custom metadata schemas
- Notebook integration

## 🤝 Contributing

Have ideas to improve the workshop?

1. Test with real participants
2. Collect feedback
3. Submit PRs with improvements
4. Share your workshop experience

## 📝 License

These workshop materials are provided under the same license as the Quilt MCP Server.

## 🙏 Acknowledgments

Created by the Quilt team to help data scientists, researchers, and analysts leverage AI for better data management.

---

## Quick Links

- [Main Workshop Guide](WORKSHOP.md) - Start here!
- [Quick Reference](WORKSHOP_QUICK_REFERENCE.md) - Print this
- [Instructor Guide](WORKSHOP_INSTRUCTOR_GUIDE.md) - For teachers
- [Pre-Event Email](WORKSHOP_PRE_EVENT_EMAIL.md) - For organizers

---

**Questions?** Open an issue or email workshops@quiltdata.io

**Ready to start?** Jump to [WORKSHOP.md](WORKSHOP.md)!


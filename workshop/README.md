# Quilt MCP Workshop Materials

This folder contains all materials for running a Quilt MCP workshop with AWS Bedrock.

## 📚 Files Overview

### For Participants

- **[WORKSHOP.md](./WORKSHOP.md)** - Main workshop guide with step-by-step instructions
  - Installation instructions for VS Code + Continue or MCP Inspector
  - Configuration for AWS Bedrock
  - Hands-on exercises
  - Troubleshooting guide

- **[WORKSHOP_QUICK_REFERENCE.md](./WORKSHOP_QUICK_REFERENCE.md)** - Quick reference card
  - Common prompts
  - Tool categories
  - Keyboard shortcuts

- **[WORKSHOP_PRE_EVENT_EMAIL.md](./WORKSHOP_PRE_EVENT_EMAIL.md)** - Pre-event setup instructions
  - Send to participants before workshop
  - Prerequisites checklist
  - Software to install

### For Instructors

- **[WORKSHOP_INSTRUCTOR_GUIDE.md](./WORKSHOP_INSTRUCTOR_GUIDE.md)** - Complete instructor guide
  - Workshop timeline
  - Talking points
  - Common issues and solutions
  - Advanced topics

- **[HUBSPOT_EMAIL_TEMPLATE.html](./HUBSPOT_EMAIL_TEMPLATE.html)** - Email template for credentials
  - HubSpot-compatible HTML template
  - Includes AWS credentials placeholders
  - Setup instructions
  - Code examples

### For Workshop Administrators

- **[WORKSHOP_README.md](./WORKSHOP_README.md)** - Workshop overview and planning
  - Target audience
  - Learning objectives
  - Prerequisites

## 🚀 Quick Start for Instructors

1. **Before Workshop**:
   - Review [WORKSHOP_INSTRUCTOR_GUIDE.md](./WORKSHOP_INSTRUCTOR_GUIDE.md)
   - Send [WORKSHOP_PRE_EVENT_EMAIL.md](./WORKSHOP_PRE_EVENT_EMAIL.md) to participants
   - Create AWS IAM users for participants
   - Send credentials using [HUBSPOT_EMAIL_TEMPLATE.html](./HUBSPOT_EMAIL_TEMPLATE.html)

2. **During Workshop**:
   - Follow [WORKSHOP_INSTRUCTOR_GUIDE.md](./WORKSHOP_INSTRUCTOR_GUIDE.md) timeline
   - Participants follow [WORKSHOP.md](./WORKSHOP.md)
   - Keep [WORKSHOP_QUICK_REFERENCE.md](./WORKSHOP_QUICK_REFERENCE.md) handy

3. **After Workshop**:
   - Clean up AWS IAM users (instructions in instructor guide)
   - Gather feedback
   - Share additional resources

## 🏗️ Workshop Structure

### Setup (30 minutes)
- Install VS Code + Continue extension
- Configure AWS Bedrock
- Install Quilt MCP server
- Verify installation

### Exercises (90 minutes)
1. **Explore Data** (20 min) - S3 and package exploration
2. **Query Data** (20 min) - Athena queries
3. **Create Visualizations** (20 min) - Data visualization
4. **Package Analysis** (30 min) - Complete workflow

### Target Audience
- Data scientists
- Bioinformaticians
- Research engineers
- Anyone working with scientific data in AWS

## 🔧 Technical Requirements

### For Participants
- Python 3.11+
- Node.js 18+ (for MCP Inspector)
- VS Code (recommended) or terminal
- AWS credentials with Bedrock access

### For Instructors
- AWS account with:
  - IAM user creation permissions
  - Bedrock enabled
  - S3 buckets for examples
  - Athena + Glue catalog access

## 📖 Additional Resources

- Main README: [../README.md](../README.md)
- Bedrock Quickstart: [../BEDROCK_QUICKSTART.md](../BEDROCK_QUICKSTART.md) (if exists)
- API Documentation: [../docs/api/TOOLS.md](../docs/api/TOOLS.md)

## 💡 Tips for Success

1. **Test Everything**: Run through the entire workshop yourself before teaching
2. **Have Backup Plans**: Prepare for network issues, credential problems, etc.
3. **Time Management**: Exercises can take longer than expected - be flexible
4. **Encourage Questions**: The best learning happens through exploration
5. **Share Examples**: Have pre-made examples for participants who fall behind

## 🤝 Support

For questions or issues:
- Workshop-specific: Contact your workshop coordinator
- Quilt MCP technical issues: [GitHub Issues](https://github.com/quiltdata/quilt-mcp-server/issues)
- General Quilt support: support@quiltdata.io

---

*Last Updated: October 2024*


# Pre-Workshop Email Template

**Subject**: 📦 Quilt MCP Workshop - Setup Instructions (Action Required)

---

Hi [Participant Name],

Thank you for registering for the **Quilt MCP Workshop** on **[Date]** at **[Time]**!

To make the most of our time together, please complete the setup steps below **before the workshop**. This will take approximately 15-20 minutes.

---

## ✅ Pre-Workshop Checklist

Please complete these steps and verify each one works:

### 1. Install Python 3.11 or Higher

**Check if you have Python**:
```bash
python --version
```

If you see `Python 3.11.x` or higher, you're good! ✅

If not, download from: https://www.python.org/downloads/

---

### 2. Install VS Code

Download and install Visual Studio Code:
- **Download**: https://code.visualstudio.com
- **Install**: Follow the installer for your operating system
- **Launch**: Open VS Code

Verify: VS Code opens successfully.

---

### 3. Configure AWS Credentials

You'll need AWS access with permissions for:
- S3 (read/write)
- Athena (query execution)
- AWS Glue (data catalog access)

**Set up credentials**:
```bash
aws configure
```

Enter your:
- AWS Access Key ID
- AWS Secret Access Key
- Default region (e.g., `us-east-1`)
- Output format (just press Enter for default)

**Verify it works**:
```bash
aws sts get-caller-identity
```

You should see your AWS account information. ✅

**Don't have AWS credentials?** Contact us at [support-email] and we'll provide temporary workshop credentials.

---

### 4. Install `uv` (Python Package Manager)

**macOS/Linux**:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows** (PowerShell):
```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Verify installation**:
```bash
uvx --help
```

You should see help text for `uvx`. ✅

---

### 5. Test Quilt MCP Installation

Run this command to verify everything works:

```bash
uvx --from quilt-mcp quilt-mcp
```

You should see output like:
```
Quilt MCP Server starting...
```

Press `Ctrl+C` to stop it. This confirms the installation works! ✅

---

## 🚨 Need Help?

If you encounter issues during setup:

1. **Join our Slack**: [slack-invite-link] - #workshop-support channel
2. **Email us**: [support-email]
3. **Arrive early**: Come 15 minutes before the workshop starts for setup help

---

## 📅 Workshop Details

**Date**: [Workshop Date]  
**Time**: [Start Time] - [End Time] ([Timezone])  
**Location**: [Physical location or Zoom link]  
**Duration**: 90 minutes

**What to Bring**:
- Your laptop with the setup completed
- AWS credentials (or use our temporary credentials)
- Questions about your data!

---

## 📖 What We'll Cover

During the workshop, you'll learn to:

1. ✨ Discover and browse your S3 data using natural language
2. 🔍 Query data with Athena using conversational prompts
3. 📦 Create Quilt packages with metadata and documentation
4. 📊 Generate interactive visualizations for your analyses
5. 🚀 Execute the complete workflow: Query → Visualize → Package

By the end, you'll have created an analysis package with interactive visualizations!

---

## 📚 Optional Pre-Reading

Want to get a head start? Check out these resources:

- **Quilt Documentation**: https://docs.quilt.bio
- **MCP Overview**: https://modelcontextprotocol.io
- **Workshop Guide** (attached): Full step-by-step instructions

---

## 🎯 What to Prepare

Think about:
- What data do you work with? (We'll use it in examples)
- What analyses do you want to package? (Good use case for practice)
- What questions do you have about data management?

---

## ✅ Setup Verification

Please reply to this email confirming:
- [ ] Python 3.11+ installed
- [ ] VS Code installed
- [ ] Continue extension installed
- [ ] AWS credentials configured (and Bedrock access enabled)
- [ ] `uv` installed and tested
- [ ] Quilt MCP test successful

This helps us identify any issues before the workshop!

---

## 📞 Contact Information

**Workshop Instructor**: [Name] - [email]  
**Technical Support**: [support-email]  
**Slack**: [slack-invite-link]

---

Looking forward to seeing you at the workshop!

Best regards,  
[Your Name]  
[Your Title]

P.S. Can't make it? Let us know ASAP so we can offer your spot to someone on the waitlist.

---

**Attachments**:
- `WORKSHOP.md` - Complete workshop guide
- `WORKSHOP_QUICK_REFERENCE.md` - Quick reference card (print this!)


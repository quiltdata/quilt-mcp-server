# Quilt MCP DXT (Desktop Extension)

Access your Quilt data packages directly from Claude Desktop with this Model Context Protocol (MCP) extension.

## Prerequisites Check

Before installing, run the prerequisites check script to verify your system is ready:

```bash
./check-prereqs.sh
```

This script verifies you have:

- **Python 3.11+** (required for the MCP server)
- **AWS credentials** (for accessing your Quilt data)
- **Claude Desktop** (for running the extension)

## Installation

1. **Run prerequisites check**: `./check-prereqs.sh`
2. **Double-click** the `quilt-mcp-<version>.dxt` file to install in Claude Desktop
3. **Enter your catalog domain** when prompted (see Configuration below)
4. **Restart** Claude Desktop if needed

## Configuration

You only need to provide your **Quilt Catalog Domain** - everything else is automatically detected or uses defaults.

NOTE: To access advanced search, you will need to login using the command-line.

```bash
python3 -m pip install quilt3
quilt3 config https://catalog.example.com
quilt3 login
```

This generates an access code that you paste into the CLI,
that autheneticates you to the Quilt stack.

### Required Setting

- **Quilt Catalog Domain**: The DNS name of your Quilt catalog
  - Example: `catalog.example.com` (without https://)
  - Contact your admin if you're unsure of your catalog domain

The extension automatically detects your AWS credentials from your system configuration.

## Available Commands

Once configured, you can ask Claude to:

- **List packages**: "Show me available Quilt packages"
- **Browse package contents**: "What's in the sales-data package?"
- **Download data**: "Get the latest version of customer-analysis"
- **Search packages**: "Find packages containing 'quarterly-report'"
- **Check package metadata**: "Show me package details for user-behavior-2024"

## Troubleshooting

If you encounter issues:

1. **Run the prerequisites check**: `./check-prereqs.sh`
2. **Verify AWS credentials**: Run `aws sts get-caller-identity` to confirm your AWS access
3. **Check catalog domain**: Ensure your catalog domain is correct (without https://)
4. **Restart Claude Desktop**: After any configuration changes
5. **Email [support](mailto:support@quilt.bio)**: If this doesn't work with your OS or MCP Client.

### Common Issues

- **Extension not loading**: Restart Claude Desktop and verify you have the latest version
- **No packages found**: Check your catalog domain and AWS permissions
- **AWS access denied**: Confirm your AWS credentials have access to your Quilt S3 buckets

### Getting Help

If you continue experiencing issues:

1. Contact your organization's Quilt administrator
2. Verify your AWS IAM permissions for Quilt data access

## Security Notes

- This extension uses your existing AWS credentials - no additional authentication is required
- No credentials are stored within the extension itself
- All data access follows your existing AWS IAM permissions
- The extension runs locally and does not send data to external services

## Uninstalling

To remove the extension:

1. Open Claude Desktop settings
2. Navigate to Extensions
3. Find "Quilt MCP" and click Remove
4. Restart Claude Desktop

---

For more information about Quilt, visit [quiltdata.com](https://quiltdata.com)

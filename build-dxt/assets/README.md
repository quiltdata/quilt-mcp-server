# Quilt MCP Extension for Claude Desktop

Access your Quilt data packages directly from Claude Desktop with this Model Context Protocol (MCP) extension.

## Installation

1. **Download** the `quilt-mcp.dxt` file from the [latest release](https://github.com/quiltdata/fast-mcp-server/releases)
2. **Double-click** the `.dxt` file to install it in Claude Desktop
3. **Restart** Claude Desktop if prompted

## Configuration

After installation, configure the extension in Claude Desktop:

### Required Settings

- **Quilt Catalog Domain**: Your organization's Quilt catalog URL
  - Example: `https://catalog.example.com`
  - Contact your admin if you're unsure of your catalog domain

### Optional Settings

- **AWS Profile**: Specify which AWS profile to use for authentication
  - Leave blank to use your default AWS profile
  - Only needed if you have multiple AWS profiles configured

## Prerequisites

Before using this extension, ensure you have:

### AWS Credentials

The extension uses your existing AWS credentials to access Quilt data. Make sure you have AWS credentials configured through one of these methods:

- **AWS CLI**: Run `aws configure` to set up credentials
- **AWS SSO**: Use `aws sso login` if your organization uses AWS SSO
- **IAM Roles**: If running on EC2, IAM roles will be used automatically
- **Environment Variables**: Set `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`

### Quilt Access

Verify you can access your Quilt catalog:

- You should have appropriate IAM permissions for the S3 buckets containing your Quilt packages
- Test access by visiting your catalog domain in a web browser

## Available Commands

Once configured, you can ask Claude to:

- **List packages**: "Show me available Quilt packages"
- **Browse package contents**: "What's in the sales-data package?"
- **Download data**: "Get the latest version of customer-analysis"
- **Search packages**: "Find packages containing 'quarterly-report'"
- **Check package metadata**: "Show me package details for user-behavior-2024"

## Troubleshooting

### Common Issues

1. **No AWS credentials found**
   1. Configure AWS credentials using `aws configure`
   2. Verify credentials work with: `aws sts get-caller-identity`
2. **Access denied to catalog**
   1. Check your AWS IAM permissions for the catalog S3 bucket
   2. Confirm the catalog domain URL is correct
3. **Package not found**
   1. Verify the package name spelling
   2. Check if you have permissions to access the specific package
   3. Try listing all available packages first
4. **Extension not loading**
   1. Restart Claude Desktop
   2. Check that you're using the latest version of Claude Desktop
   3. Verify the `.dxt` file downloaded completely

### Getting Help

If you continue experiencing issues:

1. Check the [troubleshooting guide](https://github.com/quiltdata/fast-mcp-server/wiki/Troubleshooting)
2. Open an issue on [GitHub](https://github.com/quiltdata/fast-mcp-server/issues)
3. Contact your organization's Quilt administrator

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

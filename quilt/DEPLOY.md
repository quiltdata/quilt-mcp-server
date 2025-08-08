# Deploying Quilt MCP Server Remotely

This guide explains two ways to deploy your Quilt MCP server with a streamable HTTP interface:

1. **AWS Lambda (Recommended)** - Production-ready deployment with API Gateway
2. **Local with ngrok** - Quick development/testing setup

## Option 1: AWS Lambda Deployment (Recommended)

Deploy your Quilt MCP server as an AWS Lambda function with API Gateway for a production-ready, scalable solution.

### Prerequisites

- AWS CLI configured with appropriate permissions
- Python 3.11+ and pip
- AWS CDK CLI (`npm install -g aws-cdk`)
- A Quilt S3 read policy ARN (for accessing your S3 buckets)

### Step 1: Configure Environment

Copy the environment template and configure your settings:

```bash
cp env.example .env
```

Edit `.env` and set:
- `QUILT_READ_POLICY_ARN`: Your AWS IAM policy ARN for S3 read access
- `CDK_DEFAULT_REGION`: AWS region (optional, defaults to us-east-1)
- `AWS_PROFILE`: AWS profile to use (optional, defaults to default)

### Step 2: Deploy to AWS

```bash
cd deploy
./deploy.sh
```

The script will:
1. Install CDK dependencies
2. Bootstrap CDK (if needed)
3. Package and deploy your Lambda function
4. Create API Gateway with API key authentication
5. Output your MCP server URL and API key

### Step 3: Connect from Claude

Use the output from the deployment script:
- **URL**: The API Gateway endpoint (ends with `/mcp/`)
- **Type**: Streamable HTTP
- **API Key**: The generated API key value

### AWS Lambda Features

- **Serverless**: No servers to manage, automatic scaling
- **API Key Authentication**: Secure access with rate limiting
- **S3 Access**: Lambda uses IAM role for secure S3 bucket access
- **CORS Support**: Enabled for Claude web interface
- **Usage Plans**: Rate limiting (100 req/sec, 10k req/day)
- **CloudWatch Logs**: Automatic logging for debugging

### Management Commands

```bash
# Update the deployment
cd deploy && ./deploy.sh

# View logs
aws logs tail /aws/lambda/QuiltMcpStack-QuiltMcpFunction --follow

# Delete the stack
cd deploy && cdk destroy
```

## Option 2: Local Development with ngrok

For quick testing and development, you can run the server locally and expose it via ngrok.

### Prerequisites

You must have [ngrok](https://ngrok.com/) installed and authenticated to expose your local server to the internet.

### a. Install ngrok

If you do not have ngrok installed, download it from [ngrok.com/download](https://ngrok.com/download) and follow the installation instructions for your platform.

For example, on macOS with Homebrew:

```bash
brew install ngrok/ngrok/ngrok
```

Or download and unzip manually:

```bash
# Download from https://ngrok.com/download
unzip ngrok-stable-*.zip
sudo mv ngrok /usr/local/bin
```

### b. Authenticate ngrok (first time only)

Sign up for a free ngrok account at [ngrok.com](https://ngrok.com/), then get your auth token from your dashboard.

Authenticate ngrok with your token:

```bash
ngrok config add-authtoken <YOUR_NGROK_AUTHTOKEN>
```

## 1. Launch the Server

Navigate to the `quilt` directory and run the remote server script:

```bash
python remote.py
```

By default, this will start the server on `http://0.0.0.0:8000/mcp/`.

## 2. Expose the Server Remotely (Required: ngrok)

To access the server from outside your local machine (e.g., from Claude or other clients), you **must** use ngrok to expose your local server to the internet.

Start ngrok to forward HTTP traffic to your local server:

```bash
ngrok http 8000
```

You will see output like:

```log
Forwarding    https://<random>.ngrok.io -> http://localhost:8000
```

Your public URL will be `https://<random>.ngrok.io/mcp/`.

Leave ngrok running while you want your server to be accessible remotely.

## 3. Connect from Claude as a Remote MCP Server

In Claude, add a new remote MCP server with the following settings:

- **URL:** `https://<random>.ngrok.io/mcp/`
- **Type:** Streamable HTTP (or "http")
- **API Key:** (leave blank unless you have added authentication)

Use the public URL provided by ngrok (ending with `/mcp/`).

## 4. Security Notes

- For production, consider adding authentication and HTTPS.
- Do not expose the server to the public internet without proper security controls.
- The ngrok free plan provides a random URL each time you start it; for a fixed domain, see ngrok paid plans.

## 5. Troubleshooting

- Ensure the server is running and accessible from the client machine.
- Check firewall and network settings if you cannot connect.
- Make sure ngrok is running and the tunnel is active.
- Review server and ngrok logs for errors.

---
For more details, see the [FastMCP documentation](https://gofastmcp.com/deployment/running-server#streamable-http).

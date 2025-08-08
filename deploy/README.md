# AWS Lambda Deployment

This directory contains the AWS CDK infrastructure code to deploy the Quilt MCP server as a Lambda function with API Gateway.

## Files

- `app.py` - CDK application entry point
- `quilt_mcp_stack.py` - Main CDK stack defining Lambda, API Gateway, and IAM resources
- `deploy.sh` - Automated deployment script
- `requirements.txt` - CDK Python dependencies
- `cdk.json` - CDK configuration

## Quick Start

1. Configure environment:
   ```bash
   cp ../env.example ../.env
   # Edit .env with your QUILT_READ_POLICY_ARN
   ```

2. Deploy:
   ```bash
   ./deploy.sh
   ```

3. Connect Claude to the output URL with the provided API key.

## Architecture

- **Lambda Function**: Python 3.11 runtime running the Quilt MCP server
- **API Gateway**: HTTP API with CORS and API key authentication
- **IAM Role**: Lambda execution role with S3 read permissions via your policy ARN
- **Usage Plan**: Rate limiting (100 req/sec, 200 burst, 10k daily)

## Environment Variables

- `QUILT_READ_POLICY_ARN` (required) - ARN of IAM policy for S3 bucket access
- `CDK_DEFAULT_ACCOUNT` (optional) - AWS account ID
- `CDK_DEFAULT_REGION` (optional) - AWS region, defaults to us-east-1
- `AWS_PROFILE` (optional) - AWS CLI profile to use

## Costs

AWS Lambda pricing:
- Free tier: 1M requests/month + 400k GB-seconds compute
- After free tier: ~$0.20 per 1M requests + $0.0000166667 per GB-second
- API Gateway: ~$3.50 per million API calls

Typical usage costs are minimal for MCP workloads.
#!/usr/bin/env python3
"""
Generate Lambda test events for API Gateway integration testing.
"""

import json
import base64
import argparse
from typing import Dict, Any, Optional

def create_api_gateway_event(
    method: str = "POST",
    path: str = "/mcp",
    body: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
    query_params: Optional[Dict[str, str]] = None,
    stage: str = "prod"
) -> Dict[str, Any]:
    """Create an API Gateway proxy event for Lambda testing."""
    
    default_headers = {
        "Content-Type": "application/json",
        "User-Agent": "test-client/1.0"
    }
    
    if headers:
        default_headers.update(headers)
    
    # Base64 encode body if present
    is_base64_encoded = False
    if body:
        try:
            # Try to parse as JSON to validate
            json.loads(body)
            # For JSON, we don't need base64 encoding in this test
            encoded_body = body
        except json.JSONDecodeError:
            # If not valid JSON, base64 encode it
            encoded_body = base64.b64encode(body.encode()).decode()
            is_base64_encoded = True
    else:
        encoded_body = None
    
    event = {
        "resource": path,
        "path": path,
        "httpMethod": method,
        "headers": default_headers,
        "multiValueHeaders": {key: [value] for key, value in default_headers.items()},
        "queryStringParameters": query_params,
        "multiValueQueryStringParameters": {key: [value] for key, value in (query_params or {}).items()},
        "pathParameters": None,
        "stageVariables": None,
        "requestContext": {
            "resourceId": "test",
            "resourcePath": path,
            "httpMethod": method,
            "extendedRequestId": "test-request-id",
            "requestTime": "08/Jan/2025:12:00:00 +0000",
            "path": f"/{stage}{path}",
            "accountId": "123456789012",
            "protocol": "HTTP/1.1",
            "stage": stage,
            "domainPrefix": "test-api",
            "requestTimeEpoch": 1736337600000,
            "requestId": "test-request-id",
            "identity": {
                "cognitoIdentityPoolId": None,
                "accountId": None,
                "cognitoIdentityId": None,
                "caller": None,
                "sourceIp": "127.0.0.1",
                "principalOrgId": None,
                "accessKey": None,
                "cognitoAuthenticationType": None,
                "cognitoAuthenticationProvider": None,
                "userArn": None,
                "userAgent": "test-client/1.0",
                "user": None
            },
            "domainName": "test-api.execute-api.us-east-1.amazonaws.com",
            "apiId": "test-api-id"
        },
        "body": encoded_body,
        "isBase64Encoded": is_base64_encoded
    }
    
    return event

def create_mcp_tools_list_event() -> Dict[str, Any]:
    """Create a specific event for MCP tools/list request."""
    mcp_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {}
    }
    
    return create_api_gateway_event(
        method="POST",
        path="/mcp",
        body=json.dumps(mcp_request),
        headers={"Content-Type": "application/json"}
    )

def create_mcp_resources_list_event() -> Dict[str, Any]:
    """Create a specific event for MCP resources/list request."""
    mcp_request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "resources/list",
        "params": {}
    }
    
    return create_api_gateway_event(
        method="POST",
        path="/mcp",
        body=json.dumps(mcp_request),
        headers={"Content-Type": "application/json"}
    )

def create_health_check_event() -> Dict[str, Any]:
    """Create a health check event."""
    return create_api_gateway_event(
        method="GET",
        path="/mcp/health",
        headers={"Accept": "application/json"}
    )

def main():
    parser = argparse.ArgumentParser(description="Generate Lambda test events")
    parser.add_argument(
        "--event-type",
        choices=["tools-list", "resources-list", "health-check", "custom"],
        default="tools-list",
        help="Type of event to generate"
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output file (default: stdout)"
    )
    parser.add_argument(
        "--method",
        default="POST",
        help="HTTP method for custom events"
    )
    parser.add_argument(
        "--path",
        default="/mcp",
        help="Request path for custom events"
    )
    parser.add_argument(
        "--body",
        help="Request body for custom events"
    )
    
    args = parser.parse_args()
    
    # Generate the appropriate event
    event = None
    if args.event_type == "tools-list":
        event = create_mcp_tools_list_event()
    elif args.event_type == "resources-list":
        event = create_mcp_resources_list_event()
    elif args.event_type == "health-check":
        event = create_health_check_event()
    elif args.event_type == "custom":
        event = create_api_gateway_event(
            method=args.method,
            path=args.path,
            body=args.body
        )
    
    if event is None:
        raise ValueError(f"Unknown event type: {args.event_type}")
    
    # Output the event
    event_json = json.dumps(event, indent=2)
    
    if args.output:
        with open(args.output, 'w') as f:
            f.write(event_json)
        print(f"Event written to {args.output}")
    else:
        print(event_json)

if __name__ == "__main__":
    main()

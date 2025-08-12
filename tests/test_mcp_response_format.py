#!/usr/bin/env python3
"""
Unit test to validate MCP tool response format compliance.
This test ensures tool responses match the exact format expected by Claude.ai.
"""

import asyncio
import json

from quilt_mcp.handlers.lambda_handler import handle_mcp_request  # type: ignore


def test_tool_response_format():
    """Test that tool responses are properly formatted for MCP compliance."""

    # Test data - tools/call request
    request_data = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "auth_status",
            "arguments": {}
        }
    }

    # Execute the handler
    response = asyncio.run(handle_mcp_request(request_data))

    # Validate response structure
    assert "jsonrpc" in response, "Response missing jsonrpc field"
    assert response["jsonrpc"] == "2.0", "Invalid jsonrpc version"
    assert "id" in response, "Response missing id field"
    assert response["id"] == 1, "Response id mismatch"

    # Validate result structure
    assert "result" in response, "Response missing result field"
    result = response["result"]

    # Check for MCP-compliant content format
    assert "content" in result, "Result missing content field"
    assert isinstance(result["content"], list), "Content must be a list"
    assert len(result["content"]) > 0, "Content list cannot be empty"

    # Validate content item structure
    content_item = result["content"][0]
    assert "type" in content_item, "Content item missing type field"
    assert content_item["type"] == "text", "Content type must be 'text'"
    assert "text" in content_item, "Content item missing text field"

    # Validate text is valid JSON (for our tool responses)
    text_content = content_item["text"]
    assert isinstance(text_content, str), "Text content must be a string"

    try:
        parsed_content = json.loads(text_content)
        assert isinstance(parsed_content, dict), "Tool response should be valid JSON object"
    except json.JSONDecodeError:
        raise AssertionError("Tool response text is not valid JSON")

    # Validate no double-encoding or nested serialization
    assert '\\\\n' not in text_content, "Text contains double-escaped newlines"
    assert '\\"' not in text_content or text_content.count('\\"') < 5, "Text appears to be double-encoded JSON"

    print("✅ Tool response format validation passed")


def test_invalid_tool_error_format():
    """Test that invalid tool calls return proper error format."""

    request_data = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "nonexistent_tool",
            "arguments": {}
        }
    }

    response = asyncio.run(handle_mcp_request(request_data))

    # Should return an error response
    assert "error" in response, "Invalid tool call should return error"
    assert "result" not in response, "Error response should not have result"

    error = response["error"]
    assert "code" in error, "Error missing code field"
    assert "message" in error, "Error missing message field"
    assert isinstance(error["code"], int), "Error code must be integer"

    print("✅ Invalid tool error format validation passed")


def test_tools_list_format():
    """Test that tools/list response format is correct."""

    request_data = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/list",
        "params": {}
    }

    response = asyncio.run(handle_mcp_request(request_data))

    # Validate basic structure
    assert "result" in response
    result = response["result"]
    assert "tools" in result
    assert isinstance(result["tools"], list)

    # Validate each tool schema
    for tool in result["tools"]:
        assert "name" in tool, "Tool missing name field"
        assert "description" in tool, "Tool missing description field"
        assert "inputSchema" in tool, "Tool missing inputSchema field"

        # Validate schema structure
        schema = tool["inputSchema"]
        assert "type" in schema, "Tool schema missing type field"
        assert schema["type"] == "object", "Tool schema type must be 'object'"
        assert "properties" in schema, "Tool schema missing properties field"

    print("✅ Tools list format validation passed")


def test_initialize_format():
    """Test that initialize response format is correct."""

    request_data = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"roots": {"listChanged": True}, "sampling": {}},
            "clientInfo": {"name": "Claude", "version": "3.0"}
        }
    }

    response = asyncio.run(handle_mcp_request(request_data))

    # Validate structure
    assert "result" in response
    result = response["result"]

    # Check required fields
    assert "protocolVersion" in result
    assert "capabilities" in result
    assert "serverInfo" in result

    # Check capabilities structure
    capabilities = result["capabilities"]
    assert "tools" in capabilities
    assert "roots" in capabilities
    assert "sampling" in capabilities

    # Check server info
    server_info = result["serverInfo"]
    assert "name" in server_info
    assert "version" in server_info

    print("✅ Initialize format validation passed")


if __name__ == "__main__":
    print("🧪 Running MCP response format validation tests...")

    try:
        test_tools_list_format()
        test_initialize_format()
        test_tool_response_format()
        test_invalid_tool_error_format()

        print("\n🎉 All MCP response format tests passed!")
        print("Your MCP server responses are properly formatted for Claude.ai compatibility.")

    except Exception as e:
        print(f"\n❌ MCP response format test failed: {str(e)}")
        print("This indicates a compliance issue that could cause Claude.ai to disable your connector.")
        raise

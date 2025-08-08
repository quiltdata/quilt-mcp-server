import json
import asyncio
from typing import Dict, Any
import logging
import sys
import os

# Add the current directory to path to import our local quilt module
sys.path.insert(0, os.path.dirname(__file__))
from quilt import mcp  # type: ignore

# Configure logging
log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler for the Quilt MCP server.
    Processes HTTP requests and returns MCP-compatible responses.
    """
    print("=== LAMBDA HANDLER CALLED ===")
    print(f"Event keys: {list(event.keys())}")
    
    logger.info("Lambda handler called")
    logger.debug(f"Event: {json.dumps(event, default=str)}")
    
    try:
        # Parse the incoming request
        http_method = event.get('httpMethod', 'GET')
        path = event.get('path', '')
        query_params = event.get('queryStringParameters') or {}
        headers = event.get('headers', {})
        body = event.get('body', '')
        
        print(f"=== REQUEST: {http_method} {path} ===")
        logger.info(f"Received {http_method} request to {path}")
        
        # Handle CORS preflight
        if http_method == 'OPTIONS':
            print("=== HANDLING OPTIONS REQUEST ===")
            return {
                'statusCode': 200,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type,Authorization,X-Amz-Date',
                    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
                },
                'body': ''
            }
        
        # Parse request body if present
        request_data = {}
        if body:
            try:
                request_data = json.loads(body)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse request body: {body}")
        
        # Handle MCP requests
        if http_method == 'POST':
            # Handle MCP method calls
            response_data = asyncio.run(handle_mcp_request(request_data))
        else:
            # Handle GET requests (server info, capabilities, etc.)
            response_data = asyncio.run(handle_mcp_info_request(query_params))
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,Authorization,X-Amz-Date',
                'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
            },
            'body': json.dumps(response_data, default=str)
        }
        
    except Exception as e:
        print(f"=== HANDLER EXCEPTION: {str(e)} ===")
        logger.error(f"Handler error: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': f'Internal server error: {str(e)}'
            })
        }

async def handle_mcp_request(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle MCP method calls."""
    try:
        method = request_data.get('method', '')
        params = request_data.get('params', {})
        request_id = request_data.get('id', 1)
        
        logger.info(f"MCP method call: {method}")
        
        if method == 'tools/list':
            # Return available tools
            tools = []
            for tool_name, tool in mcp._tool_manager._tools.items():
                tools.append({
                    'name': tool.name,
                    'description': tool.description or '',
                    'inputSchema': tool.parameters or {}
                })
            
            return {
                'jsonrpc': '2.0',
                'id': request_id,
                'result': {'tools': tools}
            }
            
        elif method == 'tools/call':
            # Call a specific tool
            tool_name = params.get('name', '')
            tool_args = params.get('arguments', {})
            
            if tool_name in mcp._tool_manager._tools:
                try:
                    result = await mcp.call_tool(tool_name, tool_args)
                    # Handle the result properly - convert to JSON string
                    content_text = json.dumps(result, default=str) if result else "{}"
                    return {
                        'jsonrpc': '2.0',
                        'id': request_id,
                        'result': {
                            'content': [
                                {
                                    'type': 'text',
                                    'text': content_text
                                }
                            ]
                        }
                    }
                except Exception as e:
                    logger.error(f"Tool execution error: {str(e)}")
                    return {
                        'jsonrpc': '2.0',
                        'id': request_id,
                        'error': {
                            'code': -32603,
                            'message': f'Tool execution failed: {str(e)}'
                        }
                    }
            else:
                return {
                    'jsonrpc': '2.0',
                    'id': request_id,
                    'error': {
                        'code': -32601,
                        'message': f'Tool not found: {tool_name}'
                    }
                }
        
        elif method == 'initialize':
            # Handle MCP initialization
            return {
                'jsonrpc': '2.0',
                'id': request_id,
                'result': {
                    'protocolVersion': '2024-11-05',
                    'capabilities': {
                        'tools': {}
                    },
                    'serverInfo': {
                        'name': 'quilt-mcp-server',
                        'version': '1.0.0'
                    }
                }
            }
        
        else:
            return {
                'jsonrpc': '2.0',
                'id': request_id,
                'error': {
                    'code': -32601,
                    'message': f'Method not found: {method}'
                }
            }
            
    except Exception as e:
        logger.error(f"MCP request error: {str(e)}")
        return {
            'jsonrpc': '2.0',
            'id': request_data.get('id', 1),
            'error': {
                'code': -32603,
                'message': f'Internal error: {str(e)}'
            }
        }

async def handle_mcp_info_request(query_params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle GET requests for server information."""
    return {
        'name': 'quilt-mcp-server',
        'version': '1.0.0',
        'description': 'Claude-compatible MCP server for Quilt data access',
        'capabilities': {
            'tools': list(mcp._tool_manager._tools.keys())
        }
    }
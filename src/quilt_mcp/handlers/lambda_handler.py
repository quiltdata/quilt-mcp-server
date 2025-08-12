import json
import asyncio
from typing import Dict, Any
import logging
import sys
import os

from .. import mcp

# Force rebuild timestamp: 2025-08-10T00:58:00Z

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
    # Ensure working directory is writable in Lambda
    try:
        os.chdir('/tmp')
    except Exception:
        pass
    
    # Create directories that might be needed (safe if already present)
    os.makedirs('/tmp/.config', exist_ok=True)
    os.makedirs('/tmp/.cache', exist_ok=True)
    os.makedirs('/tmp/.local/share', exist_ok=True)
    os.makedirs('/tmp/quilt', exist_ok=True)
        
    # Create quilt3 directories
    os.makedirs('/tmp/quilt/cache', exist_ok=True)
    os.makedirs('/tmp/quilt/tempfiles', exist_ok=True)
    
    logger.debug("Lambda handler invoked")
    logger.debug(f"Event keys: {list(event.keys())}")
    logger.debug(f"Working directory: {os.getcwd()}")
    logger.debug(f"HOME: {os.environ.get('HOME')}")
    logger.debug(f"QUILT_CONFIG_DIR: {os.environ.get('QUILT_CONFIG_DIR')}")
    logger.debug(f"XDG_CONFIG_HOME: {os.environ.get('XDG_CONFIG_HOME')}")
    
    logger.info("Lambda handler called")
    logger.debug(f"Event: {json.dumps(event, default=str)}")
    
    try:
        # Parse the incoming request - handle both REST API and HTTP API v2 formats
        http_method = (event.get('httpMethod') or 
                       event.get('requestContext', {}).get('http', {}).get('method', 'GET'))
        path = event.get('path', event.get('rawPath', ''))
        query_params = event.get('queryStringParameters') or {}
        headers = event.get('headers', {})
        body = event.get('body', '')

        logger.info(f"Request: {http_method} {path}")
        
        # Handle CORS preflight
        if http_method == 'OPTIONS':
            logger.debug("Handling CORS preflight (OPTIONS)")
            return {
                'statusCode': 200,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type,Authorization,X-Amz-Date,X-Requested-With,Accept,Origin,Referer,User-Agent',
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
                'Access-Control-Allow-Headers': 'Content-Type,Authorization,X-Amz-Date,X-Requested-With,Accept,Origin,Referer,User-Agent',
                'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
            },
            'body': json.dumps(response_data, default=str)
        }
        
    except Exception as e:
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
                input_schema = tool.parameters or {}
                # Ensure schema has required type and properties fields
                if not isinstance(input_schema, dict) or 'type' not in input_schema:
                    input_schema = {
                        'type': 'object',
                        'properties': input_schema if isinstance(input_schema, dict) else {}
                    }
                tools.append({
                    'name': tool.name,
                    'description': tool.description or '',
                    'inputSchema': input_schema
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
                    # Extract clean text from the result
                    if isinstance(result, (list, tuple)) and len(result) >= 2:
                        # Get the actual result from the second element
                        actual_result = result[1].get('result', {}) if isinstance(result[1], dict) else result[1]
                        content_text = json.dumps(actual_result, indent=2)
                    else:
                        content_text = json.dumps(result, indent=2, default=str)
                    
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
                        'tools': {},
                        'roots': {'listChanged': True},
                        'sampling': {}
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
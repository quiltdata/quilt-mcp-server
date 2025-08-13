"""AWS Lambda event adapter for MCP processing.

This adapter converts AWS Lambda API Gateway events to MCP requests,
processes them with the core processor, and returns Lambda-compatible responses.
"""

import base64
import json
import logging
from typing import Any, Dict, Optional

from ..core import MCPProcessor, MCPError

logger = logging.getLogger(__name__)


class LambdaHandler:
    """AWS Lambda event handler for MCP requests."""
    
    def __init__(self):
        self.processor = MCPProcessor()
        self._setup_lambda_environment()
    
    def _setup_lambda_environment(self) -> None:
        """Setup Lambda-specific environment."""
        try:
            import os
            # Change to /tmp for writeable filesystem in Lambda
            os.chdir('/tmp')
            
            # Create necessary directories
            for directory in ['/tmp/.config', '/tmp/.cache', '/tmp/quilt']:
                os.makedirs(directory, exist_ok=True)
                
            logger.debug("Lambda environment setup completed")
        except Exception as e:
            logger.warning(f"Lambda environment setup failed: {e}")
    
    def handle_event(self, event: Dict[str, Any], context: Any) -> Dict[str, Any]:
        """Handle AWS Lambda event and return response.
        
        Args:
            event: AWS Lambda event from API Gateway
            context: AWS Lambda context (unused)
            
        Returns:
            AWS Lambda response for API Gateway
        """
        try:
            logger.info(f"Processing Lambda event: {event.get('httpMethod', 'UNKNOWN')} {event.get('path', '/')}")
            
            # Handle CORS preflight requests
            if event.get('httpMethod') == 'OPTIONS':
                return self._cors_response()
            
            # Handle health check
            if event.get('httpMethod') == 'GET':
                return self._health_check_response()
            
            # Extract MCP request from Lambda event
            mcp_request = self._extract_mcp_request(event)
            if not mcp_request:
                return self._error_response(400, "Invalid request body")
            
            # Process MCP request
            mcp_response = self.processor.process_request(mcp_request)
            
            # Convert to Lambda response
            return self._success_response(mcp_response)
            
        except Exception as e:
            logger.error(f"Lambda handler error: {e}", exc_info=True)
            return self._error_response(500, f"Internal server error: {str(e)}")
    
    def _extract_mcp_request(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract MCP request from Lambda event.
        
        Args:
            event: AWS Lambda event
            
        Returns:
            Parsed MCP request or None if invalid
        """
        try:
            body = event.get('body', '')
            
            # Handle base64 encoded body
            if event.get('isBase64Encoded', False):
                body = base64.b64decode(body).decode('utf-8')
            
            if not body:
                logger.warning("Empty request body")
                return None
            
            # Parse JSON
            mcp_request = json.loads(body)
            
            # Validate basic structure
            if not isinstance(mcp_request, dict):
                logger.warning("Request body is not a JSON object")
                return None
                
            return mcp_request
            
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON in request body: {e}")
            return None
        except Exception as e:
            logger.error(f"Error extracting MCP request: {e}")
            return None
    
    def _success_response(self, mcp_response: Dict[str, Any]) -> Dict[str, Any]:
        """Create a successful Lambda response.
        
        Args:
            mcp_response: MCP response data
            
        Returns:
            Lambda response
        """
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,Authorization,Mcp-Session-Id',
                'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
            },
            'body': json.dumps(mcp_response, separators=(',', ':'))
        }
    
    def _error_response(self, status_code: int, message: str) -> Dict[str, Any]:
        """Create an error Lambda response.
        
        Args:
            status_code: HTTP status code
            message: Error message
            
        Returns:
            Lambda error response
        """
        return {
            'statusCode': status_code,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,Authorization,Mcp-Session-Id',
                'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
            },
            'body': json.dumps({
                'error': {
                    'code': -32603,  # Internal error
                    'message': message
                }
            }, separators=(',', ':'))
        }
    
    def _cors_response(self) -> Dict[str, Any]:
        """Create a CORS preflight response.
        
        Returns:
            Lambda CORS response
        """
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,Authorization,Mcp-Session-Id',
                'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
                'Access-Control-Max-Age': '86400'  # 24 hours
            },
            'body': ''
        }
    
    def _health_check_response(self) -> Dict[str, Any]:
        """Create a health check response.
        
        Returns:
            Lambda health check response
        """
        health_data = {
            'status': 'ok',
            'server': 'quilt-mcp-server',
            'version': '0.1.0',
            'timestamp': self._get_timestamp()
        }
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(health_data, separators=(',', ':'))
        }
    
    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format.
        
        Returns:
            ISO formatted timestamp
        """
        from datetime import datetime
        return datetime.utcnow().isoformat() + 'Z'


# Global handler instance for Lambda
_handler_instance: Optional[LambdaHandler] = None


def get_lambda_handler() -> LambdaHandler:
    """Get or create Lambda handler instance.
    
    Returns:
        Lambda handler instance
    """
    global _handler_instance
    if _handler_instance is None:
        _handler_instance = LambdaHandler()
    return _handler_instance


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """AWS Lambda entry point.
    
    This is the function that AWS Lambda will call.
    
    Args:
        event: AWS Lambda event
        context: AWS Lambda context
        
    Returns:
        AWS Lambda response
    """
    handler = get_lambda_handler()
    return handler.handle_event(event, context)
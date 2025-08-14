"""Tests for server module."""

import os
import unittest
from unittest.mock import patch, MagicMock
import logging

from quilt_mcp.server import (
    is_lambda_environment,
    get_transport,
    main
)


class TestServer(unittest.TestCase):
    """Test server functions."""

    def test_is_lambda_environment_true(self):
        """Test Lambda environment detection when AWS_LAMBDA_FUNCTION_NAME is set."""
        with patch.dict(os.environ, {'AWS_LAMBDA_FUNCTION_NAME': 'test-function'}):
            self.assertTrue(is_lambda_environment())

    def test_is_lambda_environment_false(self):
        """Test Lambda environment detection when AWS_LAMBDA_FUNCTION_NAME is not set."""
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(is_lambda_environment())

    def test_get_transport_default(self):
        """Test default transport."""
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(get_transport(), "streamable-http")

    def test_get_transport_stdio(self):
        """Test stdio transport."""
        with patch.dict(os.environ, {'FASTMCP_TRANSPORT': 'stdio'}):
            self.assertEqual(get_transport(), "stdio")

    def test_get_transport_sse(self):
        """Test sse transport."""
        with patch.dict(os.environ, {'FASTMCP_TRANSPORT': 'sse'}):
            self.assertEqual(get_transport(), "sse")

    def test_get_transport_streamable_http(self):
        """Test streamable-http transport."""
        with patch.dict(os.environ, {'FASTMCP_TRANSPORT': 'streamable-http'}):
            self.assertEqual(get_transport(), "streamable-http")

    def test_get_transport_invalid_defaults_to_http(self):
        """Test invalid transport defaults to streamable-http."""
        with patch.dict(os.environ, {'FASTMCP_TRANSPORT': 'invalid'}):
            with patch('quilt_mcp.server.logger') as mock_logger:
                result = get_transport()
                self.assertEqual(result, "streamable-http")
                mock_logger.warning.assert_called_once()

    @patch('quilt_mcp.adapters.fastmcp_bridge.FastMCPBridge')
    def test_main_success(self, mock_bridge_class):
        """Test successful main execution."""
        mock_bridge = MagicMock()
        mock_bridge_class.return_value = mock_bridge
        
        with patch('quilt_mcp.server.get_transport', return_value='streamable-http'):
            main()
            
        mock_bridge_class.assert_called_once_with("quilt")
        mock_bridge.run.assert_called_once_with(transport='streamable-http')

    @patch('quilt_mcp.adapters.fastmcp_bridge.FastMCPBridge')
    def test_main_keyboard_interrupt(self, mock_bridge_class):
        """Test main handling KeyboardInterrupt."""
        mock_bridge = MagicMock()
        mock_bridge.run.side_effect = KeyboardInterrupt()
        mock_bridge_class.return_value = mock_bridge
        
        with patch('quilt_mcp.server.logger') as mock_logger:
            main()  # Should not raise
            mock_logger.info.assert_any_call("Server stopped by user")

    @patch('quilt_mcp.adapters.fastmcp_bridge.FastMCPBridge')
    def test_main_exception(self, mock_bridge_class):
        """Test main handling exceptions."""
        mock_bridge = MagicMock()
        test_exception = RuntimeError("Test error")
        mock_bridge.run.side_effect = test_exception
        mock_bridge_class.return_value = mock_bridge
        
        with patch('quilt_mcp.server.logger') as mock_logger:
            with self.assertRaises(RuntimeError):
                main()
            mock_logger.error.assert_called_once()

    def test_logging_configuration(self):
        """Test logging is configured properly."""
        # Check that logger exists
        from quilt_mcp import server
        self.assertTrue(hasattr(server, 'logger'))
        self.assertIsInstance(server.logger, logging.Logger)
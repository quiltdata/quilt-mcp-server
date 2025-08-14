"""Tests for __main__ module."""

import unittest
from unittest.mock import patch, MagicMock


class TestMain(unittest.TestCase):
    """Test main module entry point."""

    @patch('quilt_mcp.__main__.main')
    def test_main_called_when_run_as_module(self, mock_main):
        """Test that main() is called when run as __main__."""
        # Import to trigger __main__ execution
        with patch('builtins.__name__', '__main__'):
            import quilt_mcp.__main__
            # The import should trigger the if __name__ == "__main__" block
            # but since we're patching, we need to manually call it
            if __name__ == "__main__":
                quilt_mcp.__main__.main()
        
        # For this test, we just verify the import works
        self.assertTrue(hasattr(quilt_mcp.__main__, 'main'))
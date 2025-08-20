"""AWS integration utilities for Quilt MCP Server.

This package provides AWS-specific functionality including:
- Permission discovery and analysis
- IAM and bucket policy parsing
- Safe, non-destructive permission testing
- Smart bucket recommendations
"""

from .permission_discovery import AWSPermissionDiscovery, PermissionLevel
from .policy_analyzer import PolicyAnalyzer
from .safe_testing import SafePermissionTester

__all__ = [
    "AWSPermissionDiscovery",
    "PermissionLevel",
    "PolicyAnalyzer", 
    "SafePermissionTester",
]

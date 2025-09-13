#!/usr/bin/env python3
"""
Simple script to check coverage of optimization/integration.py without matplotlib conflicts
"""

import sys
import os
sys.path.insert(0, 'src')

import coverage
from unittest.mock import patch, Mock

# Start coverage
cov = coverage.Coverage()
cov.start()

# Mock problematic imports before they can cause issues
with patch.dict('sys.modules', {
    'matplotlib': Mock(),
    'matplotlib.pyplot': Mock(),
}):
    # Import the module under test
    from quilt_mcp.optimization.integration import (
        OptimizedMCPServer,
        create_optimized_server,
        optimization_tool,
        run_optimized_server,
        patch_utils_for_optimization,
    )
    
    # Exercise some basic functionality to increase coverage
    # This is just for coverage measurement, not proper testing
    try:
        with patch('quilt_mcp.optimization.integration.create_configured_server'), \
             patch('quilt_mcp.optimization.integration.TelemetryConfig'), \
             patch('quilt_mcp.optimization.integration.configure_telemetry'), \
             patch('quilt_mcp.optimization.integration.get_tool_interceptor'), \
             patch('quilt_mcp.optimization.integration.get_telemetry_collector'):
            
            # Test basic instantiation 
            server = OptimizedMCPServer(enable_optimization=False)
            
            # Test factory function
            server2 = create_optimized_server(enable_optimization=False)
            
            # Test stats when disabled
            stats = server.get_optimization_stats()
            
            print("Basic functionality tested")
    except Exception as e:
        print(f"Error testing basic functionality: {e}")

cov.stop()
cov.save()

# Generate report for just this module
print("\nCoverage Report for optimization/integration.py:")
cov.report(include='src/quilt_mcp/optimization/integration.py', show_missing=True)
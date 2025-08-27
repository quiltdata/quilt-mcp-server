#!/usr/bin/env python3
"""
Autonomous MCP Optimization Script for Cursor

This script can be run by Cursor to automatically optimize MCP server performance.
It provides comprehensive testing, analysis, and autonomous improvement capabilities.
"""

import asyncio
import sys
import logging
import json
from pathlib import Path
from datetime import datetime

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "app"))

try:
    from quilt_mcp.optimization.autonomous import CursorAutonomousRunner
    from quilt_mcp.optimization.scenarios import create_all_test_scenarios, create_optimization_challenge_scenarios
    from quilt_mcp.telemetry.collector import TelemetryConfig, configure_telemetry
except ImportError as e:
    print(f"Failed to import optimization modules: {e}")
    print("Make sure you're running from the project root directory")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('optimization.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


async def run_quick_optimization():
    """Run a quick optimization cycle for immediate feedback."""
    print("🚀 Starting Quick MCP Optimization...")
    
    runner = CursorAutonomousRunner()
    
    # Configure telemetry for optimization
    telemetry_config = TelemetryConfig(
        enabled=True,
        level="standard",
        local_only=True
    )
    configure_telemetry(telemetry_config)
    
    try:
        results = await runner.run_optimization_session()
        
        print("\n" + "="*60)
        print("🎯 MCP OPTIMIZATION RESULTS")
        print("="*60)
        
        summary = results['summary']
        print(f"📊 Optimizations Applied: {summary['optimizations_applied']}")
        
        improvements = summary.get('performance_improvement', {})
        if improvements:
            print("\n📈 Performance Improvements:")
            for metric, improvement in improvements.items():
                emoji = "✅" if improvement > 0 else "⚠️" if improvement < 0 else "➖"
                print(f"  {emoji} {metric}: {improvement:+.1%}")
        
        recommendations = summary.get('recommendations', [])
        if recommendations:
            print("\n💡 Recommendations:")
            for i, rec in enumerate(recommendations, 1):
                print(f"  {i}. {rec}")
        
        print(f"\n📄 Detailed report saved to: {results['report_file']}")
        
        # Show baseline vs current metrics
        baseline = results.get('baseline_metrics', {})
        if baseline:
            print(f"\n📋 Baseline Metrics:")
            print(f"  Success Rate: {baseline.get('success_rate', 0):.1%}")
            print(f"  Avg Execution Time: {baseline.get('avg_execution_time', 0):.2f}s")
            print(f"  Avg Call Count: {baseline.get('avg_call_count', 0):.1f}")
            print(f"  Efficiency Score: {baseline.get('avg_efficiency_score', 0):.3f}")
        
        print("="*60)
        
        return 0
        
    except Exception as e:
        print(f"❌ Optimization failed: {e}")
        logger.error(f"Optimization failed: {e}", exc_info=True)
        return 1


async def run_comprehensive_analysis():
    """Run comprehensive optimization analysis with detailed reporting."""
    print("🔍 Starting Comprehensive MCP Analysis...")
    
    from quilt_mcp.optimization.testing import OptimizationTester
    from quilt_mcp.optimization.interceptor import get_tool_interceptor
    
    # Create tester and add scenarios
    tester = OptimizationTester()
    
    # Add all test scenarios
    all_scenarios = create_all_test_scenarios()
    challenge_scenarios = create_optimization_challenge_scenarios()
    
    for scenario in all_scenarios + challenge_scenarios:
        tester.add_scenario(scenario)
    
    print(f"📝 Loaded {len(all_scenarios + challenge_scenarios)} test scenarios")
    
    try:
        # Run baseline tests
        print("🏁 Running baseline tests...")
        baseline_results = await tester.run_baseline_tests()
        
        # Run optimization tests
        print("⚡ Running optimization tests...")
        optimization_results = await tester.run_optimization_tests()
        
        # Generate comprehensive report
        report = tester.generate_test_report()
        
        # Save detailed results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = f"mcp_analysis_{timestamp}.json"
        
        full_report = {
            'timestamp': datetime.now().isoformat(),
            'baseline_results': {name: {
                'success': result.success,
                'total_time': result.total_time,
                'total_calls': result.total_calls,
                'efficiency_score': result.efficiency_score,
                'optimization_suggestions': result.optimization_suggestions
            } for name, result in baseline_results.items()},
            'optimization_results': optimization_results,
            'test_report': report,
            'interceptor_report': get_tool_interceptor().get_optimization_report()
        }
        
        with open(results_file, 'w') as f:
            json.dump(full_report, f, indent=2, default=str)
        
        # Display summary
        print("\n" + "="*70)
        print("📊 COMPREHENSIVE MCP ANALYSIS RESULTS")
        print("="*70)
        
        print(f"🧪 Total Scenarios Tested: {report['total_scenarios']}")
        
        performance_summary = report.get('performance_summary', {})
        if performance_summary:
            print(f"✅ Success Rate: {performance_summary.get('success_rate', 0):.1%}")
            print(f"⚡ Avg Efficiency: {performance_summary.get('avg_efficiency_score', 0):.3f}")
            print(f"⏱️  Avg Execution Time: {performance_summary.get('avg_execution_time', 0):.2f}s")
        
        # Show improvements
        improvements = optimization_results.get('improvements', {})
        if improvements:
            print(f"\n📈 Scenario Improvements:")
            for scenario, improvement_data in improvements.items():
                improvement = improvement_data.get('improvement', 0)
                emoji = "🚀" if improvement > 0.1 else "✅" if improvement > 0 else "⚠️"
                print(f"  {emoji} {scenario}: {improvement:+.1%}")
        
        # Show recommendations
        recommendations = report.get('recommendations', [])
        if recommendations:
            print(f"\n💡 Top Recommendations:")
            for i, rec in enumerate(recommendations[:5], 1):
                print(f"  {i}. {rec}")
        
        print(f"\n📄 Detailed analysis saved to: {results_file}")
        print("="*70)
        
        return 0
        
    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        logger.error(f"Analysis failed: {e}", exc_info=True)
        return 1


def print_usage():
    """Print usage information."""
    print("""
🔧 MCP Optimization Tool

Usage:
  python optimize_mcp.py [command]

Commands:
  quick       Run quick optimization (default)
  analyze     Run comprehensive analysis
  help        Show this help message

Examples:
  python optimize_mcp.py           # Quick optimization
  python optimize_mcp.py quick     # Same as above
  python optimize_mcp.py analyze   # Comprehensive analysis
  python optimize_mcp.py help      # Show help

The tool will:
1. 🧪 Test MCP server performance with real scenarios
2. 📊 Identify optimization opportunities
3. ⚡ Apply autonomous improvements
4. 📈 Measure performance gains
5. 💡 Provide actionable recommendations

Results are saved to JSON files for detailed analysis.
""")


async def main():
    """Main function."""
    command = sys.argv[1] if len(sys.argv) > 1 else "quick"
    
    if command == "help":
        print_usage()
        return 0
    elif command == "quick":
        return await run_quick_optimization()
    elif command == "analyze":
        return await run_comprehensive_analysis()
    else:
        print(f"❌ Unknown command: {command}")
        print_usage()
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⏹️  Optimization interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)

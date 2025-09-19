#!/usr/bin/env python3
"""
Test script for the automatic visualization generation system.

This script demonstrates how to use the VisualizationEngine to automatically
generate visualizations for Quilt packages.
"""

import os
import sys
import tempfile
import json
from pathlib import Path

# Add the current directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from quilt_mcp.visualization import VisualizationEngine


def create_sample_package():
    """Create a sample package for testing."""
    # Create a temporary directory for the sample package
    temp_dir = tempfile.mkdtemp(prefix="quilt_viz_test_")
    package_path = Path(temp_dir)

    print(f"Creating sample package in: {package_path}")

    # Create sample CSV data
    csv_content = """category,value,date
A,100,2023-01-01
B,150,2023-01-02
C,200,2023-01-03
D,175,2023-01-04
E,225,2023-01-05"""

    csv_file = package_path / "sample_data.csv"
    with open(csv_file, "w") as f:
        f.write(csv_content)

    # Create sample JSON data
    json_content = {
        "metrics": {
            "accuracy": 0.95,
            "precision": 0.92,
            "recall": 0.88,
            "f1_score": 0.90,
        },
        "parameters": {"learning_rate": 0.001, "batch_size": 32, "epochs": 100},
    }

    json_file = package_path / "config.json"
    with open(json_file, "w") as f:
        json.dump(json_content, f, indent=2)

    # Create sample genomic data (FASTA format)
    fasta_content = """>sample_1|chr1|1000|2000
ATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCG
>sample_2|chr1|1500|2500
GCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTA"""

    fasta_file = package_path / "genomic_data.fasta"
    with open(fasta_file, "w") as f:
        f.write(fasta_content)

    # Create README
    readme_content = """# Sample Package

This is a sample package for testing the automatic visualization generation system.

## Contents
- sample_data.csv: Sample numerical data
- config.json: Configuration parameters
- genomic_data.fasta: Sample genomic sequences

## Usage
This package demonstrates various data types that can be automatically visualized.
"""

    readme_file = package_path / "README.md"
    with open(readme_file, "w") as f:
        f.write(readme_content)

    print("Sample package created with:")
    print(f"  - {csv_file.name}")
    print(f"  - {json_file.name}")
    print(f"  - {fasta_file.name}")
    print(f"  - {readme_file.name}")

    return package_path


def test_visualization_engine():
    """Test the visualization engine with the sample package."""
    print("\n" + "=" * 60)
    print("Testing Automatic Visualization Generation")
    print("=" * 60)

    try:
        # Create sample package
        package_path = create_sample_package()

        # Initialize visualization engine
        print("\nInitializing visualization engine...")
        engine = VisualizationEngine()

        # Analyze package contents
        print("\nAnalyzing package contents...")
        analysis = engine.analyze_package_contents(str(package_path))

        print("Package analysis complete:")
        print(f"  - File types: {list(analysis.file_types.keys())}")
        print(f"  - Data files: {len(analysis.data_files)}")
        print(f"  - Genomic files: {len(analysis.genomic_files)}")
        print(f"  - Suggested visualizations: {analysis.suggested_visualizations}")

        # Generate visualizations
        print("\nGenerating visualizations...")
        visualizations = engine.generate_visualizations(analysis)

        print(f"Generated {len(visualizations)} visualizations:")
        for viz in visualizations:
            print(f"  - {viz.type}: {viz.title}")

        # Create quilt_summarize.json
        print("\nCreating quilt_summarize.json...")
        quilt_summary = engine.create_quilt_summary(visualizations)

        # Save quilt_summarize.json
        summary_file = package_path / "quilt_summarize.json"
        with open(summary_file, "w") as f:
            f.write(quilt_summary)

        print(f"quilt_summarize.json created: {summary_file}")

        # Display the summary
        print("\nquilt_summarize.json contents:")
        print(json.dumps(json.loads(quilt_summary), indent=2))

        # Complete workflow test
        print("\nTesting complete workflow...")
        result = engine.generate_package_visualizations(str(package_path))

        if result["success"]:
            print("✅ Visualization generation successful!")
            print(f"  - Package: {result['package_path']}")
            print(f"  - Visualizations: {result['visualization_count']}")
            print(f"  - Summary file: {summary_file}")
        else:
            print("❌ Visualization generation failed:")
            print(f"  - Error: {result.get('error', 'Unknown error')}")

        # Clean up
        print("\nCleaning up temporary files...")
        import shutil

        shutil.rmtree(package_path)
        print("Cleanup complete.")

        return result["success"]

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Main function to run the visualization test."""
    print("🚀 Quilt Package Automatic Visualization Generation Test")
    print("=" * 60)

    success = test_visualization_engine()

    if success:
        print("\n🎉 All tests passed! The visualization system is working correctly.")
        print("\nNext steps:")
        print("1. Install the required dependencies (pandas, numpy, matplotlib)")
        print("2. Use the VisualizationEngine in your Quilt MCP tools")
        print("3. Customize visualization types and configurations")
    else:
        print("\n💥 Some tests failed. Check the error messages above.")
        print("\nTroubleshooting:")
        print("1. Ensure all required modules are created")
        print("2. Check for syntax errors in the code")
        print("3. Verify the module structure is correct")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
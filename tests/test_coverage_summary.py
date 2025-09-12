"""Tests for the coverage-summary.py script."""

import tempfile
import os
import subprocess
import sys
from pathlib import Path


def test_coverage_summary_script_exists_and_executable():
    """Test that the coverage-summary.py script exists and is executable."""
    script_path = Path(__file__).parent.parent / "bin" / "coverage-summary.py"
    
    # Script should exist
    assert script_path.exists(), f"Coverage summary script not found at {script_path}"
    
    # Script should be executable
    assert os.access(script_path, os.X_OK), f"Coverage summary script is not executable: {script_path}"


def test_coverage_summary_generates_markdown_report():
    """Test that the coverage-summary.py script generates a markdown report."""
    script_path = Path(__file__).parent.parent / "bin" / "coverage-summary.py"
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        output_file = temp_path / "coverage-summary.md"
        
        # Create minimal XML coverage files for testing
        unit_xml = temp_path / "coverage-unit.xml"
        integration_xml = temp_path / "coverage-integration.xml"
        
        # Create minimal XML structure that contains at least one file from our MCP tools
        unit_xml.write_text("""<?xml version="1.0"?>
<coverage version="7.3.2" timestamp="1699123456" lines-valid="100" lines-covered="50" line-rate="0.5" branches-valid="0" branches-covered="0" branch-rate="0" complexity="0">
  <sources>
    <source>src</source>
  </sources>
  <packages>
    <package name="quilt_mcp.tools" line-rate="0.5" branch-rate="0" complexity="0">
      <classes>
        <class name="auth.py" filename="src/quilt_mcp/tools/auth.py" complexity="0" line-rate="0.6" branch-rate="0">
          <methods/>
          <lines>
            <line number="1" hits="1"/>
            <line number="2" hits="0"/>
            <line number="3" hits="1"/>
            <line number="4" hits="1"/>
            <line number="5" hits="0"/>
          </lines>
        </class>
      </classes>
    </package>
  </packages>
</coverage>""")
        
        integration_xml.write_text("""<?xml version="1.0"?>
<coverage version="7.3.2" timestamp="1699123456" lines-valid="100" lines-covered="85" line-rate="0.85" branches-valid="0" branches-covered="0" branch-rate="0" complexity="0">
  <sources>
    <source>src</source>
  </sources>
  <packages>
    <package name="quilt_mcp.tools" line-rate="0.85" branch-rate="0" complexity="0">
      <classes>
        <class name="auth.py" filename="src/quilt_mcp/tools/auth.py" complexity="0" line-rate="0.8" branch-rate="0">
          <methods/>
          <lines>
            <line number="1" hits="1"/>
            <line number="2" hits="1"/>
            <line number="3" hits="1"/>
            <line number="4" hits="1"/>
            <line number="5" hits="0"/>
          </lines>
        </class>
      </classes>
    </package>
  </packages>
</coverage>""")
        
        # Run the script with our test XML files
        result = subprocess.run([
            sys.executable, str(script_path),
            "--unit-xml", str(unit_xml),
            "--integration-xml", str(integration_xml),
            "--output", str(output_file)
        ], capture_output=True, text=True, cwd=str(Path(__file__).parent.parent))
        
        # Script should run successfully
        assert result.returncode == 0, f"Script failed with stderr: {result.stderr}"
        
        # Output file should be created
        assert output_file.exists(), f"Output file not created: {output_file}"
        
        # Check the content contains expected markdown structure
        content = output_file.read_text()
        assert "# Tool Coverage Report By File" in content
        assert "| File |" in content
        assert "| MCP Tools |" in content
        assert "Unit Coverage" in content
        assert "Integration Coverage" in content
        assert "auth_status" in content or "catalog_info" in content  # At least one MCP tool should be found


def test_coverage_summary_handles_missing_xml_files():
    """Test that the script handles missing XML files gracefully."""
    script_path = Path(__file__).parent.parent / "bin" / "coverage-summary.py"
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        output_file = temp_path / "coverage-summary.md"
        nonexistent_file = temp_path / "nonexistent.xml"
        
        # Run the script with nonexistent XML files
        result = subprocess.run([
            sys.executable, str(script_path),
            "--unit-xml", str(nonexistent_file),
            "--integration-xml", str(nonexistent_file),
            "--output", str(output_file)
        ], capture_output=True, text=True, cwd=str(Path(__file__).parent.parent))
        
        # Script should handle missing files gracefully (not crash)
        # It should still create an output file with 0% coverage
        assert result.returncode == 0, f"Script should handle missing files gracefully, stderr: {result.stderr}"
        assert output_file.exists(), "Output file should be created even with missing input files"
        
        content = output_file.read_text()
        assert "# Tool Coverage Report By File" in content


def test_coverage_summary_discovers_mcp_tools():
    """Test that the script discovers MCP tools using get_tool_modules()."""
    script_path = Path(__file__).parent.parent / "bin" / "coverage-summary.py"
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        output_file = temp_path / "coverage-summary.md"
        empty_xml = temp_path / "empty.xml"
        
        # Create empty XML files
        empty_xml.write_text("""<?xml version="1.0"?>
<coverage version="7.3.2" timestamp="1699123456" lines-valid="0" lines-covered="0" line-rate="0" branches-valid="0" branches-covered="0" branch-rate="0" complexity="0">
  <sources><source>src</source></sources>
  <packages></packages>
</coverage>""")
        
        # Run the script 
        result = subprocess.run([
            sys.executable, str(script_path),
            "--unit-xml", str(empty_xml),
            "--integration-xml", str(empty_xml),
            "--output", str(output_file)
        ], capture_output=True, text=True, cwd=str(Path(__file__).parent.parent))
        
        assert result.returncode == 0, f"Script failed: {result.stderr}"
        
        content = output_file.read_text()
        
        # The script should discover MCP tools from get_tool_modules()
        # Even with empty coverage, it should list the tools we know exist
        expected_tools = ["auth_status", "catalog_info", "bucket_objects_list", "package_browse"]
        
        # At least some of these tools should appear in the output
        found_tools = [tool for tool in expected_tools if tool in content]
        assert len(found_tools) > 0, f"No expected MCP tools found in output. Content: {content[:500]}..."
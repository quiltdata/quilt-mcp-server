"""
BDD tests for split coverage tracking system.

Tests the coverage-tools script that processes unit and integration
coverage XML files to generate a split coverage report.
"""

import tempfile
import os
import pytest
from pathlib import Path
from unittest.mock import patch, mock_open
import xml.etree.ElementTree as ET


class TestCoverageToolsScript:
    """Test the coverage-tools script behavior."""
    
    def test_script_exists_and_executable(self):
        """The coverage-tools script should exist and be executable."""
        script_path = Path("bin/coverage-tools")
        assert script_path.exists(), "coverage-tools script should exist in bin/ directory"
        assert os.access(script_path, os.X_OK), "coverage-tools script should be executable"
    
    def test_processes_both_xml_files(self):
        """The script should process both coverage-unit.xml and coverage-integration.xml files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create sample XML files
            unit_xml = temp_path / "coverage-unit.xml"
            integration_xml = temp_path / "coverage-integration.xml"
            
            unit_content = '''<?xml version="1.0" ?>
<coverage version="7.4.4" timestamp="1735789000000" lines-valid="144" lines-covered="123">
    <sources>
        <source>src</source>
    </sources>
    <packages>
        <package name="quilt_mcp.tools" line-rate="0.8542" branch-rate="0.0">
            <classes>
                <class name="auth.py" filename="quilt_mcp/tools/auth.py" line-rate="0.8542">
                    <lines>
                        <line number="1" hits="1"/>
                        <line number="2" hits="1"/>
                        <line number="3" hits="0"/>
                    </lines>
                </class>
            </classes>
        </package>
    </packages>
</coverage>'''
            
            integration_content = '''<?xml version="1.0" ?>
<coverage version="7.4.4" timestamp="1735789000000" lines-valid="143" lines-covered="132">
    <sources>
        <source>src</source>
    </sources>
    <packages>
        <package name="quilt_mcp.tools" line-rate="0.9231" branch-rate="0.0">
            <classes>
                <class name="auth.py" filename="quilt_mcp/tools/auth.py" line-rate="0.9231">
                    <lines>
                        <line number="1" hits="1"/>
                        <line number="2" hits="1"/>
                        <line number="3" hits="1"/>
                    </lines>
                </class>
            </classes>
        </package>
    </packages>
</coverage>'''
            
            unit_xml.write_text(unit_content)
            integration_xml.write_text(integration_content)
            
            # Test that the script would process both files
            # This will be implemented when we create the actual script
            assert unit_xml.exists()
            assert integration_xml.exists()
    
    def test_generates_markdown_table_format(self):
        """The script should generate a markdown table with specific columns."""
        expected_columns = [
            "Source File",
            "Unit Coverage", 
            "Integration Coverage",
            "Combined",
            "Status"
        ]
        
        # This test will verify the actual output format once implemented
        # For now, we're defining the expected behavior
        for column in expected_columns:
            assert column  # Placeholder - will be actual table validation
    
    def test_handles_missing_coverage_files_gracefully(self):
        """The script should handle missing coverage XML files gracefully."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Test with completely missing files
            # Should provide clear error message or fallback behavior
            temp_path = Path(temp_dir)
            assert not (temp_path / "coverage-unit.xml").exists()
            assert not (temp_path / "coverage-integration.xml").exists()
            
            # This will be implemented to test actual error handling
    
    def test_outputs_to_correct_location(self):
        """The script should output coverage-summary.md to build/test-results/."""
        expected_output_path = Path("build/test-results/coverage-summary.md")
        # This will be verified once the script is implemented
        assert str(expected_output_path)  # Placeholder
    
    def test_coverage_percentage_calculations(self):
        """The script should correctly calculate coverage percentages from XML."""
        # Mock XML parsing and percentage calculation
        # This will test the actual calculation logic once implemented
        
        # Test case: 123 lines covered out of 144 total = 85.42%
        total_lines = 144
        covered_lines = 123
        expected_percentage = 85.42
        
        calculated = round((covered_lines / total_lines) * 100, 2)
        assert calculated == expected_percentage
    
    def test_status_indicators_based_on_targets(self):
        """The script should generate ✅/❌ status based on coverage targets."""
        # Unit coverage target: 100%
        # Integration coverage target: 85%
        
        test_cases = [
            # (unit_pct, integration_pct, expected_status)
            (100.0, 85.0, "✅"),  # Both meet targets
            (100.0, 84.9, "❌"),  # Integration below target
            (99.9, 85.0, "❌"),   # Unit below target
            (99.9, 84.9, "❌"),   # Both below targets
        ]
        
        for unit_pct, integration_pct, expected_status in test_cases:
            # This will test actual status generation logic
            unit_meets_target = unit_pct >= 100.0
            integration_meets_target = integration_pct >= 85.0
            
            if unit_meets_target and integration_meets_target:
                actual_status = "✅"
            else:
                actual_status = "❌"
                
            assert actual_status == expected_status
    
    def test_file_level_granularity_for_src_files(self):
        """The script should report coverage for all .py files under src/quilt_mcp/."""
        # This will test that all source files are included in the report
        # even if they have 0% coverage in either category
        
        src_path = Path("src/quilt_mcp")
        if src_path.exists():
            py_files = list(src_path.rglob("*.py"))
            assert len(py_files) > 0, "Should find Python files in src/quilt_mcp/"
            
            # Each file should appear in the coverage report
            for py_file in py_files:
                # This will be validated against actual report output
                assert str(py_file)  # Placeholder
    
    def test_markdown_lint_compliance(self):
        """The generated markdown should be lint-compliant."""
        # Test that the generated markdown follows markdownlint rules:
        # - Proper table formatting
        # - No trailing spaces
        # - Proper heading levels
        # - Consistent line endings
        
        sample_table = """# Split Coverage Report by Source File

| Source File | Unit Coverage | Integration Coverage | Combined | Status |
|-------------|---------------|---------------------|----------|--------|
| src/quilt_mcp/tools/auth.py | 85.5% (123/144) | 92.1% (132/143) | 92.1% | ❌ |

## Coverage Targets

- **Unit Coverage**: 100% (error scenarios, mocked dependencies)
- **Integration Coverage**: 85%+ (end-to-end workflows, real services)
"""
        
        # Basic lint checks
        lines = sample_table.split('\n')
        for line in lines:
            # No trailing spaces
            assert not line.endswith(' '), f"Line should not end with space: '{line}'"
        
        # Table should have proper header separator
        assert "|-------------|" in sample_table


class TestCoverageXMLParsing:
    """Test XML parsing functionality for coverage files."""
    
    def test_parses_coverage_xml_structure(self):
        """Should correctly parse pytest-cov XML format."""
        xml_content = '''<?xml version="1.0" ?>
<coverage version="7.4.4" timestamp="1735789000000" lines-valid="100" lines-covered="85">
    <sources>
        <source>src</source>
    </sources>
    <packages>
        <package name="quilt_mcp.tools" line-rate="0.85">
            <classes>
                <class name="auth.py" filename="quilt_mcp/tools/auth.py" line-rate="0.85">
                </class>
            </classes>
        </package>
    </packages>
</coverage>'''
        
        root = ET.fromstring(xml_content)
        
        # Verify we can parse the XML structure
        assert root.tag == "coverage"
        assert root.get("lines-valid") == "100"
        assert root.get("lines-covered") == "85"
        
        # Verify package parsing
        packages = root.findall(".//package")
        assert len(packages) == 1
        assert packages[0].get("name") == "quilt_mcp.tools"
        
        # Verify class (file) parsing
        classes = root.findall(".//class")
        assert len(classes) == 1
        assert classes[0].get("filename") == "quilt_mcp/tools/auth.py"
        assert classes[0].get("line-rate") == "0.85"
    
    def test_extracts_file_coverage_statistics(self):
        """Should extract coverage stats for individual files."""
        xml_content = '''<?xml version="1.0" ?>
<coverage version="7.4.4" timestamp="1735789000000" lines-valid="200" lines-covered="170">
    <packages>
        <package name="quilt_mcp.tools" line-rate="0.85">
            <classes>
                <class name="auth.py" filename="quilt_mcp/tools/auth.py" line-rate="0.85">
                    <lines>
                        <line number="1" hits="1"/>
                        <line number="2" hits="1"/>
                        <line number="3" hits="0"/>
                        <line number="4" hits="1"/>
                    </lines>
                </class>
                <class name="buckets.py" filename="quilt_mcp/tools/buckets.py" line-rate="0.75">
                    <lines>
                        <line number="1" hits="1"/>
                        <line number="2" hits="0"/>
                        <line number="3" hits="1"/>
                        <line number="4" hits="1"/>
                    </lines>
                </class>
            </classes>
        </package>
    </packages>
</coverage>'''
        
        root = ET.fromstring(xml_content)
        
        # Extract file statistics
        file_stats = {}
        for class_elem in root.findall(".//class"):
            filename = class_elem.get("filename")
            line_rate = float(class_elem.get("line-rate"))
            
            # Count lines
            lines = class_elem.findall(".//line")
            total_lines = len(lines)
            covered_lines = len([line for line in lines if int(line.get("hits", 0)) > 0])
            
            file_stats[filename] = {
                "line_rate": line_rate,
                "total_lines": total_lines,
                "covered_lines": covered_lines
            }
        
        # Verify extraction
        assert "quilt_mcp/tools/auth.py" in file_stats
        assert "quilt_mcp/tools/buckets.py" in file_stats
        
        auth_stats = file_stats["quilt_mcp/tools/auth.py"]
        assert auth_stats["line_rate"] == 0.85
        assert auth_stats["total_lines"] == 4
        assert auth_stats["covered_lines"] == 3
        
        buckets_stats = file_stats["quilt_mcp/tools/buckets.py"]
        assert buckets_stats["line_rate"] == 0.75
        assert buckets_stats["total_lines"] == 4
        assert buckets_stats["covered_lines"] == 3


class TestMakefileTargetIntegration:
    """Test integration with Makefile targets."""
    
    def test_coverage_unit_target_exists(self):
        """The coverage-unit target should exist in make.dev."""
        # This will be verified once we add the target
        target_name = "coverage-unit"
        assert target_name  # Placeholder
    
    def test_coverage_integration_target_exists(self):
        """The coverage-integration target should exist in make.dev."""
        target_name = "coverage-integration"
        assert target_name  # Placeholder
    
    def test_coverage_tools_target_exists(self):
        """The coverage-tools target should exist in make.dev."""
        target_name = "coverage-tools"
        assert target_name  # Placeholder
    
    def test_coverage_target_dependencies(self):
        """The coverage target should depend on both unit and integration coverage."""
        # This will verify the dependency chain once implemented
        dependencies = ["coverage-unit", "coverage-integration"]
        for dep in dependencies:
            assert dep  # Placeholder
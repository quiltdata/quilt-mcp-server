#!/usr/bin/env python3
"""
UAT Validation Script
Validates that all UAT components are properly set up and functional
"""

import json
import sys
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional


class UATValidator:
    """Validates UAT setup and functionality."""
    
    def __init__(self, project_root: Optional[Path] = None):
        if project_root is None:
            # Find project root by looking for Makefile
            current = Path(__file__).parent.parent.parent
            while current != current.parent:
                if (current / "Makefile").exists():
                    project_root = current
                    break
                current = current.parent
        
        self.project_root = project_root
        self.uat_root = project_root / "uat"
        self.results = []
    
    def log_result(self, test_name: str, success: bool, message: str = "") -> None:
        """Log a test result."""
        status = "✅" if success else "❌"
        self.results.append({
            "test": test_name,
            "success": success,
            "message": message
        })
        print(f"{status} {test_name}: {message}")
    
    def validate_directory_structure(self) -> bool:
        """Validate UAT directory structure is complete."""
        print("Validating UAT Directory Structure...")
        
        required_dirs = [
            "uat",
            "uat/scripts",
            "uat/logs", 
            "uat/scenarios"
        ]
        
        required_files = [
            "uat/README.md",
            "uat/scripts/client-test.sh",
            "uat/scripts/log-analyzer.py",
            "uat/logs/patterns.json",
            "uat/logs/analysis.md",
            "uat/scenarios/claude-desktop.md",
            "uat/scenarios/vscode.md",
            "uat/scenarios/cursor.md"
        ]
        
        all_valid = True
        
        # Check directories
        for dir_path in required_dirs:
            full_path = self.project_root / dir_path
            if full_path.exists() and full_path.is_dir():
                self.log_result(f"Directory {dir_path}", True, "exists")
            else:
                self.log_result(f"Directory {dir_path}", False, "missing")
                all_valid = False
        
        # Check files
        for file_path in required_files:
            full_path = self.project_root / file_path
            if full_path.exists() and full_path.is_file():
                self.log_result(f"File {file_path}", True, "exists")
            else:
                self.log_result(f"File {file_path}", False, "missing")
                all_valid = False
        
        return all_valid
    
    def validate_scripts_executable(self) -> bool:
        """Validate scripts are executable."""
        print("\nValidating Script Permissions...")
        
        scripts = [
            "uat/scripts/client-test.sh",
            "uat/scripts/log-analyzer.py"
        ]
        
        all_valid = True
        
        for script in scripts:
            script_path = self.project_root / script
            if script_path.exists():
                # Check if executable
                if script_path.stat().st_mode & 0o111:
                    self.log_result(f"Script {script}", True, "executable")
                else:
                    self.log_result(f"Script {script}", False, "not executable")
                    all_valid = False
            else:
                self.log_result(f"Script {script}", False, "missing")
                all_valid = False
        
        return all_valid
    
    def validate_patterns_json(self) -> bool:
        """Validate patterns.json is valid JSON with required structure."""
        print("\nValidating Log Patterns Configuration...")
        
        patterns_file = self.project_root / "uat/logs/patterns.json"
        
        try:
            with open(patterns_file, 'r') as f:
                patterns = json.load(f)
            
            # Check required structure
            if "clients" not in patterns:
                self.log_result("patterns.json structure", False, "missing 'clients' section")
                return False
            
            required_clients = ["claude_desktop", "vscode", "cursor"]
            
            for client in required_clients:
                if client not in patterns["clients"]:
                    self.log_result(f"patterns.json {client}", False, "missing client definition")
                    return False
                
                client_config = patterns["clients"][client]
                
                # Check required fields
                required_fields = ["success_patterns", "failure_patterns"]
                for field in required_fields:
                    if field not in client_config:
                        self.log_result(f"patterns.json {client}.{field}", False, "missing field")
                        return False
                
                self.log_result(f"patterns.json {client}", True, "valid configuration")
            
            self.log_result("patterns.json", True, "valid structure")
            return True
            
        except json.JSONDecodeError as e:
            self.log_result("patterns.json", False, f"invalid JSON: {e}")
            return False
        except FileNotFoundError:
            self.log_result("patterns.json", False, "file not found")
            return False
    
    def validate_client_test_script(self) -> bool:
        """Validate client-test.sh script functionality."""
        print("\nValidating Client Test Script...")
        
        script_path = self.project_root / "uat/scripts/client-test.sh"
        
        if not script_path.exists():
            self.log_result("client-test.sh", False, "script missing")
            return False
        
        try:
            # Test script help/usage
            result = subprocess.run(
                [str(script_path)],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Script should exit with error code and show usage when no args
            if result.returncode != 0 and "Usage:" in result.stdout:
                self.log_result("client-test.sh usage", True, "shows usage when no args")
            else:
                self.log_result("client-test.sh usage", False, "doesn't show proper usage")
                return False
            
            # Test with invalid client
            result = subprocess.run(
                [str(script_path), "invalid_client"],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=self.project_root
            )
            
            if result.returncode != 0:
                self.log_result("client-test.sh validation", True, "rejects invalid clients")
            else:
                self.log_result("client-test.sh validation", False, "accepts invalid clients")
            
            return True
            
        except subprocess.TimeoutExpired:
            self.log_result("client-test.sh", False, "script timed out")
            return False
        except Exception as e:
            self.log_result("client-test.sh", False, f"execution error: {e}")
            return False
    
    def validate_log_analyzer(self) -> bool:
        """Validate log-analyzer.py functionality."""
        print("\nValidating Log Analyzer Script...")
        
        script_path = self.project_root / "uat/scripts/log-analyzer.py"
        
        if not script_path.exists():
            self.log_result("log-analyzer.py", False, "script missing")
            return False
        
        try:
            # Test script help
            result = subprocess.run(
                ["python3", str(script_path), "--help"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0 and "usage:" in result.stdout.lower():
                self.log_result("log-analyzer.py help", True, "shows help")
            else:
                self.log_result("log-analyzer.py help", False, "help not working")
                return False
            
            # Test with invalid arguments
            result = subprocess.run(
                ["python3", str(script_path), "--invalid-arg"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                self.log_result("log-analyzer.py validation", True, "rejects invalid arguments")
            else:
                self.log_result("log-analyzer.py validation", False, "accepts invalid arguments")
            
            # Test basic functionality (report mode)
            result = subprocess.run(
                ["python3", str(script_path), "--report", "--json"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                try:
                    # Should produce valid JSON
                    json.loads(result.stdout)
                    self.log_result("log-analyzer.py JSON output", True, "produces valid JSON")
                except json.JSONDecodeError:
                    self.log_result("log-analyzer.py JSON output", False, "invalid JSON output")
                    return False
            else:
                self.log_result("log-analyzer.py execution", False, "failed to execute report")
                return False
            
            return True
            
        except subprocess.TimeoutExpired:
            self.log_result("log-analyzer.py", False, "script timed out")
            return False
        except Exception as e:
            self.log_result("log-analyzer.py", False, f"execution error: {e}")
            return False
    
    def validate_mcp_config_integration(self) -> bool:
        """Validate integration with make mcp-config."""
        print("\nValidating MCP Configuration Integration...")
        
        try:
            # Test make target exists
            result = subprocess.run(
                ["make", "--dry-run", "mcp-config"],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=self.project_root
            )
            
            if result.returncode == 0:
                self.log_result("make mcp-config target", True, "exists")
            else:
                self.log_result("make mcp-config target", False, "missing or broken")
                return False
            
            # Test batch mode
            result = subprocess.run(
                ["make", "mcp-config", "BATCH=1"],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=self.project_root
            )
            
            if result.returncode == 0:
                try:
                    # Should produce valid JSON
                    config = json.loads(result.stdout)
                    if "mcpServers" in config:
                        self.log_result("make mcp-config BATCH=1", True, "produces valid MCP config")
                    else:
                        self.log_result("make mcp-config BATCH=1", False, "missing mcpServers section")
                        return False
                except json.JSONDecodeError:
                    self.log_result("make mcp-config BATCH=1", False, "invalid JSON output")
                    return False
            else:
                self.log_result("make mcp-config BATCH=1", False, f"failed: {result.stderr}")
                return False
            
            return True
            
        except subprocess.TimeoutExpired:
            self.log_result("make mcp-config", False, "command timed out")
            return False
        except Exception as e:
            self.log_result("make mcp-config", False, f"execution error: {e}")
            return False
    
    def validate_server_startup(self) -> bool:
        """Validate MCP server can start successfully."""
        print("\nValidating MCP Server Startup...")
        
        try:
            # Test server startup with a different port to avoid conflicts
            import os
            env = os.environ.copy()
            env["FASTMCP_PORT"] = "8001"  # Use different port for testing
            
            # Test server startup
            process = subprocess.Popen(
                ["make", "-C", "app", "run"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=self.project_root,
                env=env
            )
            
            # Give server time to start
            import time
            time.sleep(5)
            
            # Check if process is still running
            if process.poll() is None:
                self.log_result("MCP server startup", True, "server started successfully on port 8001")
                process.terminate()
                process.wait(timeout=10)
                return True
            else:
                stdout, stderr = process.communicate()
                
                # Check if the error is just port conflict (not a real failure)
                if "address already in use" in stderr.lower():
                    # Try to start with different port
                    env["FASTMCP_PORT"] = "8002"
                    process2 = subprocess.Popen(
                        ["make", "-C", "app", "run"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        cwd=self.project_root,
                        env=env
                    )
                    
                    time.sleep(5)
                    
                    if process2.poll() is None:
                        self.log_result("MCP server startup", True, "server started successfully on port 8002")
                        process2.terminate()
                        process2.wait(timeout=10)
                        return True
                    else:
                        stdout2, stderr2 = process2.communicate()
                        self.log_result("MCP server startup", False, f"server failed even with different port: {stderr2}")
                        return False
                else:
                    self.log_result("MCP server startup", False, f"server failed: {stderr}")
                    return False
            
        except subprocess.TimeoutExpired:
            self.log_result("MCP server startup", False, "server startup timed out")
            return False
        except Exception as e:
            self.log_result("MCP server startup", False, f"startup error: {e}")
            return False
    
    def run_validation(self) -> Dict[str, Any]:
        """Run complete UAT validation."""
        print("UAT Validation Report")
        print("=" * 50)
        
        if not self.project_root:
            print("❌ Could not find project root (looking for Makefile)")
            return {"success": False, "error": "Project root not found"}
        
        print(f"Project root: {self.project_root}")
        print(f"UAT root: {self.uat_root}")
        print()
        
        # Run all validations
        validations = [
            ("Directory Structure", self.validate_directory_structure),
            ("Script Permissions", self.validate_scripts_executable),
            ("Log Patterns Config", self.validate_patterns_json),
            ("Client Test Script", self.validate_client_test_script),
            ("Log Analyzer Script", self.validate_log_analyzer),
            ("MCP Config Integration", self.validate_mcp_config_integration),
            ("MCP Server Startup", self.validate_server_startup)
        ]
        
        all_passed = True
        
        for name, validator in validations:
            try:
                passed = validator()
                if not passed:
                    all_passed = False
            except Exception as e:
                self.log_result(name, False, f"validation error: {e}")
                all_passed = False
        
        # Summary
        print("\nValidation Summary:")
        print("=" * 50)
        
        passed_count = sum(1 for r in self.results if r["success"])
        total_count = len(self.results)
        
        print(f"Tests passed: {passed_count}/{total_count}")
        
        if all_passed:
            print("✅ All UAT validations passed!")
        else:
            print("❌ Some UAT validations failed!")
            print("\nFailed tests:")
            for result in self.results:
                if not result["success"]:
                    print(f"  - {result['test']}: {result['message']}")
        
        return {
            "success": all_passed,
            "passed": passed_count,
            "total": total_count,
            "results": self.results
        }


def main():
    """Main validation function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate UAT setup and functionality")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument("--project-root", type=Path, help="Project root directory")
    
    args = parser.parse_args()
    
    validator = UATValidator(args.project_root)
    results = validator.run_validation()
    
    if args.json:
        print(json.dumps(results, indent=2))
    
    # Exit with appropriate code
    sys.exit(0 if results["success"] else 1)


if __name__ == "__main__":
    main()
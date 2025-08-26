#!/usr/bin/env python3
"""
MCP Client Log Analyzer
Parses client logs and validates MCP server connection patterns
"""

import json
import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime


class LogAnalyzer:
    """Analyzes MCP client logs for connection success/failure patterns."""
    
    def __init__(self):
        self.patterns = self.load_patterns()
        
    def load_patterns(self) -> Dict[str, Any]:
        """Load log patterns from patterns.json if available, otherwise use defaults."""
        patterns_file = Path(__file__).parent.parent / "logs" / "patterns.json"
        
        # Default patterns
        default_patterns = {
            "claude_desktop": {
                "success_patterns": [
                    r"Server started and connected successfully",
                    r"Message from client.*initialize"
                ],
                "failure_patterns": [
                    r"spawn .* ENOENT",
                    r"Server disconnected",
                    r"can't open file",
                    r"No such file or directory"
                ],
                "log_file": "~/Library/Logs/Claude/mcp-server-quilt.log"
            },
            "vscode": {
                "success_patterns": [
                    r"MCP server.*connected",
                    r"Extension Host.*MCP.*ready"
                ],
                "failure_patterns": [
                    r"MCP server.*failed",
                    r"Extension.*error.*MCP"
                ],
                "log_file": None  # Requires manual inspection
            },
            "cursor": {
                "success_patterns": [
                    r"MCP.*connected successfully",
                    r"Server.*ready"
                ],
                "failure_patterns": [
                    r"MCP.*connection failed",
                    r"Server.*error"
                ],
                "log_file": None  # Requires manual inspection
            }
        }
        
        if patterns_file.exists():
            try:
                with open(patterns_file, 'r') as f:
                    loaded_patterns = json.load(f)
                # Merge with defaults
                for client, patterns in loaded_patterns.get("clients", {}).items():
                    if client in default_patterns:
                        default_patterns[client].update(patterns)
                    else:
                        default_patterns[client] = patterns
            except (json.JSONDecodeError, KeyError):
                print("⚠️  Warning: Could not load patterns.json, using defaults")
        
        return default_patterns
    
    def get_log_file_path(self, client: str) -> Optional[Path]:
        """Get the log file path for a client."""
        if client not in self.patterns:
            return None
            
        log_file = self.patterns[client].get("log_file")
        if not log_file:
            return None
            
        # Expand home directory
        if log_file.startswith("~/"):
            return Path.home() / log_file[2:]
        
        return Path(log_file)
    
    def analyze_log_file(self, log_file: Path, client: str) -> Dict[str, Any]:
        """Analyze a log file for MCP connection patterns."""
        if not log_file.exists():
            return {
                "status": "file_not_found",
                "message": f"Log file not found: {log_file}",
                "success_count": 0,
                "failure_count": 0,
                "recent_entries": []
            }
        
        client_patterns = self.patterns.get(client, {})
        success_patterns = client_patterns.get("success_patterns", [])
        failure_patterns = client_patterns.get("failure_patterns", [])
        
        success_count = 0
        failure_count = 0
        recent_entries = []
        
        try:
            with open(log_file, 'r') as f:
                lines = f.readlines()
                
            # Analyze each line
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                # Check for success patterns
                for pattern in success_patterns:
                    if re.search(pattern, line, re.IGNORECASE):
                        success_count += 1
                        recent_entries.append({
                            "type": "success",
                            "line": line,
                            "pattern": pattern
                        })
                        break
                
                # Check for failure patterns
                for pattern in failure_patterns:
                    if re.search(pattern, line, re.IGNORECASE):
                        failure_count += 1
                        recent_entries.append({
                            "type": "failure", 
                            "line": line,
                            "pattern": pattern
                        })
                        break
            
            # Keep only recent entries (last 20)
            recent_entries = recent_entries[-20:]
            
            # Determine overall status
            if failure_count > success_count:
                status = "failing"
            elif success_count > 0:
                status = "success"
            else:
                status = "unknown"
            
            return {
                "status": status,
                "success_count": success_count,
                "failure_count": failure_count,
                "recent_entries": recent_entries,
                "total_lines": len(lines)
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error reading log file: {e}",
                "success_count": 0,
                "failure_count": 0,
                "recent_entries": []
            }
    
    def analyze_client(self, client: str) -> Dict[str, Any]:
        """Analyze logs for a specific client."""
        log_file = self.get_log_file_path(client)
        
        if not log_file:
            return {
                "client": client,
                "status": "no_log_file",
                "message": f"No log file configured for {client}",
                "analysis": {}
            }
        
        analysis = self.analyze_log_file(log_file, client)
        
        return {
            "client": client,
            "log_file": str(log_file),
            "analysis": analysis
        }
    
    def check_connection_success(self, client: str) -> bool:
        """Check if MCP server connection was successful for a client."""
        result = self.analyze_client(client)
        analysis = result.get("analysis", {})
        return analysis.get("status") == "success"
    
    def generate_report(self, clients: Optional[List[str]] = None) -> Dict[str, Any]:
        """Generate a comprehensive analysis report."""
        if clients is None:
            clients = list(self.patterns.keys())
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "clients": {},
            "summary": {
                "total_clients": len(clients),
                "successful_clients": 0,
                "failing_clients": 0,
                "unknown_clients": 0
            }
        }
        
        for client in clients:
            client_result = self.analyze_client(client)
            report["clients"][client] = client_result
            
            status = client_result.get("analysis", {}).get("status", "unknown")
            if status == "success":
                report["summary"]["successful_clients"] += 1
            elif status in ["failing", "error"]:
                report["summary"]["failing_clients"] += 1
            else:
                report["summary"]["unknown_clients"] += 1
        
        return report
    
    def display_report(self, report: Dict[str, Any]) -> None:
        """Display a formatted report."""
        print("MCP Client Log Analysis Report")
        print("=" * 50)
        print(f"Generated: {report['timestamp']}")
        print()
        
        summary = report["summary"]
        print("Summary:")
        print(f"  Total clients analyzed: {summary['total_clients']}")
        print(f"  ✅ Successful: {summary['successful_clients']}")
        print(f"  ❌ Failing: {summary['failing_clients']}")
        print(f"  ⚠️  Unknown: {summary['unknown_clients']}")
        print()
        
        print("Client Details:")
        print("-" * 50)
        
        for client, result in report["clients"].items():
            analysis = result.get("analysis", {})
            status = analysis.get("status", "unknown")
            
            if status == "success":
                indicator = "✅"
            elif status in ["failing", "error"]:
                indicator = "❌"
            else:
                indicator = "⚠️"
            
            print(f"{indicator} {client.upper()}:")
            
            if "log_file" in result:
                print(f"    Log file: {result['log_file']}")
            
            if status == "file_not_found":
                print(f"    Status: Log file not found")
            elif status == "no_log_file":
                print(f"    Status: No log file configured")
            elif status == "error":
                print(f"    Status: Error - {analysis.get('message', 'Unknown error')}")
            else:
                success_count = analysis.get("success_count", 0)
                failure_count = analysis.get("failure_count", 0)
                print(f"    Success events: {success_count}")
                print(f"    Failure events: {failure_count}")
                
                # Show recent entries
                recent = analysis.get("recent_entries", [])
                if recent:
                    print(f"    Recent activity:")
                    for entry in recent[-3:]:  # Last 3 entries
                        entry_type = "✅" if entry["type"] == "success" else "❌"
                        print(f"      {entry_type} {entry['line'][:80]}...")
            
            print()


def main():
    parser = argparse.ArgumentParser(description="Analyze MCP client logs")
    parser.add_argument("--client", help="Specific client to analyze (claude_desktop, vscode, cursor)")
    parser.add_argument("--check-connection", action="store_true", 
                       help="Check if MCP server connection is successful")
    parser.add_argument("--report", action="store_true", 
                       help="Generate comprehensive report for all clients")
    parser.add_argument("--json", action="store_true", 
                       help="Output results as JSON")
    
    args = parser.parse_args()
    
    analyzer = LogAnalyzer()
    
    if args.check_connection:
        if not args.client:
            print("Error: --check-connection requires --client")
            sys.exit(1)
            
        success = analyzer.check_connection_success(args.client)
        
        if args.json:
            result = {"client": args.client, "connection_successful": success}
            print(json.dumps(result, indent=2))
        else:
            status = "✅ Connected" if success else "❌ Failed"
            print(f"{args.client}: {status}")
        
        sys.exit(0 if success else 1)
    
    elif args.report:
        clients = [args.client] if args.client else None
        report = analyzer.generate_report(clients)
        
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            analyzer.display_report(report)
    
    elif args.client:
        result = analyzer.analyze_client(args.client)
        
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            analysis = result.get("analysis", {})
            status = analysis.get("status", "unknown")
            print(f"Client: {args.client}")
            print(f"Status: {status}")
            if "log_file" in result:
                print(f"Log file: {result['log_file']}")
            
            success_count = analysis.get("success_count", 0)
            failure_count = analysis.get("failure_count", 0)
            print(f"Success events: {success_count}")
            print(f"Failure events: {failure_count}")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Comprehensive health check diagnostics for MCP server deployment.
This script tests all aspects of the health check system.
"""

import requests
import json
import subprocess
import sys
import time
from datetime import datetime
from typing import Dict, List, Any


class HealthCheckDiagnostics:
    """Diagnostic tool for MCP server health checks."""
    
    def __init__(self):
        self.base_url = "https://demo.quiltdata.com"
        self.cluster_name = "sales-prod"
        self.services = {
            "production": "sales-prod-mcp-server-production",
            "sse": "sales-prod-mcp-server-sse"
        }
        self.target_groups = {
            "production": "sales-prod-mcp",
            "sse": "sales-prod-mcp-sse"
        }
    
    def run_aws_command(self, command: List[str]) -> Dict[str, Any]:
        """Run AWS CLI command and return parsed JSON."""
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            return json.loads(result.stdout) if result.stdout.strip() else {}
        except subprocess.CalledProcessError as e:
            return {"error": f"Command failed: {e.stderr}"}
        except json.JSONDecodeError as e:
            return {"error": f"JSON decode error: {e}"}
    
    def test_endpoint_health(self, endpoint: str, description: str) -> Dict[str, Any]:
        """Test endpoint health directly."""
        print(f"\n{'='*60}")
        print(f"Testing: {description}")
        print(f"URL: {endpoint}")
        
        try:
            response = requests.get(endpoint, timeout=10)
            return {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body": response.text[:500],
                "success": response.status_code == 200,
                "error": None
            }
        except requests.exceptions.RequestException as e:
            return {
                "status_code": None,
                "headers": {},
                "body": "",
                "success": False,
                "error": str(e)
            }
    
    def check_ecs_service_status(self) -> Dict[str, Any]:
        """Check ECS service status."""
        print(f"\n{'='*60}")
        print("ECS SERVICE STATUS CHECK")
        print(f"{'='*60}")
        
        results = {}
        for service_type, service_name in self.services.items():
            print(f"\n{service_type.upper()} Service: {service_name}")
            
            # Get service details
            command = [
                "aws", "ecs", "describe-services",
                "--cluster", self.cluster_name,
                "--services", service_name
            ]
            service_data = self.run_aws_command(command)
            
            if "error" in service_data:
                results[service_type] = {"error": service_data["error"]}
                continue
            
            if not service_data.get("services"):
                results[service_type] = {"error": "Service not found"}
                continue
            
            service = service_data["services"][0]
            deployment = service.get("deployments", [{}])[0]
            
            result = {
                "service_name": service_name,
                "status": service.get("status"),
                "desired_count": deployment.get("desiredCount", 0),
                "running_count": deployment.get("runningCount", 0),
                "pending_count": deployment.get("pendingCount", 0),
                "task_definition": deployment.get("taskDefinition", ""),
                "health_check_grace_period": service.get("healthCheckGracePeriodSeconds"),
                "load_balancers": service.get("loadBalancers", [])
            }
            
            # Check for tasks
            task_command = [
                "aws", "ecs", "list-tasks",
                "--cluster", self.cluster_name,
                "--service-name", service_name
            ]
            tasks_data = self.run_aws_command(task_command)
            result["task_count"] = len(tasks_data.get("taskArns", []))
            
            results[service_type] = result
            
            # Print summary
            print(f"  Status: {result['status']}")
            print(f"  Desired: {result['desired_count']}, Running: {result['running_count']}, Pending: {result['pending_count']}")
            print(f"  Tasks: {result['task_count']}")
            print(f"  Task Definition: {result['task_definition'].split('/')[-1] if result['task_definition'] else 'None'}")
        
        return results
    
    def check_target_group_health(self) -> Dict[str, Any]:
        """Check ALB target group health."""
        print(f"\n{'='*60}")
        print("TARGET GROUP HEALTH CHECK")
        print(f"{'='*60}")
        
        results = {}
        
        # Get all target groups
        tg_command = [
            "aws", "elbv2", "describe-target-groups",
            "--query", "TargetGroups[?contains(TargetGroupName, `mcp`)]"
        ]
        target_groups = self.run_aws_command(tg_command)
        
        if "error" in target_groups:
            return {"error": target_groups["error"]}
        
        for tg in target_groups:
            tg_name = tg["TargetGroupName"]
            tg_arn = tg["TargetGroupArn"]
            
            print(f"\nTarget Group: {tg_name}")
            
            # Get health status
            health_command = [
                "aws", "elbv2", "describe-target-health",
                "--target-group-arn", tg_arn
            ]
            health_data = self.run_aws_command(health_command)
            
            if "error" in health_data:
                results[tg_name] = {"error": health_data["error"]}
                continue
            
            targets = health_data.get("TargetHealthDescriptions", [])
            healthy_count = sum(1 for t in targets if t["TargetHealth"]["State"] == "healthy")
            unhealthy_count = sum(1 for t in targets if t["TargetHealth"]["State"] == "unhealthy")
            draining_count = sum(1 for t in targets if t["TargetHealth"]["State"] == "draining")
            
            result = {
                "total_targets": len(targets),
                "healthy": healthy_count,
                "unhealthy": unhealthy_count,
                "draining": draining_count,
                "targets": []
            }
            
            for target in targets:
                target_info = {
                    "id": target["Target"]["Id"],
                    "port": target["Target"]["Port"],
                    "state": target["TargetHealth"]["State"],
                    "reason": target["TargetHealth"].get("Reason", ""),
                    "description": target["TargetHealth"].get("Description", "")
                }
                result["targets"].append(target_info)
                print(f"  Target {target_info['id']}:{target_info['port']} - {target_info['state']}")
                if target_info["reason"]:
                    print(f"    Reason: {target_info['reason']}")
                if target_info["description"]:
                    print(f"    Description: {target_info['description']}")
            
            results[tg_name] = result
        
        return results
    
    def check_task_health(self) -> Dict[str, Any]:
        """Check individual ECS task health."""
        print(f"\n{'='*60}")
        print("ECS TASK HEALTH CHECK")
        print(f"{'='*60}")
        
        results = {}
        
        for service_type, service_name in self.services.items():
            print(f"\n{service_type.upper()} Service Tasks:")
            
            # Get tasks
            task_command = [
                "aws", "ecs", "list-tasks",
                "--cluster", self.cluster_name,
                "--service-name", service_name
            ]
            tasks_data = self.run_aws_command(task_command)
            
            if "error" in tasks_data or not tasks_data.get("taskArns"):
                results[service_type] = {"error": "No tasks found" if "error" not in tasks_data else tasks_data["error"]}
                continue
            
            task_arns = tasks_data["taskArns"]
            results[service_type] = {"tasks": []}
            
            for task_arn in task_arns:
                # Get task details
                detail_command = [
                    "aws", "ecs", "describe-tasks",
                    "--cluster", self.cluster_name,
                    "--tasks", task_arn
                ]
                task_data = self.run_aws_command(detail_command)
                
                if "error" in task_data or not task_data.get("tasks"):
                    continue
                
                task = task_data["tasks"][0]
                task_id = task_arn.split("/")[-1]
                
                task_info = {
                    "task_id": task_id,
                    "last_status": task.get("lastStatus"),
                    "desired_status": task.get("desiredStatus"),
                    "health_status": task.get("healthStatus"),
                    "created_at": task.get("createdAt"),
                    "started_at": task.get("startedAt"),
                    "containers": []
                }
                
                # Check container health
                for container in task.get("containers", []):
                    container_info = {
                        "name": container.get("name"),
                        "last_status": container.get("lastStatus"),
                        "health_status": container.get("healthStatus"),
                        "exit_code": container.get("exitCode"),
                        "reason": container.get("reason")
                    }
                    task_info["containers"].append(container_info)
                    print(f"  Task {task_id}:")
                    print(f"    Status: {task_info['last_status']} (Health: {task_info['health_status']})")
                    print(f"    Container {container_info['name']}: {container_info['last_status']} (Health: {container_info['health_status']})")
                    if container_info["reason"]:
                        print(f"    Reason: {container_info['reason']}")
                
                results[service_type]["tasks"].append(task_info)
        
        return results
    
    def check_cloudwatch_logs(self) -> Dict[str, Any]:
        """Check CloudWatch logs for errors."""
        print(f"\n{'='*60}")
        print("CLOUDWATCH LOGS CHECK")
        print(f"{'='*60}")
        
        results = {}
        log_groups = ["/ecs/mcp-server-production", "/ecs/mcp-server-sse"]
        
        for log_group in log_groups:
            print(f"\nLog Group: {log_group}")
            
            # Get recent log streams
            streams_command = [
                "aws", "logs", "describe-log-streams",
                "--log-group-name", log_group,
                "--order-by", "LastEventTime",
                "--descending",
                "--max-items", "5"
            ]
            streams_data = self.run_aws_command(streams_command)
            
            if "error" in streams_data:
                results[log_group] = {"error": streams_data["error"]}
                continue
            
            streams = streams_data.get("logStreams", [])
            if not streams:
                results[log_group] = {"error": "No log streams found"}
                continue
            
            latest_stream = streams[0]
            stream_name = latest_stream["logStreamName"]
            
            # Get recent events
            events_command = [
                "aws", "logs", "get-log-events",
                "--log-group-name", log_group,
                "--log-stream-name", stream_name,
                "--start-time", str(int((datetime.now().timestamp() - 3600) * 1000)),  # Last hour
                "--limit", "50"
            ]
            events_data = self.run_aws_command(events_command)
            
            if "error" in events_data:
                results[log_group] = {"error": events_data["error"]}
                continue
            
            events = events_data.get("events", [])
            error_events = [e for e in events if "error" in e.get("message", "").lower() or "exception" in e.get("message", "").lower()]
            
            result = {
                "total_events": len(events),
                "error_events": len(error_events),
                "recent_errors": [e["message"] for e in error_events[-5:]]  # Last 5 errors
            }
            
            results[log_group] = result
            
            print(f"  Total events (last hour): {result['total_events']}")
            print(f"  Error events: {result['error_events']}")
            if result["recent_errors"]:
                print("  Recent errors:")
                for error in result["recent_errors"]:
                    print(f"    {error}")
        
        return results
    
    def test_health_endpoints(self) -> Dict[str, Any]:
        """Test health endpoints directly."""
        print(f"\n{'='*60}")
        print("HEALTH ENDPOINT TESTS")
        print(f"{'='*60}")
        
        endpoints = [
            f"{self.base_url}/healthz",
            f"{self.base_url}/mcp/",
            f"{self.base_url}/sse/"
        ]
        
        results = {}
        for endpoint in endpoints:
            result = self.test_endpoint_health(endpoint, f"Health check: {endpoint}")
            results[endpoint] = result
        
        return results
    
    def generate_diagnostic_report(self) -> Dict[str, Any]:
        """Generate comprehensive diagnostic report."""
        print(f"\n{'='*80}")
        print(f"MCP SERVER HEALTH CHECK DIAGNOSTICS - {datetime.now()}")
        print(f"{'='*80}")
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "ecs_services": self.check_ecs_service_status(),
            "target_groups": self.check_target_group_health(),
            "tasks": self.check_task_health(),
            "logs": self.check_cloudwatch_logs(),
            "endpoints": self.test_health_endpoints()
        }
        
        # Summary
        print(f"\n{'='*80}")
        print("DIAGNOSTIC SUMMARY")
        print(f"{'='*80}")
        
        # ECS Service Summary
        ecs_issues = []
        for service_type, service_data in report["ecs_services"].items():
            if "error" in service_data:
                ecs_issues.append(f"{service_type}: {service_data['error']}")
            elif service_data.get("running_count", 0) == 0:
                ecs_issues.append(f"{service_type}: No running tasks (desired: {service_data.get('desired_count', 0)})")
        
        if ecs_issues:
            print("❌ ECS Service Issues:")
            for issue in ecs_issues:
                print(f"  - {issue}")
        else:
            print("✅ ECS Services: All healthy")
        
        # Target Group Summary
        tg_issues = []
        for tg_name, tg_data in report["target_groups"].items():
            if "error" in tg_data:
                tg_issues.append(f"{tg_name}: {tg_data['error']}")
            elif tg_data.get("healthy", 0) == 0:
                tg_issues.append(f"{tg_name}: No healthy targets")
            elif tg_data.get("unhealthy", 0) > 0:
                tg_issues.append(f"{tg_name}: {tg_data['unhealthy']} unhealthy targets")
        
        if tg_issues:
            print("❌ Target Group Issues:")
            for issue in tg_issues:
                print(f"  - {issue}")
        else:
            print("✅ Target Groups: All healthy")
        
        # Endpoint Summary
        endpoint_issues = []
        for endpoint, endpoint_data in report["endpoints"].items():
            if not endpoint_data.get("success", False):
                endpoint_issues.append(f"{endpoint}: {endpoint_data.get('error', 'Failed')}")
        
        if endpoint_issues:
            print("❌ Endpoint Issues:")
            for issue in endpoint_issues:
                print(f"  - {issue}")
        else:
            print("✅ Endpoints: All responding")
        
        return report


def main():
    """Run health check diagnostics."""
    diagnostics = HealthCheckDiagnostics()
    report = diagnostics.generate_diagnostic_report()
    
    # Save report
    with open("health_check_report.json", "w") as f:
        json.dump(report, f, indent=2, default=str)
    
    print(f"\n📄 Full diagnostic report saved to: health_check_report.json")
    
    # Exit with error code if issues found
    total_issues = 0
    for section in ["ecs_services", "target_groups", "endpoints"]:
        if section in report:
            for item in report[section].values():
                if "error" in item or not item.get("success", True):
                    total_issues += 1
    
    if total_issues > 0:
        print(f"\n⚠️  Found {total_issues} issues. Check the report for details.")
        sys.exit(1)
    else:
        print(f"\n✅ All health checks passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()


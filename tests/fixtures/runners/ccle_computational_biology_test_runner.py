#!/usr/bin/env python3
"""
CCLE Computational Biology Test Runner

This script validates the MCP server's ability to handle real-world
computational biology workflows using CCLE (Cancer Cell Line Encyclopedia) data.

Tests are based on actual user stories from bioinformaticians working with
genomics data in cloud environments.
"""

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import MCP server components
import sys

sys.path.append(str(Path(__file__).parent / "app"))

from quilt_mcp.utils import create_mcp_server, register_tools


class CCLEComputationalBiologyTester:
    """Test runner for CCLE computational biology use cases."""

    def __init__(self):
        self.server = None
        self.tools = {}
        self.test_results = []
        self.start_time = None

    async def setup(self):
        """Initialize MCP server and tools."""
        print("🧬 Setting up CCLE Computational Biology Test Environment...")
        try:
            self.server = create_mcp_server()
            tool_count = register_tools(self.server, verbose=False)
            self.tools = await self.server.get_tools()
            print(f"✅ MCP server initialized with {tool_count} tools")
            print(f"✅ {len(self.tools)} tools available for testing")
            return True
        except Exception as e:
            print(f"❌ Setup failed: {e}")
            return False

    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all CCLE computational biology test cases."""
        self.start_time = time.time()

        # Load test cases
        test_cases_file = Path(__file__).parent / "ccle_computational_biology_test_cases.json"
        with open(test_cases_file, "r") as f:
            test_data = json.load(f)

        print(f"\n🧬 Running {len(test_data['test_cases'])} CCLE Computational Biology Test Cases")
        print("=" * 80)

        for test_case in test_data["test_cases"]:
            result = await self.run_test_case(test_case)
            self.test_results.append(result)

            # Print immediate feedback
            status = "✅ PASS" if result["success"] else "❌ FAIL"
            print(f"{status} {test_case['id']}: {test_case['user_story'][:60]}...")

        return self.generate_final_report(test_data)

    async def run_test_case(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """Run a single CCLE test case."""
        test_id = test_case["id"]
        category = test_case["category"]

        print(f"\n🔬 Testing {test_id}: {category}")
        print(f"   User Story: {test_case['user_story']}")
        print(f"   Objective: {test_case['objective']}")

        result = {
            "test_id": test_id,
            "category": category,
            "user_story": test_case["user_story"],
            "success": False,
            "steps_completed": [],
            "steps_failed": [],
            "execution_time_ms": 0,
            "tools_used": [],
            "data_accessed": [],
            "errors": [],
            "recommendations": [],
        }

        start_time = time.time()

        try:
            # Execute test based on category
            if category == "Molecular Target Discovery":
                await self.test_molecular_target_discovery(test_case, result)
            elif category == "Tool Benchmarking":
                await self.test_tool_benchmarking(test_case, result)
            elif category == "Visual Data Exploration":
                await self.test_visual_data_exploration(test_case, result)
            elif category == "Cross-Package Analysis":
                await self.test_cross_package_analysis(test_case, result)
            elif category == "Longitudinal Analysis":
                await self.test_longitudinal_analysis(test_case, result)
            elif category == "Collaborative Research":
                await self.test_collaborative_research(test_case, result)
            else:
                result["errors"].append(f"Unknown test category: {category}")

        except Exception as e:
            result["errors"].append(f"Test execution failed: {str(e)}")
            logger.error(f"Test {test_id} failed with exception: {e}")

        result["execution_time_ms"] = round((time.time() - start_time) * 1000, 2)
        result["success"] = len(result["errors"]) == 0 and len(result["steps_failed"]) == 0

        return result

    async def test_molecular_target_discovery(self, test_case: Dict[str, Any], result: Dict[str, Any]):
        """Test CB001: Molecular target discovery workflow."""
        # Step 1: Check Tabulator availability
        try:
            tabulator_result = await self.call_tool("tabulator_tables_list", {"bucket_name": "quilt-sandbox-bucket"})
            if tabulator_result.get("success"):
                result["steps_completed"].append("tabulator_connectivity")
                result["tools_used"].append("tabulator_tables_list")
            else:
                result["steps_failed"].append("tabulator_connectivity")
                result["errors"].append("Tabulator not accessible")
        except Exception as e:
            result["steps_failed"].append("tabulator_connectivity")
            result["errors"].append(f"Tabulator check failed: {str(e)}")

        # Step 2: Search for CCLE expression data
        try:
            search_result = await self.call_tool("packages_search", {"query": "CCLE expression RNA-seq", "limit": 5})
            if search_result.get("success") and search_result.get("results"):
                result["steps_completed"].append("ccle_data_discovery")
                result["tools_used"].append("packages_search")
                result["data_accessed"].extend(
                    [r.get("_source", {}).get("key", "unknown") for r in search_result["results"][:3]]
                )
            else:
                result["steps_failed"].append("ccle_data_discovery")
                result["errors"].append("No CCLE expression data found")
        except Exception as e:
            result["steps_failed"].append("ccle_data_discovery")
            result["errors"].append(f"CCLE data search failed: {str(e)}")

        # Step 3: Attempt Athena query for ERBB2 expression
        try:
            # Try to execute a representative query
            query = """
            SELECT 
                cell_line_name,
                tissue_type,
                ERBB2_tpm
            FROM ccle_expression_data 
            WHERE tissue_type = 'breast' 
            ORDER BY ERBB2_tpm DESC 
            LIMIT 10
            """

            athena_result = await self.call_tool("athena_query_execute", {"query": query, "max_results": 10})

            if athena_result.get("success"):
                result["steps_completed"].append("erbb2_expression_query")
                result["tools_used"].append("athena_query_execute")
                result["recommendations"].append("Successfully executed ERBB2 expression ranking query")
            else:
                result["steps_failed"].append("erbb2_expression_query")
                error_msg = athena_result.get("error", "Unknown Athena error")
                if "table" in error_msg.lower() or "database" in error_msg.lower():
                    result["errors"].append("CCLE expression table not available in current environment")
                    result["recommendations"].append("Set up CCLE Tabulator tables for expression data queries")
                else:
                    result["errors"].append(f"Athena query failed: {error_msg}")
        except Exception as e:
            result["steps_failed"].append("erbb2_expression_query")
            result["errors"].append(f"Athena query execution failed: {str(e)}")

        # Step 4: Validate workflow orchestration capability
        try:
            workflow_result = await self.call_tool(
                "workflow_create",
                {
                    "workflow_id": f"ccle-target-discovery-{int(time.time())}",
                    "name": "CCLE ERBB2 Target Discovery",
                    "description": "Identify breast cancer cell lines with high ERBB2 expression",
                },
            )

            if workflow_result.get("success"):
                result["steps_completed"].append("workflow_orchestration")
                result["tools_used"].append("workflow_create")
                result["recommendations"].append("Workflow orchestration available for complex CCLE analyses")
            else:
                result["steps_failed"].append("workflow_orchestration")
                result["errors"].append("Workflow orchestration not available")
        except Exception as e:
            result["steps_failed"].append("workflow_orchestration")
            result["errors"].append(f"Workflow creation failed: {str(e)}")

    async def test_tool_benchmarking(self, test_case: Dict[str, Any], result: Dict[str, Any]):
        """Test CB002: Tool benchmarking workflow."""
        # Step 1: Search for CCLE FASTQ packages
        try:
            fastq_search = await self.call_tool("packages_search", {"query": "CCLE FASTQ RNA-seq raw", "limit": 3})

            if fastq_search.get("success") and fastq_search.get("results"):
                result["steps_completed"].append("fastq_discovery")
                result["tools_used"].append("packages_search")
                result["data_accessed"].extend(
                    [r.get("_source", {}).get("key", "unknown") for r in fastq_search["results"]]
                )
            else:
                result["steps_failed"].append("fastq_discovery")
                result["errors"].append("No CCLE FASTQ packages found")
        except Exception as e:
            result["steps_failed"].append("fastq_discovery")
            result["errors"].append(f"FASTQ search failed: {str(e)}")

        # Step 2: Browse package structure for FASTQs
        try:
            # Try to browse a known CCLE package or search result
            browse_result = await self.call_tool("packages_list", {"limit": 5})

            if browse_result.get("success") and browse_result.get("packages"):
                # Try to browse the first package
                first_package = browse_result["packages"][0]["name"]
                package_browse = await self.call_tool(
                    "package_browse",
                    {"package_name": first_package, "recursive": False},
                )

                if package_browse.get("success"):
                    result["steps_completed"].append("package_structure_analysis")
                    result["tools_used"].extend(["packages_list", "package_browse"])
                    result["recommendations"].append("Package browsing available for FASTQ file discovery")
                else:
                    result["steps_failed"].append("package_structure_analysis")
                    result["errors"].append("Package browsing failed")
            else:
                result["steps_failed"].append("package_structure_analysis")
                result["errors"].append("No packages available for browsing")
        except Exception as e:
            result["steps_failed"].append("package_structure_analysis")
            result["errors"].append(f"Package browsing failed: {str(e)}")

        # Step 3: Generate presigned URLs for file access
        try:
            # Test presigned URL generation capability
            url_result = await self.call_tool(
                "bucket_object_link",
                {
                    "s3_uri": "s3://quilt-sandbox-bucket/test-file.fastq.gz",
                    "expiration": 3600,
                },
            )

            if url_result.get("success"):
                result["steps_completed"].append("presigned_url_generation")
                result["tools_used"].append("bucket_object_link")
                result["recommendations"].append("Presigned URLs available for FASTQ file access")
            else:
                result["steps_failed"].append("presigned_url_generation")
                result["errors"].append("Presigned URL generation failed")
        except Exception as e:
            result["steps_failed"].append("presigned_url_generation")
            result["errors"].append(f"URL generation failed: {str(e)}")

        # Step 4: Search for Salmon quantification results
        try:
            salmon_search = await self.call_tool(
                "bucket_objects_search",
                {
                    "bucket": "s3://quilt-sandbox-bucket",
                    "query": "salmon quant.sf TPM",
                    "limit": 5,
                },
            )

            if salmon_search.get("success"):
                result["steps_completed"].append("salmon_results_discovery")
                result["tools_used"].append("bucket_objects_search")
                result["recommendations"].append("Salmon quantification results discoverable for benchmarking")
            else:
                result["steps_failed"].append("salmon_results_discovery")
                result["errors"].append("Salmon results not found")
        except Exception as e:
            result["steps_failed"].append("salmon_results_discovery")
            result["errors"].append(f"Salmon search failed: {str(e)}")

    async def test_visual_data_exploration(self, test_case: Dict[str, Any], result: Dict[str, Any]):
        """Test CB003: Visual data exploration workflow."""
        # Step 1: Search for BAM files
        try:
            bam_search = await self.call_tool("packages_search", {"query": "CCLE BAM alignment RNA-seq", "limit": 3})

            if bam_search.get("success"):
                result["steps_completed"].append("bam_discovery")
                result["tools_used"].append("packages_search")
            else:
                result["steps_failed"].append("bam_discovery")
                result["errors"].append("No CCLE BAM packages found")
        except Exception as e:
            result["steps_failed"].append("bam_discovery")
            result["errors"].append(f"BAM search failed: {str(e)}")

        # Step 2: Generate catalog URLs for IGV integration
        try:
            catalog_url = await self.call_tool(
                "catalog_url",
                {
                    "registry": "s3://quilt-sandbox-bucket",
                    "package_name": "ccle/alignments-example",
                },
            )

            if catalog_url.get("success"):
                result["steps_completed"].append("igv_integration")
                result["tools_used"].append("catalog_url")
                result["recommendations"].append("Catalog URLs available for IGV browser integration")
            else:
                result["steps_failed"].append("igv_integration")
                result["errors"].append("Catalog URL generation failed")
        except Exception as e:
            result["steps_failed"].append("igv_integration")
            result["errors"].append(f"IGV integration test failed: {str(e)}")

        # Step 3: Test BAM file access
        try:
            bam_access = await self.call_tool(
                "bucket_object_info",
                {"s3_uri": "s3://quilt-sandbox-bucket/ccle/sample.bam"},
            )

            if bam_access.get("success"):
                result["steps_completed"].append("bam_file_access")
                result["tools_used"].append("bucket_object_info")
            else:
                result["steps_failed"].append("bam_file_access")
                result["errors"].append("BAM file access validation failed")
        except Exception as e:
            result["steps_failed"].append("bam_file_access")
            result["errors"].append(f"BAM access test failed: {str(e)}")

    async def test_cross_package_analysis(self, test_case: Dict[str, Any], result: Dict[str, Any]):
        """Test CB004: Cross-package analysis workflow."""
        # Step 1: Search for multiple CCLE data types
        data_types = ["expression", "mutation", "drug-response"]

        for data_type in data_types:
            try:
                search_result = await self.call_tool("packages_search", {"query": f"CCLE {data_type}", "limit": 2})

                if search_result.get("success") and search_result.get("results"):
                    result["steps_completed"].append(f"{data_type}_discovery")
                    result["tools_used"].append("packages_search")
                else:
                    result["steps_failed"].append(f"{data_type}_discovery")
                    result["errors"].append(f"No CCLE {data_type} data found")
            except Exception as e:
                result["steps_failed"].append(f"{data_type}_discovery")
                result["errors"].append(f"CCLE {data_type} search failed: {str(e)}")

        # Step 2: Test workflow template for cross-package analysis
        try:
            workflow_template = await self.call_tool(
                "workflow_template_apply",
                {
                    "template_name": "cross-package-aggregation",
                    "workflow_id": f"ccle-multiomics-{int(time.time())}",
                    "params": {
                        "source_packages": [
                            "ccle/expression",
                            "ccle/mutations",
                            "ccle/drug-response",
                        ],
                        "target_package": "ccle/integrated-multiomics",
                    },
                },
            )

            if workflow_template.get("success"):
                result["steps_completed"].append("multiomics_workflow")
                result["tools_used"].append("workflow_template_apply")
                result["recommendations"].append(
                    "Cross-package workflow templates available for multi-omics integration"
                )
            else:
                result["steps_failed"].append("multiomics_workflow")
                result["errors"].append("Multi-omics workflow template failed")
        except Exception as e:
            result["steps_failed"].append("multiomics_workflow")
            result["errors"].append(f"Workflow template failed: {str(e)}")

    async def test_longitudinal_analysis(self, test_case: Dict[str, Any], result: Dict[str, Any]):
        """Test CB005: Longitudinal analysis workflow."""
        # Step 1: Test Athena connectivity for temporal queries
        try:
            workgroups = await self.call_tool("athena_workgroups_list")

            if workgroups.get("success") and workgroups.get("workgroups"):
                result["steps_completed"].append("athena_connectivity")
                result["tools_used"].append("athena_workgroups_list")
            else:
                result["steps_failed"].append("athena_connectivity")
                result["errors"].append("Athena workgroups not accessible")
        except Exception as e:
            result["steps_failed"].append("athena_connectivity")
            result["errors"].append(f"Athena connectivity failed: {str(e)}")

        # Step 2: Test temporal analysis query
        try:
            temporal_query = """
            SELECT 
                processing_date,
                batch_id,
                COUNT(*) as sample_count,
                AVG(mapping_rate) as avg_mapping_rate
            FROM ccle_qc_metrics 
            WHERE processing_date >= '2023-01-01'
            GROUP BY processing_date, batch_id 
            ORDER BY processing_date DESC
            LIMIT 20
            """

            query_result = await self.call_tool("athena_query_execute", {"query": temporal_query, "max_results": 20})

            if query_result.get("success"):
                result["steps_completed"].append("temporal_analysis")
                result["tools_used"].append("athena_query_execute")
                result["recommendations"].append("Temporal analysis queries supported for batch effect detection")
            else:
                result["steps_failed"].append("temporal_analysis")
                error_msg = query_result.get("error", "Unknown error")
                if "table" in error_msg.lower():
                    result["errors"].append("CCLE QC metrics table not available")
                    result["recommendations"].append("Set up CCLE QC metrics table for longitudinal analysis")
                else:
                    result["errors"].append(f"Temporal query failed: {error_msg}")
        except Exception as e:
            result["steps_failed"].append("temporal_analysis")
            result["errors"].append(f"Temporal analysis failed: {str(e)}")

    async def test_collaborative_research(self, test_case: Dict[str, Any], result: Dict[str, Any]):
        """Test CB006: Collaborative research workflow."""
        # Step 1: Test package creation for sharing
        try:
            package_create = await self.call_tool(
                "package_create",
                {
                    "name": f"ccle/breast-cancer-subset-{int(time.time())}",
                    "files": ["s3://quilt-sandbox-bucket/ccle/breast-samples.csv"],
                    "description": "CCLE breast cancer cell lines for collaborative study",
                    "metadata_template": "standard",
                    "dry_run": True,
                },
            )

            if package_create.get("success"):
                result["steps_completed"].append("collaborative_package_creation")
                result["tools_used"].append("package_create")
                result["recommendations"].append("Package creation available for data sharing")
            else:
                result["steps_failed"].append("collaborative_package_creation")
                result["errors"].append("Package creation for sharing failed")
        except Exception as e:
            result["steps_failed"].append("collaborative_package_creation")
            result["errors"].append(f"Package creation failed: {str(e)}")

        # Step 2: Test package validation
        try:
            # Use a known package for validation test
            packages_result = await self.call_tool("packages_list", {"limit": 1})

            if packages_result.get("success") and packages_result.get("packages"):
                first_package = packages_result["packages"][0]["name"]
                validation_result = await self.call_tool("package_validate", {"package_name": first_package})

                if validation_result.get("success"):
                    result["steps_completed"].append("package_validation")
                    result["tools_used"].append("package_validate")
                    result["recommendations"].append("Package validation available for data integrity checks")
                else:
                    result["steps_failed"].append("package_validation")
                    result["errors"].append("Package validation failed")
            else:
                result["steps_failed"].append("package_validation")
                result["errors"].append("No packages available for validation test")
        except Exception as e:
            result["steps_failed"].append("package_validation")
            result["errors"].append(f"Package validation failed: {str(e)}")

        # Step 3: Generate shareable URLs
        try:
            catalog_url = await self.call_tool(
                "catalog_url",
                {
                    "registry": "s3://quilt-sandbox-bucket",
                    "package_name": "ccle/example-package",
                },
            )

            if catalog_url.get("success"):
                result["steps_completed"].append("shareable_url_generation")
                result["tools_used"].append("catalog_url")
                result["recommendations"].append("Shareable catalog URLs available for collaborator access")
            else:
                result["steps_failed"].append("shareable_url_generation")
                result["errors"].append("Shareable URL generation failed")
        except Exception as e:
            result["steps_failed"].append("shareable_url_generation")
            result["errors"].append(f"URL generation failed: {str(e)}")

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call an MCP tool safely."""
        try:
            if tool_name not in self.tools:
                return {"success": False, "error": f"Tool '{tool_name}' not available"}

            tool_obj = self.tools[tool_name]
            if hasattr(tool_obj, "run"):
                result = await tool_obj.run(**arguments)
            elif callable(tool_obj):
                if asyncio.iscoroutinefunction(tool_obj):
                    result = await tool_obj(**arguments)
                else:
                    result = tool_obj(**arguments)
            else:
                return {
                    "success": False,
                    "error": f"Tool '{tool_name}' is not callable",
                }

            return result if isinstance(result, dict) else {"success": True, "result": result}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def generate_final_report(self, test_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive test report."""
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r["success"])
        failed_tests = total_tests - passed_tests

        # Categorize results
        results_by_category = {}
        for result in self.test_results:
            category = result["category"]
            if category not in results_by_category:
                results_by_category[category] = {"passed": 0, "failed": 0, "tests": []}

            if result["success"]:
                results_by_category[category]["passed"] += 1
            else:
                results_by_category[category]["failed"] += 1

            results_by_category[category]["tests"].append(result)

        # Collect all tools used
        all_tools_used = set()
        for result in self.test_results:
            all_tools_used.update(result["tools_used"])

        # Collect all errors and recommendations
        all_errors = []
        all_recommendations = []
        for result in self.test_results:
            all_errors.extend(result["errors"])
            all_recommendations.extend(result["recommendations"])

        execution_time = time.time() - self.start_time if self.start_time else 0

        report = {
            "test_suite": "CCLE Computational Biology User Stories",
            "execution_timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_time_seconds": round(execution_time, 2),
            "summary": {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": failed_tests,
                "success_rate": (round((passed_tests / total_tests) * 100, 1) if total_tests > 0 else 0),
            },
            "results_by_category": results_by_category,
            "tools_coverage": {
                "tools_used": sorted(list(all_tools_used)),
                "total_tools_used": len(all_tools_used),
            },
            "detailed_results": self.test_results,
            "error_summary": {
                "total_errors": len(all_errors),
                "unique_errors": len(set(all_errors)),
                "common_errors": self._get_common_errors(all_errors),
            },
            "recommendations": {
                "total_recommendations": len(all_recommendations),
                "unique_recommendations": list(set(all_recommendations)),
            },
            "computational_biology_assessment": self._assess_computational_biology_readiness(),
            "next_steps": self._generate_next_steps(),
        }

        return report

    def _get_common_errors(self, errors: List[str]) -> List[Dict[str, Any]]:
        """Identify common error patterns."""
        error_counts = {}
        for error in errors:
            # Normalize error messages for pattern detection
            normalized = error.lower()
            if "table" in normalized or "database" in normalized:
                key = "Missing database/table"
            elif "permission" in normalized or "access denied" in normalized:
                key = "Permission/access issues"
            elif "athena" in normalized:
                key = "Athena connectivity issues"
            elif "package" in normalized and "not found" in normalized:
                key = "Package discovery issues"
            else:
                key = "Other errors"

            error_counts[key] = error_counts.get(key, 0) + 1

        return [
            {"error_type": k, "count": v} for k, v in sorted(error_counts.items(), key=lambda x: x[1], reverse=True)
        ]

    def _assess_computational_biology_readiness(self) -> Dict[str, Any]:
        """Assess readiness for computational biology workflows."""
        # Analyze test results for computational biology specific capabilities
        capabilities = {
            "genomics_data_access": False,
            "sql_analytics": False,
            "workflow_orchestration": False,
            "data_sharing": False,
            "visualization_support": False,
        }

        for result in self.test_results:
            if "discovery" in result["steps_completed"]:
                capabilities["genomics_data_access"] = True
            if "query" in result["steps_completed"] or "athena" in str(result["tools_used"]):
                capabilities["sql_analytics"] = True
            if "workflow" in result["steps_completed"]:
                capabilities["workflow_orchestration"] = True
            if "sharing" in result["steps_completed"] or "url" in result["steps_completed"]:
                capabilities["data_sharing"] = True
            if "igv" in result["steps_completed"] or "catalog_url" in result["tools_used"]:
                capabilities["visualization_support"] = True

        readiness_score = sum(capabilities.values()) / len(capabilities) * 100

        return {
            "capabilities": capabilities,
            "readiness_score": round(readiness_score, 1),
            "readiness_level": (
                "Production Ready"
                if readiness_score >= 80
                else (
                    "Mostly Ready"
                    if readiness_score >= 60
                    else "Needs Development"
                    if readiness_score >= 40
                    else "Not Ready"
                )
            ),
        }

    def _generate_next_steps(self) -> List[str]:
        """Generate actionable next steps based on test results."""
        next_steps = []

        # Analyze common failure patterns
        failed_steps = []
        for result in self.test_results:
            failed_steps.extend(result["steps_failed"])

        if any("tabulator" in step for step in failed_steps):
            next_steps.append("Set up CCLE Tabulator tables for expression and metadata queries")

        if any("athena" in step for step in failed_steps):
            next_steps.append("Configure Athena workgroups and Glue Data Catalog for CCLE data")

        if any("discovery" in step for step in failed_steps):
            next_steps.append("Populate test environment with CCLE sample packages")

        if any("permission" in str(result).lower() for result in self.test_results):
            next_steps.append("Review and fix AWS permissions for comprehensive data access")

        # Add general recommendations
        next_steps.extend(
            [
                "Create CCLE-specific documentation and tutorials",
                "Set up monitoring for computational biology workflow performance",
                "Implement CCLE data validation and quality checks",
                "Consider caching strategies for large genomics datasets",
            ]
        )

        return next_steps[:10]  # Limit to top 10 recommendations


async def main():
    """Main test execution function."""
    tester = CCLEComputationalBiologyTester()

    # Setup
    if not await tester.setup():
        print("❌ Test setup failed. Exiting.")
        return

    # Run tests
    report = await tester.run_all_tests()

    # Save detailed report
    report_file = Path(__file__).parent / "ccle_computational_biology_test_report.json"
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2)

    # Print summary
    print("\n" + "=" * 80)
    print("🧬 CCLE COMPUTATIONAL BIOLOGY TEST RESULTS")
    print("=" * 80)

    summary = report["summary"]
    print(f"📊 Total Tests: {summary['total_tests']}")
    print(f"✅ Passed: {summary['passed_tests']}")
    print(f"❌ Failed: {summary['failed_tests']}")
    print(f"📈 Success Rate: {summary['success_rate']}%")

    print(f"\n🔧 Tools Used: {report['tools_coverage']['total_tools_used']}")
    print(f"⚡ Execution Time: {report['execution_time_seconds']}s")

    # Print category breakdown
    print("\n📋 Results by Category:")
    for category, results in report["results_by_category"].items():
        print(f"   {category}: {results['passed']}/{results['passed'] + results['failed']} passed")

    # Print readiness assessment
    assessment = report["computational_biology_assessment"]
    print(f"\n🧬 Computational Biology Readiness: {assessment['readiness_level']} ({assessment['readiness_score']}%)")

    # Print top recommendations
    if report["recommendations"]["unique_recommendations"]:
        print("\n💡 Key Recommendations:")
        for rec in report["recommendations"]["unique_recommendations"][:5]:
            print(f"   • {rec}")

    print(f"\n📄 Detailed report saved to: {report_file}")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())

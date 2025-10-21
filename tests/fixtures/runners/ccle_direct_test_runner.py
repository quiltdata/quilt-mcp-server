#!/usr/bin/env python3
"""
CCLE Computational Biology Direct Test Runner

This script validates the MCP server's ability to handle real-world
computational biology workflows using direct tool calls.
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any
import sys

# Add the app directory to the path
sys.path.append(str(Path(__file__).parent / "app"))

# Import tools directly
from quilt_mcp.tools import (
    packages,
    athena_glue,
    tabulator,
    buckets,
    package_ops,
    workflow_orchestration,
    auth,
    search,
)


class CCLEDirectTester:
    """Direct test runner for CCLE computational biology use cases."""

    def __init__(self):
        self.test_results = []
        self.start_time = None

    def run_all_tests(self) -> Dict[str, Any]:
        """Run all CCLE computational biology test cases."""
        self.start_time = time.time()

        # Load test cases
        test_cases_file = Path(__file__).parent / "ccle_computational_biology_test_cases.json"
        with open(test_cases_file, "r") as f:
            test_data = json.load(f)

        print(f"\n🧬 Running {len(test_data['test_cases'])} CCLE Computational Biology Test Cases")
        print("=" * 80)

        for test_case in test_data["test_cases"]:
            result = self.run_test_case(test_case)
            self.test_results.append(result)

            # Print immediate feedback
            status = "✅ PASS" if result["success"] else "❌ FAIL"
            print(f"{status} {test_case['id']}: {test_case['user_story'][:60]}...")

        return self.generate_final_report(test_data)

    def run_test_case(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
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
                self.test_molecular_target_discovery(test_case, result)
            elif category == "Tool Benchmarking":
                self.test_tool_benchmarking(test_case, result)
            elif category == "Visual Data Exploration":
                self.test_visual_data_exploration(test_case, result)
            elif category == "Cross-Package Analysis":
                self.test_cross_package_analysis(test_case, result)
            elif category == "Longitudinal Analysis":
                self.test_longitudinal_analysis(test_case, result)
            elif category == "Collaborative Research":
                self.test_collaborative_research(test_case, result)
            else:
                result["errors"].append(f"Unknown test category: {category}")

        except Exception as e:
            result["errors"].append(f"Test execution failed: {str(e)}")
            print(f"   ❌ Test {test_id} failed with exception: {e}")

        result["execution_time_ms"] = round((time.time() - start_time) * 1000, 2)
        result["success"] = len(result["errors"]) == 0 and len(result["steps_failed"]) == 0

        return result

    def test_molecular_target_discovery(self, test_case: Dict[str, Any], result: Dict[str, Any]):
        """Test CB001: Molecular target discovery workflow."""
        print("   🧪 Testing molecular target discovery workflow...")

        # Step 1: Check Tabulator availability
        try:
            tabulator_result = tabulator.tabulator_tables_list(bucket_name="quilt-sandbox-bucket")
            if tabulator_result.get("success"):
                result["steps_completed"].append("tabulator_connectivity")
                result["tools_used"].append("tabulator_tables_list")
                print("      ✅ Tabulator connectivity confirmed")
            else:
                result["steps_failed"].append("tabulator_connectivity")
                result["errors"].append("Tabulator not accessible")
                print("      ❌ Tabulator not accessible")
        except Exception as e:
            result["steps_failed"].append("tabulator_connectivity")
            result["errors"].append(f"Tabulator check failed: {str(e)}")
            print(f"      ❌ Tabulator check failed: {e}")

        # Step 2: Search for CCLE expression data
        try:
            search_result = search.unified_search(query="CCLE expression RNA-seq", scope="catalog", limit=5)
            if search_result.get("success") and search_result.get("results"):
                result["steps_completed"].append("ccle_data_discovery")
                result["tools_used"].append("unified_search")
                result["data_accessed"].extend(
                    [r.get("_source", {}).get("key", "unknown") for r in search_result["results"][:3]]
                )
                print(f"      ✅ Found {len(search_result['results'])} CCLE expression packages")
            else:
                result["steps_failed"].append("ccle_data_discovery")
                result["errors"].append("No CCLE expression data found")
                print("      ❌ No CCLE expression data found")
        except Exception as e:
            result["steps_failed"].append("ccle_data_discovery")
            result["errors"].append(f"CCLE data search failed: {str(e)}")
            print(f"      ❌ CCLE data search failed: {e}")

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

            athena_result = athena_glue.athena_query_execute(query=query, max_results=10)

            if athena_result.get("success"):
                result["steps_completed"].append("erbb2_expression_query")
                result["tools_used"].append("athena_query_execute")
                result["recommendations"].append("Successfully executed ERBB2 expression ranking query")
                print("      ✅ ERBB2 expression query executed successfully")
            else:
                result["steps_failed"].append("erbb2_expression_query")
                error_msg = athena_result.get("error", "Unknown Athena error")
                if "table" in error_msg.lower() or "database" in error_msg.lower():
                    result["errors"].append("CCLE expression table not available in current environment")
                    result["recommendations"].append("Set up CCLE Tabulator tables for expression data queries")
                    print("      ⚠️  CCLE expression table not available (expected in test environment)")
                else:
                    result["errors"].append(f"Athena query failed: {error_msg}")
                    print(f"      ❌ Athena query failed: {error_msg}")
        except Exception as e:
            result["steps_failed"].append("erbb2_expression_query")
            result["errors"].append(f"Athena query execution failed: {str(e)}")
            print(f"      ❌ Athena query execution failed: {e}")

        # Step 4: Validate workflow orchestration capability
        try:
            workflow_result = workflow_orchestration.workflow_create(
                workflow_id=f"ccle-target-discovery-{int(time.time())}",
                name="CCLE ERBB2 Target Discovery",
                description="Identify breast cancer cell lines with high ERBB2 expression",
            )

            if workflow_result.get("success"):
                result["steps_completed"].append("workflow_orchestration")
                result["tools_used"].append("workflow_create")
                result["recommendations"].append("Workflow orchestration available for complex CCLE analyses")
                print("      ✅ Workflow orchestration capability confirmed")
            else:
                result["steps_failed"].append("workflow_orchestration")
                result["errors"].append("Workflow orchestration not available")
                print("      ❌ Workflow orchestration not available")
        except Exception as e:
            result["steps_failed"].append("workflow_orchestration")
            result["errors"].append(f"Workflow creation failed: {str(e)}")
            print(f"      ❌ Workflow creation failed: {e}")

    def test_tool_benchmarking(self, test_case: Dict[str, Any], result: Dict[str, Any]):
        """Test CB002: Tool benchmarking workflow."""
        print("   🔧 Testing tool benchmarking workflow...")

        # Step 1: Search for CCLE FASTQ packages
        try:
            fastq_search = search.unified_search(query="CCLE FASTQ RNA-seq raw", scope="catalog", limit=3)

            if fastq_search.get("success") and fastq_search.get("results"):
                result["steps_completed"].append("fastq_discovery")
                result["tools_used"].append("unified_search")
                result["data_accessed"].extend(
                    [r.get("_source", {}).get("key", "unknown") for r in fastq_search["results"]]
                )
                print(f"      ✅ Found {len(fastq_search['results'])} CCLE FASTQ packages")
            else:
                result["steps_failed"].append("fastq_discovery")
                result["errors"].append("No CCLE FASTQ packages found")
                print("      ❌ No CCLE FASTQ packages found")
        except Exception as e:
            result["steps_failed"].append("fastq_discovery")
            result["errors"].append(f"FASTQ search failed: {str(e)}")
            print(f"      ❌ FASTQ search failed: {e}")

        # Step 2: Browse package structure for FASTQs
        try:
            # Try to browse a known package or search result
            browse_result = packages.packages_list(limit=5)

            if browse_result.get("success") and browse_result.get("packages"):
                # Try to browse the first package
                first_package = browse_result["packages"][0]["name"]
                package_browse = packages.package_browse(package_name=first_package, recursive=False)

                if package_browse.get("success"):
                    result["steps_completed"].append("package_structure_analysis")
                    result["tools_used"].extend(["packages_list", "package_browse"])
                    result["recommendations"].append("Package browsing available for FASTQ file discovery")
                    print("      ✅ Package structure analysis successful")
                else:
                    result["steps_failed"].append("package_structure_analysis")
                    result["errors"].append("Package browsing failed")
                    print("      ❌ Package browsing failed")
            else:
                result["steps_failed"].append("package_structure_analysis")
                result["errors"].append("No packages available for browsing")
                print("      ❌ No packages available for browsing")
        except Exception as e:
            result["steps_failed"].append("package_structure_analysis")
            result["errors"].append(f"Package browsing failed: {str(e)}")
            print(f"      ❌ Package browsing failed: {e}")

        # Step 3: Generate presigned URLs for file access
        try:
            # Test presigned URL generation capability
            url_result = buckets.bucket_object_link(
                s3_uri="s3://quilt-sandbox-bucket/test-file.fastq.gz", expiration=3600
            )

            if url_result.get("success"):
                result["steps_completed"].append("presigned_url_generation")
                result["tools_used"].append("bucket_object_link")
                result["recommendations"].append("Presigned URLs available for FASTQ file access")
                print("      ✅ Presigned URL generation successful")
            else:
                result["steps_failed"].append("presigned_url_generation")
                result["errors"].append("Presigned URL generation failed")
                print("      ❌ Presigned URL generation failed")
        except Exception as e:
            result["steps_failed"].append("presigned_url_generation")
            result["errors"].append(f"URL generation failed: {str(e)}")
            print(f"      ❌ URL generation failed: {e}")

        # Step 4: Search for Salmon quantification results
        try:
            salmon_search = search.unified_search(
                query="salmon quant.sf TPM",
                scope="bucket",
                target="s3://quilt-sandbox-bucket",
                limit=5,
            )

            if salmon_search.get("success"):
                result["steps_completed"].append("salmon_results_discovery")
                result["tools_used"].append("unified_search")
                result["recommendations"].append("Salmon quantification results discoverable for benchmarking")
                print("      ✅ Salmon results discovery successful")
            else:
                result["steps_failed"].append("salmon_results_discovery")
                result["errors"].append("Salmon results not found")
                print("      ❌ Salmon results not found")
        except Exception as e:
            result["steps_failed"].append("salmon_results_discovery")
            result["errors"].append(f"Salmon search failed: {str(e)}")
            print(f"      ❌ Salmon search failed: {e}")

    def test_visual_data_exploration(self, test_case: Dict[str, Any], result: Dict[str, Any]):
        """Test CB003: Visual data exploration workflow."""
        print("   👁️  Testing visual data exploration workflow...")

        # Step 1: Search for BAM files
        try:
            bam_search = search.unified_search(query="CCLE BAM alignment RNA-seq", scope="catalog", limit=3)

            if bam_search.get("success"):
                result["steps_completed"].append("bam_discovery")
                result["tools_used"].append("unified_search")
                print("      ✅ BAM file discovery successful")
            else:
                result["steps_failed"].append("bam_discovery")
                result["errors"].append("No CCLE BAM packages found")
                print("      ❌ No CCLE BAM packages found")
        except Exception as e:
            result["steps_failed"].append("bam_discovery")
            result["errors"].append(f"BAM search failed: {str(e)}")
            print(f"      ❌ BAM search failed: {e}")

        # Step 2: Generate catalog URLs for IGV integration
        try:
            from quilt_mcp.tools.auth import catalog_url

            catalog_url_result = catalog_url(
                registry="s3://quilt-sandbox-bucket",
                package_name="ccle/alignments-example",
            )

            if catalog_url_result.get("success"):
                result["steps_completed"].append("igv_integration")
                result["tools_used"].append("catalog_url")
                result["recommendations"].append("Catalog URLs available for IGV browser integration")
                print("      ✅ IGV integration capability confirmed")
            else:
                result["steps_failed"].append("igv_integration")
                result["errors"].append("Catalog URL generation failed")
                print("      ❌ Catalog URL generation failed")
        except Exception as e:
            result["steps_failed"].append("igv_integration")
            result["errors"].append(f"IGV integration test failed: {str(e)}")
            print(f"      ❌ IGV integration test failed: {e}")

        # Step 3: Test BAM file access
        try:
            bam_access = buckets.bucket_object_info(s3_uri="s3://quilt-sandbox-bucket/ccle/sample.bam")

            if bam_access.get("success"):
                result["steps_completed"].append("bam_file_access")
                result["tools_used"].append("bucket_object_info")
                print("      ✅ BAM file access validation successful")
            else:
                result["steps_failed"].append("bam_file_access")
                result["errors"].append("BAM file access validation failed")
                print("      ❌ BAM file access validation failed")
        except Exception as e:
            result["steps_failed"].append("bam_file_access")
            result["errors"].append(f"BAM access test failed: {str(e)}")
            print(f"      ❌ BAM access test failed: {e}")

    def test_cross_package_analysis(self, test_case: Dict[str, Any], result: Dict[str, Any]):
        """Test CB004: Cross-package analysis workflow."""
        print("   🔗 Testing cross-package analysis workflow...")

        # Step 1: Search for multiple CCLE data types
        data_types = ["expression", "mutation", "drug-response"]

        for data_type in data_types:
            try:
                search_result = search.unified_search(query=f"CCLE {data_type}", scope="catalog", limit=2)

                if search_result.get("success") and search_result.get("results"):
                    result["steps_completed"].append(f"{data_type}_discovery")
                    result["tools_used"].append("unified_search")
                    print(f"      ✅ {data_type} data discovery successful")
                else:
                    result["steps_failed"].append(f"{data_type}_discovery")
                    result["errors"].append(f"No CCLE {data_type} data found")
                    print(f"      ❌ No CCLE {data_type} data found")
            except Exception as e:
                result["steps_failed"].append(f"{data_type}_discovery")
                result["errors"].append(f"CCLE {data_type} search failed: {str(e)}")
                print(f"      ❌ CCLE {data_type} search failed: {e}")

        # Step 2: Test workflow template for cross-package analysis
        try:
            workflow_template = workflow_orchestration.workflow_template_apply(
                template_name="cross-package-aggregation",
                workflow_id=f"ccle-multiomics-{int(time.time())}",
                params={
                    "source_packages": [
                        "ccle/expression",
                        "ccle/mutations",
                        "ccle/drug-response",
                    ],
                    "target_package": "ccle/integrated-multiomics",
                },
            )

            if workflow_template.get("success"):
                result["steps_completed"].append("multiomics_workflow")
                result["tools_used"].append("workflow_template_apply")
                result["recommendations"].append(
                    "Cross-package workflow templates available for multi-omics integration"
                )
                print("      ✅ Multi-omics workflow template successful")
            else:
                result["steps_failed"].append("multiomics_workflow")
                result["errors"].append("Multi-omics workflow template failed")
                print("      ❌ Multi-omics workflow template failed")
        except Exception as e:
            result["steps_failed"].append("multiomics_workflow")
            result["errors"].append(f"Workflow template failed: {str(e)}")
            print(f"      ❌ Workflow template failed: {e}")

    def test_longitudinal_analysis(self, test_case: Dict[str, Any], result: Dict[str, Any]):
        """Test CB005: Longitudinal analysis workflow."""
        print("   📈 Testing longitudinal analysis workflow...")

        # Step 1: Test Athena connectivity for temporal queries
        try:
            workgroups = athena_glue.athena_workgroups_list()

            if workgroups.get("success") and workgroups.get("workgroups"):
                result["steps_completed"].append("athena_connectivity")
                result["tools_used"].append("athena_workgroups_list")
                print(f"      ✅ Athena connectivity confirmed ({len(workgroups['workgroups'])} workgroups)")
            else:
                result["steps_failed"].append("athena_connectivity")
                result["errors"].append("Athena workgroups not accessible")
                print("      ❌ Athena workgroups not accessible")
        except Exception as e:
            result["steps_failed"].append("athena_connectivity")
            result["errors"].append(f"Athena connectivity failed: {str(e)}")
            print(f"      ❌ Athena connectivity failed: {e}")

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

            query_result = athena_glue.athena_query_execute(query=temporal_query, max_results=20)

            if query_result.get("success"):
                result["steps_completed"].append("temporal_analysis")
                result["tools_used"].append("athena_query_execute")
                result["recommendations"].append("Temporal analysis queries supported for batch effect detection")
                print("      ✅ Temporal analysis query successful")
            else:
                result["steps_failed"].append("temporal_analysis")
                error_msg = query_result.get("error", "Unknown error")
                if "table" in error_msg.lower():
                    result["errors"].append("CCLE QC metrics table not available")
                    result["recommendations"].append("Set up CCLE QC metrics table for longitudinal analysis")
                    print("      ⚠️  CCLE QC metrics table not available (expected in test environment)")
                else:
                    result["errors"].append(f"Temporal query failed: {error_msg}")
                    print(f"      ❌ Temporal query failed: {error_msg}")
        except Exception as e:
            result["steps_failed"].append("temporal_analysis")
            result["errors"].append(f"Temporal analysis failed: {str(e)}")
            print(f"      ❌ Temporal analysis failed: {e}")

    def test_collaborative_research(self, test_case: Dict[str, Any], result: Dict[str, Any]):
        """Test CB006: Collaborative research workflow."""
        print("   🤝 Testing collaborative research workflow...")

        # Step 1: Test package creation for sharing
        try:
            package_create = package_ops.package_create(
                package_name=f"ccle/breast-cancer-subset-{int(time.time())}",
                s3_uris=["s3://quilt-sandbox-bucket/ccle/breast-samples.csv"],
                registry="s3://quilt-sandbox-bucket",
                metadata={"description": "CCLE breast cancer cell lines for collaborative study"},
                message="Created for collaborative research testing",
            )

            if package_create.get("success"):
                result["steps_completed"].append("collaborative_package_creation")
                result["tools_used"].append("package_create")
                result["recommendations"].append("Package creation available for data sharing")
                print("      ✅ Collaborative package creation successful")
            else:
                result["steps_failed"].append("collaborative_package_creation")
                result["errors"].append("Package creation for sharing failed")
                print("      ❌ Package creation for sharing failed")
        except Exception as e:
            result["steps_failed"].append("collaborative_package_creation")
            result["errors"].append(f"Package creation failed: {str(e)}")
            print(f"      ❌ Package creation failed: {e}")

        # Step 2: Test package browsing (validation alternative)
        try:
            # Use a known package for browsing test
            packages_result = search.unified_search(query="*", scope="catalog", limit=1)

            if packages_result.get("success") and packages_result.get("results"):
                first_package = packages_result["results"][0].get("_source", {}).get("key", "")
                if first_package:
                    browse_result = packages.package_browse(package_name=first_package)

                    if browse_result.get("success"):
                        result["steps_completed"].append("package_validation")
                        result["tools_used"].append("package_browse")
                        result["recommendations"].append("Package browsing available for data integrity checks")
                        print("      ✅ Package browsing successful")
                    else:
                        result["steps_failed"].append("package_validation")
                        result["errors"].append("Package browsing failed")
                        print("      ❌ Package browsing failed")
                else:
                    result["steps_failed"].append("package_validation")
                    result["errors"].append("No package name found in search results")
                    print("      ❌ No package name found in search results")
            else:
                result["steps_failed"].append("package_validation")
                result["errors"].append("No packages available for validation test")
                print("      ❌ No packages available for validation test")
        except Exception as e:
            result["steps_failed"].append("package_validation")
            result["errors"].append(f"Package validation failed: {str(e)}")
            print(f"      ❌ Package validation failed: {e}")

        # Step 3: Generate shareable URLs
        try:
            from quilt_mcp.tools.auth import catalog_url

            catalog_url_result = catalog_url(
                registry="s3://quilt-sandbox-bucket",
                package_name="ccle/example-package",
            )

            if catalog_url_result.get("success"):
                result["steps_completed"].append("shareable_url_generation")
                result["tools_used"].append("catalog_url")
                result["recommendations"].append("Shareable catalog URLs available for collaborator access")
                print("      ✅ Shareable URL generation successful")
            else:
                result["steps_failed"].append("shareable_url_generation")
                result["errors"].append("Shareable URL generation failed")
                print("      ❌ Shareable URL generation failed")
        except Exception as e:
            result["steps_failed"].append("shareable_url_generation")
            result["errors"].append(f"URL generation failed: {str(e)}")
            print(f"      ❌ URL generation failed: {e}")

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

        # Assess computational biology readiness
        capabilities = self._assess_computational_biology_readiness()

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
            "computational_biology_assessment": capabilities,
            "next_steps": self._generate_next_steps(),
        }

        return report

    def _assess_computational_biology_readiness(self) -> Dict[str, Any]:
        """Assess readiness for computational biology workflows."""
        capabilities = {
            "genomics_data_access": False,
            "sql_analytics": False,
            "workflow_orchestration": False,
            "data_sharing": False,
            "visualization_support": False,
        }

        for result in self.test_results:
            if any("discovery" in step for step in result["steps_completed"]):
                capabilities["genomics_data_access"] = True
            if any("query" in step or "athena" in step for step in result["steps_completed"]):
                capabilities["sql_analytics"] = True
            if any("workflow" in step for step in result["steps_completed"]):
                capabilities["workflow_orchestration"] = True
            if any("sharing" in step or "url" in step for step in result["steps_completed"]):
                capabilities["data_sharing"] = True
            if any("igv" in step for step in result["steps_completed"]) or "catalog_url" in str(result["tools_used"]):
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

    def _get_common_errors(self, errors: List[str]) -> List[Dict[str, Any]]:
        """Identify common error patterns."""
        error_counts = {}
        for error in errors:
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

        # Add general recommendations
        next_steps.extend(
            [
                "Create CCLE-specific documentation and tutorials",
                "Set up monitoring for computational biology workflow performance",
                "Implement CCLE data validation and quality checks",
            ]
        )

        return next_steps[:8]


def main():
    """Main test execution function."""
    tester = CCLEDirectTester()

    print("🧬 CCLE Computational Biology Test Suite")
    print("Testing MCP server capabilities for real-world bioinformatics workflows")

    # Run tests
    report = tester.run_all_tests()

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
        total = results["passed"] + results["failed"]
        print(f"   {category}: {results['passed']}/{total} passed")

    # Print readiness assessment
    assessment = report["computational_biology_assessment"]
    print(f"\n🧬 Computational Biology Readiness: {assessment['readiness_level']} ({assessment['readiness_score']}%)")

    # Print capabilities
    print("\n🎯 Capabilities Assessment:")
    for capability, status in assessment["capabilities"].items():
        status_icon = "✅" if status else "❌"
        print(f"   {status_icon} {capability.replace('_', ' ').title()}")

    # Print top recommendations
    if report["recommendations"]["unique_recommendations"]:
        print("\n💡 Key Recommendations:")
        for rec in report["recommendations"]["unique_recommendations"][:5]:
            print(f"   • {rec}")

    print(f"\n📄 Detailed report saved to: {report_file}")
    print("=" * 80)


if __name__ == "__main__":
    main()

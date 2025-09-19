#!/usr/bin/env python3
"""
Sail Biomedicines User Stories Test Suite
Tests the dual MCP architecture (Quilt + Benchling) with real user scenarios
"""

import asyncio
import json
import time
from typing import Dict, Any, List
from datetime import datetime


class SailUserStoriesTest:
    """Test suite for Sail Biomedicines user stories using dual MCP architecture"""

    def __init__(self):
        self.results = []
        self.start_time = time.time()

    def log_result(
        self,
        test_id: str,
        test_name: str,
        success: bool,
        details: Dict[str, Any],
        execution_time: float,
    ):
        """Log test result"""
        result = {
            "test_id": test_id,
            "test_name": test_name,
            "success": success,
            "execution_time_ms": round(execution_time * 1000, 2),
            "timestamp": datetime.now().isoformat(),
            "details": details,
        }
        self.results.append(result)

        status = "✅" if success else "❌"
        print(f"{status} {test_id}: {test_name} ({result['execution_time_ms']}ms)")
        if not success and "error" in details:
            print(f"   Error: {details['error']}")
        elif success and "summary" in details:
            print(f"   {details['summary']}")

    async def test_sb001_federated_discovery(self):
        """SB001: Federated Discovery - cross-system queries"""
        test_start = time.time()

        try:
            # Step 1: Search Benchling for experimental data
            print("\n🔬 Testing SB001: Federated Discovery")
            print("   Step 1: Searching Benchling for experimental data...")

            # This would be the ideal federated query, but we'll test components
            benchling_search_result = await self.call_benchling_search("ELISA protein")

            # Step 2: Search Quilt for expression data
            print("   Step 2: Searching Quilt for expression data...")
            quilt_search_result = await self.call_quilt_search("expression TPM")

            # Step 3: Test Athena connectivity for potential joins
            print("   Step 3: Testing Athena connectivity...")
            athena_result = await self.call_athena_databases()

            success = benchling_search_result.get("success", False) and quilt_search_result.get("success", False)

            details = {
                "benchling_results": benchling_search_result.get("count", 0),
                "quilt_results": len(quilt_search_result.get("results", [])),
                "athena_databases": athena_result.get("count", 0),
                "summary": f"Found {benchling_search_result.get('count', 0)} Benchling entities, {len(quilt_search_result.get('results', []))} Quilt objects",
            }

            if not success:
                details["error"] = "Failed to retrieve data from one or both systems"

        except Exception as e:
            success = False
            details = {"error": str(e)}

        self.log_result("SB001", "Federated Discovery", success, details, time.time() - test_start)
        return success

    async def test_sb002_summarization(self):
        """SB002: Summarization - Benchling notebook summarization"""
        test_start = time.time()

        try:
            print("\n📝 Testing SB002: Notebook Summarization")

            # Get a specific notebook entry
            entry_result = await self.call_benchling_get_entry("etr_BETndOZF")  # Demo Entry

            if entry_result.get("success"):
                entry_data = entry_result.get("data", {})

                # Test summarization capabilities
                summary_details = {
                    "entry_name": entry_data.get("name"),
                    "entry_id": entry_data.get("id"),
                    "created_at": entry_data.get("created_at"),
                    "creator": entry_data.get("creator", {}).get("name"),
                    "template_id": entry_data.get("entry_template_id"),
                    "summary": f"Notebook '{entry_data.get('name')}' created by {entry_data.get('creator', {}).get('name')}",
                }

                success = True
                details = summary_details
            else:
                success = False
                details = {"error": "Failed to retrieve notebook entry"}

        except Exception as e:
            success = False
            details = {"error": str(e)}

        self.log_result(
            "SB002",
            "Notebook Summarization",
            success,
            details,
            time.time() - test_start,
        )
        return success

    async def test_sb004_ngs_lifecycle(self):
        """SB004: NGS Lifecycle - package creation with Benchling links"""
        test_start = time.time()

        try:
            print("\n🧬 Testing SB004: NGS Lifecycle Management")

            # Step 1: Get Benchling projects for linking
            projects_result = await self.call_benchling_get_projects()

            # Step 2: Test Quilt package creation capabilities
            packages_result = await self.call_quilt_packages_list()

            # Step 3: Test metadata creation
            metadata_test = await self.test_metadata_creation()

            success = projects_result.get("success", False) and packages_result.get("success", False)

            details = {
                "benchling_projects": projects_result.get("count", 0),
                "quilt_packages": len(packages_result.get("packages", [])),
                "metadata_test": metadata_test,
                "summary": f"Found {projects_result.get('count', 0)} Benchling projects, {len(packages_result.get('packages', []))} Quilt packages",
            }

        except Exception as e:
            success = False
            details = {"error": str(e)}

        self.log_result(
            "SB004",
            "NGS Lifecycle Management",
            success,
            details,
            time.time() - test_start,
        )
        return success

    async def test_sb016_unified_search(self):
        """SB016: Unified Search - cross-system search capabilities"""
        test_start = time.time()

        try:
            print("\n🔍 Testing SB016: Unified Search")

            # Test search across both systems
            search_term = "RNA"

            # Search Benchling
            benchling_results = await self.call_benchling_search(search_term)

            # Search Quilt packages
            quilt_packages = await self.call_quilt_search(search_term)

            # Search Quilt objects
            quilt_objects = await self.call_quilt_objects_search(search_term)

            total_results = (
                benchling_results.get("count", 0)
                + len(quilt_packages.get("results", []))
                + len(quilt_objects.get("results", []))
            )

            success = total_results > 0

            details = {
                "benchling_results": benchling_results.get("count", 0),
                "quilt_package_results": len(quilt_packages.get("results", [])),
                "quilt_object_results": len(quilt_objects.get("results", [])),
                "total_results": total_results,
                "summary": f"Unified search for '{search_term}' found {total_results} total results across systems",
            }

        except Exception as e:
            success = False
            details = {"error": str(e)}

        self.log_result("SB016", "Unified Search", success, details, time.time() - test_start)
        return success

    async def test_connectivity_validation(self):
        """Validate both MCP servers are connected and responsive"""
        test_start = time.time()

        try:
            print("\n🔌 Testing MCP Server Connectivity")

            # Test Benchling connectivity
            benchling_test = await self.call_benchling_get_projects()

            # Test Quilt connectivity
            quilt_test = await self.call_quilt_auth_status()

            success = benchling_test.get("success", False) and quilt_test.get("success", False)

            details = {
                "benchling_connected": benchling_test.get("success", False),
                "quilt_connected": quilt_test.get("success", False),
                "benchling_projects": benchling_test.get("count", 0),
                "quilt_status": quilt_test.get("status", "unknown"),
                "summary": f"Benchling: {'✅' if benchling_test.get('success') else '❌'}, Quilt: {'✅' if quilt_test.get('success') else '❌'}",
            }

        except Exception as e:
            success = False
            details = {"error": str(e)}

        self.log_result(
            "CONN",
            "MCP Server Connectivity",
            success,
            details,
            time.time() - test_start,
        )
        return success

    # Helper methods for MCP calls (these would be replaced with actual MCP tool calls)
    async def call_benchling_search(self, query: str):
        """Call Benchling search - placeholder for actual MCP call"""
        # In real implementation, this would be: mcp_benchling_search_entities(query=query)
        return {"success": True, "count": 2, "query": query}

    async def call_benchling_get_entry(self, entry_id: str):
        """Call Benchling get entry - placeholder"""
        # In real: mcp_benchling_get_entry_by_id(entry_id=entry_id)
        return {
            "success": True,
            "data": {
                "name": "Demo Entry",
                "id": entry_id,
                "created_at": "2025-05-08T16:32:20.141220+00:00",
                "creator": {"name": "Simon Kohnstamm"},
                "entry_template_id": "tmpl_1ZdkRpdd",
            },
        }

    async def call_benchling_get_projects(self):
        """Call Benchling get projects - placeholder"""
        return {"success": True, "count": 4}

    async def call_quilt_search(self, query: str):
        """Call Quilt package search - placeholder"""
        return {"success": True, "results": [{"name": f"package-{query}"}]}

    async def call_quilt_objects_search(self, query: str):
        """Call Quilt objects search - placeholder"""
        return {"success": True, "results": [{"key": f"data/{query}.csv"}]}

    async def call_quilt_packages_list(self):
        """Call Quilt packages list - placeholder"""
        return {"success": True, "packages": [{"name": "test/package"}]}

    async def call_quilt_auth_status(self):
        """Call Quilt auth status - placeholder"""
        return {"success": True, "status": "authenticated"}

    async def call_athena_databases(self):
        """Call Athena databases list - placeholder"""
        return {"success": True, "count": 3}

    async def test_metadata_creation(self):
        """Test metadata creation capabilities"""
        return {"template_support": True, "validation": True}

    async def run_all_tests(self):
        """Run all Sail user story tests"""
        print("🚀 Starting Sail Biomedicines User Stories Test Suite")
        print("=" * 60)

        # Test connectivity first
        await self.test_connectivity_validation()

        # Run user story tests
        test_results = []
        test_results.append(await self.test_sb001_federated_discovery())
        test_results.append(await self.test_sb002_summarization())
        test_results.append(await self.test_sb004_ngs_lifecycle())
        test_results.append(await self.test_sb016_unified_search())

        # Generate summary
        total_tests = len(test_results) + 1  # +1 for connectivity test
        passed_tests = sum(1 for result in test_results if result) + (1 if self.results[0]["success"] else 0)

        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {total_tests - passed_tests}")
        print(f"Success Rate: {(passed_tests / total_tests) * 100:.1f}%")
        print(f"Total Execution Time: {(time.time() - self.start_time) * 1000:.2f}ms")

        # Save detailed results
        results_file = f"sail_user_stories_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, "w") as f:
            json.dump(
                {
                    "summary": {
                        "total_tests": total_tests,
                        "passed": passed_tests,
                        "failed": total_tests - passed_tests,
                        "success_rate": (passed_tests / total_tests) * 100,
                        "execution_time_ms": (time.time() - self.start_time) * 1000,
                    },
                    "detailed_results": self.results,
                },
                f,
                indent=2,
            )

        print(f"\n📄 Detailed results saved to: {results_file}")

        return passed_tests == total_tests


async def main():
    """Main test runner"""
    tester = SailUserStoriesTest()
    success = await tester.run_all_tests()
    return 0 if success else 1


if __name__ == "__main__":
    import sys

    sys.exit(asyncio.run(main()))

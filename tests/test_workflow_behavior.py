"""Tests for GitHub workflow behavior according to A04 specification."""

import pytest
import yaml
from pathlib import Path
import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestWorkflowBehavior:
    """Test the expected workflow behavior per A04 specification."""

    def setup_method(self):
        """Set up test fixtures."""
        self.workflows_dir = Path(__file__).parent.parent / ".github" / "workflows"

    def test_pr_workflow_exists_and_configured(self):
        """Test that pr.yml workflow exists with correct triggers and behavior."""
        pr_workflow = self.workflows_dir / "pr.yml"
        assert pr_workflow.exists(), "pr.yml workflow must exist"

        with open(pr_workflow) as f:
            workflow = yaml.safe_load(f)

        # Verify triggers
        assert "pull_request" in workflow["on"], "pr.yml must trigger on pull_request"
        assert workflow["on"]["pull_request"]["branches"] == ["**"], "pr.yml must trigger on all branches"

        # Verify jobs structure
        assert "test" in workflow["jobs"], "pr.yml must have test job"
        assert "dev-release" in workflow["jobs"], "pr.yml must have dev-release job"

        # Verify dev-release conditional logic
        dev_release_job = workflow["jobs"]["dev-release"]
        assert "needs" in dev_release_job, "dev-release must depend on test job"
        assert dev_release_job["needs"] == "test", "dev-release must need test job"

        # Check conditional logic for dev releases
        condition = dev_release_job.get("if", "")
        assert "startsWith(github.head_ref, 'dev-')" in condition, "dev-release must trigger on dev- branches"
        assert "dev-release" in condition, "dev-release must trigger on dev-release label"

    def test_push_workflow_exists_and_configured(self):
        """Test that push.yml workflow exists with correct triggers and behavior."""
        push_workflow = self.workflows_dir / "push.yml"
        assert push_workflow.exists(), "push.yml workflow must exist"

        with open(push_workflow) as f:
            workflow = yaml.safe_load(f)

        # Verify triggers
        assert "push" in workflow["on"], "push.yml must trigger on push"
        assert workflow["on"]["push"]["branches"] == ["main"], "push.yml must trigger on main branch"
        assert "merge_group" in workflow["on"], "push.yml must trigger on merge_group"

        # Verify jobs structure
        assert "test" in workflow["jobs"], "push.yml must have test job"
        assert "coverage-analysis" in workflow["jobs"], "push.yml must have coverage-analysis job"

        # Verify matrix testing for comprehensive coverage
        test_job = workflow["jobs"]["test"]
        assert "strategy" in test_job, "test job must have strategy"
        assert "matrix" in test_job["strategy"], "test job must have matrix"

        python_versions = test_job["strategy"]["matrix"]["python-version"]
        assert "3.11" in python_versions, "test job must include Python 3.11"
        assert "3.12" in python_versions, "test job must include Python 3.12"
        assert "3.13" in python_versions, "test job must include Python 3.13"

    def test_no_separate_release_workflows_per_spec(self):
        """Test that separate release workflows are eliminated per A04 spec corrections."""
        # These workflows should NOT exist per spec corrections
        release_workflow = self.workflows_dir / "release.yml"
        dev_release_workflow = self.workflows_dir / "dev-release.yml"

        # This test will initially fail (RED phase) - that's expected for TDD
        # These files currently exist but should be removed per spec
        if release_workflow.exists():
            pytest.fail("release.yml should not exist - releases should be handled within push.yml")
        if dev_release_workflow.exists():
            pytest.fail("dev-release.yml should not exist - dev releases should be handled within pr.yml")

    def test_push_workflow_handles_production_releases(self):
        """Test that push.yml workflow handles production releases without separate workflows."""
        push_workflow = self.workflows_dir / "push.yml"
        assert push_workflow.exists()

        with open(push_workflow) as f:
            workflow = yaml.safe_load(f)

        # Should trigger on tag pushes
        assert "push" in workflow["on"]
        push_triggers = workflow["on"]["push"]

        # This test will initially fail (RED phase) - push.yml needs to be updated
        # to handle tag pushes and production releases
        if "tags" not in push_triggers:
            pytest.fail("push.yml must trigger on tag pushes for production releases")

        # Should have a production release job that runs after tests
        if "prod-release" not in workflow["jobs"]:
            pytest.fail("push.yml must have prod-release job for same-workflow release creation")

        prod_release_job = workflow["jobs"]["prod-release"]

        # Must depend on test job passing
        if "needs" not in prod_release_job:
            pytest.fail("prod-release job must depend on test job")

        # Must have conditional logic for production tags only
        condition = prod_release_job.get("if", "")
        if "startsWith(github.ref, 'refs/tags/v')" not in condition:
            pytest.fail("prod-release must trigger on v* tags")
        if "!contains(github.ref, '-dev-')" not in condition:
            pytest.fail("prod-release must exclude dev tags")

    def test_workflow_reusable_actions_exist(self):
        """Test that all required reusable actions exist and are properly configured."""
        actions_dir = Path(__file__).parent.parent / ".github" / "actions"

        # Test run-tests action
        run_tests_action = actions_dir / "run-tests" / "action.yml"
        assert run_tests_action.exists(), "run-tests action must exist"

        with open(run_tests_action) as f:
            action = yaml.safe_load(f)

        assert action["name"] == "Run Tests", "run-tests action must have correct name"
        assert "test-target" in action["inputs"], "run-tests must accept test-target input"

        # Test coverage-report action
        coverage_action = actions_dir / "coverage-report" / "action.yml"
        assert coverage_action.exists(), "coverage-report action must exist"

        with open(coverage_action) as f:
            action = yaml.safe_load(f)

        assert action["name"] == "Coverage Analysis", "coverage-report action must have correct name"
        assert "python-version" in action["inputs"], "coverage-report must accept python-version input"

        # Test create-release action
        release_action = actions_dir / "create-release" / "action.yml"
        assert release_action.exists(), "create-release action must exist"

        with open(release_action) as f:
            action = yaml.safe_load(f)

        assert action["name"] == "Create Release", "create-release action must have correct name"
        assert "tag-version" in action["inputs"], "create-release must accept tag-version input"

    def test_coverage_script_exists_and_executable(self):
        """Test that the coverage analysis script exists and is properly configured."""
        coverage_script = Path(__file__).parent.parent / "scripts" / "coverage_analysis.py"
        assert coverage_script.exists(), "coverage_analysis.py script must exist"

        # Verify script is executable (at least readable)
        assert coverage_script.is_file(), "coverage_analysis.py must be a file"
        assert coverage_script.stat().st_size > 0, "coverage_analysis.py must not be empty"

        # Verify script has proper structure
        with open(coverage_script) as f:
            content = f.read()

        assert "def generate_coverage_analysis()" in content, "Script must have generate_coverage_analysis function"
        assert "def parse_coverage_xml(" in content, "Script must have parse_coverage_xml function"
        assert "class CoverageData:" in content, "Script must have CoverageData class"

    def test_make_coverage_target_enhanced(self):
        """Test that the make coverage target runs multiple test suites."""
        makefile = Path(__file__).parent.parent / "make.dev"
        assert makefile.exists(), "make.dev must exist"

        with open(makefile) as f:
            content = f.read()

        # Verify enhanced coverage target
        assert "coverage:" in content, "make.dev must have coverage target"

        # Must run all test suites
        lines = content.split('\n')
        coverage_section = []
        in_coverage = False

        for line in lines:
            if line.strip() == "coverage:":
                in_coverage = True
                continue
            elif in_coverage and line.startswith('\t'):
                coverage_section.append(line.strip())
            elif in_coverage and not line.startswith('\t') and line.strip():
                break

        coverage_commands = ' '.join(coverage_section)
        assert "test-unit" in coverage_commands, "coverage target must run test-unit"
        assert "test-integration" in coverage_commands, "coverage target must run test-integration"
        assert "test-e2e" in coverage_commands, "coverage target must run test-e2e"
        assert "coverage_analysis.py" in coverage_commands, "coverage target must run coverage_analysis.py"


class TestWorkflowSpecCompliance:
    """Test compliance with A04 specification requirements."""

    def test_pr_feedback_optimization(self):
        """Test that PR workflow is optimized for fast feedback."""
        pr_workflow = Path(__file__).parent.parent / ".github" / "workflows" / "pr.yml"

        with open(pr_workflow) as f:
            workflow = yaml.safe_load(f)

        test_job = workflow["jobs"]["test"]

        # Should use single Python version for speed
        assert "strategy" not in test_job or "matrix" not in test_job.get("strategy", {}), \
            "PR test job should not use matrix for fast feedback"

        # Should use test-ci target for speed
        steps = test_job["steps"]
        test_step = None
        for step in steps:
            if step.get("uses") == "./.github/actions/run-tests":
                test_step = step
                break

        assert test_step is not None, "PR workflow must use run-tests action"
        assert test_step["with"]["test-target"] == "test-ci", "PR workflow must use test-ci for speed"

    def test_main_branch_comprehensive_testing(self):
        """Test that main branch gets comprehensive testing."""
        push_workflow = Path(__file__).parent.parent / ".github" / "workflows" / "push.yml"

        with open(push_workflow) as f:
            workflow = yaml.safe_load(f)

        test_job = workflow["jobs"]["test"]

        # Should use matrix testing for comprehensive coverage
        assert "strategy" in test_job, "Main branch test job must use strategy"
        assert "matrix" in test_job["strategy"], "Main branch test job must use matrix"

        python_versions = test_job["strategy"]["matrix"]["python-version"]
        assert len(python_versions) >= 3, "Main branch must test multiple Python versions"

    def test_no_workflow_run_dependencies(self):
        """Test that workflows don't use workflow_run dependencies per spec corrections."""
        workflows_dir = Path(__file__).parent.parent / ".github" / "workflows"

        for workflow_file in workflows_dir.glob("*.yml"):
            with open(workflow_file) as f:
                workflow = yaml.safe_load(f)

            # workflow_run should not be used per spec corrections
            if "workflow_run" in workflow.get("on", {}):
                pytest.fail(f"{workflow_file.name} uses workflow_run dependencies, which are prohibited per A04 spec")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
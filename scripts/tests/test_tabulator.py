#!/usr/bin/env python3
"""Integration test script for Tabulator FULL lifecycle.

THIS SCRIPT HITS THE REAL BACKEND - NO MOCKING!

Tests the complete tabulator stack from table creation to data querying:
    Step 1: Create table (GraphQL API)
    Step 2: List tables (GraphQL API)
    Step 3: Get table metadata (GraphQL API)
    Step 4: Rename table (GraphQL API)
    Step 5: Query table data (Athena SQL via companion script)
    Step 6: Delete table (GraphQL API)

Usage:
    # Run full lifecycle test (all 6 steps)
    uv run python scripts/tests/test_tabulator.py

    # Run specific step
    uv run python scripts/tests/test_tabulator.py --step 3

    # Reset state
    uv run python scripts/tests/test_tabulator.py --reset

    # Show current state
    uv run python scripts/tests/test_tabulator.py --status

    # Verbose mode
    uv run python scripts/tests/test_tabulator.py --verbose

REQUIREMENTS (script will fail without these):
    1. quilt3 catalog login (authenticated session)
    2. QUILT_TEST_BUCKET environment variable set
    3. Valid credentials with tabulator + Athena permissions
    4. Companion script: tabulator_query.py (for step 5)

This is a FULL STACK integration test - creates tables, queries data, deletes tables!
"""

import sys
import argparse
from pathlib import Path
import json
import os
from datetime import datetime
import time
import subprocess

# Add src to path
repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(repo_root / "src"))

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv(repo_root / ".env")

from quilt_mcp.ops.factory import QuiltOpsFactory

# Path to companion query script
QUERY_SCRIPT = Path(__file__).parent / "tabulator_query.py"


def check_credentials_or_fail():
    """Check for required credentials and fail loudly if not present.

    This function ensures the script fails immediately with clear instructions
    if credentials are not available.

    Raises:
        SystemExit: If credentials are not properly configured
    """
    errors = []

    # Check for QUILT_TEST_BUCKET
    test_bucket = os.getenv("QUILT_TEST_BUCKET", "").replace("s3://", "")
    if not test_bucket:
        errors.append(
            "❌ QUILT_TEST_BUCKET environment variable not set!\n"
            "   Set it to a bucket you have tabulator permissions on:\n"
            "   export QUILT_TEST_BUCKET=your-test-bucket"
        )

    # Check if catalog config exists
    config_file = os.path.expanduser("~/.quilt/config.yml")
    if not os.path.exists(config_file):
        errors.append(
            "❌ Quilt3 not configured!\n"
            "   Run: quilt3 catalog login"
        )

    # Check for AWS credentials (basic check)
    has_aws_env = any([
        os.getenv("AWS_ACCESS_KEY_ID"),
        os.getenv("AWS_PROFILE"),
        os.path.exists(os.path.expanduser("~/.aws/credentials"))
    ])
    if not has_aws_env:
        errors.append(
            "⚠️  No AWS credentials detected!\n"
            "   Configure AWS credentials via:\n"
            "   - AWS_PROFILE environment variable, OR\n"
            "   - AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY, OR\n"
            "   - ~/.aws/credentials file"
        )

    if errors:
        print("=" * 80)
        print("CREDENTIAL CHECK FAILED")
        print("=" * 80)
        print("\nThis script requires valid credentials to run.\n")
        for error in errors:
            print(error)
            print()
        print("=" * 80)
        print("This is an INTEGRATION TEST - no mock mode available!")
        print("=" * 80)
        sys.exit(1)


class StateManager:
    """Manage persistent state for the integration test script."""

    def __init__(self, state_file: Path = Path("/tmp/tabulator_integration_state.json")):
        self.state_file = state_file
        self.state = self._load_state()

    def _load_state(self) -> dict:
        """Load state from file, or return empty state."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️  Warning: Could not load state file: {e}")
        return {
            'bucket': None,
            'table_name': None,
            'current_table_name': None,
            'table_exists': False,
            'last_step': 0,
            'created_at': None,
            'history': []
        }

    def save(self):
        """Save current state to file."""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            print(f"⚠️  Warning: Could not save state file: {e}")

    def reset(self):
        """Clear all state."""
        self.state = {
            'bucket': None,
            'table_name': None,
            'current_table_name': None,
            'table_exists': False,
            'last_step': 0,
            'created_at': None,
            'history': []
        }
        if self.state_file.exists():
            self.state_file.unlink()
        print(f"✅ State cleared: {self.state_file}")

    def record_step(self, step_num: int, step_name: str, success: bool):
        """Record a step execution in history."""
        self.state['last_step'] = step_num
        self.state['history'].append({
            'step': step_num,
            'name': step_name,
            'success': success,
            'timestamp': datetime.now().isoformat()
        })
        self.save()

    def get_status(self) -> str:
        """Get a human-readable status summary."""
        if not self.state['bucket']:
            return "No state (run from step 1)"

        status_lines = [
            f"Bucket: {self.state['bucket']}",
            f"Original table: {self.state['table_name']}",
            f"Current table: {self.state['current_table_name']}",
            f"Table exists: {self.state['table_exists']}",
            f"Last step: {self.state['last_step']}",
            f"Created: {self.state.get('created_at', 'unknown')}"
        ]
        return "\n  ".join(status_lines)


# Example config for testing
EXAMPLE_CONFIG_YAML = """schema:
- name: sample_id
  type: STRING
- name: collection_date
  type: TIMESTAMP
- name: concentration
  type: FLOAT
- name: quality_score
  type: INT
- name: passed_qc
  type: BOOLEAN
source:
  type: quilt-packages
  package_name: ^experiments/(?<year>\\d{4})/(?<experiment_id>[^/]+)$
  logical_key: samples/(?<sample_type>[^/]+)\\.csv$
parser:
  format: csv
  delimiter: ","
  header: true"""


def print_section(title):
    """Print a section header."""
    print("\n" + "=" * 80)
    print(title.upper())
    print("=" * 80 + "\n")


def print_result(label, data, indent=2):
    """Print a formatted result."""
    prefix = " " * indent
    print(f"{prefix}{label}")
    if isinstance(data, dict):
        print(f"{prefix}{json.dumps(data, indent=2)}")
    else:
        print(f"{prefix}{data}")


def demo_create_table(backend, bucket, table_name, state_manager, verbose=False):
    """REAL API CALL: Create a tabulator table."""
    print("[Step 1] Creating Tabulator Table (REAL API CALL)")
    print(f"  Bucket: {bucket}")
    print(f"  Table: {table_name}")

    try:
        result = backend.create_tabulator_table(
            bucket=bucket,
            table_name=table_name,
            config=EXAMPLE_CONFIG_YAML
        )

        if result.get('__typename') == 'BucketConfig':
            print(f"  ✅ Table created successfully")
            if verbose:
                print_result("Response:", result, indent=4)

            # Update state
            state_manager.state['bucket'] = bucket
            state_manager.state['table_name'] = table_name
            state_manager.state['current_table_name'] = table_name
            state_manager.state['table_exists'] = True
            state_manager.state['created_at'] = datetime.now().isoformat()
            state_manager.record_step(1, "create_table", True)
            return True
        else:
            print(f"  ❌ Create failed: {result}")
            state_manager.record_step(1, "create_table", False)
            return False

    except Exception as e:
        print(f"  ❌ Error: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        state_manager.record_step(1, "create_table", False)
        return False


def demo_list_tables(backend, bucket, state_manager, verbose=False):
    """REAL API CALL: List tabulator tables."""
    print("\n[Step 2] Listing Tables in Bucket (REAL API CALL)")
    print(f"  Bucket: {bucket}")

    try:
        tables = backend.list_tabulator_tables(bucket)

        if tables:
            print(f"  ✅ Found {len(tables)} table(s):")
            for table in tables:
                table_name = table.get('name', 'unknown')
                config = table.get('config', '')
                lines = config.split('\n') if config else []
                schema_count = sum(1 for line in lines if line.strip().startswith('- name:'))
                print(f"    - {table_name} ({schema_count} columns)")

                if verbose:
                    print(f"      Config preview:")
                    for line in lines[:10]:
                        print(f"        {line}")
        else:
            print(f"  ℹ️  No tables found")

        state_manager.record_step(2, "list_tables", True)
        return True
    except Exception as e:
        print(f"  ❌ Error: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        state_manager.record_step(2, "list_tables", False)
        return False


def demo_get_table(backend, bucket, table_name, state_manager, verbose=False):
    """REAL API CALL: Get a specific table."""
    print("\n[Step 3] Getting Specific Table (REAL API CALL)")
    print(f"  Bucket: {bucket}")
    print(f"  Table: {table_name}")

    try:
        table = backend.get_tabulator_table(bucket, table_name)

        print(f"  ✅ Table found")
        print(f"    Name: {table.get('name')}")

        if verbose:
            config = table.get('config', '')
            print(f"    Config:")
            for line in config.split('\n')[:15]:
                print(f"      {line}")

        state_manager.record_step(3, "get_table", True)
        return True
    except Exception as e:
        print(f"  ❌ Error: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        state_manager.record_step(3, "get_table", False)
        return False


def demo_rename_table(backend, bucket, old_name, new_name, state_manager, verbose=False):
    """REAL API CALL: Rename a table."""
    print("\n[Step 4] Renaming Table (REAL API CALL)")
    print(f"  Bucket: {bucket}")
    print(f"  Old name: {old_name}")
    print(f"  New name: {new_name}")

    try:
        result = backend.rename_tabulator_table(bucket, old_name, new_name)

        if result.get('__typename') == 'BucketConfig':
            print(f"  ✅ Table renamed successfully")
            if verbose:
                print_result("Response:", result, indent=4)

            # Update state
            state_manager.state['current_table_name'] = new_name
            state_manager.record_step(4, "rename_table", True)
            return True
        else:
            print(f"  ❌ Rename failed: {result}")
            state_manager.record_step(4, "rename_table", False)
            return False

    except Exception as e:
        print(f"  ❌ Error: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        state_manager.record_step(4, "rename_table", False)
        return False


def demo_query_table(bucket, table_name, state_manager, verbose=False):
    """REAL ATHENA QUERY: Query table via companion script."""
    print(f"\n[Step 5] Querying Table via Athena (REAL ATHENA QUERY)")
    print(f"  Bucket: {bucket}")
    print(f"  Table: {table_name}")
    print(f"  Using companion script: {QUERY_SCRIPT}")

    if not QUERY_SCRIPT.exists():
        print(f"\n❌ FATAL: Query script not found at {QUERY_SCRIPT}")
        print(f"   This is a FULL STACK integration test - querying is REQUIRED!")
        print(f"   Expected location: {QUERY_SCRIPT}")
        state_manager.record_step(5, "query_table", False)
        return False

    try:
        # Call the companion query script
        # The script will auto-discover stack, catalog, and workgroup from bucket config
        cmd = [
            "uv", "run", "python", str(QUERY_SCRIPT),
            "--bucket", bucket,
            "--table", table_name,
            "--limit", "5"
        ]

        if verbose:
            print(f"  Running: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode == 0:
            print(f"  ✅ Query executed successfully")
            if verbose:
                print("\n  Query output:")
                for line in result.stdout.split('\n'):
                    print(f"    {line}")
            else:
                # Show just summary
                lines = result.stdout.split('\n')
                for line in lines:
                    if 'row(s) returned' in line or 'Query completed' in line:
                        print(f"  {line.strip()}")

            state_manager.record_step(5, "query_table", True)
            return True
        else:
            print(f"  ❌ Query failed with exit code {result.returncode}")
            if verbose or True:  # Always show errors
                print(f"  Error output:")
                for line in result.stderr.split('\n')[:10]:
                    if line.strip():
                        print(f"    {line}")
            state_manager.record_step(5, "query_table", False)
            return False

    except subprocess.TimeoutExpired:
        print(f"  ❌ Query timed out after 60 seconds")
        state_manager.record_step(5, "query_table", False)
        return False
    except Exception as e:
        print(f"  ❌ Error running query: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        state_manager.record_step(5, "query_table", False)
        return False


def demo_delete_table(backend, bucket, table_name, state_manager, verbose=False):
    """REAL API CALL: Delete a tabulator table."""
    print("\n[Step 6] Deleting Table (REAL API CALL)")
    print(f"  Bucket: {bucket}")
    print(f"  Table: {table_name}")

    try:
        result = backend.delete_tabulator_table(bucket, table_name)

        if result.get('__typename') == 'BucketConfig':
            print(f"  ✅ Table deleted successfully")
            if verbose:
                print_result("Response:", result, indent=4)

            # Update state
            state_manager.state['table_exists'] = False
            state_manager.record_step(6, "delete_table", True)
            return True
        else:
            print(f"  ❌ Delete failed: {result}")
            state_manager.record_step(6, "delete_table", False)
            return False

    except Exception as e:
        print(f"  ❌ Error: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        state_manager.record_step(6, "delete_table", False)
        return False


def main():
    """Main integration test function."""
    parser = argparse.ArgumentParser(
        description="Integration test for Tabulator lifecycle (REAL backend only)",
        epilog="This script hits the REAL backend - no mock mode!"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed output"
    )
    parser.add_argument(
        "--step",
        type=int,
        choices=[1, 2, 3, 4, 5, 6],
        help="Run a specific step (1-6)"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset persistent state and exit"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show current state and exit"
    )
    args = parser.parse_args()

    # Initialize state manager
    state_manager = StateManager()

    # Handle --reset flag
    if args.reset:
        state_manager.reset()
        return

    # Handle --status flag
    if args.status:
        print_section("Current State")
        print(f"  {state_manager.get_status()}")
        return

    # Check credentials FIRST - fail loudly if not present
    check_credentials_or_fail()

    try:
        print_section("Tabulator Lifecycle Integration Test")
        print("Running in: REAL MODE (hitting actual backend)")
        print("⚠️  Warning: This will create and delete actual tables!")

        bucket = os.getenv("QUILT_TEST_BUCKET", "").replace("s3://", "")
        print(f"⚠️  Bucket: {bucket}")

        # Create backend using factory
        print("\n[Step 0] Initializing Backend")
        backend = QuiltOpsFactory.create()
        print(f"  ✅ Backend initialized: {backend.__class__.__name__}")
        print(f"  ℹ️  Has TabulatorMixin: {hasattr(backend, 'list_tabulator_tables')}")

        # Generate unique table name for this run
        timestamp = int(time.time())
        table_name = f"test_tabulator_{timestamp}"
        new_table_name = f"test_genomics_{timestamp}"

        # Show current state
        if state_manager.state['bucket']:
            print("\n[State] Resuming from previous session")
            print(f"  {state_manager.get_status()}")

        # Track results
        results = []

        # Define step functions
        steps = [
            (1, "Create table", lambda: demo_create_table(backend, bucket, table_name, state_manager, args.verbose)),
            (2, "List tables", lambda: demo_list_tables(backend, bucket, state_manager, args.verbose)),
            (3, "Get specific table", lambda: demo_get_table(backend, bucket, table_name, state_manager, args.verbose)),
            (4, "Rename table", lambda: demo_rename_table(backend, bucket, table_name, new_table_name, state_manager, args.verbose)),
            (5, "Query table", lambda: demo_query_table(bucket, new_table_name, state_manager, args.verbose)),
            (6, "Delete table", lambda: demo_delete_table(backend, bucket, new_table_name, state_manager, args.verbose)),
        ]

        # Run specific step or all steps
        if args.step:
            print(f"\n[Mode] Running step {args.step} only")
            step_num, step_name, step_func = steps[args.step - 1]
            result = step_func()
            results = [result]
            print(f"\n{'✅ SUCCESS' if result else '❌ FAILURE'}")
        else:
            print(f"\n[Mode] Running all steps")
            for step_num, step_name, step_func in steps:
                result = step_func()
                results.append(result)

        # Print summary
        if not args.step:
            print_section("Summary")

            passed_count = sum(1 for r in results if r)
            total = len(results)

            if passed_count == total:
                print(f"✅ All integration tests completed successfully!")
            else:
                print(f"⚠️  {passed_count}/{total} integration tests passed")

            print("\nSteps tested:")
            for (step_num, scenario, _), result_passed in zip(steps, results):
                status = "✅" if result_passed else "❌"
                print(f"  {status} Step {step_num}: {scenario}")

            print(f"\nTotal: {passed_count}/{total} steps passed")
            print(f"\nResult: {'✅ SUCCESS' if passed_count == total else '❌ FAILURE'}")

            # Show state file location
            print(f"\nℹ️  State saved to: {state_manager.state_file}")
            print(f"ℹ️  Use --status to view current state")
            print(f"ℹ️  Use --step N to run a specific step")
            print(f"ℹ️  Use --reset to clear state")

            # Exit code
            sys.exit(0 if passed_count == total else 1)

    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

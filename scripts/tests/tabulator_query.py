#!/usr/bin/env python3
"""Query tabulator tables using Athena.

This companion script uses quilt3 and boto3 to run actual SQL queries
against tabulator tables created by test_tabulator.py.

Usage:
    # Query with auto-discovered stack (from quilt3 config)
    uv run python scripts/tests/tabulator_query.py --bucket my-bucket --table my_table

    # Query with explicit stack name
    uv run python scripts/tests/tabulator_query.py --bucket my-bucket --stack-name quilt-staging --table my_table

    # List available tables
    uv run python scripts/tests/tabulator_query.py --bucket my-bucket --list-tables

    # Custom SQL query
    uv run python scripts/tests/tabulator_query.py --bucket my-bucket --query "SELECT * FROM my_table LIMIT 10"

Requirements:
    - quilt3 login (use: quilt3 login)
    - AWS credentials configured
    - Access to the bucket with tabulator tables
"""

import sys
import argparse
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

try:
    import quilt3 as q3
    import boto3
    from botocore.exceptions import ClientError
    from quiltx import get_catalog_url, get_catalog_region
    from quiltx.stack import find_matching_stack, fetch_catalog_config
    from quiltx.utils import get_bucket_region
except ImportError:
    print("❌ Error: This script requires quilt3, boto3, and quiltx")
    print("Install with: uv pip install quilt3 boto3 quiltx")
    sys.exit(1)


class TabulatorQueryClient:
    """Client for querying tabulator tables via Athena."""

    def __init__(self, bucket: str, stack_name: Optional[str] = None):
        self.bucket = bucket

        # Auto-detect bucket region
        try:
            self.bucket_region = get_bucket_region(bucket)
            print(f"✅ Auto-detected bucket region: {self.bucket_region}")
        except Exception as e:
            print(f"⚠️  Could not detect bucket region: {e}")
            print(f"ℹ️  Defaulting to us-east-1")
            self.bucket_region = 'us-east-1'

        # Auto-detect stack region from quilt3 config
        try:
            self.stack_region = get_catalog_region()
            print(f"✅ Auto-detected stack region: {self.stack_region}")
        except Exception as e:
            print(f"⚠️  Could not detect stack region: {e}")
            print(f"ℹ️  Using bucket region: {self.bucket_region}")
            self.stack_region = self.bucket_region

        # Auto-discover stack name if not provided
        if not stack_name:
            try:
                catalog_url = get_catalog_url()
                stack = find_matching_stack(catalog_url)
                stack_name = stack.get('StackName')
                print(f"✅ Auto-discovered stack: {stack_name}")
            except Exception as e:
                print(f"⚠️  Could not auto-discover stack: {e}")

        self.stack_name = stack_name
        self.catalog_name = f"quilt-{stack_name}-tabulator" if stack_name else None
        self.workgroup = f"QuiltUserAthena-{stack_name}-NonManagedRoleWorkgroup" if stack_name else None
        self.athena_client = None
        self.s3_client = None
        self._init_clients()

    def _init_clients(self):
        """Initialize AWS clients."""
        try:
            # Athena uses stack region, S3 uses bucket region
            athena_session = boto3.Session(region_name=self.stack_region)
            s3_session = boto3.Session(region_name=self.bucket_region)
            self.athena_client = athena_session.client('athena')
            self.s3_client = s3_session.client('s3')
            print(f"✅ Connected to AWS")
            print(f"   Bucket region: {self.bucket_region}")
            print(f"   Stack region: {self.stack_region}")
            if self.stack_name:
                print(f"   Stack: {self.stack_name}")
                print(f"   Catalog: {self.catalog_name}")
                print(f"   Workgroup: {self.workgroup}")
        except Exception as e:
            print(f"❌ Failed to initialize AWS clients: {e}")
            print("Make sure you've run 'quilt3 login' and have AWS credentials configured")
            sys.exit(1)

    def get_catalog_name(self) -> str:
        """Get the Athena catalog name for tabulator tables."""
        if self.catalog_name:
            return self.catalog_name

        # Default to AwsDataCatalog if no stack name provided
        print(f"⚠️  No stack name provided, using default catalog")
        return 'AwsDataCatalog'

    def get_athena_database(self) -> Optional[str]:
        """Get the Athena database name for tabulator tables using quiltx."""
        try:
            catalog_url = f"https://s3.{self.bucket_region}.amazonaws.com/{self.bucket}/.quilt/catalog/config.json"
            config = fetch_catalog_config(catalog_url)
            if config and 'tabulator' in config:
                db_name = config['tabulator'].get('athena_database')
                if db_name:
                    print(f"✅ Found Athena database: {db_name}")
                    return db_name
        except Exception:
            pass  # Fall through to default

        # Default database name is just the bucket name
        default_db = self.bucket
        print(f"ℹ️  Using default database name: {default_db}")
        return default_db

    def list_tables(self) -> list:
        """List available tabulator tables in Athena."""
        database = self.get_athena_database()
        if not database:
            return []

        try:
            query = f'SHOW TABLES IN "{database}"'
            results = self.execute_query(query)

            tables = []
            for row in results.get('rows', []):
                if row:
                    tables.append(row[0])

            print(f"✅ Found {len(tables)} table(s) in database '{database}'")
            return tables
        except Exception as e:
            print(f"❌ Failed to list tables: {e}")
            return []

    def execute_query(self, query: str, max_results: int = 100) -> Dict[str, Any]:
        """Execute an Athena query and return results.

        Args:
            query: SQL query to execute
            max_results: Maximum number of results to return

        Returns:
            Dict with 'columns' and 'rows' keys
        """
        database = self.get_athena_database()

        # Start query execution
        print(f"\n📊 Executing query...")
        print(f"   Database: {database}")
        print(f"   Query: {query[:100]}{'...' if len(query) > 100 else ''}")

        try:
            # Create output location in bucket
            output_location = f"s3://{self.bucket}/.quilt/queries/"

            # Set up execution parameters with catalog
            catalog = self.get_catalog_name()
            execution_params = {
                'QueryString': query,
                'QueryExecutionContext': {
                    'Catalog': catalog
                },
                'ResultConfiguration': {'OutputLocation': output_location}
            }

            # Add workgroup if specified
            if self.workgroup:
                execution_params['WorkGroup'] = self.workgroup
                print(f"   Workgroup: {self.workgroup}")

            print(f"   Catalog: {catalog}")
            response = self.athena_client.start_query_execution(**execution_params)

            query_execution_id = response['QueryExecutionId']
            print(f"   Query ID: {query_execution_id}")

            # Wait for query to complete
            print("   Waiting for query to complete...", end='', flush=True)
            import time
            while True:
                status = self.athena_client.get_query_execution(
                    QueryExecutionId=query_execution_id
                )
                state = status['QueryExecution']['Status']['State']

                if state in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
                    print(f" {state}")
                    break

                print(".", end='', flush=True)
                time.sleep(1)

            if state != 'SUCCEEDED':
                reason = status['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
                raise Exception(f"Query {state}: {reason}")

            # Get query results
            results = self.athena_client.get_query_results(
                QueryExecutionId=query_execution_id,
                MaxResults=max_results
            )

            # Parse results
            columns = []
            rows = []

            result_set = results.get('ResultSet', {})
            metadata = result_set.get('ResultSetMetadata', {}).get('ColumnInfo', [])
            result_rows = result_set.get('Rows', [])

            # Extract column names
            if result_rows:
                header_row = result_rows[0]
                columns = [col['VarCharValue'] for col in header_row.get('Data', [])]
                result_rows = result_rows[1:]  # Skip header

            # Extract data rows
            for row in result_rows:
                row_data = []
                for field in row.get('Data', []):
                    row_data.append(field.get('VarCharValue'))
                rows.append(row_data)

            print(f"✅ Query completed: {len(rows)} row(s) returned")

            return {
                'columns': columns,
                'rows': rows,
                'metadata': metadata
            }

        except Exception as e:
            print(f"\n❌ Query failed: {e}")
            raise

    def format_results(self, results: Dict[str, Any], max_rows: int = 50):
        """Format query results as a table."""
        columns = results.get('columns', [])
        rows = results.get('rows', [])

        if not columns or not rows:
            print("\n(No results)")
            return

        # Calculate column widths
        widths = [len(col) for col in columns]
        for row in rows[:max_rows]:
            for i, cell in enumerate(row):
                widths[i] = max(widths[i], len(str(cell or '')))

        # Print header
        print("\n" + "=" * (sum(widths) + len(columns) * 3 + 1))
        header = " | ".join(col.ljust(widths[i]) for i, col in enumerate(columns))
        print(f"| {header} |")
        print("=" * (sum(widths) + len(columns) * 3 + 1))

        # Print rows
        for row in rows[:max_rows]:
            row_str = " | ".join(str(cell or '').ljust(widths[i]) for i, cell in enumerate(row))
            print(f"| {row_str} |")

        print("=" * (sum(widths) + len(columns) * 3 + 1))

        if len(rows) > max_rows:
            print(f"\n(Showing {max_rows} of {len(rows)} rows)")


def load_demo_state() -> Optional[Dict[str, Any]]:
    """Load state from test_tabulator.py."""
    state_file = Path("/tmp/tabulator_demo_state.json")
    if state_file.exists():
        try:
            with open(state_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  Warning: Could not load demo state: {e}")
    return None


def main():
    """Main query function."""
    parser = argparse.ArgumentParser(
        description="Query tabulator tables using Athena"
    )
    parser.add_argument(
        "--bucket",
        help="S3 bucket name (default: from demo state)"
    )
    parser.add_argument(
        "--table",
        help="Table name to query (default: from demo state)"
    )
    parser.add_argument(
        "--query",
        help="Custom SQL query to execute"
    )
    parser.add_argument(
        "--list-tables",
        action="store_true",
        help="List available tables and exit"
    )
    parser.add_argument(
        "--stack-name",
        default=None,
        help="CloudFormation stack name (e.g., quilt-staging). Will auto-discover from quilt3 config if not provided."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="LIMIT for default query (default: 10)"
    )
    args = parser.parse_args()

    # Load state from demo script if available
    state = load_demo_state()

    # Determine bucket and table
    bucket = args.bucket or (state and state.get('bucket'))
    table = args.table or (state and state.get('current_table_name'))

    if not bucket or not isinstance(bucket, str):
        print("❌ Error: No bucket specified and no demo state found")
        print("Use --bucket or run test_tabulator.py first")
        sys.exit(1)

    print("=" * 80)
    print("TABULATOR QUERY CLIENT")
    print("=" * 80)

    if state and not args.bucket:
        print(f"\n✅ Using state from demo script:")
        print(f"   Bucket: {bucket}")
        print(f"   Table: {table}")
        print(f"   Table exists: {state.get('table_exists')}")
        print(f"   Last step: {state.get('last_step')}")

    # Initialize client
    client = TabulatorQueryClient(bucket, args.stack_name)

    # List tables if requested
    if args.list_tables:
        tables = client.list_tables()
        if tables:
            print("\nAvailable tables:")
            for t in tables:
                print(f"  • {t}")
        else:
            print("\nNo tables found")
        return

    # Execute query
    if args.query:
        # Use custom query
        query = args.query
    elif table:
        # Build fully qualified table name with proper quoting
        catalog = client.get_catalog_name()
        database = client.get_athena_database()
        # Use double quotes for identifiers with special characters
        # Format: "catalog"."database".table
        query = f'SELECT * FROM "{catalog}"."{database}".{table} LIMIT {args.limit}'
    else:
        print("❌ Error: No table specified and no demo state found")
        print("Use --table, --query, or run test_tabulator.py first")
        sys.exit(1)

    try:
        results = client.execute_query(query)
        client.format_results(results)

        print(f"\n✅ Query completed successfully")
        print(f"   Columns: {len(results.get('columns', []))}")
        print(f"   Rows: {len(results.get('rows', []))}")

    except Exception as e:
        print(f"\n❌ Query failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

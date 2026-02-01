#!/usr/bin/env python3
"""Query tabulator tables using Athena.

This companion script uses quilt3 and boto3 to run actual SQL queries
against tabulator tables created by demo_tabulator_lifecycle.py.

Usage:
    # Query using state from demo script
    uv run python scripts/tests/query_tabulator.py

    # Query specific bucket/table
    uv run python scripts/tests/query_tabulator.py --bucket my-bucket --table my_table

    # Custom SQL query
    uv run python scripts/tests/query_tabulator.py --query "SELECT * FROM my_table LIMIT 10"

    # List available tables
    uv run python scripts/tests/query_tabulator.py --list-tables

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
except ImportError:
    print("❌ Error: This script requires quilt3 and boto3")
    print("Install with: uv pip install quilt3 boto3")
    sys.exit(1)


class TabulatorQueryClient:
    """Client for querying tabulator tables via Athena."""

    def __init__(self, bucket: str, region: str = 'us-east-1'):
        self.bucket = bucket
        self.region = region
        self.athena_client = None
        self.s3_client = None
        self._init_clients()

    def _init_clients(self):
        """Initialize AWS clients."""
        try:
            # Get credentials from quilt3 session
            # This ensures we're using the same credentials as quilt3
            session = boto3.Session(region_name=self.region)
            self.athena_client = session.client('athena')
            self.s3_client = session.client('s3')
            print(f"✅ Connected to AWS region: {self.region}")
        except Exception as e:
            print(f"❌ Failed to initialize AWS clients: {e}")
            print("Make sure you've run 'quilt3 login' and have AWS credentials configured")
            sys.exit(1)

    def get_catalog_config(self) -> Optional[Dict[str, Any]]:
        """Get the Quilt catalog configuration for the bucket."""
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket,
                Key='.quilt/catalog/config.json'
            )
            config = json.loads(response['Body'].read())
            return config
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                print(f"⚠️  No catalog config found in bucket: {self.bucket}")
                return None
            raise

    def get_athena_database(self) -> Optional[str]:
        """Get the Athena database name for tabulator tables."""
        config = self.get_catalog_config()
        if config and 'tabulator' in config:
            db_name = config['tabulator'].get('athena_database')
            if db_name:
                print(f"✅ Found Athena database: {db_name}")
                return db_name

        # Default database name pattern
        default_db = f"quilt_{self.bucket.replace('-', '_')}"
        print(f"ℹ️  Using default database name: {default_db}")
        return default_db

    def list_tables(self) -> list:
        """List available tabulator tables in Athena."""
        database = self.get_athena_database()
        if not database:
            return []

        try:
            query = f"SHOW TABLES IN {database}"
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
            # Create output location in the bucket
            output_location = f"s3://{self.bucket}/.quilt/queries/"

            response = self.athena_client.start_query_execution(
                QueryString=query,
                QueryExecutionContext={'Database': database},
                ResultConfiguration={'OutputLocation': output_location}
            )

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
    """Load state from demo_tabulator_lifecycle.py."""
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
        "--region",
        default="us-east-1",
        help="AWS region (default: us-east-1)"
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

    if not bucket:
        print("❌ Error: No bucket specified and no demo state found")
        print("Use --bucket or run demo_tabulator_lifecycle.py first")
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
    client = TabulatorQueryClient(bucket, args.region)

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
        # Default query for the table
        query = f"SELECT * FROM {table} LIMIT {args.limit}"
    else:
        print("❌ Error: No table specified and no demo state found")
        print("Use --table, --query, or run demo_tabulator_lifecycle.py first")
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

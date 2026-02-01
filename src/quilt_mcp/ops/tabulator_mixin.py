"""Shared Tabulator operations using GraphQL.

This mixin provides table management for Quilt tabulator functionality.
Works with any backend implementing execute_graphql_query().
"""

from typing import List, Dict, Any, Optional
from quilt_mcp.ops.exceptions import BackendError, ValidationError


class TabulatorMixin:
    """Shared Tabulator operations using GraphQL.

    This mixin provides Tabulator table management operations that work
    with any backend implementing execute_graphql_query().

    Requires the including class to implement:
        - execute_graphql_query(query: str, variables: Optional[Dict]) -> Dict
    """

    def list_tabulator_tables(self, bucket: str) -> List[Dict[str, str]]:
        """List all tabulator tables in a bucket.

        Args:
            bucket: S3 bucket name

        Returns:
            List of dicts with 'name' and 'config' (YAML string) keys

        Raises:
            BackendError: If GraphQL query fails
            ValidationError: If bucket not found
        """
        query = """
        query ListTabulatorTables($name: String!) {
          bucketConfig(name: $name) {
            tabulatorTables {
              name
              config
            }
          }
        }
        """

        try:
            result = self.execute_graphql_query(query, {"name": bucket})
        except Exception as e:
            raise BackendError(
                f"Failed to list tabulator tables: {str(e)}",
                context={"bucket": bucket}
            ) from e

        # Extract tables from GraphQL response
        bucket_config = result.get('data', {}).get('bucketConfig')
        if not bucket_config:
            raise ValidationError(f"Bucket not found: {bucket}")

        tables = bucket_config.get('tabulatorTables', [])
        return tables

    def get_tabulator_table(self, bucket: str, table_name: str) -> Dict[str, str]:
        """Get a specific tabulator table configuration.

        Args:
            bucket: S3 bucket name
            table_name: Table name

        Returns:
            Dict with 'name' and 'config' (YAML string) keys

        Raises:
            BackendError: If GraphQL query fails
            ValidationError: If table not found
        """
        tables = self.list_tabulator_tables(bucket)

        for table in tables:
            if table['name'] == table_name:
                return table

        raise ValidationError(f"Table not found: {table_name}")

    def create_tabulator_table(
        self,
        bucket: str,
        table_name: str,
        config: str
    ) -> Dict[str, Any]:
        """Create or update a tabulator table.

        Args:
            bucket: S3 bucket name
            table_name: Table name
            config: YAML configuration string

        Returns:
            Dict with operation result

        Raises:
            BackendError: If GraphQL mutation fails
            ValidationError: If configuration is invalid
            PermissionError: If user lacks write access
        """
        mutation = """
        mutation SetTabulatorTable(
          $bucketName: String!
          $tableName: String!
          $config: String
        ) {
          bucketSetTabulatorTable(
            bucketName: $bucketName
            tableName: $tableName
            config: $config
          ) {
            ... on BucketSetTabulatorTableSuccess {
              bucketConfig {
                name
                tabulatorTables {
                  name
                  config
                }
              }
            }
            ... on InvalidInput {
              message
            }
            ... on BucketNotFound {
              message
            }
            ... on BucketNotAllowed {
              message
            }
          }
        }
        """

        try:
            result = self.execute_graphql_query(mutation, {
                "bucketName": bucket,
                "tableName": table_name,
                "config": config
            })
        except Exception as e:
            raise BackendError(
                f"Failed to create/update tabulator table: {str(e)}",
                context={"bucket": bucket, "table_name": table_name}
            ) from e

        # Check for GraphQL errors
        data = result.get('data', {}).get('bucketSetTabulatorTable', {})
        typename = data.get('__typename')

        if typename == 'InvalidInput':
            raise ValidationError(f"Invalid configuration: {data.get('message')}")
        elif typename == 'BucketNotFound':
            raise ValidationError(f"Bucket not found: {data.get('message')}")
        elif typename == 'BucketNotAllowed':
            raise PermissionError(f"Not authorized for bucket: {data.get('message')}")

        return data

    def update_tabulator_table(
        self,
        bucket: str,
        table_name: str,
        config: str
    ) -> Dict[str, Any]:
        """Update an existing tabulator table configuration.

        This is an alias for create_tabulator_table() since the GraphQL
        mutation handles both create and update.

        Args:
            bucket: S3 bucket name
            table_name: Table name
            config: YAML configuration string

        Returns:
            Dict with operation result
        """
        return self.create_tabulator_table(bucket, table_name, config)

    def rename_tabulator_table(
        self,
        bucket: str,
        old_name: str,
        new_name: str
    ) -> Dict[str, Any]:
        """Rename a tabulator table.

        Args:
            bucket: S3 bucket name
            old_name: Current table name
            new_name: New table name

        Returns:
            Dict with operation result

        Raises:
            BackendError: If GraphQL mutation fails
            ValidationError: If old table not found or new name invalid
        """
        mutation = """
        mutation RenameTabulatorTable(
          $bucketName: String!
          $tableName: String!
          $newTableName: String!
        ) {
          bucketRenameTabulatorTable(
            bucketName: $bucketName
            tableName: $tableName
            newTableName: $newTableName
          ) {
            ... on BucketSetTabulatorTableSuccess {
              bucketConfig {
                name
                tabulatorTables {
                  name
                  config
                }
              }
            }
            ... on InvalidInput {
              message
            }
            ... on BucketNotFound {
              message
            }
            ... on BucketNotAllowed {
              message
            }
          }
        }
        """

        try:
            result = self.execute_graphql_query(mutation, {
                "bucketName": bucket,
                "tableName": old_name,
                "newTableName": new_name
            })
        except Exception as e:
            raise BackendError(
                f"Failed to rename tabulator table: {str(e)}",
                context={"bucket": bucket, "old_name": old_name, "new_name": new_name}
            ) from e

        # Check for GraphQL errors
        data = result.get('data', {}).get('bucketRenameTabulatorTable', {})
        typename = data.get('__typename')

        if typename == 'InvalidInput':
            raise ValidationError(f"Invalid rename: {data.get('message')}")
        elif typename == 'BucketNotFound':
            raise ValidationError(f"Bucket not found: {data.get('message')}")
        elif typename == 'BucketNotAllowed':
            raise PermissionError(f"Not authorized: {data.get('message')}")

        return data

    def delete_tabulator_table(
        self,
        bucket: str,
        table_name: str
    ) -> Dict[str, Any]:
        """Delete a tabulator table.

        Deletion is implemented by setting config to null.

        Args:
            bucket: S3 bucket name
            table_name: Table name to delete

        Returns:
            Dict with operation result

        Raises:
            BackendError: If GraphQL mutation fails
        """
        return self.create_tabulator_table(bucket, table_name, None)

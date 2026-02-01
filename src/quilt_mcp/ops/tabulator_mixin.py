"""Shared Tabulator operations using GraphQL.

This mixin provides table management for Quilt tabulator functionality.
Works with any backend implementing the required auth/endpoint methods.
"""

import logging
from typing import List, Dict, Any, Optional
from quilt_mcp.ops.exceptions import BackendError, ValidationError, AuthenticationError

logger = logging.getLogger(__name__)


class TabulatorMixin:
    """Shared Tabulator operations using GraphQL.

    This mixin provides backend-agnostic Tabulator table management operations.
    It implements execute_graphql_query() generically by delegating auth and
    endpoint discovery to the backend.

    Requires the including class to implement:
        - get_graphql_endpoint() -> str
        - get_graphql_auth_headers() -> Dict[str, str]
    """

    # These must be implemented by the backend
    def get_graphql_endpoint(self) -> str:
        """Get GraphQL endpoint URL - must be implemented by backend."""
        raise NotImplementedError("Backend must implement get_graphql_endpoint()")

    def get_graphql_auth_headers(self) -> Dict[str, str]:
        """Get auth headers - must be implemented by backend."""
        raise NotImplementedError("Backend must implement get_graphql_auth_headers()")

    def execute_graphql_query(
        self, query: str, variables: Optional[Dict[str, Any]] = None, registry: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute GraphQL query using backend-provided auth and endpoint.

        This is a generic implementation that works with any backend. It delegates
        auth credential retrieval and endpoint discovery to the backend through
        the get_graphql_auth_headers() and get_graphql_endpoint() methods.

        Args:
            query: GraphQL query string
            variables: Optional query variables
            registry: Legacy parameter (ignored, endpoint comes from backend)

        Returns:
            GraphQL response dict

        Raises:
            AuthenticationError: When auth credentials are unavailable
            BackendError: When query execution fails
            ValidationError: When query syntax is invalid
        """
        try:
            import requests

            logger.debug("Executing GraphQL query")

            # Get endpoint and auth from backend (polymorphic - no quilt3 coupling!)
            endpoint = self.get_graphql_endpoint()
            headers = self.get_graphql_auth_headers()

            # Prepare payload (generic GraphQL)
            payload: Dict[str, Any] = {"query": query}
            if variables:
                payload["variables"] = variables

            # Execute query (generic HTTP request)
            response = requests.post(endpoint, json=payload, headers=headers)
            response.raise_for_status()

            logger.debug("GraphQL query executed successfully")
            result: Dict[str, Any] = response.json()

            # Check for GraphQL errors (generic GraphQL error handling)
            if 'errors' in result:
                error_messages = []
                for error in result['errors']:
                    msg = error.get('message', str(error))
                    error_messages.append(msg)
                error_text = '; '.join(error_messages)
                logger.error(f"GraphQL query returned errors: {error_text}")
                raise BackendError(f"GraphQL query failed: {error_text}")

            return result

        except requests.HTTPError as e:
            if hasattr(e, 'response') and e.response and e.response.status_code == 403:
                logger.error("GraphQL query authorization failed")
                raise AuthenticationError("GraphQL query not authorized")
            else:
                error_text = e.response.text if hasattr(e, 'response') and e.response else str(e)
                logger.error(f"GraphQL query HTTP error: {error_text}")
                # Try to parse GraphQL errors from response
                if hasattr(e, 'response') and e.response:
                    try:
                        error_data = e.response.json()
                        if 'errors' in error_data:
                            error_messages = [err.get('message', str(err)) for err in error_data['errors']]
                            error_text = '; '.join(error_messages)
                    except Exception:
                        pass
                raise BackendError(f"GraphQL query failed: {error_text}")
        except Exception as e:
            logger.error(f"GraphQL query failed: {str(e)}")
            raise BackendError(f"GraphQL query failed: {str(e)}")

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
            raise BackendError(f"Failed to list tabulator tables: {str(e)}", context={"bucket": bucket}) from e

        # Extract tables from GraphQL response
        bucket_config = result.get('data', {}).get('bucketConfig')
        if not bucket_config:
            raise ValidationError(f"Bucket not found: {bucket}")

        tables: List[Dict[str, str]] = bucket_config.get('tabulatorTables', [])
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

    def create_tabulator_table(self, bucket: str, table_name: str, config: Optional[str]) -> Dict[str, Any]:
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
            __typename
            ... on BucketConfig {
              name
              tabulatorTables {
                name
                config
              }
            }
            ... on InvalidInput {
              errors {
                path
                message
                name
                context
              }
            }
            ... on OperationError {
              message
            }
          }
        }
        """

        try:
            result = self.execute_graphql_query(
                mutation, {"bucketName": bucket, "tableName": table_name, "config": config}
            )
        except Exception as e:
            raise BackendError(
                f"Failed to create/update tabulator table: {str(e)}",
                context={"bucket": bucket, "table_name": table_name},
            ) from e

        # Check for GraphQL errors
        data: Dict[str, Any] = result.get('data', {}).get('bucketSetTabulatorTable', {})
        typename = data.get('__typename')

        if typename == 'InvalidInput':
            errors = data.get('errors', [])
            error_messages = [f"{err.get('path', 'unknown')}: {err.get('message', str(err))}" for err in errors]
            raise ValidationError(f"Invalid configuration: {'; '.join(error_messages)}")
        elif typename == 'OperationError':
            raise BackendError(f"Operation failed: {data.get('message')}")

        return data

    def update_tabulator_table(self, bucket: str, table_name: str, config: str) -> Dict[str, Any]:
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

    def rename_tabulator_table(self, bucket: str, old_name: str, new_name: str) -> Dict[str, Any]:
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
            __typename
            ... on BucketConfig {
              name
              tabulatorTables {
                name
                config
              }
            }
            ... on InvalidInput {
              errors {
                path
                message
                name
                context
              }
            }
            ... on OperationError {
              message
            }
          }
        }
        """

        try:
            result = self.execute_graphql_query(
                mutation, {"bucketName": bucket, "tableName": old_name, "newTableName": new_name}
            )
        except Exception as e:
            raise BackendError(
                f"Failed to rename tabulator table: {str(e)}",
                context={"bucket": bucket, "old_name": old_name, "new_name": new_name},
            ) from e

        # Check for GraphQL errors
        data: Dict[str, Any] = result.get('data', {}).get('bucketRenameTabulatorTable', {})
        typename = data.get('__typename')

        if typename == 'InvalidInput':
            errors = data.get('errors', [])
            error_messages = [f"{err.get('path', 'unknown')}: {err.get('message', str(err))}" for err in errors]
            raise ValidationError(f"Invalid rename: {'; '.join(error_messages)}")
        elif typename == 'OperationError':
            raise BackendError(f"Operation failed: {data.get('message')}")

        return data

    def delete_tabulator_table(self, bucket: str, table_name: str) -> Dict[str, Any]:
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

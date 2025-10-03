# Governance Tools Analysis & Implementation Plan

## Executive Summary

The governance toolset currently consists of stub implementations that return "Admin APIs are not yet available" errors. However, the Quilt GraphQL schema DOES provide comprehensive admin APIs. This document outlines the proper GraphQL-based implementation.

## GraphQL Schema Analysis

### Admin Queries (via `admin: AdminQueries!`)

```graphql
type AdminQueries {
  user: UserAdminQueries!
  ssoConfig: SsoConfig
  isDefaultRoleSettingDisabled: Boolean!
  tabulatorOpenQuery: Boolean!
  packager: PackagerAdminQueries!
}

type UserAdminQueries {
  list: [User!]!
  get(name: String!): User
}

type User {
  name: String!
  email: String!
  dateJoined: Datetime!
  lastLogin: Datetime!
  isActive: Boolean!
  isAdmin: Boolean!
  isSsoOnly: Boolean!
  isService: Boolean!
  role: Role
  extraRoles: [Role!]!
  isRoleAssignmentDisabled: Boolean!
  isAdminAssignmentDisabled: Boolean!
}
```

### Admin Mutations (via `admin: AdminMutations!`)

```graphql
type AdminMutations {
  user: UserAdminMutations!
  setSsoConfig(config: String): SetSsoConfigResult
  bucketSetTabulatorTable(bucketName: String!, tableName: String!, config: String): BucketSetTabulatorTableResult!
  bucketRenameTabulatorTable(bucketName: String!, tableName: String!, newTableName: String!): BucketSetTabulatorTableResult!
  setTabulatorOpenQuery(enabled: Boolean!): TabulatorOpenQueryResult!
  packager: PackagerAdminMutations!
}

type UserAdminMutations {
  create(input: UserInput!): UserResult!
  mutate(name: String!): MutateUserAdminMutations
}

type MutateUserAdminMutations {
  delete: OperationResult!
  setEmail(email: String!): UserResult!
  setRole(role: String!, extraRoles: [String!], append: Boolean! = false): UserResult!
  addRoles(roles: [String!]!): UserResult!
  removeRoles(roles: [String!]!, fallback: String): UserResult!
  setAdmin(admin: Boolean!): UserResult!
  setActive(active: Boolean!): UserResult!
  resetPassword: OperationResult!
}

input UserInput {
  name: String!
  email: String!
  role: String!
  extraRoles: [String!]
}
```

### Roles (direct query, not under admin)

```graphql
type Query {
  roles: [Role!]! @admin
  role(id: ID!): Role @admin
  defaultRole: Role @admin
}
```

## Implementation Requirements

### 1. User Management Functions

#### `admin_users_list()` 
**GraphQL Query:**
```graphql
query AdminUsersList {
  admin {
    user {
      list {
        name
        email
        dateJoined
        lastLogin
        isActive
        isAdmin
        isSsoOnly
        isService
        role {
          ... on ManagedRole { name }
          ... on UnmanagedRole { name }
        }
        extraRoles {
          ... on ManagedRole { name }
          ... on UnmanagedRole { name }
        }
      }
    }
  }
}
```

#### `admin_user_get(name: str)`
**GraphQL Query:**
```graphql
query AdminUserGet($name: String!) {
  admin {
    user {
      get(name: $name) {
        name
        email
        dateJoined
        lastLogin
        isActive
        isAdmin
        role {
          ... on ManagedRole { name }
          ... on UnmanagedRole { name }
        }
        extraRoles {
          ... on ManagedRole { name }
          ... on UnmanagedRole { name }
        }
      }
    }
  }
}
```

#### `admin_user_create(name, email, role, extra_roles)`
**GraphQL Mutation:**
```graphql
mutation AdminUserCreate($input: UserInput!) {
  admin {
    user {
      create(input: $input) {
        ... on User {
          name
          email
          isActive
          isAdmin
        }
        ... on InvalidInput {
          errors {
            name
            message
            path
          }
        }
        ... on OperationError {
          message
          name
        }
      }
    }
  }
}
```

#### `admin_user_delete(name: str)`
**GraphQL Mutation:**
```graphql
mutation AdminUserDelete($name: String!) {
  admin {
    user {
      mutate(name: $name) {
        delete {
          ... on Ok {
            _
          }
          ... on InvalidInput {
            errors {
              name
              message
            }
          }
          ... on OperationError {
            message
            name
          }
        }
      }
    }
  }
}
```

#### `admin_user_set_email(name: str, email: str)`
**GraphQL Mutation:**
```graphql
mutation AdminUserSetEmail($name: String!, $email: String!) {
  admin {
    user {
      mutate(name: $name) {
        setEmail(email: $email) {
          ... on User {
            name
            email
          }
          ... on InvalidInput {
            errors { name message }
          }
          ... on OperationError {
            message
          }
        }
      }
    }
  }
}
```

#### `admin_user_set_admin(name: str, admin: bool)`
**GraphQL Mutation:**
```graphql
mutation AdminUserSetAdmin($name: String!, $admin: Boolean!) {
  admin {
    user {
      mutate(name: $name) {
        setAdmin(admin: $admin) {
          ... on User {
            name
            isAdmin
          }
          ... on InvalidInput {
            errors { name message }
          }
          ... on OperationError {
            message
          }
        }
      }
    }
  }
}
```

#### `admin_user_set_active(name: str, active: bool)`
**GraphQL Mutation:**
```graphql
mutation AdminUserSetActive($name: String!, $active: Boolean!) {
  admin {
    user {
      mutate(name: $name) {
        setActive(active: $active) {
          ... on User {
            name
            isActive
          }
          ... on InvalidInput {
            errors { name message }
          }
          ... on OperationError {
            message
          }
        }
      }
    }
  }
}
```

### 2. Role Management Functions

#### `admin_roles_list()`
**GraphQL Query:**
```graphql
query AdminRolesList {
  roles {
    ... on ManagedRole {
      id
      name
      arn
      policies {
        id
        title
      }
      permissions {
        bucket { name }
        level
      }
    }
    ... on UnmanagedRole {
      id
      name
      arn
    }
  }
}
```

#### `admin_role_get(name: str)` - NOTE: Schema uses ID, not name
Need to query by ID, not name. This function signature is incorrect.

**GraphQL Query:**
```graphql
query AdminRoleGet($id: ID!) {
  role(id: $id) {
    ... on ManagedRole {
      id
      name
      arn
      policies {
        id
        title
      }
    }
    ... on UnmanagedRole {
      id
      name
      arn
    }
  }
}
```

#### `admin_role_create(name, description)` 
Schema supports creating managed/unmanaged roles via mutations:
```graphql
mutation {
  roleCreateManaged(input: ManagedRoleInput!): RoleCreateResult! @admin
  roleCreateUnmanaged(input: UnmanagedRoleInput!): RoleCreateResult! @admin
}
```

However, these require complex inputs (policies, ARNs). Current function signature is too simple.

#### `admin_role_delete(name: str)`
Schema uses ID, not name:
```graphql
mutation AdminRoleDelete($id: ID!) {
  roleDelete(id: $id) {
    ... on Ok { _ }
    ... on InvalidInput {
      errors { name message }
    }
    ... on OperationError {
      message
    }
  }
}
```

### 3. SSO Configuration Functions

#### `admin_sso_config_get()`
**GraphQL Query:**
```graphql
query AdminSsoConfigGet {
  admin {
    ssoConfig {
      text
      timestamp
      uploader {
        name
        email
      }
    }
  }
}
```

#### `admin_sso_config_set(config: Dict[str, Any])`
**GraphQL Mutation:**
```graphql
mutation AdminSsoConfigSet($config: String) {
  admin {
    setSsoConfig(config: $config) {
      ... on SsoConfig {
        text
        timestamp
      }
      ... on InvalidInput {
        errors { name message }
      }
      ... on OperationError {
        message
      }
    }
  }
}
```
**Note:** Config is a STRING, not a Dict! Needs to be JSON-serialized.

### 4. Tabulator Functions

#### `admin_tabulator_list(bucket_name: str)`
This is NOT in the GraphQL schema. Tabulator tables are queried via:
```graphql
bucketConfig(name: String!) {
  tabulatorTables {
    name
    config
  }
}
```

#### `admin_tabulator_create(bucket_name, table_name, config_yaml)`
**GraphQL Mutation:**
```graphql
mutation AdminTabulatorCreate($bucketName: String!, $tableName: String!, $config: String) {
  admin {
    bucketSetTabulatorTable(bucketName: $bucketName, tableName: $tableName, config: $config) {
      ... on BucketConfig {
        name
        tabulatorTables {
          name
          config
        }
      }
      ... on InvalidInput {
        errors { name message }
      }
      ... on OperationError {
        message
      }
    }
  }
}
```

#### `admin_tabulator_delete(bucket_name, table_name)`
**GraphQL Mutation:**
```graphql
mutation AdminTabulatorDelete($bucketName: String!, $tableName: String!) {
  admin {
    bucketSetTabulatorTable(bucketName: $bucketName, tableName: $tableName, config: null) {
      ... on BucketConfig {
        name
      }
      ... on InvalidInput {
        errors { name message }
      }
      ... on OperationError {
        message
      }
    }
  }
}
```
**Note:** Delete is done by setting config to null.

#### `admin_tabulator_open_query_get()`
**GraphQL Query:**
```graphql
query AdminTabulatorOpenQueryGet {
  admin {
    tabulatorOpenQuery
  }
}
```

#### `admin_tabulator_open_query_set(enabled: bool)`
**GraphQL Mutation:**
```graphql
mutation AdminTabulatorOpenQuerySet($enabled: Boolean!) {
  admin {
    setTabulatorOpenQuery(enabled: $enabled) {
      tabulatorOpenQuery
    }
  }
}
```

## Stateless Architecture Compliance

All functions must:
1. ✅ Use `get_active_token()` from runtime context (not QuiltService)
2. ✅ Use `resolve_catalog_url()` for catalog URL
3. ✅ Call `catalog_graphql_query()` from `clients.catalog`
4. ✅ Handle GraphQL union types (User | InvalidInput | OperationError)
5. ✅ Return properly formatted response dicts with `success` and `error` keys
6. ✅ Log operations for debugging

## Issues Found

### 1. Function Signature Mismatches
- `admin_role_get(name)` - Schema uses ID, not name
- `admin_role_delete(name)` - Schema uses ID, not name
- `admin_role_create(name, description)` - Schema requires complex inputs

### 2. Missing GraphQL Support
- `admin_tabulator_list()` - Not a direct admin query, needs bucket query

### 3. Type Mismatches
- `admin_sso_config_set(config: Dict)` - Schema expects String (JSON)

## Recommendations

### Immediate Actions
1. Implement all user management functions with GraphQL
2. Implement SSO config functions (fix type conversion)
3. Implement tabulator functions (fix list behavior)
4. Update role functions to use ID instead of name
5. Add proper error handling for GraphQL union types

### curl Test Plan

Add to `make.dev`:

```makefile
test-governance-curl: test-governance-users test-governance-roles test-governance-sso test-governance-tabulator
	@echo "✅ All governance curl tests completed"

test-governance-users:
	@echo "🔍 Testing governance user management..."
	# Test users list
	curl -s -X POST $(DEV_ENDPOINT) \
		-H "Content-Type: application/json" \
		-H "Authorization: Bearer $(QUILT_TEST_TOKEN)" \
		-d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"governance","arguments":{"action":"users_list"}}}' \
		| python3 -m json.tool | tee $(RESULTS_DIR)/governance-users-list.json

test-governance-roles:
	@echo "🔍 Testing governance role management..."
	# Test roles list
	curl -s -X POST $(DEV_ENDPOINT) \
		-H "Content-Type: application/json" \
		-H "Authorization: Bearer $(QUILT_TEST_TOKEN)" \
		-d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"governance","arguments":{"action":"roles_list"}}}' \
		| python3 -m json.tool | tee $(RESULTS_DIR)/governance-roles-list.json

test-governance-sso:
	@echo "🔍 Testing governance SSO config..."
	curl -s -X POST $(DEV_ENDPOINT) \
		-H "Content-Type: application/json" \
		-H "Authorization: Bearer $(QUILT_TEST_TOKEN)" \
		-d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"governance","arguments":{"action":"sso_config_get"}}}' \
		| python3 -m json.tool | tee $(RESULTS_DIR)/governance-sso-get.json

test-governance-tabulator:
	@echo "🔍 Testing governance tabulator settings..."
	curl -s -X POST $(DEV_ENDPOINT) \
		-H "Content-Type: application/json" \
		-H "Authorization: Bearer $(QUILT_TEST_TOKEN)" \
		-d '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"governance","arguments":{"action":"tabulator_open_query_get"}}}' \
		| python3 -m json.tool | tee $(RESULTS_DIR)/governance-tabulator-open-query.json
```

## Next Steps

1. Implement GraphQL-based governance functions
2. Update unit tests to expect GraphQL calls instead of stubs
3. Add curl tests to Makefile
4. Test against real Quilt catalog with admin privileges
5. Document admin permission requirements


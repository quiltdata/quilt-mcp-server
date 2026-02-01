# QuiltOps API Documentation

## Overview

QuiltOps is a domain-driven abstraction layer that provides backend-agnostic access to Quilt functionality. It enables MCP tools to work with Quilt concepts (packages, content, buckets) without being tied to specific backend implementations like the quilt3 library or Platform GraphQL API.

## Architecture

The QuiltOps abstraction consists of three main components:

1. **Domain Objects**: Backend-agnostic data structures (`Package_Info`, `Content_Info`, `Bucket_Info`)
2. **QuiltOps Interface**: Abstract base class defining domain operations
3. **Backend Implementations**: Concrete implementations for different Quilt backends

```
MCP Tools → QuiltOps Interface → Backend Implementation → External System
                                (Quilt3_Backend)      (quilt3 library)
```

## Domain Objects

### Package_Info

Represents package metadata consistently across backends.

```python
@dataclass
class Package_Info:
    name: str                    # Package name in "user/package" format
    description: Optional[str]   # Package description
    tags: List[str]             # Package tags
    modified_date: str          # ISO format modification date
    registry: str               # Registry URL (e.g., "s3://my-registry")
    bucket: str                 # S3 bucket name
    top_hash: str               # Package version hash
```

**Usage Example:**
```python
package = Package_Info(
    name="user/my-package",
    description="Example package",
    tags=["data", "analysis"],
    modified_date="2024-01-01T12:00:00Z",
    registry="s3://my-registry",
    bucket="my-bucket",
    top_hash="abc123def456"
)
```

### Content_Info

Represents file/directory information consistently across backends.

```python
@dataclass
class Content_Info:
    path: str                      # File/directory path within package
    size: Optional[int]            # File size in bytes (None for directories)
    type: str                      # "file" or "directory"
    modified_date: Optional[str]   # ISO format modification date
    download_url: Optional[str]    # Direct download URL (if available)
```

**Usage Example:**
```python
content = Content_Info(
    path="data/analysis.csv",
    size=1024,
    type="file",
    modified_date="2024-01-01T12:00:00Z",
    download_url="https://s3.amazonaws.com/bucket/file.csv"
)
```

### Bucket_Info

Represents bucket metadata consistently across backends.

```python
@dataclass
class Bucket_Info:
    name: str                      # Bucket name
    region: str                    # AWS region
    access_level: str              # Access level description
    created_date: Optional[str]    # ISO format creation date
```

**Usage Example:**
```python
bucket = Bucket_Info(
    name="my-data-bucket",
    region="us-east-1",
    access_level="read-write",
    created_date="2024-01-01T00:00:00Z"
)
```

## QuiltOps Interface

The `QuiltOps` abstract base class defines the core operations for interacting with Quilt data.

### Methods

#### search_packages(query: str, registry: str) -> List[Package_Info]

Search for packages matching the given query.

**Parameters:**
- `query`: Search query string to match against package names, descriptions, tags
- `registry`: Registry URL (e.g., "s3://my-registry-bucket") to search within

**Returns:**
- List of `Package_Info` objects representing matching packages

**Raises:**
- `AuthenticationError`: When authentication credentials are invalid or missing
- `BackendError`: When the backend operation fails (network, API errors, etc.)
- `ValidationError`: When query or registry parameters are invalid

**Example:**
```python
quilt_ops = QuiltOpsFactory.create()
packages = quilt_ops.search_packages("machine learning", "s3://my-registry")
for package in packages:
    print(f"Found: {package.name} - {package.description}")
```

#### get_package_info(package_name: str, registry: str) -> Package_Info

Get detailed information about a specific package.

**Parameters:**
- `package_name`: Full package name in "user/package" format
- `registry`: Registry URL where the package is stored

**Returns:**
- `Package_Info` object with detailed package metadata

**Raises:**
- `AuthenticationError`: When authentication credentials are invalid or missing
- `BackendError`: When the backend operation fails or package is not found
- `ValidationError`: When package_name or registry parameters are invalid

**Example:**
```python
package_info = quilt_ops.get_package_info("user/my-package", "s3://my-registry")
print(f"Package: {package_info.name}")
print(f"Description: {package_info.description}")
print(f"Tags: {', '.join(package_info.tags)}")
```

#### browse_content(package_name: str, registry: str, path: str = "") -> List[Content_Info]

Browse contents of a package at the specified path.

**Parameters:**
- `package_name`: Full package name in "user/package" format
- `registry`: Registry URL where the package is stored
- `path`: Path within the package to browse (defaults to root)

**Returns:**
- List of `Content_Info` objects representing files and directories

**Raises:**
- `AuthenticationError`: When authentication credentials are invalid or missing
- `BackendError`: When the backend operation fails or package/path is not found
- `ValidationError`: When parameters are invalid or path doesn't exist

**Example:**
```python
content = quilt_ops.browse_content("user/my-package", "s3://my-registry", "data/")
for item in content:
    if item.type == "file":
        print(f"File: {item.path} ({item.size} bytes)")
    else:
        print(f"Directory: {item.path}")
```

#### list_buckets() -> List[Bucket_Info]

List accessible S3 buckets for Quilt operations.

**Returns:**
- List of `Bucket_Info` objects representing accessible buckets

**Raises:**
- `AuthenticationError`: When authentication credentials are invalid or missing
- `BackendError`: When the backend operation fails or AWS access is denied

**Example:**
```python
buckets = quilt_ops.list_buckets()
for bucket in buckets:
    print(f"Bucket: {bucket.name} in {bucket.region}")
```

#### get_content_url(package_name: str, registry: str, path: str) -> str

Get download URL for specific content within a package.

**Parameters:**
- `package_name`: Full package name in "user/package" format
- `registry`: Registry URL where the package is stored
- `path`: Path to the specific file within the package

**Returns:**
- URL string for accessing the content

**Raises:**
- `AuthenticationError`: When authentication credentials are invalid or missing
- `BackendError`: When the backend operation fails or content is not found
- `ValidationError`: When parameters are invalid or path doesn't exist

**Example:**
```python
url = quilt_ops.get_content_url("user/my-package", "s3://my-registry", "data/file.csv")
print(f"Download URL: {url}")
```

## QuiltOpsFactory

The `QuiltOpsFactory` handles authentication detection and backend selection.

### create() -> QuiltOps

Create QuiltOps instance with appropriate backend based on available authentication.

**Authentication Priority (Phase 1):**
1. Quilt3 session (via `quilt3 login`)

**Returns:**
- `QuiltOps` instance with appropriate backend

**Raises:**
- `AuthenticationError`: When no valid authentication is found

**Example:**
```python
from quilt_mcp.ops.factory import QuiltOpsFactory

# Create QuiltOps instance (automatically detects authentication)
quilt_ops = QuiltOpsFactory.create()

# Use the instance
packages = quilt_ops.search_packages("data", "s3://my-registry")
```

## Backend Implementations

### Quilt3_Backend

Implements QuiltOps using the quilt3 Python library.

**Features:**
- Uses quilt3 library for all operations
- Transforms quilt3 objects to domain objects
- Comprehensive error handling with context
- Debug logging for all operations

**Authentication:**
- Requires valid quilt3 session (via `quilt3 login`)
- Validates session during initialization

## Error Handling

### Exception Types

#### AuthenticationError
Raised when authentication credentials are invalid or missing.

**Common Causes:**
- No quilt3 session available
- Invalid or expired session
- Missing authentication configuration

**Example Error Message:**
```
No valid authentication found. Please provide valid quilt3 session.
To authenticate with quilt3, run: quilt3 login
For more information, see: https://docs.quiltdata.com/installation-and-setup
```

#### BackendError
Raised when backend operations fail.

**Features:**
- Includes backend type in error message
- Provides operation context for debugging
- Preserves original error information

**Example Error Message:**
```
Quilt3 backend search failed: Network timeout
Context: {'query': 'test', 'registry': 's3://my-registry'}
```

#### ValidationError
Raised when input parameters are invalid.

**Common Causes:**
- Invalid package name format
- Malformed registry URLs
- Invalid path specifications

## Usage Patterns

### Basic Package Search and Browse

```python
from quilt_mcp.ops.factory import QuiltOpsFactory

# Initialize QuiltOps
quilt_ops = QuiltOpsFactory.create()

# Search for packages
packages = quilt_ops.search_packages("machine learning", "s3://my-registry")

# Get detailed info for first package
if packages:
    package_info = quilt_ops.get_package_info(packages[0].name, "s3://my-registry")
    
    # Browse package contents
    content = quilt_ops.browse_content(package_info.name, package_info.registry)
    
    # Get download URL for specific file
    if content:
        file_content = [c for c in content if c.type == "file"][0]
        url = quilt_ops.get_content_url(
            package_info.name, 
            package_info.registry, 
            file_content.path
        )
        print(f"Download: {url}")
```

### Error Handling Pattern

```python
from quilt_mcp.ops.factory import QuiltOpsFactory
from quilt_mcp.ops.exceptions import AuthenticationError, BackendError

try:
    quilt_ops = QuiltOpsFactory.create()
    packages = quilt_ops.search_packages("data", "s3://my-registry")
    
except AuthenticationError as e:
    print(f"Authentication failed: {e}")
    print("Please run 'quilt3 login' to authenticate")
    
except BackendError as e:
    print(f"Operation failed: {e}")
    if hasattr(e, 'context'):
        print(f"Context: {e.context}")
```

### Working with Domain Objects

```python
# Convert domain objects to dictionaries for JSON serialization
from dataclasses import asdict

packages = quilt_ops.search_packages("data", "s3://my-registry")
packages_dict = [asdict(pkg) for pkg in packages]

# Use domain object fields
for package in packages:
    print(f"Package: {package.name}")
    print(f"Modified: {package.modified_date}")
    print(f"Tags: {', '.join(package.tags)}")
    print(f"Registry: {package.registry}")
```

## Migration from QuiltService

### Key Changes

1. **Import Changes:**
   ```python
   # Old
   from quilt_mcp.services.quilt_service import QuiltService
   
   # New
   from quilt_mcp.ops.factory import QuiltOpsFactory
   ```

2. **Initialization Changes:**
   ```python
   # Old
   quilt_service = QuiltService()
   
   # New
   quilt_ops = QuiltOpsFactory.create()
   ```

3. **Method Changes:**
   ```python
   # Old
   packages = quilt_service.search_packages(query, registry)
   
   # New
   packages = quilt_ops.search_packages(query, registry)
   ```

4. **Return Type Changes:**
   ```python
   # Old - returns quilt3 objects
   packages = quilt_service.search_packages(query, registry)
   for pkg in packages:
       print(pkg.name)  # quilt3.Package object
   
   # New - returns domain objects
   packages = quilt_ops.search_packages(query, registry)
   for pkg in packages:
       print(pkg.name)  # Package_Info object
   ```

### Migration Checklist

- [ ] Replace `QuiltService` imports with `QuiltOpsFactory`
- [ ] Update initialization code to use `QuiltOpsFactory.create()`
- [ ] Update method calls to use QuiltOps interface
- [ ] Update code to work with domain objects instead of quilt3 objects
- [ ] Update error handling to catch `AuthenticationError` and `BackendError`
- [ ] Test with actual quilt3 session authentication

## Best Practices

### 1. Use Factory Pattern
Always use `QuiltOpsFactory.create()` instead of directly instantiating backends.

### 2. Handle Errors Gracefully
Always catch and handle `AuthenticationError` and `BackendError` exceptions.

### 3. Work with Domain Objects
Use the domain objects (`Package_Info`, `Content_Info`, `Bucket_Info`) instead of backend-specific types.

### 4. Validate Inputs
Validate package names, registry URLs, and paths before calling QuiltOps methods.

### 5. Use Context Information
When handling `BackendError`, check for context information to aid debugging.

## Troubleshooting

### Common Issues

#### "No valid authentication found"
**Cause:** No quilt3 session available
**Solution:** Run `quilt3 login` to authenticate

#### "Quilt3 backend search failed"
**Cause:** Network issues, invalid registry, or permission problems
**Solution:** Check network connectivity, verify registry URL, and ensure proper permissions

#### "Package not found"
**Cause:** Package doesn't exist or insufficient permissions
**Solution:** Verify package name and check access permissions

### Debug Logging

Enable debug logging to see detailed operation information:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# QuiltOps operations will now produce debug logs
quilt_ops = QuiltOpsFactory.create()
packages = quilt_ops.search_packages("data", "s3://my-registry")
```

## Future Enhancements (Phase 2)

The QuiltOps abstraction is designed to support multiple backends. Phase 2 will add:

- **Platform_Backend**: GraphQL API backend for HTTP/JWT authentication
- **JWT Authentication**: Support for JWT token-based authentication
- **Backend Selection**: Automatic routing based on authentication type
- **Enhanced Error Handling**: Backend-specific error recovery strategies

The interface will remain the same, ensuring backward compatibility for existing code.
# Domain Objects Documentation

## Overview

Domain objects in the QuiltOps abstraction layer provide backend-agnostic representations of Quilt concepts. These objects ensure that MCP tools work with consistent data structures regardless of the underlying backend implementation (quilt3 library, Platform GraphQL, etc.).

## Design Principles

### 1. Backend Agnostic
Domain objects abstract away backend-specific details, providing a unified interface for all Quilt operations.

### 2. Immutable Data
All domain objects are implemented as dataclasses with immutable fields, ensuring data consistency and thread safety.

### 3. JSON Serializable
All domain objects can be converted to dictionaries using `dataclasses.asdict()` for JSON serialization in MCP responses.

### 4. Type Safe
All fields are properly typed with Python type hints for better IDE support and runtime validation.

## Domain Objects

### Package_Info

Represents package metadata consistently across all backends.

```python
@dataclass
class Package_Info:
    name: str                    # Package name in "user/package" format
    description: Optional[str]   # Package description (can be None)
    tags: List[str]             # List of package tags (empty list if none)
    modified_date: str          # ISO 8601 format modification date
    registry: str               # Registry URL (e.g., "s3://my-registry")
    bucket: str                 # S3 bucket name
    top_hash: str               # Package version hash identifier
```

#### Field Details

**name** (str, required)
- Format: "namespace/package-name"
- Example: "user/my-data-package"
- Validation: Must contain exactly one forward slash

**description** (Optional[str])
- Human-readable package description
- Can be None if no description is available
- Example: "Machine learning dataset for image classification"

**tags** (List[str])
- List of package tags for categorization
- Empty list if no tags are assigned
- Example: ["machine-learning", "images", "classification"]

**modified_date** (str, required)
- ISO 8601 formatted timestamp
- Always in UTC timezone
- Example: "2024-01-15T14:30:00Z"

**registry** (str, required)
- Full S3 URI of the registry
- Example: "s3://my-company-registry"

**bucket** (str, required)
- S3 bucket name (without s3:// prefix)
- Example: "my-company-registry"

**top_hash** (str, required)
- Unique identifier for the package version
- Example: "abc123def456789"

#### Usage Examples

```python
# Creating a Package_Info object
package = Package_Info(
    name="data-team/customer-analysis",
    description="Customer behavior analysis dataset",
    tags=["analytics", "customer", "behavior"],
    modified_date="2024-01-15T14:30:00Z",
    registry="s3://company-data-registry",
    bucket="company-data-registry",
    top_hash="a1b2c3d4e5f6"
)

# Accessing fields
print(f"Package: {package.name}")
print(f"Last modified: {package.modified_date}")
print(f"Tags: {', '.join(package.tags)}")

# Converting to dictionary for JSON serialization
from dataclasses import asdict
package_dict = asdict(package)
```

### Content_Info

Represents file or directory information within a package.

```python
@dataclass
class Content_Info:
    path: str                      # File/directory path within package
    size: Optional[int]            # File size in bytes (None for directories)
    type: str                      # "file" or "directory"
    modified_date: Optional[str]   # ISO 8601 format modification date
    download_url: Optional[str]    # Direct download URL (if available)
```

#### Field Details

**path** (str, required)
- Relative path within the package
- Uses forward slashes as path separators
- Example: "data/processed/results.csv"

**size** (Optional[int])
- File size in bytes
- None for directories
- Example: 1048576 (1 MB)

**type** (str, required)
- Either "file" or "directory"
- Determines how the content should be handled
- Example: "file"

**modified_date** (Optional[str])
- ISO 8601 formatted timestamp
- Can be None if modification date is not available
- Example: "2024-01-15T14:30:00Z"

**download_url** (Optional[str])
- Direct download URL for the content
- None if URL is not available or needs to be generated
- Example: "https://s3.amazonaws.com/bucket/path/file.csv"

#### Usage Examples

```python
# File content
file_content = Content_Info(
    path="data/analysis/results.csv",
    size=2048,
    type="file",
    modified_date="2024-01-15T14:30:00Z",
    download_url="https://s3.amazonaws.com/bucket/results.csv"
)

# Directory content
dir_content = Content_Info(
    path="data/raw",
    size=None,  # Directories don't have size
    type="directory",
    modified_date="2024-01-15T14:30:00Z",
    download_url=None  # Directories don't have download URLs
)

# Working with content lists
content_list = [file_content, dir_content]
files = [c for c in content_list if c.type == "file"]
directories = [c for c in content_list if c.type == "directory"]

print(f"Found {len(files)} files and {len(directories)} directories")
```

### Bucket_Info

Represents S3 bucket metadata for Quilt operations.

```python
@dataclass
class Bucket_Info:
    name: str                      # Bucket name
    region: str                    # AWS region
    access_level: str              # Access level description
    created_date: Optional[str]    # ISO 8601 format creation date
```

#### Field Details

**name** (str, required)
- S3 bucket name (without s3:// prefix)
- Example: "my-data-bucket"

**region** (str, required)
- AWS region where the bucket is located
- Example: "us-east-1"

**access_level** (str, required)
- Human-readable access level description
- Example: "read-write", "read-only", "admin"

**created_date** (Optional[str])
- ISO 8601 formatted creation timestamp
- Can be None if creation date is not available
- Example: "2024-01-01T00:00:00Z"

#### Usage Examples

```python
# Creating a Bucket_Info object
bucket = Bucket_Info(
    name="company-data-lake",
    region="us-west-2",
    access_level="read-write",
    created_date="2024-01-01T00:00:00Z"
)

# Accessing fields
print(f"Bucket: {bucket.name} in {bucket.region}")
print(f"Access: {bucket.access_level}")

# Working with bucket lists
buckets = [bucket]  # List of Bucket_Info objects
writable_buckets = [b for b in buckets if "write" in b.access_level]
```

## Common Patterns

### JSON Serialization

All domain objects can be easily converted to JSON-serializable dictionaries:

```python
from dataclasses import asdict
import json

# Convert single object
package_dict = asdict(package_info)
json_str = json.dumps(package_dict)

# Convert list of objects
packages_dict = [asdict(pkg) for pkg in packages_list]
json_str = json.dumps(packages_dict)
```

### Filtering and Processing

Domain objects work well with Python's built-in functions and list comprehensions:

```python
# Filter packages by tag
ml_packages = [pkg for pkg in packages if "machine-learning" in pkg.tags]

# Find large files
large_files = [content for content in content_list 
               if content.type == "file" and content.size and content.size > 1000000]

# Group by bucket region
from collections import defaultdict
buckets_by_region = defaultdict(list)
for bucket in buckets:
    buckets_by_region[bucket.region].append(bucket)
```

### Validation

While domain objects don't include built-in validation, you can add validation logic:

```python
def validate_package_name(name: str) -> bool:
    """Validate package name format."""
    return "/" in name and len(name.split("/")) == 2

def validate_content_path(path: str) -> bool:
    """Validate content path format."""
    return not path.startswith("/") and not path.endswith("/")

# Usage
if validate_package_name(package.name):
    print("Valid package name")
```

## Backend Transformation

Domain objects are created by transforming backend-specific objects. Each backend implements transformation methods:

### Quilt3_Backend Transformations

```python
def _transform_package(self, quilt3_package) -> Package_Info:
    """Transform quilt3.Package to Package_Info."""
    return Package_Info(
        name=quilt3_package.name,
        description=quilt3_package.description,
        tags=quilt3_package.tags or [],
        modified_date=quilt3_package.modified.isoformat(),
        registry=quilt3_package.registry,
        bucket=quilt3_package.bucket,
        top_hash=quilt3_package.top_hash
    )
```

### Error Handling in Transformations

Transformation methods include error handling for missing or invalid data:

```python
def _transform_content(self, quilt3_entry) -> Content_Info:
    """Transform quilt3 content entry to Content_Info."""
    try:
        # Handle missing or None fields gracefully
        size = getattr(quilt3_entry, 'size', None)
        modified_date = None
        if hasattr(quilt3_entry, 'modified') and quilt3_entry.modified:
            modified_date = quilt3_entry.modified.isoformat()
        
        return Content_Info(
            path=quilt3_entry.name,
            size=size,
            type="directory" if getattr(quilt3_entry, 'is_dir', False) else "file",
            modified_date=modified_date,
            download_url=None
        )
    except Exception as e:
        raise BackendError(f"Content transformation failed: {str(e)}")
```

## Testing Domain Objects

Domain objects are easy to test due to their simple structure:

```python
def test_package_info_creation():
    """Test Package_Info object creation."""
    package = Package_Info(
        name="test/package",
        description="Test package",
        tags=["test"],
        modified_date="2024-01-01T00:00:00Z",
        registry="s3://test-registry",
        bucket="test-bucket",
        top_hash="test123"
    )
    
    assert package.name == "test/package"
    assert package.description == "Test package"
    assert "test" in package.tags
    assert package.registry == "s3://test-registry"

def test_content_info_file_vs_directory():
    """Test Content_Info for files vs directories."""
    file_content = Content_Info(
        path="file.txt",
        size=100,
        type="file",
        modified_date="2024-01-01T00:00:00Z",
        download_url="https://example.com/file.txt"
    )
    
    dir_content = Content_Info(
        path="directory",
        size=None,
        type="directory",
        modified_date="2024-01-01T00:00:00Z",
        download_url=None
    )
    
    assert file_content.type == "file"
    assert file_content.size == 100
    assert dir_content.type == "directory"
    assert dir_content.size is None
```

## Migration from Backend-Specific Objects

When migrating from direct backend usage to domain objects:

### Before (quilt3-specific)
```python
# Working directly with quilt3 objects
packages = quilt3.search("query", registry="s3://registry")
for pkg in packages:
    print(f"Package: {pkg.name}")  # quilt3.Package object
    print(f"Modified: {pkg.modified}")  # datetime object
    print(f"Tags: {pkg.tags}")  # might be None
```

### After (domain objects)
```python
# Working with domain objects
packages = quilt_ops.search_packages("query", "s3://registry")
for pkg in packages:
    print(f"Package: {pkg.name}")  # str
    print(f"Modified: {pkg.modified_date}")  # ISO string
    print(f"Tags: {', '.join(pkg.tags)}")  # always a list
```

## Best Practices

### 1. Use Type Hints
Always use proper type hints when working with domain objects:

```python
from typing import List
from quilt_mcp.domain import Package_Info

def process_packages(packages: List[Package_Info]) -> None:
    for package in packages:
        # IDE will provide proper autocomplete
        print(package.name)
```

### 2. Handle Optional Fields
Always check for None values in optional fields:

```python
if content.size is not None:
    print(f"File size: {content.size} bytes")

if package.description:
    print(f"Description: {package.description}")
```

### 3. Use dataclasses.asdict() for Serialization
Use the built-in dataclasses function for JSON serialization:

```python
from dataclasses import asdict

# Correct
package_dict = asdict(package)

# Avoid manual dictionary creation
# package_dict = {
#     "name": package.name,
#     "description": package.description,
#     # ... manual field mapping
# }
```

### 4. Leverage List Comprehensions
Use Python's list comprehensions for filtering and processing:

```python
# Find packages with specific tags
ml_packages = [pkg for pkg in packages if "ml" in pkg.tags]

# Get file sizes
file_sizes = [c.size for c in content if c.type == "file" and c.size]
```

## Future Enhancements

Domain objects are designed to be extensible for future backend implementations:

### Planned Additions (Phase 2)
- Additional metadata fields for Platform backend
- Enhanced validation methods
- Serialization optimizations
- Caching support for frequently accessed objects

### Backward Compatibility
All changes to domain objects will maintain backward compatibility to ensure existing code continues to work.
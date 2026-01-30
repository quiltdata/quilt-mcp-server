# Error Handling Documentation

## Overview

The QuiltOps abstraction layer provides comprehensive error handling that transforms backend-specific errors into domain-appropriate exceptions with clear error messages and actionable remediation steps.

## Error Hierarchy

```
Exception
├── QuiltOpsError (base class)
    ├── AuthenticationError
    ├── BackendError
    └── ValidationError
```

## Exception Types

### AuthenticationError

Raised when authentication credentials are invalid, missing, or expired.

```python
class AuthenticationError(Exception):
    """Raised when authentication fails or is missing."""
    
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message
```

#### Common Scenarios

**No Authentication Available**
```python
# Error message
"No valid authentication found. Please provide valid quilt3 session.
To authenticate with quilt3, run: quilt3 login
For more information, see: https://docs.quiltdata.com/installation-and-setup"
```

**Invalid Session**
```python
# Error message
"Invalid quilt3 session: Session expired or corrupted.
Please re-authenticate with: quilt3 login"
```

**Missing quilt3 Library**
```python
# Error message
"quilt3 library is not available. Please install quilt3:
pip install quilt3"
```

#### Handling AuthenticationError

```python
from quilt_mcp.ops.factory import QuiltOpsFactory
from quilt_mcp.ops.exceptions import AuthenticationError

try:
    quilt_ops = QuiltOpsFactory.create()
except AuthenticationError as e:
    print(f"Authentication failed: {e}")
    print("Please run 'quilt3 login' to authenticate")
    return None
```

### BackendError

Raised when backend operations fail due to network issues, API errors, or data problems.

```python
class BackendError(Exception):
    """Raised when backend operations fail."""
    
    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.context = context or {}
```

#### Features

**Backend Type Identification**
All BackendError messages include the backend type for debugging:
```python
"Quilt3 backend search failed: Network timeout"
"Platform backend browse_content failed: GraphQL query error"
```

**Operation Context**
BackendError includes context information about the failed operation:
```python
context = {
    'query': 'machine learning',
    'registry': 's3://my-registry',
    'operation': 'search_packages'
}
```

**Original Error Preservation**
The original backend error is preserved in the error message:
```python
"Quilt3 backend search failed: ConnectionError: Unable to connect to registry"
```

#### Common Scenarios

**Network Errors**
```python
# Error message
"Quilt3 backend search failed: Network timeout after 30 seconds"
# Context
{'query': 'data', 'registry': 's3://my-registry', 'timeout': 30}
```

**Permission Errors**
```python
# Error message
"Quilt3 backend browse_content failed: Access denied to package 'private/data'"
# Context
{'package_name': 'private/data', 'registry': 's3://registry', 'path': ''}
```

**Package Not Found**
```python
# Error message
"Quilt3 backend get_package_info failed: Package 'user/nonexistent' not found"
# Context
{'package_name': 'user/nonexistent', 'registry': 's3://registry'}
```

**Data Transformation Errors**
```python
# Error message
"Quilt3 backend package transformation failed: Invalid date format in package metadata"
# Context
{'package_name': 'user/package', 'field': 'modified_date'}
```

#### Handling BackendError

```python
from quilt_mcp.ops.exceptions import BackendError

try:
    packages = quilt_ops.search_packages("query", "s3://registry")
except BackendError as e:
    print(f"Operation failed: {e}")
    
    # Access context information for debugging
    if hasattr(e, 'context') and e.context:
        print(f"Context: {e.context}")
        
        # Handle specific error types based on context
        if 'timeout' in str(e):
            print("Network timeout - please try again later")
        elif 'access denied' in str(e).lower():
            print("Permission denied - check your access rights")
        elif 'not found' in str(e).lower():
            print("Resource not found - verify the name and try again")
```

### ValidationError

Raised when input parameters are invalid or malformed.

```python
class ValidationError(Exception):
    """Raised when input validation fails."""
    
    def __init__(self, message: str, field: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.field = field
```

#### Common Scenarios

**Invalid Package Name**
```python
# Error message
"Invalid package name format: 'invalid-name'. Expected format: 'user/package'"
# Field
field = "package_name"
```

**Invalid Registry URL**
```python
# Error message
"Invalid registry URL: 'not-a-url'. Expected S3 URI format: 's3://bucket-name'"
# Field
field = "registry"
```

**Invalid Path**
```python
# Error message
"Invalid path format: '/absolute/path'. Paths must be relative within the package"
# Field
field = "path"
```

#### Handling ValidationError

```python
from quilt_mcp.ops.exceptions import ValidationError

def safe_search_packages(query: str, registry: str):
    try:
        return quilt_ops.search_packages(query, registry)
    except ValidationError as e:
        print(f"Invalid input: {e}")
        if hasattr(e, 'field') and e.field:
            print(f"Problem with field: {e.field}")
        return []
```

## Error Handling Patterns

### Comprehensive Error Handling

```python
from quilt_mcp.ops.factory import QuiltOpsFactory
from quilt_mcp.ops.exceptions import AuthenticationError, BackendError, ValidationError

def robust_package_search(query: str, registry: str):
    """Perform package search with comprehensive error handling."""
    try:
        # Create QuiltOps instance
        quilt_ops = QuiltOpsFactory.create()
        
        # Perform search
        packages = quilt_ops.search_packages(query, registry)
        
        return {
            'success': True,
            'packages': packages,
            'count': len(packages)
        }
        
    except AuthenticationError as e:
        return {
            'success': False,
            'error': 'authentication_failed',
            'message': str(e),
            'remediation': 'Run "quilt3 login" to authenticate'
        }
        
    except ValidationError as e:
        return {
            'success': False,
            'error': 'invalid_input',
            'message': str(e),
            'field': getattr(e, 'field', None),
            'remediation': 'Check input parameters and try again'
        }
        
    except BackendError as e:
        error_type = 'backend_error'
        remediation = 'Please try again later'
        
        # Provide specific remediation based on error type
        error_msg = str(e).lower()
        if 'timeout' in error_msg or 'network' in error_msg:
            error_type = 'network_error'
            remediation = 'Check network connection and try again'
        elif 'access denied' in error_msg or 'permission' in error_msg:
            error_type = 'permission_error'
            remediation = 'Check access permissions for the registry'
        elif 'not found' in error_msg:
            error_type = 'not_found'
            remediation = 'Verify the registry URL and package names'
            
        return {
            'success': False,
            'error': error_type,
            'message': str(e),
            'context': getattr(e, 'context', {}),
            'remediation': remediation
        }
        
    except Exception as e:
        # Catch-all for unexpected errors
        return {
            'success': False,
            'error': 'unexpected_error',
            'message': f'Unexpected error: {str(e)}',
            'remediation': 'Please report this issue'
        }
```

### Retry Logic for Transient Errors

```python
import time
from typing import Optional, Callable, Any

def retry_on_transient_error(
    operation: Callable,
    max_retries: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0
) -> Any:
    """Retry operation on transient errors with exponential backoff."""
    
    for attempt in range(max_retries + 1):
        try:
            return operation()
            
        except BackendError as e:
            error_msg = str(e).lower()
            
            # Check if error is transient (retryable)
            is_transient = any(keyword in error_msg for keyword in [
                'timeout', 'network', 'connection', 'temporary', 'rate limit'
            ])
            
            if not is_transient or attempt == max_retries:
                raise  # Re-raise if not transient or max retries reached
                
            # Wait before retry with exponential backoff
            wait_time = delay * (backoff_factor ** attempt)
            print(f"Transient error, retrying in {wait_time:.1f}s... (attempt {attempt + 1}/{max_retries})")
            time.sleep(wait_time)
            
        except (AuthenticationError, ValidationError):
            # Don't retry authentication or validation errors
            raise

# Usage
def search_with_retry(query: str, registry: str):
    quilt_ops = QuiltOpsFactory.create()
    
    def search_operation():
        return quilt_ops.search_packages(query, registry)
    
    return retry_on_transient_error(search_operation)
```

### Graceful Degradation

```python
def search_packages_with_fallback(query: str, registries: List[str]):
    """Search packages with fallback to alternative registries."""
    results = []
    errors = []
    
    for registry in registries:
        try:
            packages = quilt_ops.search_packages(query, registry)
            results.extend(packages)
            
        except AuthenticationError:
            # Authentication errors are not recoverable
            raise
            
        except BackendError as e:
            # Log error but continue with other registries
            errors.append({
                'registry': registry,
                'error': str(e),
                'context': getattr(e, 'context', {})
            })
            continue
            
        except ValidationError as e:
            # Validation errors apply to all registries
            raise
    
    if not results and errors:
        # If no results and we have errors, raise the first error
        first_error = errors[0]
        raise BackendError(
            f"All registries failed. First error: {first_error['error']}",
            context={'failed_registries': [e['registry'] for e in errors]}
        )
    
    return {
        'packages': results,
        'errors': errors,
        'successful_registries': len(registries) - len(errors)
    }
```

## Logging and Debugging

### Debug Logging

Enable debug logging to see detailed error information:

```python
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# QuiltOps operations will now produce debug logs
try:
    quilt_ops = QuiltOpsFactory.create()
    packages = quilt_ops.search_packages("data", "s3://registry")
except Exception as e:
    # Debug logs will show the full error chain
    logging.exception("Operation failed")
```

### Error Context Analysis

```python
def analyze_backend_error(error: BackendError) -> Dict[str, Any]:
    """Analyze BackendError for debugging information."""
    analysis = {
        'error_type': type(error).__name__,
        'message': str(error),
        'backend': 'unknown',
        'operation': 'unknown',
        'likely_cause': 'unknown'
    }
    
    # Extract backend type from error message
    error_msg = str(error)
    if 'Quilt3 backend' in error_msg:
        analysis['backend'] = 'quilt3'
    elif 'Platform backend' in error_msg:
        analysis['backend'] = 'platform'
    
    # Extract operation from context
    if hasattr(error, 'context') and error.context:
        context = error.context
        analysis['context'] = context
        
        # Determine operation from context
        if 'query' in context:
            analysis['operation'] = 'search_packages'
        elif 'package_name' in context and 'path' in context:
            analysis['operation'] = 'browse_content'
        elif 'package_name' in context:
            analysis['operation'] = 'get_package_info'
    
    # Analyze likely cause
    error_lower = error_msg.lower()
    if 'timeout' in error_lower or 'network' in error_lower:
        analysis['likely_cause'] = 'network_issue'
    elif 'access denied' in error_lower or 'permission' in error_lower:
        analysis['likely_cause'] = 'permission_issue'
    elif 'not found' in error_lower:
        analysis['likely_cause'] = 'resource_not_found'
    elif 'invalid' in error_lower or 'malformed' in error_lower:
        analysis['likely_cause'] = 'data_format_issue'
    
    return analysis
```

## Error Recovery Strategies

### Automatic Recovery

```python
class QuiltOpsWithRecovery:
    """QuiltOps wrapper with automatic error recovery."""
    
    def __init__(self):
        self.quilt_ops = None
        self._initialize()
    
    def _initialize(self):
        """Initialize QuiltOps with error handling."""
        try:
            self.quilt_ops = QuiltOpsFactory.create()
        except AuthenticationError:
            # Try to re-authenticate automatically
            self._attempt_reauth()
    
    def _attempt_reauth(self):
        """Attempt automatic re-authentication."""
        # This would implement automatic re-authentication logic
        # For now, just raise the original error
        raise AuthenticationError(
            "Authentication failed. Please run 'quilt3 login' to re-authenticate."
        )
    
    def search_packages(self, query: str, registry: str, max_retries: int = 3):
        """Search packages with automatic retry on transient errors."""
        for attempt in range(max_retries):
            try:
                return self.quilt_ops.search_packages(query, registry)
                
            except BackendError as e:
                if attempt == max_retries - 1:
                    raise  # Last attempt, re-raise error
                
                # Check if error is retryable
                if self._is_retryable_error(e):
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
                else:
                    raise  # Non-retryable error
    
    def _is_retryable_error(self, error: BackendError) -> bool:
        """Determine if an error is retryable."""
        retryable_keywords = ['timeout', 'network', 'temporary', 'rate limit']
        error_msg = str(error).lower()
        return any(keyword in error_msg for keyword in retryable_keywords)
```

## Best Practices

### 1. Always Handle Authentication Errors

```python
# Good
try:
    quilt_ops = QuiltOpsFactory.create()
except AuthenticationError as e:
    print(f"Please authenticate: {e}")
    return

# Bad - unhandled authentication error will crash the application
quilt_ops = QuiltOpsFactory.create()  # May raise AuthenticationError
```

### 2. Use Context Information for Debugging

```python
# Good
try:
    packages = quilt_ops.search_packages(query, registry)
except BackendError as e:
    print(f"Search failed: {e}")
    if hasattr(e, 'context'):
        print(f"Context: {e.context}")

# Bad - missing valuable debugging information
try:
    packages = quilt_ops.search_packages(query, registry)
except BackendError as e:
    print("Search failed")  # No details
```

### 3. Provide Actionable Error Messages

```python
# Good
except AuthenticationError as e:
    return {
        'error': str(e),
        'action': 'Run "quilt3 login" to authenticate',
        'help_url': 'https://docs.quiltdata.com/installation-and-setup'
    }

# Bad - no guidance for user
except AuthenticationError as e:
    return {'error': 'Auth failed'}
```

### 4. Implement Appropriate Retry Logic

```python
# Good - retry only transient errors
def is_transient_error(error):
    transient_keywords = ['timeout', 'network', 'rate limit']
    return any(keyword in str(error).lower() for keyword in transient_keywords)

if is_transient_error(error):
    # Retry with backoff
    pass
else:
    # Don't retry, handle appropriately
    raise

# Bad - retry all errors (including authentication/validation)
for attempt in range(3):
    try:
        return operation()
    except Exception:
        if attempt < 2:
            time.sleep(1)
        else:
            raise
```

### 5. Log Errors Appropriately

```python
import logging

logger = logging.getLogger(__name__)

# Good - structured logging with context
try:
    packages = quilt_ops.search_packages(query, registry)
except BackendError as e:
    logger.error(
        "Package search failed",
        extra={
            'query': query,
            'registry': registry,
            'error': str(e),
            'context': getattr(e, 'context', {})
        }
    )

# Bad - minimal logging
try:
    packages = quilt_ops.search_packages(query, registry)
except Exception as e:
    logger.error("Error occurred")
```

## Migration from QuiltService Error Handling

### Before (QuiltService)
```python
try:
    packages = quilt_service.search_packages(query, registry)
except Exception as e:
    # Generic exception handling
    print(f"Error: {e}")
```

### After (QuiltOps)
```python
try:
    packages = quilt_ops.search_packages(query, registry)
except AuthenticationError as e:
    # Specific authentication error handling
    print(f"Authentication failed: {e}")
    print("Run 'quilt3 login' to authenticate")
except BackendError as e:
    # Backend-specific error handling with context
    print(f"Backend operation failed: {e}")
    if hasattr(e, 'context'):
        print(f"Context: {e.context}")
except ValidationError as e:
    # Input validation error handling
    print(f"Invalid input: {e}")
    if hasattr(e, 'field'):
        print(f"Problem with field: {e.field}")
```

This migration provides much more specific error handling and better user experience through actionable error messages and remediation steps.
# Navigation Context Integration

This document describes the integration between Qurator's native navigation tools and the MCP server tools, enabling seamless context-aware operations.

## Overview

The navigation context integration allows MCP tools to automatically adapt to the user's current navigation state, providing smart defaults and enhanced user experience.

## Architecture

### Navigation Context Types

```python
@dataclass
class NavigationContext:
    route: Route
    stack_info: Optional[StackInfo] = None

@dataclass
class Route:
    name: str  # e.g., "bucket.overview", "bucket.object", "home"
    params: Optional[RouteParams] = None

@dataclass
class RouteParams:
    bucket: Optional[str] = None
    path: Optional[str] = None
    version: Optional[str] = None
    mode: Optional[str] = None
```

### Context Helper Functions

- `get_context_scope_and_target()` - Extract scope and target from navigation context
- `get_context_path_prefix()` - Get directory path for prefix-aware searches
- `suggest_package_name_from_context()` - Suggest package names based on current location
- `is_bucket_context()`, `is_object_context()`, `is_prefix_context()` - Context type detection

## Integration Points

### 1. Search Tool Integration

The search tool now automatically detects the current navigation context and applies smart defaults:

```python
# Auto-detect scope and target from navigation context
if _context and scope == "auto":
    context_scope, context_target = get_context_scope_and_target(_context)
    mapped_params["scope"] = context_scope
    if context_target and not mapped_params.get("target"):
        mapped_params["target"] = context_target

# Add path prefix filter for directory-aware searches
if is_prefix_context(_context):
    path_prefix = get_context_path_prefix(_context)
    if path_prefix:
        filters = mapped_params.get("filters", {})
        filters["path_prefix"] = path_prefix
        mapped_params["filters"] = filters
```

**Benefits:**
- When viewing a bucket, searches automatically scope to that bucket
- When viewing a directory, searches automatically filter to that directory
- Users don't need to manually specify bucket/path parameters

### 2. Packaging Tool Integration

The packaging tool provides context-aware package name suggestions:

```python
# Apply navigation context for smart defaults
if _context and not name:
    suggested_name = suggest_package_name_from_context(_context)
    if suggested_name:
        return {
            "success": False,
            "error": f"Package name is required. Suggested name based on current context: {suggested_name}",
            "suggested_name": suggested_name,
            "context_info": {
                "route": _context.route.name,
                "bucket": get_context_bucket(_context),
                "path": get_context_path(_context),
            }
        }
```

**Benefits:**
- When in a directory, suggests package name based on directory name
- When viewing a file, suggests package name based on file name
- Provides helpful context information in error messages

### 3. Buckets Tool Integration

The buckets tool provides enhanced object information when viewing the same object:

```python
# Apply navigation context for smart defaults
if _context and is_object_context(_context):
    context_bucket = get_context_bucket(_context)
    context_path = get_context_path(_context)
    
    # If we're viewing the same object, provide enhanced info
    if (context_bucket and context_path and 
        params.get("bucket") == context_bucket and 
        params.get("key") == context_path):
        return {
            "success": True,
            "object": {
                "bucket": context_bucket,
                "key": context_path,
                "version": get_context_version(_context),
                "native_context": True,
                "navigation_url": f"/b/{context_bucket}/files/{context_path}",
                "message": "Object info from current navigation context"
            }
        }
```

**Benefits:**
- When viewing an object, provides enhanced metadata from navigation context
- Includes navigation URL for easy access
- Indicates when information comes from native context

## Usage Examples

### Example 1: Context-Aware Search

```javascript
// User navigates to bucket (native tool)
navigate({ 
  route: { 
    name: 'bucket.overview', 
    params: { bucket: 'quilt-sales-raw' } 
  } 
})

// User searches for CSV files (MCP tool with context)
search.unified_search({
  query: "*.csv",
  scope: "auto",  // Auto-detects bucket from navigation context
  // target is auto-populated from current bucket
})

// User navigates to directory (native tool)
navigate({ 
  route: { 
    name: 'bucket.prefix', 
    params: { 
      bucket: 'quilt-sales-raw', 
      path: 'data/experiments/' 
    } 
  } 
})

// User searches again (MCP tool with context)
search.unified_search({
  query: "*.csv",
  scope: "auto",  // Auto-detects bucket and adds path prefix filter
  // target is auto-populated from current bucket
  // filters.path_prefix is auto-populated from current directory
})
```

### Example 2: Context-Aware Package Creation

```javascript
// User navigates to directory (native tool)
navigate({ 
  route: { 
    name: 'bucket.prefix', 
    params: { 
      bucket: 'quilt-sales-raw', 
      path: 'data/experiments/' 
    } 
  } 
})

// User tries to create package without name (MCP tool with context)
packaging.create({
  // name not provided
  files: ["s3://quilt-sales-raw/data/experiments/file1.csv"]
})

// Response includes suggested name
{
  "success": false,
  "error": "Package name is required. Suggested name based on current context: quilt-sales-raw/experiments",
  "suggested_name": "quilt-sales-raw/experiments",
  "context_info": {
    "route": "bucket.prefix",
    "bucket": "quilt-sales-raw",
    "path": "data/experiments/"
  }
}
```

### Example 3: Context-Aware Object Info

```javascript
// User navigates to specific file (native tool)
navigate({ 
  route: { 
    name: 'bucket.object', 
    params: { 
      bucket: 'quilt-sales-raw', 
      path: 'data/experiment.csv',
      version: 'abc123'
    } 
  } 
})

// User gets object info (MCP tool with context)
buckets.object_info({
  bucket: "quilt-sales-raw",
  key: "data/experiment.csv"
})

// Response includes enhanced context information
{
  "success": true,
  "object": {
    "bucket": "quilt-sales-raw",
    "key": "data/experiment.csv",
    "version": "abc123",
    "native_context": true,
    "navigation_url": "/b/quilt-sales-raw/files/data/experiment.csv",
    "message": "Object info from current navigation context"
  }
}
```

## Frontend Integration

### Passing Navigation Context

The frontend should pass navigation context to MCP tool calls:

```typescript
interface MCPToolCall {
  tool: string;
  action: string;
  params: any;
  context?: NavigationContext;  // New: navigation context
}

// Example usage
const searchResult = await mcpClient.callTool({
  tool: "search",
  action: "unified_search",
  params: {
    query: "*.csv",
    scope: "auto"
  },
  context: {
    route: {
      name: "bucket.overview",
      params: { bucket: "quilt-sales-raw" }
    },
    stackInfo: currentStackInfo
  }
});
```

### Navigation Context Structure

```typescript
interface NavigationContext {
  route: {
    name: string;
    params?: {
      bucket?: string;
      path?: string;
      version?: string;
      mode?: string;
    };
  };
  stackInfo?: {
    buckets: Array<{
      name: string;
      title?: string;
      description?: string;
      tags?: string[];
    }>;
  };
}
```

## Benefits

### 1. Reduced Cognitive Load
- Users don't need to manually specify bucket/path parameters
- Smart defaults reduce the need for repetitive input

### 2. Enhanced User Experience
- Seamless flow between native navigation and MCP operations
- Context-aware suggestions and error messages
- Automatic scope detection for searches

### 3. Improved Workflows
- Natural progression from browsing to searching to packaging
- Directory-aware searches and operations
- Enhanced object information with navigation context

### 4. Better Error Handling
- Context-aware error messages with suggestions
- Helpful information about current navigation state
- Clear guidance on next steps

## Implementation Status

✅ **Completed:**
- Navigation context types and helper functions
- Search tool integration with auto-scope detection
- Packaging tool integration with name suggestions
- Buckets tool integration with enhanced object info
- Comprehensive test coverage

🔄 **In Progress:**
- Frontend integration for passing navigation context
- Additional tool integrations (permissions, governance, etc.)

📋 **Planned:**
- Workflow orchestration between native and MCP tools
- Advanced analytics combining native and MCP capabilities
- Batch operations spanning multiple tools

## Testing

The navigation context integration has been thoroughly tested with:

- Context detection and type checking
- Scope and target extraction
- Package name suggestions
- Path prefix filtering
- Enhanced object information

All tests pass successfully, confirming the integration is ready for production deployment.

## Future Enhancements

### 1. Advanced Context Awareness
- Package context detection for package-specific operations
- User preference context for personalized defaults
- Recent activity context for smart suggestions

### 2. Workflow Integration
- Multi-step workflow orchestration
- Context preservation across tool calls
- Progress tracking and state management

### 3. Performance Optimization
- Context caching and invalidation
- Lazy loading of context information
- Efficient context updates

This navigation context integration represents a significant step forward in creating a seamless, intuitive experience that bridges the gap between Qurator's native navigation and the powerful MCP tool ecosystem.

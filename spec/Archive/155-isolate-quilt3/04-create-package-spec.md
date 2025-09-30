<!-- markdownlint-disable MD013 -->
# Create Package API Specification - Fix Abstraction Leak

**Issue**: The current `QuiltService.create_package()` method violates the abstraction layer by returning raw `quilt3.Package` objects.

**Specification**: Replace object-based manipulation with single complete operation method.

## Complete Usage Analysis

### All Package Creation Tools

The package creation ecosystem includes **4 tools** with complex call hierarchy:

1. **package_ops.py** - Basic package creation (direct QuiltService usage)
2. **s3_package.py** - Enhanced creation with auto-organization (direct QuiltService usage)
3. **unified_package.py** - Unified interface (calls s3_package.py)
4. **package_management.py** - Enhanced interface with templates (calls package_ops.py)

### Real Call Hierarchy

```text
Tools Layer:
├── create_package_enhanced() → package_ops.py → QuiltService.create_package()
└── unified_package.create_package() → s3_package.py → QuiltService.create_package()

Direct Layer:
├── package_ops.package_create() → QuiltService.create_package()
└── s3_package.package_create_from_s3() → QuiltService.create_package()
```

### Current Usage Patterns

**Pattern 1: package_ops.py:189 (Simple)**

```python
pkg = quilt_service.create_package()    # Returns quilt3.Package
pkg = _collect_objects_into_package(pkg, s3_uris, flatten, warnings)
pkg.set_meta(processed_metadata)
result = pkg.push(package_name, registry=registry, message=message)
```

**Pattern 2: s3_package.py:750 (Organized)**

```python
pkg = quilt_service.create_package()    # Returns quilt3.Package
# Smart organization logic
for folder, objects in organized_structure.items():
    pkg.set(logical_path, s3_uri)
pkg.set_meta(enhanced_metadata)
result = pkg.push(package_name, registry=registry, message=message)
```

**Pattern 3: unified_package.py:479 (Routing)**

```python
# Does NOT call QuiltService directly!
result = package_create_from_s3(  # Delegates to s3_package.py
    source_bucket=source_bucket,
    auto_organize=auto_organize,  # Routes organization strategy
    # ... other params
)
```

**Pattern 4: package_management.py:261 (Templates)**

```python
# Does NOT call QuiltService directly!
result = _base_package_create(  # Delegates to package_ops.py
    package_name=name,
    metadata=template_metadata,  # Enriched metadata
    # ... other params
)
```

### The Unifying Pattern

All 4 tools follow the same workflow:

1. **Prepare inputs** (files, metadata, organization strategy)
2. **Create empty package** (via QuiltService)
3. **Populate package** (via different strategies)
4. **Set metadata** (enriched by different layers)
5. **Push package** (same for all)

The key insight: **auto_organize** is the only real difference between the two direct usage patterns.

## Solution Design

### Single Method Approach

Replace `create_package()` with one method handling both organization strategies:

```python
class QuiltService:
    def create_package_revision(
        self,
        package_name: str,
        s3_uris: List[str],
        metadata: Optional[Dict] = None,
        registry: Optional[str] = None,
        message: str = "Package created via QuiltService",
        auto_organize: bool = True
    ) -> Dict[str, Any]:
        """Create and push package in single operation.

        Args:
            auto_organize: True for smart folder organization (s3_package style),
                          False for simple flattening (package_ops style)
        """
```

### Migration Strategy

**All tools migrate to the same method with different auto_organize values:**

- `package_ops` → `auto_organize=False` (preserve flattening)
- `s3_package` → `auto_organize=True` (preserve organization)
- `unified_package` → pass through its `auto_organize` parameter
- `enhanced_package` → pass through its `auto_organize` parameter

### Design Benefits

1. **Complete abstraction** - No quilt3.Package objects exposed
2. **Single method** - One method instead of multiple
3. **Preserves all functionality** - Each tool's behavior unchanged
4. **Simple parameter** - Boolean instead of complex strategies

## Migration Plan

### Phase 1: Add New Method

Add `create_package_revision()` to QuiltService, keep `create_package()` temporarily.

### Phase 2: Update Direct Usage

```python
# package_ops.py - Before
pkg = quilt_service.create_package()
pkg = _collect_objects_into_package(pkg, s3_uris, flatten, warnings)
pkg.set_meta(processed_metadata)
result = pkg.push(package_name, registry=registry, message=message)

# package_ops.py - After
result = quilt_service.create_package_revision(
    package_name=package_name,
    s3_uris=s3_uris,
    metadata=processed_metadata,
    registry=registry,
    message=message,
    auto_organize=False  # Preserve flattening behavior
)
```

```python
# s3_package.py - Before
pkg = quilt_service.create_package()
for folder, objects in organized_structure.items():
    pkg.set(logical_path, s3_uri)
pkg.set_meta(enhanced_metadata)
result = pkg.push(package_name, registry=registry, message=message)

# s3_package.py - After
result = quilt_service.create_package_revision(
    package_name=package_name,
    s3_uris=s3_uris,
    metadata=enhanced_metadata,
    registry=registry,
    message=message,
    auto_organize=True  # Preserve organization behavior
)
```

### Phase 3: Remove Leaky Method

Remove `create_package()` method and verify no quilt3.Package objects are exposed.

## Success Criteria

- ✅ No `quilt3.Package` objects returned from QuiltService
- ✅ Single method handles all 4 tool patterns
- ✅ All existing functionality preserved
- ✅ Tool interfaces remain unchanged

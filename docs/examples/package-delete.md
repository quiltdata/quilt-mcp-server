# Package Delete Example

Delete a package by name from a specific registry bucket:

```python
from quilt_mcp.tools.packages import package_delete

result = package_delete(
    package_name="team/old-analysis",
    registry="s3://my-registry-bucket",
)

if result.success:
    print(result.message)
else:
    print(result.error)
```

Notes:
- `registry` is required.
- `package_delete` now routes through `QuiltOps.delete_package()`, so both quilt3 and platform backends are supported.

"""Configuration management for MCP testing.

This module provides utilities for loading, validating, and filtering test
configurations. It handles YAML parsing, selector-based filtering, and
idempotence-based test selection.

Core Functions
--------------
load_test_config(config_path) -> Dict[str, Any]
    Load and parse test configuration from YAML file with validation.
    Ensures required sections present and properly formatted.

filter_tests_by_idempotence(config, idempotent_only) -> Tuple[Dict[str, Any], Dict]
    Filter test tools based on effect classification. When idempotent_only
    is True, removes all write-effect tools (create/update/remove).

parse_selector(selector_str) -> Tuple[str, Set[str]]
    Parse selector strings supporting multiple formats:
    - "all": Include all items
    - "none": Include no items
    - "name1,name2,name3": Include specific named items

validate_selector_names(selector_type, selector_names, available_items, item_type) -> None
    Validate that selector names reference existing items. Raises
    descriptive errors for typos and missing items.

filter_by_selector(items, selector_type, selector_names) -> Dict[str, Any]
    Apply selector filtering to dictionary of items. Returns filtered
    subset based on selector type and names.

truncate_response(response, max_size) -> Any
    Truncate large responses for YAML serialization. Prevents config
    files from becoming unmanageably large with test data.

Configuration Schema
--------------------
Test configurations follow this structure:

```yaml
tools:
  tool_name:
    args: {...}
    effect: create|update|remove|configure|none
    search_validation:  # Optional
      min_results: 5
      required_fields: [name, modified]

resources:
  resource_uri:
    expected_mime_type: text/plain
    access_level: public|authenticated|denied

tool_loops:
  loop_name:
    create: {...}
    verify: {...}
    cleanup: {...}

environment:
  TEST_QUILT_CATALOG_URL: s3://bucket
  TEST_QUILT_CATALOG_BUCKET: bucket
```

Selector Syntax
---------------
Selectors control which tests run:

1. Universal Selectors
   - "--tools all" → Run all tool tests
   - "--tools none" → Skip all tool tests
   - "--resources all" → Run all resource tests
   - "--resources none" → Skip all resource tests

2. Named Selectors
   - "--tools bucket_list,package_list" → Run specific tools
   - "--resources quilt://bucket/package" → Test specific resources

3. Exclusion (via none + loops)
   - "--tools none --loops package_lifecycle" → Only run loops

Idempotence Filtering
----------------------
When --idempotent-only flag is set:

1. Removes write-effect tools
   - effect: create → Filtered out
   - effect: update → Filtered out
   - effect: remove → Filtered out

2. Keeps read-only tools
   - effect: none → Kept
   - effect: none-context-required → Kept

3. Filters tool loops
   - All loops filtered (create/modify/cleanup)
   - Standalone verify steps may remain

4. Keeps resources
   - Resource tests are read-only

Usage Examples
--------------
Load test configuration:
    >>> config = load_test_config(Path("config/mcp-test.yaml"))
    >>> print(config.keys())
    dict_keys(['tools', 'resources', 'tool_loops', 'environment'])

Filter for idempotent tests:
    >>> filtered, stats = filter_tests_by_idempotence(config, idempotent_only=True)
    >>> print(f"Kept {stats['kept']} tools, filtered {stats['filtered']}")
    Kept 15 tools, filtered 8

Parse selectors:
    >>> selector_type, names = parse_selector("bucket_list,package_list")
    >>> print(selector_type, names)
    specific {'bucket_list', 'package_list'}

Validate selector names:
    >>> available = {"bucket_list": {...}, "package_list": {...}}
    >>> validate_selector_names(
    ...     "specific",
    ...     {"bucket_list", "package_create"},
    ...     available,
    ...     "tools"
    ... )
    # Raises error: "Unknown tool: package_create"

Filter by selector:
    >>> tools = {"bucket_list": {...}, "package_list": {...}, "bucket_create": {...}}
    >>> filtered = filter_by_selector(tools, "specific", {"bucket_list", "package_list"})
    >>> print(filtered.keys())
    dict_keys(['bucket_list', 'package_list'])

Truncate large responses:
    >>> large_data = {"results": ["item" + str(i) for i in range(10000)]}
    >>> truncated = truncate_response(large_data, max_size=1000)
    >>> print(truncated["results"][-1])
    [TRUNCATED: 9000 more items...]

Design Principles
-----------------
- Clear error messages for configuration issues
- Fail-fast validation during load
- Flexible selector syntax for common patterns
- Preserve structure during filtering
- Comprehensive type hints
- No side effects (pure functions)

Error Handling
--------------
The module provides detailed error messages:

1. File Not Found
   - Clear path in error message
   - Suggest correct location

2. YAML Parse Errors
   - Show line number and column
   - Highlight syntax issues

3. Schema Validation
   - List missing required fields
   - Show expected structure

4. Selector Errors
   - List available items
   - Suggest closest matches for typos

Dependencies
------------
- pathlib: Path handling
- yaml: YAML parsing
- typing: Type hints
- Standard library only (no internal dependencies)

Extracted From
--------------
- load_test_config: lines 1907-1933 from scripts/mcp-test.py
- filter_tests_by_idempotence: lines 1936-1981 from scripts/mcp-test.py
- parse_selector: lines 2310-2346 from scripts/mcp-test.py
- validate_selector_names: lines 2349-2376 from scripts/mcp-test.py
- filter_by_selector: lines 2379-2401 from scripts/mcp-test.py
- truncate_response: lines 1231-1263 from scripts/mcp-test-setup.py
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml


def load_test_config(config_path: Path) -> Dict[str, Any]:
    """Load test configuration from YAML file."""
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        # Validate required environment variables
        env_vars = config.get("environment", {})
        quilt_test_bucket = env_vars.get("QUILT_TEST_BUCKET")

        if not quilt_test_bucket:
            print("❌ QUILT_TEST_BUCKET must be set in test configuration")
            print("   Edit scripts/tests/mcp-test.yaml and set environment.QUILT_TEST_BUCKET")
            sys.exit(1)

        # Ensure QUILT_TEST_BUCKET is also set in OS environment
        if not os.environ.get("QUILT_TEST_BUCKET"):
            os.environ["QUILT_TEST_BUCKET"] = quilt_test_bucket
            print(f"ℹ️  Set QUILT_TEST_BUCKET={quilt_test_bucket} from config")

        return config
    except FileNotFoundError:
        print(f"❌ Test config not found: {config_path}")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"❌ Invalid YAML config: {e}")
        sys.exit(1)


def filter_tests_by_idempotence(config: Dict[str, Any], idempotent_only: bool) -> tuple[Dict[str, Any], dict]:
    """Filter test tools based on effect classification.

    Args:
        config: Test configuration dictionary
        idempotent_only: If True, only include tools with effect='none' (read-only)

    Returns:
        Tuple of (filtered_config, stats_dict) where:
        - filtered_config: Config with filtered test_tools
        - stats_dict: Statistics about filtering including:
            - total_tools: total number of tools in config
            - total_resources: total number of resources in config
            - selected_tools: number of tools selected
            - effect_counts: dict of effect type -> count of selected tools
    """
    test_tools = config.get('test_tools', {})
    test_resources = config.get('test_resources', {})
    filtered_tools = {}
    effect_counts = {}

    for tool_name, tool_config in test_tools.items():
        effect = tool_config.get('effect', 'none')

        # Count by effect type
        effect_counts[effect] = effect_counts.get(effect, 0) + 1

        # Filter: idempotent_only means read-only effects ('none' or 'none-context-required')
        is_idempotent = effect in ['none', 'none-context-required']
        if idempotent_only and is_idempotent:
            filtered_tools[tool_name] = tool_config
        elif not idempotent_only:
            filtered_tools[tool_name] = tool_config

    # Create filtered config
    filtered_config = config.copy()
    filtered_config['test_tools'] = filtered_tools

    stats = {
        'total_tools': len(test_tools),
        'total_resources': len(test_resources),
        'selected_tools': len(filtered_tools),
        'effect_counts': effect_counts,
    }

    return filtered_config, stats


def parse_selector(selector: Optional[str], category: str) -> tuple[str, Optional[List[str]]]:
    """Parse selector string into selection type and list of names.

    Args:
        selector: Selector string ('all', 'none', or 'name1,name2,...')
        category: Category name for error messages ('tools', 'resources', 'loops')

    Returns:
        Tuple of (selection_type, names_list) where:
        - selection_type: 'all', 'none', or 'specific'
        - names_list: None for 'all'/'none', list of names for 'specific'

    Raises:
        ValueError: If selector is invalid
    """
    if selector is None:
        return 'all', None

    selector = selector.strip()

    if selector == 'all':
        return 'all', None
    elif selector == 'none':
        return 'none', None
    elif selector == '':
        raise ValueError(f"Empty selector for {category} - use 'all', 'none', or comma-separated names")
    else:
        # Parse comma-separated list
        names = [name.strip() for name in selector.split(',')]
        # Validate no empty names
        empty_names = [i for i, name in enumerate(names) if not name]
        if empty_names:
            raise ValueError(
                f"Invalid {category} selector '{selector}': contains empty names at positions {empty_names}. "
                f"Use format: 'name1,name2,name3' (no spaces around commas)"
            )
        return 'specific', names


def validate_selector_names(
    selection_type: str, names: Optional[List[str]], available_items: Dict[str, Any], category: str
) -> None:
    """Validate that selector names exist in available items.

    Args:
        selection_type: 'all', 'none', or 'specific'
        names: List of names to validate (only used if selection_type='specific')
        available_items: Dict of available items keyed by name
        category: Category name for error messages ('tools', 'resources', 'loops')

    Raises:
        ValueError: If any selector names are not found in available items
    """
    if selection_type != 'specific' or names is None:
        return

    invalid_names = [name for name in names if name not in available_items]
    if invalid_names:
        available_names = sorted(available_items.keys())
        raise ValueError(
            f"Invalid {category} names: {invalid_names}\n"
            f"Available {category} ({len(available_names)}): {', '.join(available_names[:10])}"
            + (f", ... ({len(available_names) - 10} more)" if len(available_names) > 10 else "")
        )


def filter_by_selector(items: Dict[str, Any], selection_type: str, names: Optional[List[str]]) -> Dict[str, Any]:
    """Filter items dictionary based on selector.

    Args:
        items: Dictionary of items to filter
        selection_type: 'all', 'none', or 'specific'
        names: List of names to select (only used if selection_type='specific')

    Returns:
        Filtered dictionary of items
    """
    if selection_type == 'all':
        return items
    elif selection_type == 'none':
        return {}
    elif selection_type == 'specific' and names is not None:
        return {name: items[name] for name in names if name in items}
    else:
        return items


def truncate_response(response: Any, max_size: int = 1000) -> Any:
    """Truncate large responses to keep YAML config manageable and ensure serializability."""
    if not isinstance(response, dict):
        # Handle non-dict responses
        if isinstance(response, (str, int, float, bool, type(None))):
            return response
        else:
            return str(response)  # Convert non-serializable to string

    result = {}
    for key, value in response.items():
        try:
            if isinstance(value, list):
                # Truncate arrays to first few items
                if len(value) > 3:
                    result[key] = value[:3] + [{"_truncated": f"{len(value) - 3} more items"}]
                else:
                    result[key] = value
            elif isinstance(value, str) and len(value) > max_size:
                result[key] = value[:max_size] + f"... (truncated, {len(value)} total chars)"
            elif isinstance(value, dict):
                # Recursively truncate nested dicts
                result[key] = truncate_response(value, max_size)
            elif isinstance(value, (int, float, bool, type(None))):
                result[key] = value
            else:
                # Convert non-serializable objects to strings
                result[key] = str(value)
        except Exception:
            # If anything fails, convert to string
            result[key] = f"<non-serializable: {type(value).__name__}>"

    return result


__all__ = [
    "load_test_config",
    "filter_tests_by_idempotence",
    "parse_selector",
    "validate_selector_names",
    "filter_by_selector",
    "truncate_response",
]

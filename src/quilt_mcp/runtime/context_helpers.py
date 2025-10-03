"""Navigation context helpers for MCP tools.

The frontend passes navigation context (current bucket, package, path) via tool parameters.
These helpers extract and validate that context for use in tools.
"""

from typing import Any, Dict, Optional


def get_navigation_context(params: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """Extract navigation context from tool parameters.

    The frontend may pass context in various ways:
    - _context key in params (preferred)
    - Direct bucket/package/hash/path params

    Args:
        params: Tool parameters dictionary

    Returns:
        Dict with optional keys: bucket, package, hash, path
        All values are strings or None
    """
    context: Dict[str, Optional[str]] = {
        'bucket': None,
        'package': None,
        'hash': None,
        'path': None,
    }

    # Check for explicit _context parameter (preferred)
    if '_context' in params and isinstance(params['_context'], dict):
        nav_context = params['_context']
        for key in context:
            if key in nav_context:
                context[key] = str(nav_context[key]) if nav_context[key] else None

    # Fall back to direct parameters (lower priority)
    if 'bucket' in params and not context['bucket']:
        context['bucket'] = str(params['bucket']) if params['bucket'] else None
    if 'package' in params and not context['package']:
        context['package'] = str(params['package']) if params['package'] else None
    if 'hash' in params and not context['hash']:
        context['hash'] = str(params['hash']) if params['hash'] else None
    if 'path' in params and not context['path']:
        context['path'] = str(params['path']) if params['path'] else None

    return context


def normalize_bucket_name(bucket: str) -> str:
    """Normalize bucket name by removing s3:// prefix if present.

    Args:
        bucket: Bucket name, optionally with s3:// prefix

    Returns:
        Normalized bucket name without s3:// prefix
    """
    if bucket.startswith('s3://'):
        return bucket[5:].split('/')[0]
    return bucket


def has_package_context(context: Dict[str, Optional[str]]) -> bool:
    """Check if context has complete package information.

    Args:
        context: Navigation context from get_navigation_context()

    Returns:
        True if bucket, package, and hash are all present
    """
    return bool(context.get('bucket') and context.get('package') and context.get('hash'))


def format_package_uri(context: Dict[str, Optional[str]]) -> Optional[str]:
    """Format a Quilt package URI from navigation context.

    Args:
        context: Navigation context with bucket, package, hash

    Returns:
        Quilt URI like "quilt+s3://bucket#package=name@hash" or None
    """
    if not has_package_context(context):
        return None

    bucket = normalize_bucket_name(context['bucket'])
    return f"quilt+s3://{bucket}#package={context['package']}@{context['hash']}"

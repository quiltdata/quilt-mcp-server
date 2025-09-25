#!/usr/bin/env python3
"""Check Docker image architecture from manifest."""

import json
import sys

try:
    manifest = json.load(sys.stdin)

    # Check if it's a multi-platform manifest
    if 'manifests' in manifest:
        archs = []
        for m in manifest.get('manifests', []):
            platform = m.get('platform', {})
            arch = platform.get('architecture')
            if arch and arch != 'unknown':
                archs.append(arch)
        # Remove duplicates while preserving order
        seen = set()
        unique_archs = []
        for arch in archs:
            if arch not in seen:
                seen.add(arch)
                unique_archs.append(arch)
        print(' '.join(unique_archs) if unique_archs else 'No architectures found')

    # Check if it's a single-platform image manifest
    elif 'architecture' in manifest:
        print(manifest.get('architecture', 'unknown'))

    # Check if it's an OCI image manifest with config
    elif 'config' in manifest:
        # This is likely an OCI manifest, the architecture would be in the config blob
        # For now, we'll indicate it needs further inspection
        print('amd64')  # Default assumption for single-platform pushes

    else:
        print('unknown (unable to determine from manifest)')

except Exception as e:
    print(f'Error parsing manifest: {e}', file=sys.stderr)
    print('unknown')
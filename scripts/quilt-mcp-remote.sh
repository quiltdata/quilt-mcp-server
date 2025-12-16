#!/bin/bash
# Wrapper script for mcp-remote that reads JWT from quilt3 auth store
# Usage: quilt-mcp-remote.sh <MCP_URL> [additional mcp-remote args]

set -e

# Default to demo stack if MCP_URL not provided
MCP_URL="${1:-https://demo.quiltdata.com/mcp}"
shift 2>/dev/null || true

# Quilt auth file location (macOS)
QUILT_AUTH_FILE="${HOME}/Library/Application Support/Quilt/auth.json"

# Linux alternative
if [[ ! -f "$QUILT_AUTH_FILE" ]]; then
    QUILT_AUTH_FILE="${HOME}/.local/share/Quilt/auth.json"
fi

if [[ ! -f "$QUILT_AUTH_FILE" ]]; then
    echo "ERROR: Quilt auth file not found. Please run 'quilt3 login' first." >&2
    exit 1
fi

# Extract registry URL from MCP URL (e.g., https://demo.quiltdata.com/mcp -> https://demo-registry.quiltdata.com)
# Parse the domain from MCP URL
DOMAIN=$(echo "$MCP_URL" | sed -E 's|https?://([^/]+).*|\1|')

# Build possible registry URLs to check
REGISTRY_URL="https://${DOMAIN/demo./demo-registry.}"
REGISTRY_URL_ALT="https://${DOMAIN}-registry.${DOMAIN#*.}"

# Read access token from auth.json
# Try primary registry URL first, then alternatives
ACCESS_TOKEN=$(python3 -c "
import json
import sys
import os

auth_file = os.path.expanduser('$QUILT_AUTH_FILE')
try:
    with open(auth_file) as f:
        auth = json.load(f)
    
    # Try exact registry URL match
    for registry_url in ['$REGISTRY_URL', '$REGISTRY_URL_ALT']:
        if registry_url in auth:
            print(auth[registry_url].get('access_token', ''))
            sys.exit(0)
    
    # Fallback: try to find any matching domain
    domain = '$DOMAIN'.replace('.quiltdata.com', '').replace('-', '')
    for key, value in auth.items():
        if domain in key.lower().replace('-', ''):
            print(value.get('access_token', ''))
            sys.exit(0)
    
    # Last resort: use first available token
    for key, value in auth.items():
        if 'access_token' in value:
            print(value.get('access_token', ''))
            sys.exit(0)
    
    print('', file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f'Error reading auth file: {e}', file=sys.stderr)
    sys.exit(1)
" 2>&1)

if [[ -z "$ACCESS_TOKEN" ]]; then
    echo "ERROR: Could not extract access token from $QUILT_AUTH_FILE" >&2
    echo "Please run 'quilt3 login' for your Quilt stack." >&2
    exit 1
fi

# Run mcp-remote with the authorization header
exec npx -y mcp-remote "$MCP_URL" --header "Authorization:Bearer ${ACCESS_TOKEN}" "$@"

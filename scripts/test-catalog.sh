#!/bin/bash
# Check that quilt3 catalog configuration matches QUILT_CATALOG_URL

set -e

# Load QUILT_CATALOG_URL from .env if it exists
if [ -f .env ]; then
    export $(grep -v '^#' .env | grep QUILT_CATALOG_URL | xargs)
fi

EXPECTED_URL="${QUILT_CATALOG_URL:-}"
ACTUAL_CATALOG=$(quilt3 config 2>/dev/null || echo "")

echo "Checking quilt3 catalog configuration..."
echo "  Expected (QUILT_CATALOG_URL): ${EXPECTED_URL}"
echo "  Actual (quilt3 config):       ${ACTUAL_CATALOG}"

if [ -z "$EXPECTED_URL" ]; then
    echo "❌ QUILT_CATALOG_URL not set in environment"
    exit 1
fi

if [ -z "$ACTUAL_CATALOG" ]; then
    echo "❌ quilt3 not configured (run: quilt3 login)"
    exit 1
fi

# Normalize URLs (remove trailing slashes, ensure https://)
normalize_url() {
    local url="$1"
    # Add https:// if no protocol
    if [[ ! "$url" =~ ^https?:// ]]; then
        url="https://$url"
    fi
    # Remove trailing slashes and normalize to https
    echo "$url" | sed 's|/*$||' | sed 's|^http://|https://|'
}

EXPECTED_NORMALIZED=$(normalize_url "$EXPECTED_URL")
ACTUAL_NORMALIZED=$(normalize_url "$ACTUAL_CATALOG")

if [ "$EXPECTED_NORMALIZED" != "$ACTUAL_NORMALIZED" ]; then
    echo "❌ Catalog mismatch!"
    echo "   Expected: ${EXPECTED_NORMALIZED}"
    echo "   Actual:   ${ACTUAL_NORMALIZED}"
    echo ""
    echo "Fix: Run 'quilt3 login ${EXPECTED_URL}'"
    exit 1
fi

echo "✅ Catalog configuration matches"
exit 0

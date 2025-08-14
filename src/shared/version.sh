#!/bin/bash
# Version utilities - single source of truth for versioning

get_version() {
    git rev-parse --short HEAD 2>/dev/null || echo "unknown"
}

get_full_version() {
    git rev-parse HEAD 2>/dev/null || echo "unknown"
}

get_branch() {
    git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown"
}

get_version_tag() {
    local version=$(get_version)
    echo "quilt-mcp:$version"
}

# When sourced, export the version function
if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
    export -f get_version
    export -f get_full_version  
    export -f get_branch
    export -f get_version_tag
fi
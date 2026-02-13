# Issue 262: `docs.quilt.bio` Search Tool

## Goal
Add a dedicated MCP tool that searches Quilt documentation at `https://docs.quilt.bio` and returns relevant links for configuration and usage questions.

## Tasks
1. Add a new tool function in `src/quilt_mcp/tools/search.py`:
   - Name: `search_docs_quilt_bio`
   - Input: query string, limit, include versioned docs toggle
   - Output: structured success/error dict with ranked results
2. Implement docs discovery via `https://docs.quilt.bio/sitemap.xml`:
   - Parse sitemap index + nested page sitemaps
   - Collect URL and last modified timestamp
3. Implement ranking:
   - Tokenize query
   - Score URL/path matches
   - Return top `limit` results with matched terms
4. Implement lightweight page enrichment for top hits:
   - Fetch page title and short snippet (best effort)
   - Degrade gracefully if page fetch fails
5. Ensure tool docstring follows LLM docstring style checks.
6. Update changelog entry under `Unreleased`.

## Required Tests
1. `search_docs_quilt_bio` returns ranked docs results from sitemap data.
2. Versioned docs URLs are excluded by default.
3. Versioned docs URLs are included when requested.
4. Tool returns a structured error when sitemap fetch fails.
5. Query token extraction and matching are case-insensitive.

## Validation Commands
1. `make test`
2. `make lint`

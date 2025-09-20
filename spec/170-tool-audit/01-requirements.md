<!-- markdownlint-disable MD013 -->
# Requirements - Tool Inventory Audit

**GitHub Issue**: #170 "tool audit"
**Problem Statement**: The Quilt MCP server exposes numerous overlapping tools with inconsistent naming and ordering, making it difficult for humans and AI agents to choose the right tool quickly and safely.

## User Stories

1. **As a platform maintainer**, I want a canonical, curated list of MCP tools so that I can understand coverage and identify redundancy when planning changes.
2. **As an AI assistant integrated with the server**, I want tools to follow consistent naming and categorization patterns so that I can confidently invoke the correct capability during conversations.
3. **As a developer writing new tools**, I want documented expectations for naming, overlap avoidance, and ordering so that new additions fit seamlessly into the catalog without increasing cognitive load.

## Acceptance Criteria

1. Consolidate the current tool inventory into a single authoritative listing that includes module, function, and behavioral intent (source of truth for humans + AI).
2. Identify overlapping or redundant tools with clear disposition (keep, deprecate, merge, rename) approved by maintainers.
3. Establish naming conventions (modules, functions, descriptions) that align with Quilt terminology and avoid ambiguity.
4. Ensure the final tool list is alphabetized (or otherwise deterministically ordered) and easy to scan for both humans and automation.
5. Provide guidance for future tool authoring, covering naming, duplication checks, and documentation expectations.
6. Maintain existing automated verification (tests, lint, packaging) without regressions during the audit rollout.

## Success Metrics

1. Tool catalog consumers can rely on one inventory source with no conflicting or stale entries.
2. Name collisions or ambiguous descriptions are eliminated according to the audit decisions.
3. New tools added after the audit follow the documented conventions without requiring corrective follow-up.
4. `make test` and `make lint` continue to pass after any changes derived from the audit.

## Open Questions

1. Which combinations of tools are currently considered redundant, and who is the decision-maker for deprecation vs. rename?
2. Are there external consumers (documentation, integrations, MCP clients) that rely on existing tool names or ordering we must preserve?
3. Should the canonical inventory live exclusively in `quilt_mcp_tools.csv`, the docs, or both—and how will it stay synced with code changes?
4. Do we need automated enforcement (lint rule, generator) to prevent future drift once the audit is complete?

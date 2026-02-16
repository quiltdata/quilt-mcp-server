# SCOPE.md

> Version 1.0 | February 16, 2026

## 260210-stack-integrated

## Objective

Deliver a stack-integrated Quilt MCP server usable by the Benchling Deep Research MCP client.

## Considerations

1. Test using Claude.ai and standard MCP auth, as we lack access to the Benchling MCP client
2. Prefer a single codebase across local and remote deployment, to streamline development and testing
3. Stateless, multiuser, and readonly deployment requires removing `quilt3` dependency and disabling stateful tools/dependencies
4. ~Split admin/user when running remote~
   1. Deferring due to lack of time
5. Otherwise, expect feature parity between local and remote deployments

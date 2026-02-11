"""E2E Backend Workflow Tests.

This package contains E2E tests for complete multi-step workflows that
span multiple backend operations and real services.

Workflows test end-to-end user goals like:
- Data discovery (search → permissions → access → preview)
- Package lifecycle (create → update → delete → verify)
- Cross-bucket operations (discover → analyze → summarize)

NO MOCKING - all tests use real AWS, Elasticsearch, and Quilt services.
"""

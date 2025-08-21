Title: Optimize performance (client reuse, caching, pagination, I/O)

Labels: enhancement, performance

Summary

Some tools perform repeated network I/O to S3 and Quilt registry. There are opportunities to reduce latency and cost by reusing clients, batching/paginating efficiently, adding optional caches, and parallelizing safe-read operations.

Opportunities

- Reuse and pool boto3 and Quilt3 clients across requests; avoid per-call instantiation.
- Add read-through caching for metadata-heavy operations (e.g., `quilt_summary`, `package_browse`) using `cachetools` with TTL and bounded size.
- Optimize pagination to request larger page sizes when allowed; short-circuit when limits reached.
- Use `aioboto3` or thread pools for parallel-safe read operations where permitted; keep writes sequential.
- Normalize request timeouts and retries (exponential backoff, jitter) via shared session config.
- Avoid downloading full objects for text preview; use range reads and server-side filtering where possible.

Acceptance Criteria

- Shared client factories with reuse are implemented and used by all tools.
- Add opt-in cache for read-only endpoints with configurable TTL; default sensible (e.g., 60s) and easy to disable.
- Benchmarks added under `spec/` or `app/tests/perf/` showing at least 30% latency improvement for list/search/browse paths against a sample bucket.
- Timeouts and retries standardized; flaky network errors reduced in CI and manual tests.

Tasks

- [ ] Implement client reuse in services (see refactor issue)
- [ ] Add `cachetools`-based memoization with TTL for read-only metadata functions
- [ ] Introduce consistent pagination helpers and range-read utilities
- [ ] Add micro-benchmarks and a `make bench` target; document results

References

- Code: `app/quilt_mcp/tools/*`, `app/quilt_mcp/utils.py`
- Config: `pyproject.toml` includes `cachetools`


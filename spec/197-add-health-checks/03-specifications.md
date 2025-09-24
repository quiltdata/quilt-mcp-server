<!-- markdownlint-disable MD013 -->
# Health Check Endpoints Specifications

**Issue Reference**: GitHub Issue #197 - Add Health Checks to MCP Server
**Branch**: `197-add-health-checks`
**Status**: Technical Specifications

## Executive Summary

This specification defines the architecture for adding health check endpoints to the Quilt MCP server, enabling container orchestration platforms, monitoring systems, and load balancers to assess server health status. The solution leverages existing internal health check functionality while exposing new HTTP endpoints that work across all transport modes.

## Architectural Goals

1. **Zero-Authentication Access**: Health endpoints must be accessible without MCP protocol authentication or Quilt login credentials, enabling external monitoring systems to probe server status

2. **Minimal Performance Overhead**: Health check operations must complete within strict time bounds (< 2 seconds) with negligible resource consumption (< 10MB memory overhead)

3. **Extensible Component Architecture**: Support pluggable health check components that can be added, removed, or customized without modifying core health check logic

4. **Transport Mode Agnostic**: Health functionality must be accessible regardless of transport mode (stdio, HTTP, SSE, streamable-http), with appropriate access patterns for each

5. **Graceful Degradation**: Health endpoints must continue functioning and provide useful diagnostics even when server components are failing

6. **Container-Native Integration**: First-class support for container orchestration health probe patterns (Kubernetes, Docker Compose)

## High-Level Specifications

### 1. Health Endpoint Architecture

#### 1.1 Endpoint Structure

The server SHALL expose the following health endpoints when operating in HTTP transport mode:

1. **Primary Health Endpoint** (`/health`)
   - Default health status endpoint
   - Returns comprehensive health status with component details
   - Suitable for monitoring systems and dashboards

2. **Simple Health Endpoint** (`/health/simple`)
   - Lightweight health check for high-frequency probing
   - Returns minimal response (HTTP status code primary signal)
   - Optimized for load balancer health checks

3. **Detailed Health Endpoint** (`/health/detailed`)
   - Comprehensive diagnostic information
   - Includes configuration details and troubleshooting data
   - Intended for debugging and manual inspection

4. **Readiness Probe** (`/readiness`)
   - Kubernetes-compatible readiness indicator
   - Signals when server is ready to accept MCP requests
   - Distinct from liveness to prevent premature traffic routing

5. **Liveness Probe** (`/liveness`)
   - Kubernetes-compatible liveness indicator
   - Signals when server process is responsive
   - Triggers container restart when failing

#### 1.2 FastMCP Integration

The health endpoints SHALL be integrated with FastMCP server using the `custom_route` decorator pattern:

1. **Custom Route Registration**
   - Health endpoints registered as FastMCP custom routes
   - Routes bypass MCP protocol authentication
   - Available only when `FASTMCP_TRANSPORT=http`

2. **Route Handler Implementation**
   - Direct HTTP response generation
   - No MCP protocol wrapper
   - Standard HTTP status codes and JSON responses

3. **Fallback for Non-HTTP Transports**
   - Health check available as MCP tool when not in HTTP mode
   - Consistent response format across access methods
   - Transport-appropriate error messages

### 2. Response Format Specifications

#### 2.1 Standard Response Schema

All health endpoints SHALL return JSON responses conforming to this schema:

```json
{
  "status": "healthy" | "degraded" | "unhealthy",
  "timestamp": "ISO 8601 timestamp",
  "version": "server version string",
  "transport": "current transport mode",
  "components": {
    "component_name": {
      "status": "healthy" | "degraded" | "unhealthy",
      "message": "human-readable status",
      "latency_ms": numeric_value,
      "metadata": { optional component-specific data }
    }
  },
  "message": "overall health summary",
  "checks_passed": numeric_count,
  "checks_failed": numeric_count,
  "checks_total": numeric_count
}
```

#### 2.2 HTTP Status Code Mapping

Health endpoints SHALL return appropriate HTTP status codes:

1. **200 OK**: System healthy or degraded but operational
2. **503 Service Unavailable**: System unhealthy or critical components failing
3. **500 Internal Server Error**: Health check execution failure

#### 2.3 Component-Specific Responses

Each component health check SHALL provide:

1. **Status Classification**: healthy, degraded, or unhealthy
2. **Descriptive Message**: Human-readable status explanation
3. **Performance Metrics**: Execution latency in milliseconds
4. **Component Metadata**: Optional diagnostic details

### 3. Component Health Aggregation

#### 3.1 Core Components

The following components SHALL be monitored:

1. **Authentication Component**
   - Validates Quilt authentication status
   - Reports login state and credential validity
   - Non-critical for health endpoint access

2. **AWS Connectivity Component**
   - Verifies STS, S3, and Athena access
   - Tests actual API connectivity
   - Critical for MCP tool functionality

3. **Package Operations Component**
   - Validates package listing capability
   - Tests core Quilt functionality
   - Indicates data plane health

4. **Transport Layer Component**
   - Reports current transport mode
   - Validates transport-specific functionality
   - Always healthy for HTTP transport health checks

5. **Tool Registration Component**
   - Verifies MCP tool availability
   - Reports registration status
   - Critical for MCP protocol operations

#### 3.2 Aggregation Logic

Overall health status SHALL be determined by:

1. **Healthy**: All critical components healthy, non-critical components may be degraded
2. **Degraded**: One or more non-critical components unhealthy, all critical components healthy
3. **Unhealthy**: One or more critical components unhealthy

#### 3.3 Component Criticality

Components SHALL be classified as:

1. **Critical Components**:
   - Transport Layer
   - Tool Registration
   - AWS Connectivity (for production deployments)

2. **Non-Critical Components**:
   - Authentication (for health endpoint access)
   - Package Operations (can recover)

### 4. Transport Mode Compatibility

#### 4.1 HTTP Transport Mode

When `FASTMCP_TRANSPORT=http`:

1. All health endpoints accessible via HTTP GET requests
2. No authentication required for health endpoints
3. Endpoints served alongside MCP protocol at `/mcp`
4. Standard HTTP response headers and caching

#### 4.2 stdio Transport Mode

When `FASTMCP_TRANSPORT=stdio`:

1. Health check exposed as MCP tool `health_status`
2. Invoked through MCP protocol
3. Returns same JSON structure as HTTP endpoints
4. Requires MCP client connection

#### 4.3 SSE/Streamable-HTTP Transport Modes

When using streaming transports:

1. Health status available through MCP tool invocation
2. Streaming updates not supported for health checks
3. Single response per health check request

### 5. Integration Points

#### 5.1 FastMCP Server Integration

1. **Server Creation Hook**
   - Register health routes during server initialization
   - Conditional registration based on transport mode
   - Preserve existing tool registration flow

2. **Custom Route Decorator**
   - Utilize FastMCP `@mcp.custom_route()` pattern
   - Direct HTTP response handling
   - Bypass MCP protocol processing

3. **Error Recovery Integration**
   - Leverage existing `health_check_with_recovery()` function
   - Adapt response format for HTTP endpoints
   - Maintain backward compatibility

#### 5.2 Container Health Probes

1. **Docker HEALTHCHECK**
   - Add HEALTHCHECK directive to Dockerfile
   - Use `/health/simple` for efficiency
   - Configure appropriate timeout and interval

2. **Kubernetes Probes**
   - Map `/liveness` to livenessProbe
   - Map `/readiness` to readinessProbe
   - Configure probe parameters for container orchestration

3. **Docker Compose Integration**
   - Document health check configuration
   - Provide example compose files
   - Support dependency management

#### 5.3 Monitoring System Integration

1. **Prometheus Metrics** (future consideration)
   - Health status as gauge metric
   - Component-level metrics
   - Latency histograms

2. **CloudWatch/DataDog**
   - Structured JSON for parsing
   - Custom metric extraction
   - Alert configuration support

## Success Criteria

### 1. Functional Requirements

1. **Endpoint Availability**: All specified health endpoints respond with correct format when server running in HTTP mode
2. **Status Accuracy**: Health status correctly reflects actual server state in >99% of checks
3. **Component Coverage**: All core components monitored and reported in health responses
4. **Transport Compatibility**: Health functionality accessible in all transport modes

### 2. Performance Requirements

1. **Response Time**:
   - Simple health check: < 500ms (p95)
   - Standard health check: < 1 second (p95)
   - Detailed health check: < 2 seconds (p95)

2. **Resource Overhead**:
   - Memory usage increase: < 10MB
   - CPU usage during health check: < 5%
   - No impact on concurrent MCP operations

3. **Availability**:
   - Health endpoints available >99.9% when server running
   - Graceful degradation during component failures
   - No false negative health reports

### 3. Integration Requirements

1. **Container Orchestration**:
   - Successful integration with Docker health checks
   - Kubernetes probe compatibility validated
   - Container restart behavior correct

2. **Monitoring Systems**:
   - JSON response parseable by common monitoring tools
   - Appropriate HTTP status codes for alerting
   - Structured data for metric extraction

### 4. Quality Requirements

1. **Test Coverage**:
   - 100% code coverage for health check logic
   - Integration tests for all transport modes
   - Container health probe validation tests

2. **Documentation**:
   - API documentation for all health endpoints
   - Integration guides for container platforms
   - Troubleshooting guide for health issues

## Quality Gates

### 1. Code Quality

1. **Test Coverage**: Minimum 100% coverage for health check implementation
2. **Static Analysis**: All linting and type checking must pass
3. **Performance Tests**: Health check latency benchmarks must pass
4. **Integration Tests**: Container health probe tests must succeed

### 2. Functional Validation

1. **Endpoint Testing**: All health endpoints return expected format
2. **Status Accuracy**: Health status reflects component states correctly
3. **Error Handling**: Graceful degradation during failures
4. **Transport Testing**: Health access verified across all transport modes

### 3. Integration Validation

1. **Docker Integration**: HEALTHCHECK directive functions correctly
2. **Kubernetes Compatibility**: Probes trigger appropriate container behavior
3. **Load Balancer Testing**: Simple health endpoint meets latency requirements
4. **Monitoring Integration**: JSON responses parse correctly in monitoring tools

## Measurable Outcomes

### 1. Operational Metrics

1. **Container Restart Reduction**: 50% fewer unnecessary container restarts due to accurate health reporting
2. **Incident Detection Time**: 75% faster detection of service degradation through health monitoring
3. **Deployment Success Rate**: 95% successful deployments validated through health checks

### 2. Performance Metrics

1. **Health Check Latency**: p95 < 1 second for standard health checks
2. **Resource Efficiency**: < 1% CPU overhead from health check operations
3. **Availability**: 99.9% health endpoint availability during normal operations

### 3. Developer Experience

1. **Debugging Time**: 60% reduction in time to diagnose server issues
2. **Integration Effort**: < 1 hour to integrate with new monitoring systems
3. **Configuration Simplicity**: Zero-configuration health checks for standard deployments

## Architectural Decisions

### 1. Custom Route vs MCP Tool

**Decision**: Use FastMCP custom routes for HTTP health endpoints

**Rationale**:

- Enables zero-authentication access required for external monitoring
- Provides standard HTTP interface expected by infrastructure tools
- Maintains separation between health monitoring and MCP protocol

### 2. Component Granularity

**Decision**: Monitor five core components with extensible architecture

**Rationale**:

- Balances comprehensive monitoring with performance overhead
- Provides sufficient granularity for troubleshooting
- Enables future addition of custom health checks

### 3. Response Format Standardization

**Decision**: Single JSON schema across all health endpoints with varying detail levels

**Rationale**:

- Simplifies client integration and parsing
- Maintains consistency across transport modes
- Enables progressive disclosure of diagnostic information

### 4. Transport-Specific Behavior

**Decision**: HTTP endpoints for HTTP transport, MCP tool fallback for other transports

**Rationale**:

- Leverages transport-specific capabilities appropriately
- Maintains functionality across all deployment scenarios
- Provides consistent health monitoring regardless of transport

## Risk Mitigation

### 1. FastMCP Limitations

**Risk**: FastMCP may not support custom HTTP routes

**Mitigation**:

- Investigate FastMCP source code for extension points
- Prepare fallback using MCP tool with HTTP wrapper
- Consider contributing custom route support to FastMCP

### 2. Performance Impact

**Risk**: Health checks may impact MCP tool performance

**Mitigation**:

- Implement caching for expensive health checks
- Provide lightweight simple endpoint for frequent probing
- Use async execution where possible

### 3. Security Exposure

**Risk**: Health endpoints may expose sensitive information

**Mitigation**:

- Limit diagnostic details in standard endpoints
- Require authentication for detailed diagnostics (optional)
- Sanitize error messages and stack traces

## Future Considerations

### 1. Metrics Endpoint

- Prometheus-compatible `/metrics` endpoint
- Performance metrics and business KPIs
- Integration with observability platforms

### 2. Custom Health Checks

- Plugin architecture for user-defined health checks
- Configuration-driven health check registration
- Domain-specific health validations

### 3. Health Check History

- Persistent health status history
- Trend analysis and prediction
- Automated remediation triggers

### 4. WebSocket Health Updates

- Real-time health status streaming
- Push-based monitoring for dashboards
- Efficient for continuous monitoring scenarios

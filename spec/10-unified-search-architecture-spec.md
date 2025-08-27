# Unified Search Architecture for Quilt MCP Server

## Overview

This specification defines a comprehensive, unified search architecture for the Quilt MCP Server that provides intelligent, context-aware search capabilities across Quilt catalogs, packages, and S3 buckets using multiple backend engines.

## Current State Analysis

### Existing Quilt Infrastructure (Leveraging Existing Capabilities)

**Quilt Enterprise GraphQL System**:
- Mature GraphQL schema with `ObjectsSearchContext` and `PackagesSearchContext`
- Built-in search handlers with pagination and result processing
- Supports both objects and packages search with unified interface
- Error handling with `QuerySyntaxError` and validation

**Quilt3 Elasticsearch Integration**:
- `bucket.search(query, limit)` with Query String and DSL support
- Searches both `{bucket}` and `{bucket}_packages` indices automatically
- `/api/search` endpoint with `action=search` (query string) and `action=freeform` (DSL)
- Built-in session management and authentication

**Existing MCP Tools**:
1. **`packages_search`** - Uses quilt3 search API
2. **`package_contents_search`** - Within-package file search
3. **`bucket_objects_search`** - Uses quilt3.Bucket.search()
4. **`bucket_objects_search_graphql`** - Uses enterprise GraphQL endpoints

### Current Limitations
- No unified interface that leverages all existing capabilities
- Users must choose between different search paradigms
- No intelligent query routing between GraphQL and Elasticsearch
- Limited cross-index search coordination
- No query optimization or result enhancement

## Design Goals

### 1. Unified Interface
- Single `unified_search` tool that intelligently routes queries
- Context-aware query interpretation
- Automatic backend selection based on query type and available services

### 2. Leverage Existing Infrastructure
- **Quilt3 Elasticsearch**: Use existing `bucket.search()` and `/api/search` endpoints
- **Enterprise GraphQL**: Leverage existing `ObjectsSearchContext` and `PackagesSearchContext`
- **Session Management**: Use existing quilt3 session and authentication
- **Fallback to S3**: Use existing S3 list operations when search unavailable

### 3. Intelligent Query Processing
- Natural language query interpretation
- Automatic query optimization for each backend
- Smart result aggregation and deduplication
- Performance-based backend selection

### 4. Progressive Enhancement
- Graceful degradation when backends are unavailable
- Automatic fallback chains
- Performance monitoring and adaptive routing

## Architecture Design

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Unified Search API                       │
├─────────────────────────────────────────────────────────────┤
│  unified_search(query, scope, options)                     │
│  search_suggest(partial_query)                             │
│  search_explain(query)                                     │
└─────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                Query Intelligence Layer                     │
├─────────────────────────────────────────────────────────────┤
│  • Query Parser & Classifier                               │
│  • Intent Detection (find files, browse packages, etc.)    │
│  • Scope Resolution (catalog, package, bucket)             │
│  • Backend Selection Strategy                              │
└─────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                 Backend Router & Orchestrator              │
├─────────────────────────────────────────────────────────────┤
│  • Parallel Query Execution                                │
│  • Result Aggregation & Ranking                            │
│  • Fallback Chain Management                               │
│  • Performance Monitoring                                  │
└─────────────────────────────────────────────────────────────┘
                                │
                ┌───────────────┼───────────────┐
                ▼               ▼               ▼
    ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
    │ Quilt3 ES API   │ │ Enterprise GQL  │ │   S3 Fallback   │
    │    Backend      │ │    Backend      │ │    Backend      │
    └─────────────────┘ └─────────────────┘ └─────────────────┘
                ▼               ▼               ▼
    ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
    │ bucket.search() │ │ObjectsSearchCtx │ │ list_objects_v2 │
    │ /api/search     │ │PackagesSearchCtx│ │ Basic filtering │
    └─────────────────┘ └─────────────────┘ └─────────────────┘
```

### Query Classification System

```python
class QueryType(Enum):
    FILE_SEARCH = "file_search"           # "find CSV files"
    PACKAGE_DISCOVERY = "package_discovery"  # "packages about genomics"
    CONTENT_SEARCH = "content_search"     # "files containing 'RNA-seq'"
    METADATA_SEARCH = "metadata_search"   # "packages created in 2024"
    ANALYTICAL_SEARCH = "analytical_search"  # "largest files by size"
    CROSS_CATALOG = "cross_catalog"       # "compare across catalogs"

class SearchScope(Enum):
    GLOBAL = "global"                     # Search everything accessible
    CATALOG = "catalog"                   # Current catalog only
    PACKAGE = "package"                   # Within specific package
    BUCKET = "bucket"                     # Within specific bucket
    REGISTRY = "registry"                 # Within specific registry
```

## Implementation Plan

### Phase 1: Core Infrastructure (Week 1)
1. **Query Parser & Classifier**
   - Natural language query analysis
   - Intent detection using pattern matching
   - Scope resolution logic

2. **Backend Abstraction Layer**
   - Unified backend interface
   - Backend capability detection
   - Health monitoring

3. **Result Aggregation Engine**
   - Cross-backend result merging
   - Relevance scoring
   - Deduplication logic

### Phase 2: Backend Integration (Week 2)
1. **Enhanced Elasticsearch Integration**
   - Advanced query DSL generation
   - Faceted search capabilities
   - Performance optimization

2. **GraphQL Backend**
   - Dynamic query construction
   - Package relationship traversal
   - Metadata-rich results

3. **Athena Backend**
   - SQL query generation from natural language
   - Large dataset analytical queries
   - Cost optimization

### Phase 3: Intelligence Layer (Week 3)
1. **Smart Query Routing**
   - Performance-based backend selection
   - Automatic fallback chains
   - Query optimization

2. **Result Enhancement**
   - Context-aware result formatting
   - Related content suggestions
   - Search result explanations

3. **User Experience Features**
   - Query suggestions and autocomplete
   - Search history and favorites
   - Performance analytics

## Tool Specifications

### Primary Tools

#### 1. `unified_search`
```python
def unified_search(
    query: str,
    scope: str = "global",  # global, catalog, package, bucket
    target: str = "",       # specific package/bucket when scope is narrow
    backends: List[str] = ["auto"],  # elasticsearch, graphql, athena, s3
    limit: int = 50,
    include_metadata: bool = True,
    include_content_preview: bool = False,
    explain_query: bool = False
) -> Dict[str, Any]
```

**Features:**
- Natural language query processing
- Automatic backend selection
- Cross-backend result aggregation
- Intelligent result ranking

**Example Queries:**
- `"CSV files in genomics packages"`
- `"packages created last month"`
- `"files larger than 100MB"`
- `"RNA-seq data with quality scores"`

#### 2. `search_suggest`
```python
def search_suggest(
    partial_query: str,
    context: str = "",      # current package/bucket context
    suggestion_types: List[str] = ["auto"]  # queries, packages, files, metadata
) -> Dict[str, Any]
```

**Features:**
- Query completion suggestions
- Context-aware recommendations
- Popular query patterns
- Syntax assistance

#### 3. `search_explain`
```python
def search_explain(
    query: str,
    show_backends: bool = True,
    show_performance: bool = True
) -> Dict[str, Any]
```

**Features:**
- Query execution plan visualization
- Backend selection reasoning
- Performance metrics
- Optimization suggestions

### Enhanced Existing Tools

#### 1. `packages_search_advanced`
Enhanced version with:
- Complex query DSL support
- Faceted search (by type, date, size, etc.)
- Related package discovery
- Cross-catalog search

#### 2. `bucket_search_analytical`
Athena-powered search with:
- SQL-like analytical queries
- Aggregation and grouping
- Time-series analysis
- Cost estimation

## Query Processing Pipeline

### 1. Query Analysis
```python
def analyze_query(query: str) -> QueryAnalysis:
    """
    Analyze natural language query to determine:
    - Intent (find, browse, analyze, compare)
    - Target (files, packages, metadata)
    - Scope (global, catalog, package)
    - Filters (size, date, type, etc.)
    - Complexity (simple, complex, analytical)
    """
```

### 2. Backend Selection
```python
def select_backends(analysis: QueryAnalysis, available_backends: List[str]) -> List[Backend]:
    """
    Select optimal backends based on:
    - Query complexity and type
    - Backend availability and health
    - Historical performance data
    - Cost considerations (for Athena)
    - Result quality requirements
    """
```

### 3. Query Translation
```python
def translate_query(query: str, backend: Backend) -> BackendQuery:
    """
    Translate natural language to backend-specific queries:
    - Elasticsearch: Complex DSL with filters and aggregations
    - GraphQL: Structured queries with relationships
    - Athena: SQL with optimized joins and partitioning
    - S3: Prefix-based filtering with metadata
    """
```

### 4. Result Processing
```python
def process_results(results: List[BackendResult]) -> UnifiedResult:
    """
    Process and enhance results:
    - Normalize result formats across backends
    - Apply relevance scoring and ranking
    - Deduplicate across backends
    - Add context and relationships
    - Generate result explanations
    """
```

## Backend Implementations

### Quilt3 Elasticsearch Backend
```python
class Quilt3ElasticsearchBackend:
    def search(self, query: Union[str, dict], bucket: str, limit: int) -> ElasticResult:
        """
        Leverages existing quilt3.Bucket.search() and /api/search endpoint.
        
        Features:
        - Uses existing ES infrastructure (no new setup required)
        - Supports Query String and DSL queries
        - Searches both {bucket} and {bucket}_packages indices
        - Built-in authentication via quilt3 session
        - Fast response times (<100ms for simple queries)
        """
```

### Enterprise GraphQL Backend
```python
class EnterpriseGraphQLBackend:
    def search(self, context: SearchContext) -> GraphQLResult:
        """
        Leverages existing Enterprise GraphQL search handlers.
        
        Features:
        - Uses ObjectsSearchContext and PackagesSearchContext
        - Built-in pagination and result processing
        - Rich metadata and relationship queries
        - Existing error handling and validation
        - Structured result sets with stats
        """
```

### S3 Fallback Backend
```python
class S3FallbackBackend:
    def search(self, prefix: str, bucket: str, filters: dict) -> S3Result:
        """
        Uses existing S3 list operations when search is unavailable.
        
        Features:
        - Basic prefix-based filtering
        - Metadata-based filtering
        - No additional infrastructure required
        - Reliable fallback when ES/GraphQL unavailable
        """
```

## Example Usage Scenarios

### Scenario 1: Data Discovery
```
User: "Find all CSV files related to cell painting experiments"

Query Analysis:
- Intent: file_search
- Target: files (CSV)
- Domain: cell painting
- Scope: global

Backend Selection:
1. Quilt3 Elasticsearch (primary) - existing bucket.search() API
2. Enterprise GraphQL (secondary) - existing ObjectsSearchContext
3. S3 List (fallback) - existing list_objects_v2

Result: Unified list with package context, file metadata, and relevance scores
```

### Scenario 2: Package Exploration
```
User: "Show me genomics packages with BAM files larger than 1GB"

Query Analysis:
- Intent: package_discovery
- Target: packages
- Domain: genomics
- Filters: file_type=BAM, size>1GB
- Scope: global

Backend Selection:
1. Enterprise GraphQL (primary) - existing PackagesSearchContext
2. Quilt3 Elasticsearch (secondary) - existing /api/search with packages index
3. S3 List (fallback) - basic enumeration with filtering

Result: Packages with matching criteria, file counts, and access information
```

### Scenario 3: Content Analysis
```
User: "Find datasets with quality scores above 0.8 from the last 6 months"

Query Analysis:
- Intent: analytical_search
- Target: datasets
- Filters: quality_score>0.8, created_date>6mo
- Scope: global

Backend Selection:
1. Quilt3 Elasticsearch (primary) - complex DSL queries for analytics
2. Enterprise GraphQL (secondary) - metadata filtering and aggregation
3. S3 List (fallback) - basic enumeration with client-side filtering

Result: Analytical report with matching datasets and quality metrics
```

## Implementation Phases

### Phase 1: Foundation (Days 1-3)
**Goal**: Basic unified search with Elasticsearch and S3 fallback

**Deliverables**:
- Query parser and classifier
- Backend abstraction layer wrapping existing APIs
- Basic `unified_search` tool
- Quilt3 Elasticsearch backend (wraps bucket.search())
- S3 fallback backend (wraps existing list operations)

**Success Criteria**:
- Can route simple file searches to appropriate backends
- Handles backend failures gracefully
- Returns unified result format

### Phase 2: Intelligence (Days 4-6)
**Goal**: Smart query processing and GraphQL integration

**Deliverables**:
- Natural language query analysis
- Enterprise GraphQL backend (wraps ObjectsSearchContext/PackagesSearchContext)
- Result ranking and aggregation across existing APIs
- `search_suggest` tool

**Success Criteria**:
- Understands complex natural language queries
- Provides relevant suggestions
- Merges results from multiple backends

### Phase 3: Advanced Analytics (Days 7-9)
**Goal**: Enhanced analytical capabilities using existing Elasticsearch DSL

**Deliverables**:
- Advanced Elasticsearch DSL query generation
- Complex aggregation and analytics via existing ES infrastructure
- `search_explain` tool
- Performance monitoring and optimization

**Success Criteria**:
- Can handle analytical queries
- Provides query execution explanations
- Optimizes for cost and performance

### Phase 4: Enhancement (Days 10-12)
**Goal**: Advanced features and optimization

**Deliverables**:
- Advanced query DSL support
- Cross-catalog search
- Result caching and optimization
- Enhanced existing tools

**Success Criteria**:
- Sub-second response times for cached queries
- Cross-catalog search works reliably
- Advanced users can use complex query syntax

## File Structure

```
app/quilt_mcp/search/
├── __init__.py
├── core/
│   ├── __init__.py
│   ├── query_parser.py      # Natural language processing
│   ├── query_classifier.py  # Intent and scope detection
│   ├── backend_router.py    # Backend selection logic
│   └── result_processor.py  # Result aggregation and ranking
├── backends/
│   ├── __init__.py
│   ├── base.py             # Abstract backend interface
│   ├── elasticsearch.py   # Enhanced ES backend
│   ├── graphql.py         # GraphQL backend
│   ├── athena.py          # Athena analytical backend
│   └── s3.py              # S3 fallback backend
├── tools/
│   ├── __init__.py
│   ├── unified_search.py   # Main unified search tool
│   ├── search_suggest.py   # Query suggestions
│   └── search_explain.py   # Query explanation
└── utils/
    ├── __init__.py
    ├── query_patterns.py   # Common query patterns
    ├── result_formatters.py # Result formatting utilities
    └── performance.py      # Performance monitoring
```

## Tool Specifications

### 1. Unified Search Tool

```python
@tool
def unified_search(
    query: str,
    scope: str = "global",
    target: str = "",
    backends: List[str] = ["auto"],
    limit: int = 50,
    include_metadata: bool = True,
    include_content_preview: bool = False,
    explain_query: bool = False,
    filters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Intelligent unified search across Quilt catalogs, packages, and S3 buckets.
    
    This tool automatically:
    - Parses natural language queries
    - Selects optimal search backends
    - Aggregates and ranks results
    - Provides context and explanations
    
    Args:
        query: Natural language search query
        scope: Search scope (global, catalog, package, bucket)
        target: Specific target when scope is narrow (package/bucket name)
        backends: Preferred backends (auto, elasticsearch, graphql, athena, s3)
        limit: Maximum results to return
        include_metadata: Include rich metadata in results
        include_content_preview: Include content previews for files
        explain_query: Include query execution explanation
        filters: Additional filters (size, date, type, etc.)
    
    Returns:
        Unified search results with metadata, explanations, and suggestions
    
    Examples:
        unified_search("CSV files in genomics packages")
        unified_search("packages created last month", scope="catalog")
        unified_search("README files", scope="package", target="user/dataset")
        unified_search("files larger than 100MB", filters={"size_gt": "100MB"})
    """
```

### 2. Search Suggestions Tool

```python
@tool
def search_suggest(
    partial_query: str,
    context: str = "",
    suggestion_types: List[str] = ["auto"],
    limit: int = 10
) -> Dict[str, Any]:
    """
    Provide intelligent search suggestions and query completion.
    
    Args:
        partial_query: Incomplete query to complete
        context: Current context (package/bucket name)
        suggestion_types: Types of suggestions (queries, packages, files, metadata)
        limit: Maximum suggestions to return
    
    Returns:
        List of suggested completions with explanations
    
    Examples:
        search_suggest("CSV fil")  # → "CSV files", "CSV files in packages", etc.
        search_suggest("genomics", context="user/dataset")
    """
```

### 3. Search Explanation Tool

```python
@tool
def search_explain(
    query: str,
    show_backends: bool = True,
    show_performance: bool = True,
    show_alternatives: bool = False
) -> Dict[str, Any]:
    """
    Explain how a search query would be executed and optimized.
    
    Args:
        query: Search query to explain
        show_backends: Include backend selection reasoning
        show_performance: Include performance estimates
        show_alternatives: Suggest alternative query formulations
    
    Returns:
        Detailed explanation of query execution plan
    
    Examples:
        search_explain("large genomics files")
        search_explain("packages with RNA-seq data", show_alternatives=True)
    """
```

## Backend Selection Logic

### Decision Matrix

| Query Type | Primary Backend | Secondary | Fallback | Rationale |
|------------|----------------|-----------|----------|-----------|
| File Search | Elasticsearch | GraphQL | S3 | Fast text matching, then structure |
| Package Discovery | GraphQL | Elasticsearch | S3 | Rich metadata, then content |
| Content Search | Elasticsearch | Athena | S3 | Full-text indexing optimal |
| Metadata Search | GraphQL | Elasticsearch | S3 | Structured metadata queries |
| Analytical | Athena | GraphQL | Elasticsearch | SQL aggregations |
| Cross-Catalog | GraphQL | Elasticsearch | S3 | Multi-catalog awareness |

### Performance Thresholds

- **Elasticsearch**: < 100ms for simple queries, < 500ms for complex
- **GraphQL**: < 200ms for metadata, < 1s for relationships
- **Athena**: < 5s for analytics, < 30s for large aggregations
- **S3**: < 1s for listing, variable for large buckets

## Error Handling & Fallbacks

### Fallback Chain Example
```
Query: "genomics CSV files"

1. Try Elasticsearch → Timeout/Error
2. Try GraphQL → Success (partial results)
3. Try S3 → Success (basic enumeration)
4. Aggregate: GraphQL (primary) + S3 (supplementary)
5. Return: Combined results with explanation
```

### Error Categories
- **Backend Unavailable**: Use fallback chain
- **Authentication Failed**: Skip backend, continue with others
- **Query Too Complex**: Simplify and retry
- **No Results**: Suggest alternative queries
- **Timeout**: Return partial results with explanation

## Testing Strategy

### Unit Tests
- Query parser accuracy
- Backend selection logic
- Result aggregation correctness
- Error handling completeness

### Integration Tests
- End-to-end search scenarios
- Backend failover testing
- Performance benchmarking
- Cross-catalog functionality

### User Acceptance Tests
- Natural language query understanding
- Result relevance and ranking
- Search suggestion quality
- Performance under load

## Performance Monitoring

### Metrics to Track
- Query response times by backend
- Backend availability and health
- Query success/failure rates
- User satisfaction indicators
- Cost metrics (especially Athena)

### Optimization Strategies
- Query result caching
- Backend performance learning
- Query rewriting for optimization
- Predictive backend selection

## Migration Strategy

### Backward Compatibility
- Existing search tools remain functional
- Gradual migration to unified interface
- Legacy tool deprecation timeline
- User migration assistance

### Rollout Plan
1. **Alpha**: Internal testing with existing tools
2. **Beta**: Limited user testing with new unified tools
3. **GA**: Full deployment with migration guidance
4. **Deprecation**: Legacy tool removal (6 months post-GA)

## Success Metrics

### Technical Metrics
- Average query response time < 2s
- Backend availability > 99.5%
- Query success rate > 95%
- Cross-backend result correlation > 90%

### User Experience Metrics
- Query intent detection accuracy > 85%
- User query refinement rate < 20%
- Search abandonment rate < 10%
- User satisfaction score > 4.0/5.0

## Future Enhancements

### Phase 4: Advanced Features
- Machine learning-powered query understanding
- Personalized search results
- Collaborative filtering
- Search analytics dashboard

### Phase 5: Ecosystem Integration
- External data source integration
- API gateway for search services
- Real-time search indexing
- Multi-tenant search isolation

## Conclusion

This unified search architecture will transform the Quilt MCP Server from a collection of separate search tools into an intelligent, context-aware search platform. By leveraging multiple backends and intelligent query processing, users will be able to find their data quickly and efficiently, regardless of where it's stored or how it's organized.

The phased implementation approach ensures that we can deliver value incrementally while building toward a comprehensive solution that serves both casual users with natural language queries and power users with complex analytical needs.

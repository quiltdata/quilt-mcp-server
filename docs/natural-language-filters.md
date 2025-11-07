# Natural Language File Filters

## Quick Start

Instead of writing glob patterns, you can now use natural language to filter files when creating packages:

```python
from quilt_mcp.models.inputs import PackageCreateFromS3Params

# Natural language filter
params = PackageCreateFromS3Params(
    source_bucket="my-bucket",
    package_name="team/dataset",
    filter="include CSV and JSON files but exclude temp files"
)

# Automatically converts to:
# include_patterns = ["*.csv", "*.json"]
# exclude_patterns = ["*.tmp", "*temp*", "temp/*"]
```

## Common Examples

### Data Files

```python
filter="include CSV and JSON files"
# → ["*.csv", "*.json"]

filter="only parquet files in the data folder"
# → ["data/*.parquet", "data/**/*.parquet"]

filter="all Excel files excluding backups"
# → ["*.xlsx", "*.xls"] / ["*backup*", "~$*"]
```

### Images

```python
filter="all images except thumbnails"
# → ["*.jpg", "*.jpeg", "*.png", "*.gif", ...] / ["*thumb*", "*thumbnail*", ...]

filter="PNG and SVG files only"
# → ["*.png", "*.svg"]
```

### Code Files

```python
filter="Python files excluding tests and __pycache__"
# → ["*.py"] / ["test_*.py", "*_test.py", "tests/*", "__pycache__/*", "*.pyc"]

filter="JavaScript and TypeScript files excluding node_modules"
# → ["*.js", "*.ts", "*.jsx", "*.tsx"] / ["node_modules/*"]
```

### Documents

```python
filter="all PDFs and Word documents"
# → ["*.pdf", "*.doc", "*.docx"]

filter="markdown files excluding README"
# → ["*.md"] / ["README*", "readme*"]
```

## How It Works

1. **Natural Language → Glob Patterns**: Your filter description is sent to Claude Haiku
2. **Server-Side Processing**: Parsing happens automatically during validation
3. **Fast & Accurate**: ~200-500ms latency, very accurate results
4. **Fallback Support**: You can still use explicit `include_patterns` and `exclude_patterns`

## Override Behavior

Explicit patterns always override the natural language filter:

```python
params = PackageCreateFromS3Params(
    source_bucket="my-bucket",
    package_name="team/dataset",
    filter="include CSV files",  # ← IGNORED
    include_patterns=["*.parquet"]  # ← USED instead
)
```

## Requirements

Set the `ANTHROPIC_API_KEY` environment variable:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

## Tips for Best Results

### Be Specific
✅ **Good:** "include CSV and JSON files but exclude temp files"
❌ **Vague:** "include data files"

### Name Common Patterns
✅ **Good:** "Python files excluding tests"
✅ **Good:** "all images except thumbnails"

### Specify Folders
✅ **Good:** "only parquet files in the data folder"
✅ **Good:** "PDFs in the reports directory"

### Common Keywords
- **Include:** "include", "only", "just", "all"
- **Exclude:** "exclude", "but not", "except", "excluding"
- **Folders:** "in the X folder", "under X directory"
- **Types:** "CSV", "JSON", "images", "documents", "code files"

## Error Handling

If parsing fails, you'll get a clear error message:

```python
ValueError: Failed to parse natural language filter 'invalid description': [error details]
```

To debug, you can test the parser directly:

```python
from quilt_mcp.services.filter_parser import parse_file_filter

result = parse_file_filter("your filter description")
print(f"Include: {result.include}")
print(f"Exclude: {result.exclude}")
```

## Performance

- **Latency:** ~200-500ms per filter
- **Cost:** ~$0.0001 per filter (negligible)
- **Model:** Claude 3.5 Haiku (fast, cheap, accurate)
- **Caching:** Consider caching common filters for production use

## Comparison

### Before (Glob Patterns)
```python
params = PackageCreateFromS3Params(
    source_bucket="my-bucket",
    package_name="team/dataset",
    include_patterns=["*.csv", "*.json"],
    exclude_patterns=["*.tmp", "*temp*", "temp/*", ".tmp/*"]
)
```

### After (Natural Language)
```python
params = PackageCreateFromS3Params(
    source_bucket="my-bucket",
    package_name="team/dataset",
    filter="include CSV and JSON files but exclude temp files"
)
```

Much simpler! Especially for LLMs calling the tool.

## Advanced Usage

### Testing Filters

```python
from quilt_mcp.services.filter_parser import FilterParserService

parser = FilterParserService()
result = parser.parse_filter("your filter description")
print(result.include)
print(result.exclude)
```

### Custom API Key

```python
from quilt_mcp.services.filter_parser import FilterParserService

parser = FilterParserService(api_key="your-api-key")
result = parser.parse_filter("your filter")
```

### Batch Processing

For processing many filters, consider caching:

```python
from functools import lru_cache
from quilt_mcp.services.filter_parser import parse_file_filter

@lru_cache(maxsize=1000)
def cached_parse_filter(filter_text: str):
    return parse_file_filter(filter_text)
```

## More Examples

### Genomics Data
```python
filter="FASTQ and BAM files excluding temporary alignment files"
# → ["*.fastq", "*.fastq.gz", "*.bam"] / ["*temp*", "*.tmp"]
```

### Machine Learning
```python
filter="model checkpoints and config files but no training logs"
# → ["*.pkl", "*.h5", "*.json", "config.yaml"] / ["*.log", "logs/*"]
```

### Analytics
```python
filter="Parquet files in the processed folder"
# → ["processed/*.parquet", "processed/**/*.parquet"]
```

## Documentation

For more details, see:
- Implementation details: `/FILTER_PARSER_IMPLEMENTATION.md`
- Spec document: `/spec/227-input-schemas/04-spec-next.md`
- Source code: `/src/quilt_mcp/services/filter_parser.py`
- Tests: `/tests/test_filter_parser.py` and `/tests/test_filter_integration.py`

"""Natural language filter parser for file patterns.

Uses Claude Haiku to convert natural language descriptions into glob patterns
for filtering files in S3 buckets and packages.

Example natural language filters:
- "include CSV and JSON files but exclude temp files"
- "only parquet files in the data folder"
- "all images except thumbnails"
- "Python files excluding tests and __pycache__"
"""

from __future__ import annotations

import json
import os
from typing import Any

from anthropic import Anthropic
from pydantic import BaseModel, Field, ValidationError


class FilterPatterns(BaseModel):
    """Parsed include/exclude patterns from natural language."""

    include: list[str] = Field(
        default_factory=list,
        description="Glob patterns to include (e.g., ['*.csv', '*.json'])",
    )
    exclude: list[str] = Field(
        default_factory=list,
        description="Glob patterns to exclude (e.g., ['*.tmp', '*.log', 'temp/*'])",
    )


class FilterParserService:
    """Service for parsing natural language file filters into glob patterns.

    Uses Claude Haiku via the Anthropic API to convert human-readable filter
    descriptions into structured include/exclude glob patterns.
    """

    def __init__(self, api_key: str | None = None) -> None:
        """Initialize the filter parser service.

        Args:
            api_key: Anthropic API key. If None, reads from ANTHROPIC_API_KEY env var.

        Raises:
            ValueError: If no API key provided and ANTHROPIC_API_KEY not set.
        """
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self._api_key:
            raise ValueError(
                "Anthropic API key required. Set ANTHROPIC_API_KEY environment variable "
                "or pass api_key parameter."
            )
        self._client = Anthropic(api_key=self._api_key)

    def parse_filter(self, natural_language_filter: str) -> FilterPatterns:
        """Parse natural language filter into glob patterns.

        Args:
            natural_language_filter: Human-readable filter description.

        Returns:
            FilterPatterns with include and exclude glob patterns.

        Raises:
            ValueError: If parsing fails or LLM returns invalid response.

        Examples:
            >>> parser = FilterParserService()
            >>> result = parser.parse_filter("include CSV and JSON, exclude temp files")
            >>> result.include
            ['*.csv', '*.json']
            >>> result.exclude
            ['*.tmp', '*temp*', 'temp/*']
        """
        if not natural_language_filter or not natural_language_filter.strip():
            return FilterPatterns()

        prompt = self._build_prompt(natural_language_filter)

        try:
            response = self._client.messages.create(
                model="claude-3-5-haiku-20241022",  # Fast, cheap model for parsing
                max_tokens=1024,
                temperature=0.0,  # Deterministic parsing
                messages=[{"role": "user", "content": prompt}],
            )

            # Extract text content from response
            if not response.content or len(response.content) == 0:
                raise ValueError("Empty response from Claude")

            response_text = response.content[0].text.strip()

            # Parse JSON response
            try:
                data = json.loads(response_text)
            except json.JSONDecodeError as e:
                # Try to extract JSON from markdown code blocks
                if "```json" in response_text:
                    json_start = response_text.find("```json") + 7
                    json_end = response_text.find("```", json_start)
                    json_str = response_text[json_start:json_end].strip()
                    try:
                        data = json.loads(json_str)
                    except json.JSONDecodeError:
                        raise ValueError(
                            f"Failed to parse JSON from response: {e}"
                        ) from e
                else:
                    raise ValueError(f"Invalid JSON response: {e}") from e

            # Validate with Pydantic model
            return FilterPatterns.model_validate(data)

        except ValidationError as e:
            raise ValueError(f"Invalid pattern structure from LLM: {e}") from e
        except Exception as e:
            raise ValueError(f"Failed to parse filter: {e}") from e

    def _build_prompt(self, natural_language_filter: str) -> str:
        """Build the prompt for Claude to parse the filter.

        Args:
            natural_language_filter: User's natural language description.

        Returns:
            Formatted prompt string for Claude.
        """
        return f"""Convert this file filter description into glob patterns.

User filter description:
"{natural_language_filter}"

Rules:
1. Generate glob patterns that work with Python's fnmatch/glob
2. Common file extensions: use lowercase (e.g., *.csv not *.CSV)
3. For "data folder" or similar, use patterns like "data/*" or "data/**/*"
4. For "temp files", consider patterns like *.tmp, *temp*, temp/*, .tmp/*
5. For "thumbnails", consider patterns like *thumb*, *thumbnail*, thumbs/*
6. Be generous with patterns to avoid missing intended files
7. If the description is ambiguous, prefer broader patterns

Return ONLY valid JSON in this exact format (no markdown, no explanation):
{{"include": ["pattern1", "pattern2"], "exclude": ["pattern3", "pattern4"]}}

Examples:

Input: "include CSV and JSON files but exclude temp files"
Output: {{"include": ["*.csv", "*.json"], "exclude": ["*.tmp", "*temp*", "temp/*"]}}

Input: "only parquet files in the data folder"
Output: {{"include": ["data/*.parquet", "data/**/*.parquet"], "exclude": []}}

Input: "all images except thumbnails"
Output: {{"include": ["*.jpg", "*.jpeg", "*.png", "*.gif", "*.bmp", "*.svg", "*.webp"], "exclude": ["*thumb*", "*thumbnail*", "thumbs/*", "thumbnails/*"]}}

Input: "Python files excluding tests and cache"
Output: {{"include": ["*.py"], "exclude": ["test_*.py", "*_test.py", "tests/*", "__pycache__/*", "*.pyc"]}}

Now convert the user's filter description above.
"""


# Singleton instance for convenience
_default_parser: FilterParserService | None = None


def get_default_parser() -> FilterParserService:
    """Get or create the default filter parser instance.

    Returns:
        Shared FilterParserService instance.

    Raises:
        ValueError: If ANTHROPIC_API_KEY not set.
    """
    global _default_parser
    if _default_parser is None:
        _default_parser = FilterParserService()
    return _default_parser


def parse_file_filter(natural_language_filter: str) -> FilterPatterns:
    """Parse natural language filter using default parser.

    Convenience function that uses a shared parser instance.

    Args:
        natural_language_filter: Human-readable filter description.

    Returns:
        FilterPatterns with include and exclude glob patterns.

    Raises:
        ValueError: If parsing fails or ANTHROPIC_API_KEY not set.

    Examples:
        >>> result = parse_file_filter("CSV files only")
        >>> result.include
        ['*.csv']
    """
    parser = get_default_parser()
    return parser.parse_filter(natural_language_filter)

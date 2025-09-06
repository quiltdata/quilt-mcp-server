"""
Privacy Management for MCP Telemetry

This module handles data anonymization, hashing, and privacy-preserving
analytics to ensure user data protection while enabling optimization.
"""

import hashlib
import json
import re
from typing import Dict, Any, Set, List, Optional
import logging

logger = logging.getLogger(__name__)


class DataAnonymizer:
    """Handles data anonymization and sanitization."""

    # Patterns for sensitive data detection
    SENSITIVE_PATTERNS = {
        "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
        "ip_address": re.compile(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b"),
        "aws_key": re.compile(r"AKIA[0-9A-Z]{16}"),
        "aws_secret": re.compile(r"[A-Za-z0-9/+=]{40}"),
        "url_with_auth": re.compile(r"https?://[^:]+:[^@]+@"),
        "phone": re.compile(r"\b\d{3}-\d{3}-\d{4}\b|\b\(\d{3}\)\s*\d{3}-\d{4}\b"),
        "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        "credit_card": re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"),
    }

    # Fields that should always be anonymized
    SENSITIVE_FIELDS = {
        "password",
        "secret",
        "token",
        "key",
        "credential",
        "auth",
        "email",
        "phone",
        "ssn",
        "credit_card",
        "personal_info",
    }

    def __init__(self, salt: Optional[str] = None):
        self.salt = salt or "mcp_telemetry_salt_2024"

    def anonymize_value(self, value: Any, field_name: str = "") -> Any:
        """Anonymize a single value based on its content and field name."""
        if not isinstance(value, (str, int, float)):
            return self._hash_complex_value(value)

        value_str = str(value)

        # Check if field name indicates sensitive data
        if any(sensitive in field_name.lower() for sensitive in self.SENSITIVE_FIELDS):
            return self._hash_string(value_str)

        # Check for sensitive patterns in the value
        for pattern_name, pattern in self.SENSITIVE_PATTERNS.items():
            if pattern.search(value_str):
                logger.debug(f"Detected {pattern_name} pattern, anonymizing")
                return self._hash_string(value_str)

        # For S3 URIs, keep structure but hash sensitive parts
        if value_str.startswith("s3://"):
            return self._anonymize_s3_uri(value_str)

        # For package names, keep format but hash if it looks like personal info
        if "/" in value_str and len(value_str.split("/")) == 2:
            return self._anonymize_package_name(value_str)

        return value

    def _hash_string(self, value: str) -> str:
        """Hash a string value with salt."""
        combined = f"{self.salt}:{value}"
        return hashlib.sha256(combined.encode()).hexdigest()[:16]

    def _hash_complex_value(self, value: Any) -> str:
        """Hash complex values (dicts, lists, etc.)."""
        try:
            json_str = json.dumps(value, sort_keys=True, default=str)
            return self._hash_string(json_str)
        except (TypeError, ValueError):
            return self._hash_string(str(value))

    def _anonymize_s3_uri(self, uri: str) -> str:
        """Anonymize S3 URI while preserving structure."""
        # s3://bucket-name/path/to/file -> s3://bucket-hash/path-hash
        parts = uri.split("/", 3)
        if len(parts) >= 3:
            bucket = parts[2]
            path = parts[3] if len(parts) > 3 else ""

            bucket_hash = self._hash_string(bucket)[:8]
            path_hash = self._hash_string(path)[:8] if path else ""

            return f"s3://{bucket_hash}/{path_hash}" if path_hash else f"s3://{bucket_hash}/"

        return self._hash_string(uri)

    def _anonymize_package_name(self, package_name: str) -> str:
        """Anonymize package name while preserving format."""
        # namespace/package -> namespace-hash/package-hash
        parts = package_name.split("/")
        if len(parts) == 2:
            namespace_hash = self._hash_string(parts[0])[:8]
            package_hash = self._hash_string(parts[1])[:8]
            return f"{namespace_hash}/{package_hash}"

        return self._hash_string(package_name)


class PrivacyManager:
    """Manages privacy settings and data filtering."""

    def __init__(self, privacy_level: str = "standard"):
        self.privacy_level = privacy_level
        self.anonymizer = DataAnonymizer()

        # Define what data to collect at each privacy level
        self.privacy_configs = {
            "minimal": {
                "collect_args": False,
                "collect_context": False,
                "collect_errors": False,
                "anonymize_all": True,
            },
            "standard": {
                "collect_args": True,
                "collect_context": True,
                "collect_errors": True,
                "anonymize_sensitive": True,
            },
            "strict": {
                "collect_args": False,
                "collect_context": False,
                "collect_errors": False,
                "anonymize_all": True,
            },
        }

        self.config = self.privacy_configs.get(privacy_level, self.privacy_configs["standard"])

    def hash_args(self, args: Dict[str, Any]) -> str:
        """Create a privacy-preserving hash of function arguments."""
        if not self.config.get("collect_args", False):
            return "args_not_collected"

        # Create a sanitized version of args for hashing
        sanitized_args = {}

        for key, value in args.items():
            if self.config.get("anonymize_all", False) or self.config.get("anonymize_sensitive", False):
                sanitized_args[key] = self.anonymizer.anonymize_value(value, key)
            else:
                sanitized_args[key] = value

        # Create hash of sanitized args
        try:
            args_str = json.dumps(sanitized_args, sort_keys=True, default=str)
            return hashlib.sha256(args_str.encode()).hexdigest()[:16]
        except (TypeError, ValueError):
            return hashlib.sha256(str(sanitized_args).encode()).hexdigest()[:16]

    def filter_context(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Filter context data based on privacy settings."""
        if not self.config.get("collect_context", False):
            return None

        filtered_context = {}

        # Allow list of safe context fields
        safe_fields = {
            "task_type",
            "user_intent",
            "task_complexity",
            "session_type",
            "tool_sequence",
            "performance_hint",
            "optimization_target",
        }

        for key, value in context.items():
            if key in safe_fields:
                if self.config.get("anonymize_all", False):
                    filtered_context[key] = self.anonymizer.anonymize_value(value, key)
                else:
                    filtered_context[key] = value
            elif self.config.get("anonymize_sensitive", True):
                # Include but anonymize other fields
                filtered_context[f"anon_{key}"] = self.anonymizer.anonymize_value(value, key)

        return filtered_context if filtered_context else None

    def should_collect_errors(self) -> bool:
        """Check if error information should be collected."""
        return self.config.get("collect_errors", False)

    def anonymize_error(self, error: Exception) -> Optional[str]:
        """Anonymize error information if collection is enabled."""
        if not self.should_collect_errors():
            return None

        error_str = str(error)

        # Remove potentially sensitive information from error messages
        # Keep error type and general structure
        error_type = type(error).__name__

        if self.config.get("anonymize_all", False):
            return f"{error_type}:anonymized"

        # Anonymize sensitive patterns in error message
        anonymized_message = error_str
        for pattern_name, pattern in DataAnonymizer.SENSITIVE_PATTERNS.items():
            anonymized_message = pattern.sub(f"[{pattern_name}]", anonymized_message)

        return f"{error_type}:{anonymized_message[:100]}"  # Limit length

    def get_privacy_summary(self) -> Dict[str, Any]:
        """Get a summary of current privacy settings."""
        return {
            "privacy_level": self.privacy_level,
            "collects_args": self.config.get("collect_args", False),
            "collects_context": self.config.get("collect_context", False),
            "collects_errors": self.config.get("collect_errors", False),
            "anonymizes_sensitive": self.config.get("anonymize_sensitive", False),
            "anonymizes_all": self.config.get("anonymize_all", False),
        }


def create_privacy_manager(level: str = "standard") -> PrivacyManager:
    """Create a privacy manager with the specified level."""
    return PrivacyManager(level)

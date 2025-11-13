"""Search-specific exceptions with structured error responses.

This module defines the error handling framework for the search_catalog tool,
ensuring that all failures provide clear, actionable guidance to users.
"""

from enum import Enum
from typing import Dict, Any, Optional


class ErrorCategory(Enum):
    """Categories of search errors for classification and handling."""

    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    NOT_APPLICABLE = "not_applicable"
    CONFIGURATION = "configuration"
    BACKEND_ERROR = "backend_error"
    INVALID_INPUT = "invalid_input"
    TIMEOUT = "timeout"
    NETWORK = "network"


class SearchException(Exception):
    """Base exception for search operations with structured error responses.

    All search exceptions include:
    - Human-readable error message
    - Error category for classification
    - Detailed context about the failure
    - Clear fix instructions with commands
    - Alternative tools to use
    """

    def __init__(
        self,
        message: str,
        category: ErrorCategory,
        cause: str,
        authenticated: bool = False,
        catalog_url: Optional[str] = None,
        required_action: str = "",
        command: Optional[str] = None,
        documentation: Optional[str] = None,
        alternatives: Optional[Dict[str, str]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.category = category
        self.cause = cause
        self.authenticated = authenticated
        self.catalog_url = catalog_url
        self.required_action = required_action
        self.command = command
        self.documentation = documentation
        self.alternatives = alternatives or self._default_alternatives()

    def _default_alternatives(self) -> Dict[str, str]:
        """Default alternative tools to suggest when search fails."""
        return {
            "bucket_objects_list": "List S3 objects directly without catalog search",
            "package_browse": "Browse specific package contents",
        }

    def to_response(self) -> Dict[str, Any]:
        """Convert exception to structured error response matching spec schema.

        Returns:
            SearchErrorResponse with all required fields per specification
        """
        response: Dict[str, Any] = {
            "success": False,
            "error": self.message,
            "error_category": self.category.value,
            "details": {
                "cause": self.cause,
                "authenticated": self.authenticated,
                "catalog_url": self.catalog_url,
            },
            "fix": {
                "required_action": self.required_action,
            },
            "alternatives": self.alternatives,
        }

        # Add optional fix fields if present
        if self.command:
            response["fix"]["command"] = self.command

        if self.documentation:
            response["fix"]["documentation"] = self.documentation

        return response


class AuthenticationRequired(SearchException):
    """Raised when search requires authentication but user is not logged in.

    This exception is raised at the beginning of search operations when
    we detect that no valid quilt3 session exists.
    """

    def __init__(
        self,
        catalog_url: Optional[str] = None,
        cause: str = "No active quilt3 session found",
    ):
        super().__init__(
            message="Search catalog requires authentication",
            category=ErrorCategory.AUTHENTICATION,
            cause=cause,
            authenticated=False,
            catalog_url=catalog_url,
            required_action="Log in to Quilt catalog with quilt3",
            command="quilt3.login()",
            documentation="https://docs.quiltdata.com/api-reference/api#login",
            alternatives={
                "bucket_objects_list": "List S3 objects directly (no authentication required for public buckets)",
                "catalog_configure": "Configure catalog URL before logging in",
            },
        )


class SearchNotAvailable(SearchException):
    """Raised when no search backends are available.

    This exception is raised when:
    - User is authenticated but catalog has no search indices
    - All backends failed health checks
    - Catalog is not an Enterprise or hosted deployment
    """

    def __init__(
        self,
        authenticated: bool = True,
        catalog_url: Optional[str] = None,
        cause: str = "No search backends available",
        backend_statuses: Optional[Dict[str, str]] = None,
    ):
        details = f"{cause}."
        if backend_statuses:
            status_lines = [f"  - {name}: {status}" for name, status in backend_statuses.items()]
            details += "\n\nBackend status:\n" + "\n".join(status_lines)

        super().__init__(
            message="Catalog search not available",
            category=ErrorCategory.NOT_APPLICABLE,
            cause=details,
            authenticated=authenticated,
            catalog_url=catalog_url,
            required_action="Use bucket_objects_list for S3 exploration or verify catalog configuration",
            documentation="https://docs.quiltdata.com/catalog/searchapi",
            alternatives={
                "bucket_objects_list": "List and filter S3 objects by prefix/pattern",
                "package_browse": "Browse specific package if you know the name",
                "catalog_url": "Generate catalog URL for direct browsing",
            },
        )


class BackendError(SearchException):
    """Raised when a search backend encounters an error during query execution.

    This is used for transient errors like timeouts, API errors, or
    unexpected backend failures that aren't authentication/authorization issues.
    """

    def __init__(
        self,
        backend_name: str,
        cause: str,
        authenticated: bool = True,
        catalog_url: Optional[str] = None,
    ):
        super().__init__(
            message=f"Search backend '{backend_name}' encountered an error",
            category=ErrorCategory.BACKEND_ERROR,
            cause=cause,
            authenticated=authenticated,
            catalog_url=catalog_url,
            required_action="Retry the search or use alternative tools",
            alternatives={
                "bucket_objects_list": "List S3 objects directly without search",
                "package_browse": "Browse specific package if you know the name",
            },
        )


class InvalidQueryError(SearchException):
    """Raised when the search query is invalid or malformed."""

    def __init__(
        self,
        query: str,
        cause: str,
        authenticated: bool = True,
        catalog_url: Optional[str] = None,
    ):
        super().__init__(
            message=f"Invalid search query: {query}",
            category=ErrorCategory.INVALID_INPUT,
            cause=cause,
            authenticated=authenticated,
            catalog_url=catalog_url,
            required_action="Fix the query syntax and retry",
            documentation="https://docs.quiltdata.com/catalog/searchapi",
            alternatives={
                "search_suggest": "Get query suggestions",
                "search_explain": "Explain how a query would be processed",
            },
        )


class ConfigurationError(SearchException):
    """Raised when search configuration is invalid or missing."""

    def __init__(
        self,
        cause: str,
        authenticated: bool = False,
        catalog_url: Optional[str] = None,
        required_action: str = "Configure catalog URL and authentication",
    ):
        super().__init__(
            message="Search catalog configuration error",
            category=ErrorCategory.CONFIGURATION,
            cause=cause,
            authenticated=authenticated,
            catalog_url=catalog_url,
            required_action=required_action,
            command="catalog_configure(catalog_url)",
            documentation="https://docs.quiltdata.com/catalog/configuration",
            alternatives={
                "catalog_configure": "Set catalog URL",
                "bucket_objects_list": "List S3 objects directly without catalog",
            },
        )

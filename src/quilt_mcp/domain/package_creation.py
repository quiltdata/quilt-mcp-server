"""Package creation result domain object.

This module defines the Package_Creation_Result domain object that represents
the result of a package creation operation in a backend-agnostic way.
"""

from dataclasses import dataclass
from typing import Optional
import re


@dataclass(frozen=True)
class Package_Creation_Result:
    """Result of a package creation operation.
    
    This domain object encapsulates the result of creating and pushing a package
    to a Quilt registry. It provides a backend-agnostic representation that works
    with both quilt3 library and Platform GraphQL implementations.
    
    Attributes:
        package_name: Full package name in "user/package" format
        top_hash: Hash of the created package revision (empty if creation failed)
        registry: S3 URL of the registry where package was created
        catalog_url: Optional URL to view the package in the catalog UI
        file_count: Number of files included in the package
        success: Whether the package creation was successful
    """
    
    package_name: str
    top_hash: str
    registry: str
    catalog_url: Optional[str]
    file_count: int
    success: bool
    
    def __post_init__(self):
        """Validate Package_Creation_Result fields after initialization."""
        self._validate_package_name()
        self._validate_registry()
        self._validate_file_count()
        self._validate_success_constraints()
    
    def _validate_package_name(self) -> None:
        """Validate package name format."""
        if not self.package_name:
            raise ValueError("Package name cannot be empty")
        
        # Package name must be in "user/package" format
        if not re.match(r'^[^/]+/[^/]+$', self.package_name):
            raise ValueError("Package name must be in 'user/package' format")
    
    def _validate_registry(self) -> None:
        """Validate registry format."""
        if not self.registry:
            raise ValueError("Registry cannot be empty")
        
        # Registry must be an S3 URL
        if not self.registry.startswith('s3://'):
            raise ValueError("Registry must be an S3 URL starting with 's3://'")
    
    def _validate_file_count(self) -> None:
        """Validate file count."""
        if self.file_count < 0:
            raise ValueError("File count cannot be negative")
    
    def _validate_success_constraints(self) -> None:
        """Validate constraints when success=True."""
        if self.success:
            if not self.top_hash:
                raise ValueError("Top hash is required when success=True")
            
            if self.file_count == 0:
                raise ValueError("File count must be positive when success=True")
    
    def __str__(self) -> str:
        """Return string representation of Package_Creation_Result."""
        status = "SUCCESS" if self.success else "FAILED"
        return (
            f"Package_Creation_Result(package_name='{self.package_name}', "
            f"top_hash='{self.top_hash}', registry='{self.registry}', "
            f"file_count={self.file_count}, success={self.success}, status={status})"
        )
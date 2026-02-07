"""
Quilt3_Backend bucket operations mixin.

This module provides bucket-related operations including listing and
transformation for the Quilt3_Backend implementation.

This mixin uses self.quilt3 which is provided by Quilt3_Backend_Base.
"""

import logging
from typing import List, Dict, Any, Optional, TYPE_CHECKING

from quilt_mcp.ops.exceptions import BackendError, ValidationError
from quilt_mcp.domain.bucket_info import Bucket_Info

if TYPE_CHECKING:
    from types import ModuleType

logger = logging.getLogger(__name__)


class Quilt3_Backend_Buckets:
    """Mixin for bucket-related operations."""

    # Type hints for attributes and methods provided by Quilt3_Backend_Base
    if TYPE_CHECKING:
        quilt3: "ModuleType"

        def _normalize_string_field(self, value: Any) -> str: ...
        def _normalize_datetime(self, dt: Any) -> Optional[str]: ...

    # HIGH-LEVEL METHOD REMOVED - Now implemented in QuiltOps base class
    # list_buckets() is now a concrete method in QuiltOps that calls:
    # - _backend_list_buckets() primitive
    # - _transform_bucket_to_bucket_info() transformation (in QuiltOps base)

    def _transform_bucket(self, bucket_name: str, bucket_data: Dict[str, Any]) -> Bucket_Info:
        """Transform quilt3 bucket data to domain Bucket_Info.

        Args:
            bucket_name: Name of the bucket
            bucket_data: Bucket metadata dictionary

        Returns:
            Bucket_Info domain object

        Raises:
            BackendError: If transformation fails
        """
        try:
            logger.debug(f"Transforming bucket: {bucket_name}")

            # Validate required fields
            self._validate_bucket_fields(bucket_name, bucket_data)

            # Normalize bucket data fields with reasonable defaults
            region = bucket_data.get('region', 'unknown')
            if not region:  # Handle empty strings
                region = 'unknown'
            region = self._normalize_string_field(region)

            access_level = bucket_data.get('access_level', 'unknown')
            if not access_level:  # Handle empty strings
                access_level = 'unknown'
            access_level = self._normalize_string_field(access_level)

            created_date = self._normalize_datetime(bucket_data.get('created_date'))

            bucket_info = Bucket_Info(
                name=bucket_name,
                region=region,
                access_level=access_level,
                created_date=created_date,
            )

            logger.debug(f"Successfully transformed bucket: {bucket_info.name} in {bucket_info.region}")
            return bucket_info

        except BackendError:
            raise
        except Exception as e:
            error_context = {
                'bucket_name': bucket_name,
                'bucket_data_keys': list(bucket_data.keys()) if bucket_data and hasattr(bucket_data, 'keys') else [],
                'bucket_data_type': type(bucket_data).__name__,
            }
            logger.error(f"Bucket transformation failed: {str(e)}", extra={'context': error_context})
            raise BackendError(f"Quilt3 backend bucket transformation failed: {str(e)}", context=error_context)

    def _validate_bucket_fields(self, bucket_name: str, bucket_data: Dict[str, Any]) -> None:
        """Validate required fields for bucket transformation.

        Args:
            bucket_name: Name of the bucket
            bucket_data: Bucket metadata dictionary

        Raises:
            BackendError: If required fields are missing
        """
        if not bucket_name:
            raise BackendError("Quilt3 backend bucket validation failed: missing name")
        if bucket_data is None:
            raise BackendError("Quilt3 backend bucket validation failed: invalid bucket_data is None")

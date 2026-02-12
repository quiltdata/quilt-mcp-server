"""E2E test for package deletion visibility.

Validates create -> delete -> re-browse error behavior with real services.
"""

import time

import boto3
import pytest


@pytest.mark.e2e
@pytest.mark.package
@pytest.mark.usefixtures("backend_mode")
class TestPackageDeleteRebrowse:
    """E2E tests for package deletion and post-delete browse behavior."""

    def test_delete_then_rebrowse_errors(
        self,
        backend_with_auth,
        cleanup_packages,
        cleanup_s3_objects,
        real_test_bucket,
    ):
        timestamp = int(time.time())
        package_name = f"test/delete_rebrowse_{timestamp}"
        registry = f"s3://{real_test_bucket}"
        s3_key = f"test_delete_rebrowse/{timestamp}/input.csv"
        s3_uri = f"s3://{real_test_bucket}/{s3_key}"

        def _is_transient_network_error(exc: Exception) -> bool:
            message = str(exc).lower()
            return any(
                marker in message
                for marker in (
                    "timed out",
                    "read timed out",
                    "connection aborted",
                    "remote end closed connection",
                    "network error",
                    "connection reset",
                )
            )

        def _call_with_retry(step: str, func, *args, retries: int = 3, delay: int = 2, **kwargs):
            last_exc = None
            for attempt in range(1, retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    last_exc = exc
                    if _is_transient_network_error(exc) and attempt < retries:
                        print(f"  retry {attempt}/{retries} for {step}: {exc}")
                        time.sleep(delay)
                        continue
                    break
            if last_exc and _is_transient_network_error(last_exc):
                pytest.skip(f"Skipping due to transient network error during {step}: {last_exc}")
            raise last_exc  # type: ignore[misc]

        # Create test object.
        s3 = boto3.client("s3")
        s3.put_object(Bucket=real_test_bucket, Key=s3_key, Body=b"col\n1\n")
        cleanup_s3_objects.track_s3_object(bucket=real_test_bucket, key=s3_key)
        cleanup_packages.track_package(bucket=real_test_bucket, package_name=package_name)

        # Create package.
        create_result = _call_with_retry(
            "create package",
            backend_with_auth.create_package_revision,
            package_name=package_name,
            s3_uris=[s3_uri],
            registry=registry,
            message="E2E delete rebrowse test package",
        )
        assert create_result is not None and create_result.success, f"Create failed: {create_result}"

        # Sanity check browse before delete.
        before_delete = _call_with_retry(
            "browse before delete",
            backend_with_auth.browse_content,
            package_name=package_name,
            registry=registry,
            path="",
        )
        assert isinstance(before_delete, list)
        assert len(before_delete) > 0, "Expected non-empty browse result before delete"

        # Delete package through backend abstraction.
        deleted = _call_with_retry(
            "delete package",
            backend_with_auth.delete_package,
            bucket=registry,
            name=package_name,
        )
        assert deleted is True, "Backend reported delete failure"

        # Re-browse should eventually error after deletion.
        # Catalog/index updates may lag, so poll briefly for terminal state.
        deadline = time.time() + 30
        last_success_result = None
        while time.time() < deadline:
            try:
                last_success_result = backend_with_auth.browse_content(
                    package_name=package_name,
                    registry=registry,
                    path="",
                )
                time.sleep(2)
            except Exception:
                return

        pytest.fail(
            "Expected browse to error after delete, but it kept succeeding. "
            f"Last browse result: {last_success_result!r}"
        )

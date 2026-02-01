"""Unit tests for RequestContext."""

from __future__ import annotations

import pytest

from quilt_mcp.context.request_context import RequestContext


def test_request_context_stores_fields():
    context = RequestContext(
        request_id="req-1",
        tenant_id="tenant-a",
        user_id="user-1",
        auth_service=object(),
        permission_service=object(),
        workflow_service=object(),
    )

    assert context.request_id == "req-1"
    assert context.tenant_id == "tenant-a"
    assert context.user_id == "user-1"


@pytest.mark.parametrize(
    ("request_id", "tenant_id", "auth_service", "expected_message"),
    [
        (None, "tenant-a", object(), "request_id"),
        ("req-1", None, object(), "tenant_id"),
        ("req-1", "tenant-a", None, "auth_service"),
    ],
)
def test_request_context_requires_required_fields(request_id, tenant_id, auth_service, expected_message):
    with pytest.raises(TypeError) as excinfo:
        RequestContext(
            request_id=request_id,
            tenant_id=tenant_id,
            user_id="user-1",
            auth_service=auth_service,
            permission_service=object(),
            workflow_service=object(),
        )

    assert expected_message in str(excinfo.value)


def test_request_context_is_authenticated_reflects_auth_service():
    class StubAuthService:
        def __init__(self, valid: bool) -> None:
            self._valid = valid

        def is_valid(self) -> bool:
            return self._valid

    authenticated = RequestContext(
        request_id="req-1",
        tenant_id="tenant-a",
        user_id="user-1",
        auth_service=StubAuthService(True),
        permission_service=object(),
        workflow_service=object(),
    )
    unauthenticated = RequestContext(
        request_id="req-2",
        tenant_id="tenant-a",
        user_id=None,
        auth_service=StubAuthService(False),
        permission_service=object(),
        workflow_service=object(),
    )

    assert authenticated.is_authenticated is True
    assert unauthenticated.is_authenticated is False


def test_request_context_get_boto_session_delegates_to_auth_service():
    sentinel = object()

    class StubAuthService:
        def is_valid(self) -> bool:
            return True

        def get_boto3_session(self):
            return sentinel

    context = RequestContext(
        request_id="req-3",
        tenant_id="tenant-a",
        user_id="user-1",
        auth_service=StubAuthService(),
        permission_service=object(),
        workflow_service=object(),
    )

    assert context.get_boto_session() is sentinel


def test_request_context_permission_helpers_delegate():
    class StubPermissionService:
        def __init__(self):
            self.calls = []

        def discover_permissions(self, **kwargs):
            self.calls.append(("discover_permissions", kwargs))
            return {"success": True}

        def check_bucket_access(self, **kwargs):
            self.calls.append(("check_bucket_access", kwargs))
            return {"success": True}

    permission_service = StubPermissionService()

    context = RequestContext(
        request_id="req-5",
        tenant_id="tenant-a",
        user_id="user-1",
        auth_service=object(),
        permission_service=permission_service,
        workflow_service=object(),
    )

    assert context.discover_permissions() == {"success": True}
    assert context.check_bucket_access("bucket", operations=["read"]) == {"success": True}
    assert permission_service.calls == [
        ("discover_permissions", {}),
        ("check_bucket_access", {"bucket": "bucket", "operations": ["read"]}),
    ]


def test_request_context_workflow_helpers_delegate():
    class StubWorkflowService:
        def __init__(self):
            self.calls = []

        def create_workflow(self, **kwargs):
            self.calls.append(("create_workflow", kwargs))
            return {"success": True}

        def add_step(self, **kwargs):
            self.calls.append(("add_step", kwargs))
            return {"success": True}

        def update_step(self, **kwargs):
            self.calls.append(("update_step", kwargs))
            return {"success": True}

        def get_status(self, workflow_id: str):
            self.calls.append(("get_status", workflow_id))
            return {"success": True}

        def list_all(self):
            self.calls.append(("list_all", None))
            return {"success": True}

    workflow_service = StubWorkflowService()

    context = RequestContext(
        request_id="req-6",
        tenant_id="tenant-a",
        user_id="user-1",
        auth_service=object(),
        permission_service=object(),
        workflow_service=workflow_service,
    )

    assert context.create_workflow("wf-1", "Test") == {"success": True}
    assert context.add_workflow_step("wf-1", "step-1", "desc") == {"success": True}
    assert context.update_workflow_step("wf-1", "step-1", "completed") == {"success": True}
    assert context.get_workflow_status("wf-1") == {"success": True}
    assert context.list_workflows() == {"success": True}

    assert workflow_service.calls == [
        (
            "create_workflow",
            {"workflow_id": "wf-1", "name": "Test", "description": "", "metadata": None},
        ),
        (
            "add_step",
            {
                "workflow_id": "wf-1",
                "step_id": "step-1",
                "description": "desc",
                "step_type": "manual",
                "dependencies": None,
                "metadata": None,
            },
        ),
        (
            "update_step",
            {
                "workflow_id": "wf-1",
                "step_id": "step-1",
                "status": "completed",
                "result": None,
                "error_message": None,
            },
        ),
        ("get_status", "wf-1"),
        ("list_all", None),
    ]


@pytest.mark.parametrize(
    ("permission_service", "workflow_service", "expected_message"),
    [
        (None, object(), "permission_service"),
        (object(), None, "workflow_service"),
    ],
)
def test_request_context_rejects_missing_services(permission_service, workflow_service, expected_message):
    with pytest.raises(TypeError) as excinfo:
        RequestContext(
            request_id="req-4",
            tenant_id="tenant-a",
            user_id="user-1",
            auth_service=object(),
            permission_service=permission_service,
            workflow_service=workflow_service,
        )

    assert expected_message in str(excinfo.value)

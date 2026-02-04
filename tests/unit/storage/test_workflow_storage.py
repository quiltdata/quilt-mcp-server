"""Tests for workflow storage interface."""

from __future__ import annotations

import inspect

import pytest

from quilt_mcp.storage.workflow_storage import WorkflowStorage


def test_workflow_storage_is_abstract():
    with pytest.raises(TypeError):
        WorkflowStorage()


def test_workflow_storage_method_signatures():
    signature_map = {
        "save": {"workflow_id", "workflow"},
        "load": {"workflow_id"},
        "list_all": set(),
        "delete": {"workflow_id"},
    }

    for name, expected_params in signature_map.items():
        signature = inspect.signature(getattr(WorkflowStorage, name))
        assert expected_params.issubset(signature.parameters)
